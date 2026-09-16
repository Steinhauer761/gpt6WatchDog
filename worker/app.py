#!/usr/bin/env python3
import hashlib
import importlib.util
import os
import re
import shutil
import sys
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from intel import IntelLookupError, lookup_public_ip
from public_osint import PublicSearchError, search_public_sources
from tor_research import TOR_SOCKS_PROXY, TorResearchError, fetch_onion_text, search_ahmia
from web_crawl import PublicUrlError, crawl_public_site

API_KEY = os.environ.get("WATCHDOG_WORKER_API_KEY", "").strip()
ALLOWED_ORIGINS = [x.strip() for x in os.environ.get("WATCHDOG_ALLOWED_ORIGINS", "").split(",") if x.strip()]

app = FastAPI(title="WatchDog Worker API", version="0.3.1")

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


def require_api_key(authorization: Optional[str] = Header(default=None)):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Worker API key is not configured")
    expected = f"Bearer {API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid worker credentials")


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
        "version": "0.3.1",
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
        "authorization_confirmed": payload.authorization_confirmed,
        "note": "Validation only. Tool execution adapters are added separately and remain scope-restricted.",
    }
