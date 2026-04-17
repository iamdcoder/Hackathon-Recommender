from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    async_playwright = None  # type: ignore[assignment]
    PLAYWRIGHT_AVAILABLE = False

from utils.models import Hackathon

logger = logging.getLogger(__name__)


def _normalize_kaggle_tags(categories: list[dict[str, Any]] | None) -> list[str]:
    if not categories:
        return []
    tags: list[str] = []
    for category in categories:
        label = category.get("displayName") or category.get("name")
        if label:
            tags.append(label)
    return tags


def _infer_kaggle_registration(deadline: str | None) -> str:
    if not deadline:
        return "open"
    deadline_text = str(deadline).strip()[:10]
    try:
        deadline_date = datetime.fromisoformat(deadline_text).date()
    except ValueError:
        return "open"
    return "open" if deadline_date >= datetime.now().date() else "closed"


def _infer_programming_skills(text: str, tags: list[str]) -> list[str]:
    normalized = text.lower()
    skills: list[str] = []
    if any(keyword in normalized for keyword in ["programming", "coding", "software development", "software engineering", "code challenge", "build an app", "build a project", "developer"]):
        skills.append("Programming")
    if any(keyword in normalized for keyword in ["computer vision", "image recognition", "image processing", "vision model", "cv"]):
        skills.append("Computer Vision")
    if any(tag and any(keyword in tag.lower() for keyword in ["software", "developer", "programming", "coding"]) for tag in tags):
        skills.append("Programming")
    return sorted(set(skills))


async def scrape_kaggle(max_pages: int = 1) -> list[Hackathon]:
    logger.info("Starting Kaggle competition scrape")
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("playwright is not installed; Kaggle scraping is disabled.")
        return []

    results: list[Hackathon] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            active_responses: list[Any] = []

            def capture_response(response: Any) -> None:
                if "competitions.CompetitionService/ListCompetitions" in response.url and response.request.post_data:
                    if "LIST_OPTION_ACTIVE" in response.request.post_data:
                        active_responses.append(response)

            page.on("response", capture_response)
            await page.goto("https://www.kaggle.com/competitions", wait_until="networkidle")
            await page.wait_for_timeout(5000)

            if active_responses:
                response = active_responses[0]
                payload = await response.json()
                for item in payload.get("competitions", []):
                    tags = _normalize_kaggle_tags(item.get("categories"))
                    title = item.get("title") or item.get("competitionName", "Kaggle Competition")
                    description = item.get("briefDescription", "") or ""
                    inferred = _infer_programming_skills(" ".join([title, description]), tags)
                    combined_skills = sorted(set(tags + inferred))
                    deadline = item.get("deadline")
                    registration = _infer_kaggle_registration(deadline)
                    results.append(
                        Hackathon(
                        title=title,
                        description=description,
                        required_skills=combined_skills,
                        registration_status=registration,
                        start_date=(item.get("dateEnabled") or "")[:10],
                        end_date=str(deadline or "")[:10],
                        location="Online",
                        mode="online",
                        prize=str(item.get("reward", "")),
                        organizer=item.get("hostName", ""),
                        tags=combined_skills,
                        url=f"https://www.kaggle.com/c/{item.get('competitionName')}" if item.get("competitionName") else "",
                        source="kaggle",
                    )
                )
            await browser.close()
    except Exception as exc:
        logger.warning("Kaggle scraping failed: %s", exc)
        return []

    logger.info("Kaggle scrape completed with %s items", len(results))
    return results
