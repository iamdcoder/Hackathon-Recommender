from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Hackathon:
    title: str
    description: str
    required_skills: list[str] = field(default_factory=list)
    registration_status: str = "unknown"
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    mode: str = "online"
    prize: str = ""
    organizer: str = ""
    tags: list[str] = field(default_factory=list)
    url: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self)}


@dataclass
class UserProfile:
    manual_skills: list[str] = field(default_factory=list)
    github_urls: list[str] = field(default_factory=list)
    user_skills: list[str] = field(default_factory=list)

    def all_skills(self) -> list[str]:
        normalized = [skill.strip() for skill in self.manual_skills + self.user_skills if skill.strip()]
        return sorted(set(normalized))
