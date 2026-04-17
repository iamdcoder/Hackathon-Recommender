from __future__ import annotations

import asyncio
import logging
from typing import Any

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HackathonAggregator/1.0; +https://github.com/)"
}


async def fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    timeout: int = 15,
    delay: float = 1.0,
) -> str:
    headers = {**DEFAULT_HEADERS, **(headers or {})}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                text = await response.text()
                return text
        except Exception as exc:
            last_error = exc
            logger.warning("fetch_text failed for %s attempt %s: %s", url, attempt, exc)
            await asyncio.sleep(delay * attempt)
    raise RuntimeError(f"Failed to fetch {url}") from last_error


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    timeout: int = 15,
    delay: float = 1.0,
) -> Any:
    headers = {**DEFAULT_HEADERS, **(headers or {})}
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as exc:
            last_error = exc
            logger.warning("fetch_json failed for %s attempt %s: %s", url, attempt, exc)
            await asyncio.sleep(delay * attempt)
    raise RuntimeError(f"Failed to fetch JSON from {url}") from last_error


async def is_allowed_by_robots(url: str, session: aiohttp.ClientSession, user_agent: str = DEFAULT_HEADERS["User-Agent"] ) -> bool:
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    try:
        content = await fetch_text(session, robots_url)
    except Exception:
        logger.info("Unable to fetch robots.txt for %s; defaulting to allow", parsed.netloc)
        return True
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    user_directives = []
    applicable = False
    for line in lines:
        if line.lower().startswith("user-agent:"):
            applicable = line.split(":", 1)[1].strip() in ("*", user_agent)
        elif applicable and line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path and parsed.path.startswith(path):
                return False
    return True


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
