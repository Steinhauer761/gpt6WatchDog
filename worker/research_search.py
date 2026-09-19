#!/usr/bin/env python3
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from tor_research import search_ahmia

USER_AGENT = "WatchDog-Research/1.0 (+source discovery)"


class ResearchSearchError(ValueError):
    pass


def _unwrap_ddg(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.hostname or "") and parsed.path.startswith("/l/"):
        value = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(value) if value else href
    return href


async def _search_web(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
        response.raise_for_status()
    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    results = []
    for result in soup.select(".result"):
        anchor = result.select_one(".result__a")
        if not anchor:
            continue
        url = _unwrap_ddg(anchor.get("href", ""))
        if not url.startswith(("http://", "https://")):
            continue
        snippet = result.select_one(".result__snippet")
        results.append({
            "surface": "web",
            "source": "DuckDuckGo",
            "title": anchor.get_text(" ", strip=True)[:240],
            "url": url[:2048],
            "snippet": snippet.get_text(" ", strip=True)[:600] if snippet else None,
        })
        if len(results) >= limit:
            break
    return results


async def _search_archive(query: str, limit: int) -> list[dict]:
    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "description"),
        ("fl[]", "mediatype"),
        ("fl[]", "date"),
        ("fl[]", "creator"),
        ("rows", str(limit)),
        ("page", "1"),
        ("output", "json"),
    ]
    async with httpx.AsyncClient(timeout=18, follow_redirects=False, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get("https://archive.org/advancedsearch.php", params=params)
        response.raise_for_status()
        data = response.json()
    results = []
    for item in ((data.get("response") or {}).get("docs") or [])[:limit]:
        identifier = str(item.get("identifier") or "").strip()
        if not identifier:
            continue
        description = item.get("description")
        if isinstance(description, list):
            description = " ".join(str(x) for x in description[:3])
        results.append({
            "surface": "archive",
            "source": "Internet Archive",
            "title": str(item.get("title") or identifier)[:240],
            "url": f"https://archive.org/details/{identifier}",
            "snippet": str(description or "")[:600] or None,
            "media_type": item.get("mediatype"),
            "date": item.get("date"),
            "creator": item.get("creator"),
        })
    return results


async def search_research_sources(query: str, scope: str = "both", max_results: int = 12) -> dict:
    q = (query or "").strip()
    if not q:
        raise ResearchSearchError("Search query is required")
    if len(q) > 320:
        raise ResearchSearchError("Search query is too long")
    scope = (scope or "both").strip().lower()
    if scope not in {"web", "tor", "both"}:
        raise ResearchSearchError("Scope must be web, tor, or both")
    limit = max(1, min(int(max_results), 20))

    results: list[dict] = []
    errors: list[dict] = []

    if scope in {"web", "both"}:
        try:
            results.extend(await _search_web(q, limit))
        except Exception as exc:
            errors.append({"source": "DuckDuckGo", "error": type(exc).__name__})
        try:
            results.extend(await _search_archive(q, limit))
        except Exception as exc:
            errors.append({"source": "Internet Archive", "error": type(exc).__name__})

    if scope in {"tor", "both"}:
        try:
            tor = await search_ahmia(q, limit)
            results.extend(tor.get("results", []))
        except Exception as exc:
            errors.append({"source": "Ahmia", "error": type(exc).__name__})

    deduped = []
    seen = set()
    for item in results:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return {
        "query": q,
        "scope": scope,
        "result_count": len(deduped),
        "results": deduped[: max(limit * 3, 20)],
        "source_errors": errors,
        "note": "Search results are source leads, not proof that a claim is true. Preserve provenance and verify important claims against primary records and independent sources.",
    }
