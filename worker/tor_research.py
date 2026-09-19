#!/usr/bin/env python3
import hashlib
import os
import re
from urllib.parse import parse_qs, unquote, urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

ONION_V3_RE = re.compile(r"^[a-z2-7]{56}\.onion$", re.I)
TOR_SOCKS_PROXY = os.environ.get("TOR_SOCKS_PROXY", "").strip()
AHMIA_URL = "https://ahmia.fi/search/"
USER_AGENT = "WatchDog-Research/0.4 (+passive public-source research)"


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
    clean, _ = urldefrag(parsed.geturl())
    return clean


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
        results.append({"title": title, "url": normalized, "host": host, "source": "Ahmia public index", "surface": "tor"})
        if len(results) >= max_results:
            break
    return {"query": q, "source": "Ahmia public index", "count": len(results), "results": results, "tor_fetch_available": bool(TOR_SOCKS_PROXY)}


async def fetch_onion_text(url: str) -> dict:
    normalized = normalize_onion_url(url)
    if not TOR_SOCKS_PROXY:
        raise TorResearchError("TOR_SOCKS_PROXY is not configured on the backend")
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
            try:
                candidate = normalize_onion_url(urljoin(normalized, a.get("href", "")))
            except TorResearchError:
                continue
            links.append(candidate)
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


async def crawl_onion_site(url: str, max_pages: int = 8, max_depth: int = 1) -> dict:
    start = normalize_onion_url(url)
    if not TOR_SOCKS_PROXY:
        raise TorResearchError("TOR_SOCKS_PROXY is not configured on the backend")
    max_pages = max(1, min(int(max_pages), 12))
    max_depth = max(0, min(int(max_depth), 2))
    root_host = (urlparse(start).hostname or "").lower()
    queue: list[tuple[str, int]] = [(start, 0)]
    queued = {start}
    visited = set()
    pages = []
    errors = []

    timeout = httpx.Timeout(30.0, connect=20.0)
    async with httpx.AsyncClient(
        proxy=TOR_SOCKS_PROXY,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"},
    ) as client:
        while queue and len(pages) < max_pages:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            try:
                response = await client.get(current)
                if response.status_code >= 400:
                    raise TorResearchError(f"HTTP {response.status_code}")
                ctype = (response.headers.get("content-type") or "").lower()
                if "text/html" not in ctype and "text/plain" not in ctype:
                    raise TorResearchError("non-text content skipped")
                body = response.content[:2_000_000]
                text = body.decode(response.encoding or "utf-8", errors="replace")
                title = None
                clean_text = text[:40_000]
                discovered = []
                if "text/html" in ctype:
                    soup = BeautifulSoup(text, "html.parser")
                    for tag in soup(["script", "style", "noscript", "iframe", "form"]):
                        tag.decompose()
                    title = soup.title.get_text(" ", strip=True)[:240] if soup.title else None
                    clean_text = " ".join(soup.stripped_strings)[:40_000]
                    if depth < max_depth:
                        for a in soup.find_all("a", href=True):
                            try:
                                candidate = normalize_onion_url(urljoin(current, a.get("href", "")))
                            except TorResearchError:
                                continue
                            if (urlparse(candidate).hostname or "").lower() != root_host:
                                continue
                            if candidate not in visited and candidate not in queued:
                                queue.append((candidate, depth + 1))
                                queued.add(candidate)
                                discovered.append(candidate)
                                if len(queue) + len(pages) >= max_pages * 3:
                                    break
                pages.append({
                    "url": current,
                    "depth": depth,
                    "status": response.status_code,
                    "content_type": ctype.split(";", 1)[0],
                    "title": title,
                    "text": clean_text,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "links_queued": discovered[:30],
                })
            except Exception as exc:
                errors.append({"url": current, "error": str(exc)[:240]})

    return {
        "start_url": start,
        "host": root_host,
        "page_count": len(pages),
        "pages": pages,
        "errors": errors[:20],
        "limits": {"max_pages": max_pages, "max_depth": max_depth, "same_host_only": True, "text_only": True},
        "note": "Bounded passive same-host Tor crawl. It does not submit forms, log in, execute scripts, download files, or transact with services.",
    }
