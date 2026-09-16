#!/usr/bin/env python3
"""Bounded public-web crawler for WatchDog Site Intelligence.

This module intentionally crawls only public HTTP(S) pages and rejects targets
that resolve to loopback, private, link-local, reserved, multicast, or otherwise
non-global IP space. Redirect following is disabled at the HTTP client layer so
an apparently public URL cannot redirect the worker into an internal network.
"""

import asyncio
import hashlib
import ipaddress
import socket
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.http_clients import HttpxHttpClient


BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.aws.internal",
}


class PublicUrlError(ValueError):
    pass


def normalize_public_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw or len(raw) > 2048:
        raise PublicUrlError("URL must contain 1 to 2048 characters")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise PublicUrlError("Only http:// and https:// URLs are allowed")
    if parsed.username or parsed.password:
        raise PublicUrlError("Credentials in URLs are not allowed")
    if not parsed.hostname:
        raise PublicUrlError("URL must include a hostname")
    if parsed.hostname.lower().rstrip(".") in BLOCKED_HOSTNAMES:
        raise PublicUrlError("Local or metadata hostnames are not allowed")
    return raw


def _assert_global_ip(ip_text: str) -> None:
    ip = ipaddress.ip_address(ip_text)
    if not ip.is_global:
        raise PublicUrlError("Target resolves to non-public network space")


async def assert_public_destination(url: str) -> None:
    normalized = normalize_public_url(url)
    parsed = urlparse(normalized)
    hostname = parsed.hostname
    assert hostname is not None

    # Literal IPs are handled without DNS.
    try:
        _assert_global_ip(hostname)
        return
    except ValueError:
        pass

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise PublicUrlError("Hostname could not be resolved") from exc

    addresses = {item[4][0] for item in infos if item and item[4]}
    if not addresses:
        raise PublicUrlError("Hostname did not resolve to an address")
    for address in addresses:
        _assert_global_ip(address)


def _clean_text(text: str, limit: int = 6000) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit]


async def crawl_public_site(url: str, *, max_pages: int = 12, max_depth: int = 1) -> dict[str, Any]:
    seed = normalize_public_url(url)
    await assert_public_destination(seed)

    max_pages = max(1, min(int(max_pages), 25))
    max_depth = max(0, min(int(max_depth), 2))
    pages: list[dict[str, Any]] = []

    # Redirects are disabled deliberately. This avoids a public URL being used
    # as an SSRF trampoline into a private or cloud-metadata address.
    http_client = HttpxHttpClient(
        follow_redirects=False,
        timeout=15,
    )

    crawler = BeautifulSoupCrawler(
        http_client=http_client,
        max_requests_per_crawl=max_pages,
        max_crawl_depth=max_depth,
        max_request_retries=1,
        respect_robots_txt_file=True,
        request_handler_timeout=timedelta(seconds=20),
    )

    @crawler.pre_navigation_hook
    async def validate_request(context) -> None:
        await assert_public_destination(context.request.url)

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        soup = context.soup
        title = soup.title.get_text(strip=True) if soup.title else None
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = None
        if description_tag and description_tag.get("content"):
            description = _clean_text(str(description_tag.get("content")), 1000)

        plain_text = _clean_text(context.html_to_text())
        loaded_url = context.request.loaded_url or context.request.url
        pages.append(
            {
                "url": context.request.url,
                "loaded_url": loaded_url,
                "title": title,
                "description": description,
                "text_preview": plain_text,
                "content_sha256": hashlib.sha256(plain_text.encode("utf-8")).hexdigest(),
            }
        )

        await context.enqueue_links(strategy="same-hostname")

    await crawler.run([seed])

    return {
        "seed_url": seed,
        "pages_crawled": len(pages),
        "max_pages": max_pages,
        "max_depth": max_depth,
        "robots_respected": True,
        "redirects_followed": False,
        "scope": "same-hostname",
        "pages": pages,
    }
