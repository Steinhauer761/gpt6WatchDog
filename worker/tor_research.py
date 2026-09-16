#!/usr/bin/env python3
import hashlib
import os
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

ONION_V3_RE = re.compile(r"^[a-z2-7]{56}\.onion$", re.I)
TOR_SOCKS_PROXY = os.environ.get("TOR_SOCKS_PROXY", "").strip()
AHMIA_URL = "https://ahmia.fi/search/"
USER_AGENT = "WatchDog-Research/0.3 (+passive public-source research)"


class TorResearchError(ValueError):
    pass


def normalize_onion_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise TorResearchError("Onion URL is required")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise TorResearchError("Only http/https onion URLs are supported")
    host = (parsed.hostname or "").lower()
    if not ONION_V3_RE.fullmatch(host):
        raise TorResearchError("Only valid v3 .onion addresses are accepted")
    if parsed.username or parsed.password:
        raise TorResearchError("Credentials in onion URLs are not accepted")
    return parsed.geturl()


def _unwrap_ahmia_url(href: str) -> str | None:
    if not href:
        return None
    if ".onion" in href:
        parsed = urlparse(href)
        if parsed.path.startswith("/search/redirect"):
            value = parse_qs(parsed.query).get("redirect_url", [None])[0]
            if value:
                return unquote(value)
        match = re.search(r"https?://[a-z2-7]{56}\.onion[^\s\"'<>]*", href, re.I)
        if match:
            return match.group(0)
    return None


async def search_ahmia(query: str, max_results: int = 12) -> dict:
    q = (query or "").strip()
    if not q:
        raise TorResearchError("Search query is required")
    max_results = max(1, min(int(max_results), 25))
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get(AHMIA_URL, params={"q": q})
        response.raise_for_status()
    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    results = []
    seen = set()
    for a in soup.find_all("a", href=True):
        onion_url = _unwrap_ahmia_url(a.get("href", ""))
        if not onion_url:
            continue
        try:
            normalized = normalize_onion_url(onion_url)
        except TorResearchError:
            continue
        host = (urlparse(normalized).hostname or "").lower()
        if host in seen:
            continue
        seen.add(host)
        title = a.get_text(" ", strip=True)[:240] or host
        results.append({"title": title, "onion_url": normalized, "host": host, "source": "Ahmia public index"})
        if len(results) >= max_results:
            break
    return {"query": q, "source": "Ahmia public index", "count": len(results), "results": results, "tor_fetch_available": bool(TOR_SOCKS_PROXY)}


async def fetch_onion_text(url: str) -> dict:
    normalized = normalize_onion_url(url)
    if not TOR_SOCKS_PROXY:
        raise TorResearchError("TOR_SOCKS_PROXY is not configured on the worker")
    timeout = httpx.Timeout(25.0, connect=20.0)
    async with httpx.AsyncClient(
        proxy=TOR_SOCKS_PROXY,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"},
    ) as client:
        response = await client.get(normalized)
    if response.status_code >= 400:
        raise TorResearchError(f"Onion service returned HTTP {response.status_code}")
    ctype = (response.headers.get("content-type") or "").lower()
    if "text/html" not in ctype and "text/plain" not in ctype:
        raise TorResearchError("Only text/html and text/plain onion content is inspected")
    body = response.content[:2_000_000]
    text = body.decode(response.encoding or "utf-8", errors="replace")
    if "text/html" in ctype:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "form"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True)[:240] if soup.title else None
        clean_text = " ".join(soup.stripped_strings)[:80_000]
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if ".onion" in href:
                links.append(href[:2048])
            if len(links) >= 40:
                break
    else:
        title = None
        clean_text = text[:80_000]
        links = []
    return {
        "url": normalized,
        "status": response.status_code,
        "content_type": ctype.split(";", 1)[0],
        "title": title,
        "text": clean_text,
        "onion_links": links,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes_inspected": len(body),
        "note": "Passive text-only retrieval through the configured Tor SOCKS proxy. No forms, logins, downloads, or transactions are performed.",
    }
