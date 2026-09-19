import asyncio
import hashlib
import ipaddress
import os
import re
import socket
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
VIN_FIELDS = ["Make", "Model", "ModelYear", "Manufacturer", "VehicleType", "BodyClass", "EngineCylinders", "DisplacementL", "FuelTypePrimary", "DriveType", "PlantCountry", "ErrorCode", "ErrorText"]


def triage_text(text: str) -> dict:
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


async def lookup_public_ip(ip: str) -> dict:
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid IPv4 or IPv6 address is required") from exc
    if not address.is_global:
        raise HTTPException(status_code=400, detail="Only public-routable IP addresses can be mapped")
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers={"User-Agent": "WatchDog-IP-Intel/1.0"}) as client:
        response = await client.get(f"https://ipapi.co/{address.compressed}/json/")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="IP intelligence provider did not respond")
        data = response.json()
    if data.get("error"):
        raise HTTPException(status_code=400, detail=str(data.get("reason") or "IP lookup failed"))
    try:
        lat = round(float(data.get("latitude")), 2) if data.get("latitude") is not None else None
        lon = round(float(data.get("longitude")), 2) if data.get("longitude") is not None else None
    except (TypeError, ValueError):
        lat = lon = None
    return {
        "ip": address.compressed,
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country_name") or data.get("country"),
        "country_code": data.get("country_code") or data.get("country"),
        "latitude": lat,
        "longitude": lon,
        "timezone": data.get("timezone"),
        "asn": data.get("asn"),
        "organization": data.get("org"),
        "precision": "approximate network geolocation",
        "note": "This is network-level location context, not proof of a person's physical location.",
    }


async def decode_vin(vin: str) -> dict:
    clean = vin.strip().upper()
    if not VIN_RE.fullmatch(clean):
        raise HTTPException(status_code=400, detail="Enter a 17-character VIN without I, O or Q")
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{clean}?format=json"
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        response = await client.get(url)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The public VIN service did not respond")
    row = (response.json().get("Results") or [None])[0]
    if not row:
        raise HTTPException(status_code=502, detail="No vehicle record returned")
    return {"vin": clean, "source": "NHTSA vPIC", "decoded": {key: row.get(key) or None for key in VIN_FIELDS}}


def _clean_text(value, limit=180):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()[:limit]


async def geocode(query: str) -> dict:
    q = _clean_text(query)
    if not q:
        raise HTTPException(status_code=400, detail="Enter an address, landmark, business, city, region or country")
    params = {"q": q, "format": "jsonv2", "addressdetails": "1", "limit": "6"}
    headers = {"User-Agent": "WatchDog-Field-Tools/1.0", "Accept-Language": "en"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers=headers) as client:
        response = await client.get("https://nominatim.openstreetmap.org/search", params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Geocoder returned HTTP {response.status_code}")
    results = []
    for item in response.json() if isinstance(response.json(), list) else []:
        try:
            latitude = round(float(item.get("lat")), 6)
            longitude = round(float(item.get("lon")), 6)
        except (TypeError, ValueError):
            continue
        address = item.get("address") or {}
        coord = f"{latitude},{longitude}"
        display_name = _clean_text(item.get("display_name"), 500) or q
        results.append({
            "label": display_name,
            "display_name": display_name,
            "house_number": _clean_text(address.get("house_number"), 40) or None,
            "road": _clean_text(address.get("road") or address.get("pedestrian") or address.get("footway"), 120) or None,
            "city": _clean_text(address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or address.get("hamlet"), 120) or None,
            "region": _clean_text(address.get("state") or address.get("region") or address.get("county"), 120) or None,
            "country": _clean_text(address.get("country"), 120) or None,
            "postal_code": _clean_text(address.get("postcode"), 32) or None,
            "latitude": latitude,
            "longitude": longitude,
            "type": _clean_text(item.get("addresstype") or item.get("type"), 80) or "place",
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={quote(coord)}",
            "street_view_url": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={quote(coord)}",
            "osm_url": f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=18/{latitude}/{longitude}",
        })
    return {"query": q, "count": len(results), "results": results, "note": "Public map data and Street View are not live and should not be treated as proof that a person is at or lives at a location."}


def normalize_host(value: str) -> str:
    host = value.strip().rstrip(".")
    if not host or "/" in host or " " in host:
        raise HTTPException(status_code=400, detail="Enter one hostname or public IP, not a URL, range or path")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    if not HOST_RE.fullmatch(host):
        raise HTTPException(status_code=400, detail="Target hostname format is invalid")
    return host.lower()


async def resolve_public_host(host: str) -> list[str]:
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise HTTPException(status_code=400, detail="Private, loopback, link-local, reserved and non-global targets are blocked")
        return [str(address)]
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
            raise HTTPException(status_code=400, detail="Target resolves to a non-public address")
    return addresses


async def network_probe(target: str, ports: list[int]) -> dict:
    host = normalize_host(target)
    ports = sorted(set(ports))
    if not ports or len(ports) > 20 or any(port < 1 or port > 65535 for port in ports):
        raise HTTPException(status_code=400, detail="Enter 1-20 valid ports between 1 and 65535")
    addresses = await resolve_public_host(host)
    probe_ip = addresses[0]
    semaphore = asyncio.Semaphore(8)

    async def probe(port: int) -> bool:
        async with semaphore:
            writer = None
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(probe_ip, port), timeout=1.75)
                return True
            except Exception:
                return False
            finally:
                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass

    states = await asyncio.gather(*(probe(port) for port in ports))
    return {
        "target": host,
        "resolved_ip": probe_ip,
        "tested_ports": ports,
        "open_ports": [port for port, opened in zip(ports, states) if opened],
        "closed_or_filtered_ports": [port for port, opened in zip(ports, states) if not opened],
        "note": "Bounded single-host TCP connect probe. No stealth, exploitation, credential testing or evasion is performed.",
    }


