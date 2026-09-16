#!/usr/bin/env python3
import asyncio
import hashlib
import importlib.util
import ipaddress
import os
import re
import shutil
import socket
import sys
from typing import Optional
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from intel import IntelLookupError, lookup_public_ip
from public_osint import PublicSearchError, search_public_sources
from tor_research import TOR_SOCKS_PROXY, TorResearchError, fetch_onion_text, search_ahmia
from web_crawl import PublicUrlError, crawl_public_site

API_KEY = os.environ.get("WATCHDOG_WORKER_API_KEY", "").strip()
ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("WATCHDOG_ALLOWED_ORIGINS", "").split(",") if x.strip()]

app = FastAPI(title="WatchDog Worker API", version="0.4.0")

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
COMMON_PORTS = [22, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 3306, 3389, 5432, 8080]


class TextTriageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class JobValidationRequest(BaseModel):
    job_type: str
    target: Optional[str] = None
    authorization_confirmed: bool = False


class SiteCrawlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=12, ge=1, le=25)
    max_depth: int = Field(default=1, ge=0, le=2)


class PublicSearchRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    kind: str = Field(default="name", max_length=32)
    max_per_source: int = Field(default=6, ge=1, le=10)


class TorSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=320)
    max_results: int = Field(default=12, ge=1, le=25)


class TorFetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class IpLookupRequest(BaseModel):
    ip: str = Field(min_length=2, max_length=64)


class NetworkProbeRequest(BaseModel):
    target: str = Field(min_length=1, max_length=253)
    ports: list[int] = Field(default_factory=lambda: COMMON_PORTS.copy(), min_length=1, max_length=20)
    authorization_confirmed: bool = False


class WebSecurityProbeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    authorization_confirmed: bool = False


def require_api_key(authorization: Optional[str] = Header(default=None)):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Worker API key is not configured")
    expected = f"Bearer {API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid worker credentials")


def _normalize_host(value: str) -> str:
    host = value.strip().rstrip(".")
    if not host or "/" in host or " " in host:
        raise HTTPException(status_code=400, detail="Enter one hostname or IP address, not a URL, CIDR, range or path")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    if not HOST_RE.fullmatch(host):
        raise HTTPException(status_code=400, detail="Target hostname format is invalid")
    return host.lower()


async def _resolve_public_host(host: str) -> list[str]:
    try:
        parsed = ipaddress.ip_address(host)
        if not parsed.is_global:
            raise HTTPException(status_code=400, detail="Private, loopback, link-local, reserved and non-global targets are blocked on the cloud worker")
        return [str(parsed)]
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        rows = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Target hostname did not resolve") from exc

    addresses = sorted({row[4][0] for row in rows if row and row[4]})
    if not addresses:
        raise HTTPException(status_code=400, detail="Target hostname did not resolve")
    for value in addresses:
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Resolved address was invalid") from exc
        if not parsed.is_global:
            raise HTTPException(status_code=400, detail="Target resolves to a private, loopback, link-local, reserved or non-global address")
    return addresses


async def _port_open(ip: str, port: int, semaphore: asyncio.Semaphore) -> bool:
    async with semaphore:
        writer = None
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=1.75)
            return True
        except Exception:
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass


@app.get("/health")
def health():
    tool_paths = {
        "nmap": shutil.which("nmap"),
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "exiftool": shutil.which("exiftool"),
        "tesseract": shutil.which("tesseract"),
        "tor": shutil.which("tor"),
        "whois": shutil.which("whois"),
    }
    tools = {
        "python_tcp_probe": True,
        "python_web_security_probe": True,
        "nmap": bool(tool_paths["nmap"]),
        "ffmpeg": bool(tool_paths["ffmpeg"]),
        "ffprobe": bool(tool_paths["ffprobe"]),
        "exiftool": bool(tool_paths["exiftool"]),
        "tesseract": bool(tool_paths["tesseract"]),
        "tor_binary": bool(tool_paths["tor"]),
        "tor_proxy": bool(TOR_SOCKS_PROXY),
        "whois": bool(tool_paths["whois"]),
        "crawlee": importlib.util.find_spec("crawlee") is not None,
    }
    return {
        "status": "ok",
        "service": "watchdog-worker",
        "version": "0.4.0",
        "api_key_configured": bool(API_KEY),
        "allowed_origins_configured": bool(ALLOWED_ORIGINS),
        "runtime": {
            "docker_detected": os.path.exists("/.dockerenv"),
            "python": sys.version.split()[0],
            "cwd": os.getcwd(),
            "tool_paths": tool_paths,
            "tor_proxy_configured": bool(TOR_SOCKS_PROXY),
        },
        "tools": tools,
    }


@app.get("/v1/capabilities", dependencies=[Depends(require_api_key)])
def capabilities():
    return {
        "passive": [
            "text-indicator-extraction",
            "evidence-hashing",
            "public-osint-multi-source-search",
            "bounded-public-site-crawl",
            "ahmia-tor-index-search",
            "onion-text-fetch-when-tor-proxy-configured",
            "approximate-public-ip-network-geolocation",
            "media-forensics-tooling-health",
        ],
        "authorized_only": [
            "single-host-tcp-port-probe",
            "web-security-header-probe",
            "network-discovery",
            "firewall-assessment",
            "vulnerability-assessment",
        ],
        "disabled": [
            "hack-back",
            "third-party-firewall-bypass",
            "credential-theft",
            "private-account-access",
            "precise-person-tracking",
            "live-satellite-commanding",
        ],
    }


@app.post("/v1/triage/text", dependencies=[Depends(require_api_key)])
def triage_text(payload: TextTriageRequest):
    text = payload.text
    urls = sorted(set(URL_RE.findall(text)))
    emails = sorted(set(EMAIL_RE.findall(text)))
    ips = sorted(set(IP_RE.findall(text)))
    return {
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "urls": urls,
        "emails": emails,
        "ipv4": ips,
        "counts": {"urls": len(urls), "emails": len(emails), "ipv4": len(ips)},
    }


