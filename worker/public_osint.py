#!/usr/bin/env python3
import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from tor_research import search_ahmia

USER_AGENT = "WatchDog-OSINT/0.4 (+public-source research)"
IDENTITY_KINDS = {"name", "username", "alias", "email", "phone"}


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


def _compact(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _match_result(item: dict, value: str, kind: str) -> tuple[str, str] | None:
    """Keep only useful public-source leads and explain why they matched."""
    title = _compact(item.get("title"))
    snippet = _compact(item.get("snippet"))
    url = _compact(item.get("url"))
    haystack = " ".join((title, snippet, url)).strip()
    needle = _compact(value)

    if kind == "phone":
        target = _digits(value)
        if len(target) < 7:
            return None
        observed = _digits(haystack)
        if target in observed:
            return "exact", "Exact phone digits appear in the public result"
        return None

    if kind in {"email", "username", "domain", "phrase"}:
        if needle and needle in haystack:
            label = {
                "email": "email address",
                "username": "username/handle",
                "domain": "domain",
                "phrase": "phrase",
            }[kind]
            return "exact", f"Exact {label} appears in the public result"
        return None

    # Names and aliases are inherently ambiguous. Require either the complete
    # phrase or every meaningful token; never treat one loose token as a hit.
    tokens = [x for x in re.findall(r"[a-z0-9]+", needle) if len(x) >= 2]
    if not tokens:
        return None
    if needle in haystack:
        return "exact", "Exact name/alias phrase appears in the public result"
    if len(tokens) >= 2 and all(token in haystack for token in tokens):
        return "strong", "All name/alias terms appear in the public result"
    return None


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


async def _github_users(query: str, kind: str, limit: int) -> list[dict]:
    if kind == "phone":
        return []
    if kind == "username":
        search = f'"{query}" in:login'
    elif kind == "email":
        search = f'"{query}" in:email'
    else:
        search = f'"{query}" in:login,name,email'

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers=headers) as client:
        r = await client.get("https://api.github.com/search/users", params={"q": search, "per_page": min(limit, 10)})
        if r.status_code in {403, 422}:
            return []
        r.raise_for_status()
        data = r.json()

    out = []
    for item in data.get("items", [])[:limit]:
        login = item.get("login") or "GitHub user"
        out.append({
            "source": "GitHub public users",
            "title": login,
            "url": item.get("html_url"),
            "snippet": f"Public GitHub profile candidate ({item.get('type') or 'user'})",
        })
    return out


async def _github_repos(query: str, limit: int) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False, headers=headers) as client:
        r = await client.get("https://api.github.com/search/repositories", params={"q": f'"{query}"', "per_page": min(limit, 10)})
        if r.status_code in {403, 422}:
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
        r = await client.get("https://hn.algolia.com/api/v1/search", params={"query": f'"{query}"', "hitsPerPage": min(limit, 10)})
        r.raise_for_status()
        data = r.json()
    out = []
    for item in data.get("hits", [])[:limit]:
        url = item.get("url") or (f"https://news.ycombinator.com/item?id={item.get('objectID')}" if item.get("objectID") else None)
        out.append({
            "source": "Hacker News",
            "title": item.get("title") or item.get("story_title"),
            "url": url,
            "snippet": item.get("story_text") or item.get("comment_text"),
        })
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
    return [{
        "source": "Certificate Transparency",
        "title": name,
        "url": f"https://crt.sh/?q={name}",
        "snippet": f"Certificate name related to {q}",
    } for name in names]


async def search_public_sources(identifier: str, kind: str = "name", max_per_source: int = 6) -> dict:
    value = (identifier or "").strip()
    if not value:
        raise PublicSearchError("Identifier is required")
    if len(value) > 320:
        raise PublicSearchError("Identifier is too long")

    kind = (kind or "name").strip().lower()
    if kind not in {"name", "username", "alias", "email", "phone", "domain", "phrase"}:
        raise PublicSearchError("Unsupported identifier type")

    limit = max(1, min(int(max_per_source), 10))
    quoted_query = f'"{value}"'

    candidates: list[dict] = []
    errors: list[dict] = []

    try:
        candidates.extend(await _duckduckgo(quoted_query, limit))
    except Exception as exc:
        errors.append({"source": "DuckDuckGo", "error": type(exc).__name__})

    if kind in IDENTITY_KINDS:
        try:
            candidates.extend(await _github_users(value, kind, limit))
        except Exception as exc:
            errors.append({"source": "GitHub public users", "error": type(exc).__name__})
    else:
        try:
            candidates.extend(await _github_repos(value, limit))
        except Exception as exc:
            errors.append({"source": "GitHub", "error": type(exc).__name__})

    # Hacker News is useful for domains/phrases, but far too noisy for people,
    # usernames, email addresses and phone numbers.
    if kind in {"domain", "phrase"}:
        try:
            candidates.extend(await _hackernews(value, limit))
        except Exception as exc:
            errors.append({"source": "Hacker News", "error": type(exc).__name__})

    if kind == "domain":
        try:
            candidates.extend(await _crtsh(value, limit))
        except Exception as exc:
            errors.append({"source": "Certificate Transparency", "error": type(exc).__name__})

    try:
        tor = await search_ahmia(value, limit)
        for item in tor.get("results", []):
            candidates.append({
                "source": "Ahmia public Tor index",
                "title": item.get("title"),
                "url": item.get("onion_url"),
                "snippet": None,
                "onion": True,
            })
    except Exception as exc:
        errors.append({"source": "Ahmia", "error": type(exc).__name__})

    kept = []
    filtered_out = 0
    for item in candidates:
        match = _match_result(item, value, kind)
        if not match:
            filtered_out += 1
            continue
        strength, reason = match
        enriched = dict(item)
        enriched["match_strength"] = strength
        enriched["match_reason"] = reason
        kept.append(enriched)

    deduped = []
    seen = set()
    for item in kept:
        key = (item.get("url") or "", item.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    order = {"exact": 0, "strong": 1}
    deduped.sort(key=lambda item: (order.get(item.get("match_strength"), 9), item.get("source") or ""))

    return {
        "identifier": value,
        "kind": kind,
        "result_count": len(deduped),
        "filtered_noise_count": filtered_out,
        "results": deduped[:40],
        "source_errors": errors,
        "note": "Public-source leads only. Weak one-word or unrelated matches are filtered. Matching a name, username, email or phone does not prove identity or account ownership.",
    }
