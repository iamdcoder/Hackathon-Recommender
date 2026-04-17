from __future__ import annotations

import asyncio
import logging
from typing import Iterable

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

from utils.models import Hackathon
from utils.http import DEFAULT_HEADERS, fetch_json

logger = logging.getLogger(__name__)


def _parse_date_range(date_text: str) -> tuple[str, str]:
    if not date_text:
        return "", ""
    parts = [part.strip() for part in date_text.replace("–", "-").split("-")]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return date_text.strip(), ""


def _infer_programming_skills(text: str) -> list[str]:
    normalized = text.lower()
    skills: list[str] = []
    if any(keyword in normalized for keyword in ["programming", "coding", "software development", "software engineering", "build a project", "build an app", "code challenge", "code with", "develop"]):
        skills.append("Programming")
    if any(keyword in normalized for keyword in ["computer vision", "image recognition", "image processing", "vision model", "cv"]):
        skills.append("Computer Vision")
    return sorted(set(skills))


async def scrape_devpost(max_pages: int = 2) -> list[Hackathon]:
    logger.info("Starting Devpost scrape for up to %s pages", max_pages)
    if not AIOHTTP_AVAILABLE:
        logger.warning("aiohttp is not installed; Devpost scraping is disabled.")
        return []
    hacks: list[Hackathon] = []
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        for page_number in range(1, max_pages + 1):
            api_url = f"https://devpost.com/api/hackathons?page={page_number}"
            data = await fetch_json(session, api_url)
            for item in data.get("hackathons", []):
                location = item.get("displayed_location", {}).get("location", "Online")
                mode = "online" if "online" in location.lower() else "offline"
                if "hybrid" in location.lower():
                    mode = "hybrid"
                description = item.get("short_description", "") or item.get("description", "") or ""
                start_date, end_date = _parse_date_range(item.get("submission_period_dates", ""))
                themes = [theme.get("name", "").strip() for theme in item.get("themes", []) if theme.get("name")]
                inferred = _infer_programming_skills(" ".join([item.get("title", ""), description, " ".join(themes)]))
                skills = sorted(set(themes + inferred))
                hacks.append(
                    Hackathon(
                        title=item.get("title", "Unknown Hackathon"),
                        description=description,
                        required_skills=skills,
                        registration_status=item.get("open_state", "unknown"),
                        start_date=start_date,
                        end_date=end_date,
                        location=location,
                        mode=mode,
                        prize=item.get("prize_amount", ""),
                        organizer=item.get("organization_name", ""),
                        tags=skills,
                        url=item.get("url", ""),
                        source="devpost",
                    )
                )
            await asyncio.sleep(1.0)
    logger.info("Devpost scraping completed with %s hackathons", len(hacks))
    return hacks