@app.post("/v1/crawl/site", dependencies=[Depends(require_api_key)])
async def crawl_site(payload: SiteCrawlRequest):
    try:
        return await crawl_public_site(payload.url, max_pages=payload.max_pages, max_depth=payload.max_depth)
    except PublicUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Site crawl failed: {type(exc).__name__}") from exc


@app.post("/v1/osint/search", dependencies=[Depends(require_api_key)])
async def osint_search(payload: PublicSearchRequest):
    try:
        return await search_public_sources(payload.identifier, payload.kind, payload.max_per_source)
    except PublicSearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Public-source search failed: {type(exc).__name__}") from exc


@app.post("/v1/tor/search", dependencies=[Depends(require_api_key)])
async def tor_search(payload: TorSearchRequest):
    try:
        return await search_ahmia(payload.query, payload.max_results)
    except TorResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tor index search failed: {type(exc).__name__}") from exc


@app.post("/v1/tor/fetch", dependencies=[Depends(require_api_key)])
async def tor_fetch(payload: TorFetchRequest):
    try:
        return await fetch_onion_text(payload.url)
    except TorResearchError as exc:
        status = 503 if "TOR_SOCKS_PROXY" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Onion fetch failed: {type(exc).__name__}") from exc


@app.post("/v1/intel/ip", dependencies=[Depends(require_api_key)])
async def ip_lookup(payload: IpLookupRequest):
    try:
        return await lookup_public_ip(payload.ip)
    except IntelLookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"IP lookup failed: {type(exc).__name__}") from exc


@app.post("/v1/probe/network", dependencies=[Depends(require_api_key)])
async def network_probe(payload: NetworkProbeRequest):
    if not payload.authorization_confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required for active probing")
    target = _normalize_host(payload.target)
    ports = sorted(set(payload.ports))
    if any(port < 1 or port > 65535 for port in ports):
        raise HTTPException(status_code=400, detail="Ports must be between 1 and 65535")
    if len(ports) > 20:
        raise HTTPException(status_code=400, detail="A maximum of 20 ports is allowed per probe")
    addresses = await _resolve_public_host(target)
    probe_ip = addresses[0]
    semaphore = asyncio.Semaphore(8)
    results = await asyncio.gather(*[_port_open(probe_ip, port, semaphore) for port in ports])
    open_ports = [port for port, is_open in zip(ports, results) if is_open]
    return {
        "target": target,
        "resolved_ip": probe_ip,
        "tested_ports": ports,
        "open_ports": open_ports,
        "closed_or_filtered_ports": [port for port, is_open in zip(ports, results) if not is_open],
        "authorization_confirmed": True,
        "note": "Bounded single-host TCP connect probe. No stealth scan, exploitation, credential testing or evasion is performed.",
    }


@app.post("/v1/probe/web-security", dependencies=[Depends(require_api_key)])
async def web_security_probe(payload: WebSecurityProbeRequest):
    if not payload.authorization_confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required for active probing")
    raw = payload.url.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Enter a normal public http:// or https:// URL without embedded credentials")
    await _resolve_public_host(parsed.hostname)

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as client:
            async with client.stream(
                "GET",
                raw,
                headers={"User-Agent": "WatchDog-Field-Tools/0.4", "Range": "bytes=0-0", "Accept": "text/html,*/*;q=0.1"},
            ) as response:
                headers = {k.lower(): v for k, v in response.headers.items()}
                status_code = response.status_code
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Web security probe failed: {type(exc).__name__}") from exc

    csp = headers.get("content-security-policy", "")
    checks = [
        {"name": "HTTPS", "ok": parsed.scheme == "https", "value": parsed.scheme.upper()},
        {"name": "HSTS", "ok": bool(headers.get("strict-transport-security")), "value": headers.get("strict-transport-security")},
        {"name": "Content-Security-Policy", "ok": bool(csp), "value": csp},
        {"name": "X-Content-Type-Options", "ok": headers.get("x-content-type-options", "").lower() == "nosniff", "value": headers.get("x-content-type-options")},
        {"name": "Clickjacking protection", "ok": bool(headers.get("x-frame-options")) or "frame-ancestors" in csp.lower(), "value": headers.get("x-frame-options") or ("CSP frame-ancestors" if "frame-ancestors" in csp.lower() else None)},
        {"name": "Referrer-Policy", "ok": bool(headers.get("referrer-policy")), "value": headers.get("referrer-policy")},
        {"name": "Permissions-Policy", "ok": bool(headers.get("permissions-policy")), "value": headers.get("permissions-policy")},
    ]
    passed = sum(1 for item in checks if item["ok"])
    return {
        "url": raw,
        "status_code": status_code,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "redirect_location": headers.get("location"),
        "server": headers.get("server"),
        "authorization_confirmed": True,
        "note": "Non-exploitative response-header assessment only. Missing headers are findings to review, not proof of compromise.",
    }


@app.post("/v1/jobs/validate", dependencies=[Depends(require_api_key)])
def validate_job(payload: JobValidationRequest):
    active_types = {
        "network-discovery",
        "firewall-assessment",
        "vulnerability-assessment",
        "web-application-assessment",
    }
    if payload.job_type in active_types and not payload.authorization_confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required for active testing")
    return {
        "accepted": True,
        "job_type": payload.job_type,
        "target": payload.target,
        "authorization_confirmed": payload.authorization_confirmed,
        "note": "Scope accepted. Active probe endpoints still require authorization confirmation on every request and remain bounded to one public host or URL.",
    }
