#!/usr/bin/env python3
import asyncio
import re
from collections import defaultdict
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from tor_research import TorResearchError, normalize_onion_url, search_ahmia

USER_AGENT = "WatchDog-Onion-Discovery/1.0 (+passive public-source research)"
ONION_MENTION_RE = re.compile(
    r"(?:(?:https?://)?[a-z2-7]{56}\.onion(?:/[^\s<>\"'`\]\[(){}]*)?)",
    re.I,
)

DISCOVERY_CATEGORIES = {
    "all": [
        "news",
        "journalism",
        "independent media",
        "government documents",
        "public records",
        "archives",
        "privacy",
        "whistleblower",
        "SecureDrop",
    ],
    "news": ["news", "journalism", "independent media", "current events", "press freedom"],
    "government": ["government documents", "public records", "court records", "FOIA", "parliament", "congress"],
    "media": ["documentary", "video archive", "photo archive", "media archive", "journalism"],
    "privacy": ["privacy", "whistleblower", "SecureDrop", "press freedom", "anonymous tips"],
    "research": ["research", "documents", "archives", "investigative journalism", "public records"],
}

# Keep this discovery view research-focused. It can surface controversial or
# politically disputed sources, but it does not intentionally index obvious
# criminal marketplaces, credential theft, malware services, or abuse material.
EXCLUDED_CONTEXT_TERMS = {
    "ransomware",
    "stolen card",
    "stolen cards",
    "carding",
    "credential dump",
    "password dump",
    "malware service",
    "exploit kit",
    "hitman",
    "assassin",
    "drug market",
    "drugs market",
    "weapon market",
    "weapons market",
    "child sexual",
    "csam",
}


def _unwrap_ddg_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    if "duckduckgo.com" in (parsed.hostname or "") and parsed.path.startswith("/l/"):
        value = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(value) if value else href
    return href


def _extract_onions(text: str) -> list[str]:
    results = []
    seen = set()
    for raw in ONION_MENTION_RE.findall(text or ""):
        raw = raw.rstrip(".,;:!?")
        try:
            normalized = normalize_onion_url(raw)
        except TorResearchError:
            continue
        host = (urlparse(normalized).hostname or "").lower()
        if not host or host in seen:
            continue
        seen.add(host)
        results.append(normalized)
    return results


def _allowed_context(text: str) -> bool:
    compact = " ".join((text or "").lower().split())
    return not any(term in compact for term in EXCLUDED_CONTEXT_TERMS)


async def _reddit_search(query: str, limit: int) -> list[dict]:
    params = {
        "q": f'{query} ".onion"',
        "limit": max(1, min(int(limit), 100)),
        "sort": "relevance",
        "raw_json": 1,
        "type": "link",
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers=headers) as client:
        response = await client.get("https://www.reddit.com/search.json", params=params)
        if response.status_code in {403, 429}:
            return []
        response.raise_for_status()
        data = response.json()

    found = []
    for child in ((data.get("data") or {}).get("children") or []):
        post = child.get("data") or {}
        title = str(post.get("title") or "")
        selftext = str(post.get("selftext") or "")
        outbound = str(post.get("url") or "")
        context = " ".join((title, selftext, outbound))
        if not _allowed_context(context):
            continue
        onions = _extract_onions(context)
        if not onions:
            continue
        permalink = str(post.get("permalink") or "")
        source_url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
        subreddit = post.get("subreddit_name_prefixed") or (
            f"r/{post.get('subreddit')}" if post.get("subreddit") else "Reddit"
        )
        for onion_url in onions:
            found.append({
                "url": onion_url,
                "host": (urlparse(onion_url).hostname or "").lower(),
                "source": "Reddit",
                "source_url": source_url or None,
                "title": title[:240] or onion_url,
                "snippet": selftext[:500] or None,
                "community": subreddit,
            })
    return found


async def _ddg_mentions(search_query: str, source_name: str, limit: int) -> list[dict]:
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False, headers=headers) as client:
        response = await client.get("https://html.duckduckgo.com/html/", params={"q": search_query})
        response.raise_for_status()
    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    found = []
    for result in soup.select(".result"):
        anchor = result.select_one(".result__a")
        snippet_node = result.select_one(".result__snippet")
        title = anchor.get_text(" ", strip=True)[:240] if anchor else ""
        href = _unwrap_ddg_url(anchor.get("href", "")) if anchor else ""
        snippet = snippet_node.get_text(" ", strip=True)[:700] if snippet_node else ""
        context = " ".join((title, href, snippet))
        if not _allowed_context(context):
            continue
        for onion_url in _extract_onions(context):
            found.append({
                "url": onion_url,
                "host": (urlparse(onion_url).hostname or "").lower(),
                "source": source_name,
                "source_url": href[:2048] if href.startswith(("http://", "https://")) else None,
                "title": title or onion_url,
                "snippet": snippet or None,
            })
            if len(found) >= limit:
                return found
    return found