async def web_security_probe(url: str) -> dict:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Enter a normal public http:// or https:// URL without embedded credentials")
    await resolve_public_host(parsed.hostname)
    async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
        async with client.stream("GET", url, headers={"User-Agent": "WatchDog/1.0", "Range": "bytes=0-0"}) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
            status_code = response.status_code
    csp = headers.get("content-security-policy", "")
    checks = [
        {"name": "HTTPS", "ok": parsed.scheme == "https", "value": parsed.scheme.upper()},
        {"name": "HSTS", "ok": bool(headers.get("strict-transport-security")), "value": headers.get("strict-transport-security")},
        {"name": "Content-Security-Policy", "ok": bool(csp), "value": csp},
        {"name": "X-Content-Type-Options", "ok": headers.get("x-content-type-options", "").lower() == "nosniff", "value": headers.get("x-content-type-options")},
        {"name": "Clickjacking protection", "ok": bool(headers.get("x-frame-options")) or "frame-ancestors" in csp.lower(), "value": headers.get("x-frame-options")},
        {"name": "Referrer-Policy", "ok": bool(headers.get("referrer-policy")), "value": headers.get("referrer-policy")},
        {"name": "Permissions-Policy", "ok": bool(headers.get("permissions-policy")), "value": headers.get("permissions-policy")},
    ]
    return {"url": url, "status_code": status_code, "passed": sum(1 for item in checks if item["ok"]), "total": len(checks), "checks": checks}


async def ask_openai(message: str, history: list[dict]) -> dict:
    if os.environ.get("WATCHDOG_AI_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="WatchDog AI is switched off")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
    input_items = []
    for item in history[-8:]:
        role = "assistant" if item.get("role") == "assistant" else "user"
        content = str(item.get("content") or "")[:6000]
        if content:
            input_items.append({"role": role, "content": content})
    input_items.append({"role": "user", "content": message})
    instructions = (
        "You are WatchDog Assistant inside a defensive research and security console. "
        "Be concise and practical. Treat public-source identity matches as leads, not proof. "
        "Do not claim precise person tracking, bypass private accounts or networks, steal credentials, or hack back. "
        "Active probes must be limited to systems the user owns or is explicitly authorized to assess."
    )
    payload = {"model": model, "instructions": instructions, "input": input_items, "store": False, "reasoning": {"effort": "low"}}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload)
    data = response.json()
    if response.status_code >= 400:
        detail = ((data.get("error") or {}).get("message") if isinstance(data, dict) else None) or "OpenAI request failed"
        raise HTTPException(status_code=response.status_code, detail=detail)
    text = data.get("output_text") or ""
    if not text:
        chunks = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text" and part.get("text"):
                    chunks.append(part["text"])
        text = "\n".join(chunks).strip()
    return {"reply": text or "No text response was returned.", "model": model}
