#!/usr/bin/env python3
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from tor_research import search_ahmia

USER_AGENT = "WatchDog-OSINT/0.3 (+public-source research)"


class PublicSearchError(ValueError):
    pass


def _unwrap_ddg(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.hostname or "") and parsed.path.startswith("/l/"):
        value = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(value) if value else href
    return href


async def _duckduckgo(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
        r.raise_for_status()
    soup = BeautifulSoup(r.text[:2_000_000], "html.parser")
    out = []
    for result in soup.select(".result"):
        a = result.select_one(".result__a")
        if not a:
            continue
        url = _unwrap_ddg(a.get("href", ""))
        if not url.startswith(("http://", "https://")):
            continue
        snippet = result.select_one(".result__snippet")
        out.append({
            "source": "DuckDuckGo",
            "title": a.get_text(" ", strip=True)[:240],
            "url": url[:2048],
            "snippet": snippet.get_text(" ", strip=True)[:500] if snippet else None,
        })
        if len(out) >= limit:
            break
    return out


async def _github_repos(query: str, limit: int) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers=headers) as client:
        r = await client.get("https://api.github.com/search/repositories", params={"q": query, "per_page": min(limit, 10)})
        if r.status_code == 403:
            return []
        r.raise_for_status()
        data = r.json()
    return [{
        "source": "GitHub public repositories",
        "title": item.get("full_name"),
        "url": item.get("html_url"),
        "snippet": (item.get("description") or "")[:500] or None,
    } for item in data.get("items", [])[:limit]]


async def _hackernews(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get("https://hn.algolia.com/api/v1/search", params={"query": query, "hitsPerPage": min(limit, 10)})
        r.raise_for_status()
        data = r.json()
    out = []
    for item in data.get("hits", [])[:limit]:
        url = item.get("url") or (f"https://news.ycombinator.com/item?id={item.get('objectID')}" if item.get("objectID") else None)
        out.append({"source": "Hacker News", "title": item.get("title") or item.get("story_title"), "url": url, "snippet": None})
    return out


async def _crtsh(domain: str, limit: int) -> list[dict]:
    q = domain.strip().lower().lstrip("*.")
    if not q or "." not in q or " " in q:
        return []
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get("https://crt.sh/", params={"q": f"%.{q}", "output": "json"})
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except Exception:
            return []
    names = []
    seen = set()
    for row in data:
        for name in str(row.get("name_value") or "").splitlines():
            name = name.strip().lower()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
            if len(names) >= limit:
                break
        if len(names) >= limit:
            break
    return [{"source": "Certificate Transparency", "title": name, "url": f"https://crt.sh/?q={name}", "snippet": f"Certificate name related to {q}"} for name in names]


async def search_public_sources(identifier: str, kind: str = "name", max_per_source: int = 6) -> dict:
    value = (identifier or "").strip()
    if not value:
        raise PublicSearchError("Identifier is required")
    if len(value) > 320:
        raise PublicSearchError("Identifier is too long")
    kind = (kind or "name").strip().lower()
    limit = max(1, min(int(max_per_source), 10))
    query = f'"{value}"'

    results = []
    errors = []
    for name, fn in [
        ("DuckDuckGo", lambda: _duckduckgo(query, limit)),
        ("GitHub", lambda: _github_repos(value, limit)),
        ("Hacker News", lambda: _hackernews(value, limit)),
    ]:
        try:
            results.extend(await fn())
        except Exception as exc:
            errors.append({"source": name, "error": type(exc).__name__})

    if kind == "domain":
        try:
            results.extend(await _crtsh(value, limit))
        except Exception as exc:
            errors.append({"source": "Certificate Transparency", "error": type(exc).__name__})

    try:
        tor = await search_ahmia(value, limit)
        for item in tor.get("results", []):
            results.append({"source": "Ahmia public Tor index", "title": item.get("title"), "url": item.get("onion_url"), "snippet": None, "onion": True})
    except Exception as exc:
        errors.append({"source": "Ahmia", "error": type(exc).__name__})

    deduped = []
    seen = set()
    for item in results:
        key = (item.get("url") or "", item.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return {
        "identifier": value,
        "kind": kind,
        "result_count": len(deduped),
        "results": deduped[:40],
        "source_errors": errors,
        "note": "Public-source leads only. Matching a name, username, email or phone does not prove identity or account ownership.",
    }
