#!/usr/bin/env python3
import ipaddress

import httpx


class IntelLookupError(ValueError):
    pass


async def lookup_public_ip(ip: str) -> dict:
    raw = (ip or "").strip()
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise IntelLookupError("A valid IPv4 or IPv6 address is required") from exc
    if not addr.is_global:
        raise IntelLookupError("Only public-routable IP addresses can be mapped")

    url = f"https://ipapi.co/{addr.compressed}/json/"
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers={"User-Agent": "WatchDog-IP-Intel/0.3"}) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        raise IntelLookupError(str(data.get("reason") or "IP geolocation provider returned an error"))

    lat = data.get("latitude")
    lon = data.get("longitude")
    try:
        lat = round(float(lat), 2) if lat is not None else None
        lon = round(float(lon), 2) if lon is not None else None
    except (TypeError, ValueError):
        lat = lon = None

    return {
        "ip": addr.compressed,
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
        "note": "This is an IP/network estimate, not proof of a person's physical location. VPNs, mobile carriers, proxies and ISP routing can make it wrong by many kilometres or more.",
    }