async def _ahmia_mentions(query: str, limit: int) -> list[dict]:
    data = await search_ahmia(query, min(limit, 25))
    source_url = f"https://ahmia.fi/search/?q={quote(query)}"
    return [
        {
            "url": item.get("url"),
            "host": item.get("host"),
            "source": "Ahmia public index",
            "source_url": source_url,
            "title": item.get("title"),
            "snippet": None,
        }
        for item in data.get("results", [])
        if item.get("url")
    ]


async def discover_onion_addresses(query: str = "", category: str = "all", max_results: int = 100) -> dict:
    q = " ".join((query or "").split())[:320]
    category = (category or "all").strip().lower()
    if category not in DISCOVERY_CATEGORIES:
        raise TorResearchError(f"Unsupported discovery category: {category}")
    max_results = max(1, min(int(max_results), 100))

    seeds = [q] if q else DISCOVERY_CATEGORIES[category]
    if q and category != "all":
        seeds.append(f"{q} {DISCOVERY_CATEGORIES[category][0]}")
    seeds = list(dict.fromkeys(seed for seed in seeds if seed))[:10]

    per_source = max(8, min(25, (max_results // max(1, len(seeds))) + 5))
    tasks = []
    labels = []
    for seed in seeds:
        tasks.extend([
            _ahmia_mentions(seed, per_source),
            _reddit_search(seed, min(50, per_source * 2)),
            _ddg_mentions(f'site:reddit.com {seed} ".onion"', "Reddit via web index", per_source),
            _ddg_mentions(f'{seed} ".onion"', "Web index", per_source),
            _ddg_mentions(f'site:github.com {seed} ".onion"', "GitHub via web index", per_source),
        ])
        labels.extend([
            f"Ahmia:{seed}",
            f"Reddit:{seed}",
            f"Reddit-index:{seed}",
            f"Web-index:{seed}",
            f"GitHub-index:{seed}",
        ])

    responses = await asyncio.gather(*tasks, return_exceptions=True)
    raw = []
    errors = []
    for label, response in zip(labels, responses):
        if isinstance(response, Exception):
            errors.append({"source": label, "error": type(response).__name__})
        else:
            raw.extend(response)

    grouped: dict[str, dict] = {}
    source_sets: dict[str, set[str]] = defaultdict(set)
    for item in raw:
        try:
            normalized = normalize_onion_url(str(item.get("url") or ""))
        except TorResearchError:
            continue
        host = (urlparse(normalized).hostname or "").lower()
        if not host:
            continue

        record = grouped.get(host)
        if record is None:
            record = {
                "url": normalized,
                "host": host,
                "title": item.get("title") or host,
                "mention_count": 0,
                "source_count": 0,
                "sources": [],
                "mentions": [],
                "tor_live_status": "not_checked",
            }
            grouped[host] = record

        record["mention_count"] += 1
        source_name = str(item.get("source") or "Unknown")
        source_sets[host].add(source_name)
        if source_name not in record["sources"]:
            record["sources"].append(source_name)

        mention = {
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "community": item.get("community"),
        }
        mention = {key: value for key, value in mention.items() if value not in {None, ""}}
        mention_key = (mention.get("source"), mention.get("source_url"), mention.get("title"))
        existing_keys = {
            (entry.get("source"), entry.get("source_url"), entry.get("title"))
            for entry in record["mentions"]
        }
        if mention_key not in existing_keys and len(record["mentions"]) < 8:
            record["mentions"].append(mention)

    results = list(grouped.values())
    for item in results:
        item["source_count"] = len(source_sets[item["host"]])
    results.sort(key=lambda item: (-item["source_count"], -item["mention_count"], item["host"]))
    results = results[:max_results]

    return {
        "query": q or None,
        "category": category,
        "result_count": len(results),
        "results": results,
        "source_errors": errors[:30],
        "note": (
            "Publicly mentioned v3 .onion addresses only. Discovery does not visit the onion service. "
            "A mention does not prove that a service is safe, legal, current, authentic, or online. "
            "Obvious criminal-market, credential-theft, malware-service, and abuse-material contexts are excluded from this research view."
        ),
    }
