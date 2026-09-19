import asyncio
import ssl
from urllib.parse import urlsplit

from fastapi import HTTPException

from .services import resolve_public_host


async def _read_response_headers_pinned(url: str) -> tuple[int, dict[str, str], str]:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Enter a normal public http:// or https:// URL without embedded credentials")

    addresses = await resolve_public_host(parsed.hostname)
    connected_ip = addresses[0]
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="URL port is invalid")

    ssl_context = ssl.create_default_context() if parsed.scheme == "https" else None
    server_hostname = parsed.hostname if parsed.scheme == "https" else None

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host=connected_ip,
                port=port,
                ssl=ssl_context,
                server_hostname=server_hostname,
            ),
            timeout=8,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not connect to the validated public target: {type(exc).__name__}") from exc

    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"

    host_header = parsed.hostname
    if ":" in host_header and not host_header.startswith("["):
        host_header = f"[{host_header}]"
    if parsed.port and parsed.port not in {80, 443}:
        host_header = f"{host_header}:{parsed.port}"

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "User-Agent: WatchDog/1.1\r\n"
        "Accept: */*\r\n"
        "Range: bytes=0-0\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii", errors="ignore")

    try:
        writer.write(request)
        await asyncio.wait_for(writer.drain(), timeout=4)
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 65536:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=6)
            if not chunk:
                break
            data += chunk
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    head = data.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    lines = head.split("\r\n")
    if not lines or not lines[0].startswith("HTTP/"):
        raise HTTPException(status_code=502, detail="Target returned an invalid HTTP response")
    try:
        status_code = int(lines[0].split()[1])
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Target returned an invalid HTTP status") from exc

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return status_code, headers, connected_ip


async def web_security_probe(url: str) -> dict:
    parsed = urlsplit(url.strip())
    status_code, headers, connected_ip = await _read_response_headers_pinned(url)
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
    return {
        "url": url,
        "connected_ip": connected_ip,
        "status_code": status_code,
        "passed": sum(1 for item in checks if item["ok"]),
        "total": len(checks),
        "checks": checks,
        "note": "The connection is pinned to the already-validated public IP to prevent DNS-rebinding from reaching private addresses.",
    }
