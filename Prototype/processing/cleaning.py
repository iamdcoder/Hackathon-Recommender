from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

import pandas as pd

from utils.models import Hackathon

logger = logging.getLogger(__name__)

SKILL_NORMALIZATION = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "AI",
    "artificial intelligence": "AI",
    "deep learning": "Deep Learning",
    "nlp": "NLP",
    "computer vision": "Computer Vision",
    "cv": "Computer Vision",
    "gamedev": "Game Development",
    "game dev": "Game Development",
    "game development": "Game Development",
    "webdev": "Web Development",
    "web development": "Web Development",
    "frontend": "Frontend",
    "backend": "Backend",
    "unreal": "Unreal Engine",
    "unreal engine": "Unreal Engine",
    "unity": "Unity",
    "python": "Python",
    "reactjs": "React",
    "react": "React",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "gpt": "GPT",
}

DATE_FORMATS = ["%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%d %B %Y", "%Y/%m/%d", "%m/%d/%Y"]


def normalize_date(date_text: str) -> str:
    if not date_text:
        return ""
    date_text = date_text.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_text, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    for part in date_text.replace("to", "-", 1).split("-")[:2]:
        part = part.strip()
        if not part:
            continue
        for fmt in DATE_FORMATS:
            try:
                dt = datetime.strptime(part, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
    logger.debug("Unable to normalize date: %s", date_text)
    return ""


def normalize_skill(skill: str) -> str:
    cleaned = skill.strip().lower().replace(".", "").replace("/", " ")
    if cleaned in SKILL_NORMALIZATION:
        return SKILL_NORMALIZATION[cleaned]
    return skill.strip().title()


def clean_hackathon_fields(hack: Hackathon) -> Hackathon:
    normalized_skills = [normalize_skill(skill) for skill in hack.required_skills if skill]
    cleaned_tags = sorted({tag.strip().title() for tag in hack.tags if tag.strip()})
    return Hackathon(
        title=hack.title.strip(),
        description=hack.description.strip(),
        required_skills=sorted(set(normalized_skills)),
        registration_status=hack.registration_status.strip().lower() or "unknown",
        start_date=normalize_date(hack.start_date),
        end_date=normalize_date(hack.end_date),
        location=hack.location.strip() or "Online",
        mode=hack.mode.strip().lower() or "online",
        prize=hack.prize.strip(),
        organizer=hack.organizer.strip(),
        tags=cleaned_tags,
        url=hack.url.strip(),
        source=hack.source,
    )


def build_dataframe(hacks: Iterable[Hackathon]) -> pd.DataFrame:
    rows = [hack.to_dict() for hack in hacks]
    columns = ["title", "description", "required_skills", "registration_status", "start_date", "end_date", "location", "mode", "prize", "organizer", "tags", "url", "source"]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return pd.DataFrame(columns=columns)
    df["start_date"] = df["start_date"].apply(normalize_date)
    df["end_date"] = df["end_date"].apply(normalize_date)
    df["registration_status"] = df["registration_status"].fillna("unknown").str.lower()
    df["mode"] = df["mode"].fillna("online").str.lower()
    df["location"] = df["location"].fillna("Online")
    df["tags"] = df["tags"].apply(lambda tags: [normalize_skill(tag) for tag in tags] if isinstance(tags, list) else [])
    df["required_skills"] = df["required_skills"].apply(lambda skills: [normalize_skill(skill) for skill in skills] if isinstance(skills, list) else [])
    df = df.drop_duplicates(subset=["title", "url"], keep="first")
    logger.info("Cleaned dataframe with %s unique hackathons", len(df))
    return df


def merge_datasets(*dfs: pd.DataFrame) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame(
            columns=["title", "description", "required_skills", "registration_status", "start_date", "end_date", "location", "mode", "prize", "organizer", "tags", "url", "source"]
        )
    merged = pd.concat(dfs, ignore_index=True, sort=False)
    if merged.empty:
        return pd.DataFrame(
            columns=["title", "description", "required_skills", "registration_status", "start_date", "end_date", "location", "mode", "prize", "organizer", "tags", "url", "source"]
        )
    merged = merged.drop_duplicates(subset=["title", "url"], keep="first")
    if "required_skills" not in merged.columns:
        merged["required_skills"] = []
    merged["required_skills"] = merged["required_skills"].apply(lambda skills: [normalize_skill(skill) for skill in skills] if isinstance(skills, list) else [])
    return merged.reset_index(drop=True)
