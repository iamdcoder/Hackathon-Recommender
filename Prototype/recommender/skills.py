from __future__ import annotations

import asyncio
import logging
import re
from typing import Iterable

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

SKILL_KEYWORDS = {
    "python": "Python",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "reactjs": "React",
    "react native": "React Native",
    "node": "Node.js",
    "nodejs": "Node.js",
    "express": "Express",
    "vue": "Vue.js",
    "angular": "Angular",
    "html": "HTML",
    "css": "CSS",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "webdev": "Web Development",
    "web dev": "Web Development",
    "web development": "Web Development",
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "FullStack",
    "flutter": "Flutter",
    "dart": "Dart",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "java": "Java",
    "spring": "Spring",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "c": "C",
    "csharp": "C#",
    "c#": "C#",
    "cpp": "C++",
    "c++": "C++",
    "ruby": "Ruby",
    "php": "PHP",
    "scala": "Scala",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "unity": "Unity",
    "unreal": "Unreal Engine",
    "unreal engine": "Unreal Engine",
    "gamedev": "Game Development",
    "game dev": "Game Development",
    "game development": "Game Development",
    "computer vision": "Computer Vision",
    "cv": "Computer Vision",
    "nlu": "NLP",
    "gemini": "AI",
    "gemini vision": "Computer Vision",
    "nlp": "NLP",
    "artificial intelligence": "AI",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "data science": "Data Science",
    "data engineering": "Data Engineering",
    "big data": "Big Data",
    "analytics": "Analytics",
    "robotics": "Robotics",
    "iot": "IoT",
    "blockchain": "Blockchain",
    "web3": "Web3",
    "web": "Web Development",
    "metaverse": "Metaverse",
    "augmented reality": "AR",
    "virtual reality": "VR",
    "mixed reality": "MR",
    "nft": "NFT",
    "circuit": "Robotics",
    "electronics": "Robotics",
    "devops": "DevOps",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "apache": "Apache",
    "nginx": "Nginx",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "keras": "Keras",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "spark": "Apache Spark",
    "hadoop": "Hadoop",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "sql": "SQL",
    "nosql": "NoSQL",
    "graphql": "GraphQL",
    "rest": "REST",
    "api": "API",
    "api development": "API Development",
    "security": "Security",
    "cybersecurity": "Cybersecurity",
    "computer graphics": "Computer Graphics",
    "image processing": "Image Processing",
    "coding": "Coding",
    "programming": "Programming",
    "software development": "Programming",
    "software engineering": "Programming",
}

SKILL_PHRASES = sorted(SKILL_KEYWORDS.keys(), key=len, reverse=True)
SPECIAL_SKILL_EXPANSIONS = {
    "gemini": ["AI", "Computer Vision"],
    "gemini vision": ["Computer Vision", "AI"],
    "python": ["Programming"],
    "java": ["Programming"],
    "c": ["Programming"],
    "c++": ["Programming"],
    "c#": ["Programming"],
    "ruby": ["Programming"],
    "php": ["Programming"],
    "scala": ["Programming"],
    "swift": ["Programming"],
    "kotlin": ["Programming"],
    "javascript": ["Programming"],
    "typescript": ["Programming"],
    "go": ["Programming"],
    "rust": ["Programming"],
    "programming": ["Programming"],
    "coding": ["Programming"],
    "software development": ["Programming"],
    "software engineering": ["Programming"],
}
SKILL_PATTERN = re.compile(r"\b([A-Za-z#+-]{1,})\b")


async def _fetch_readme(session: aiohttp.ClientSession, api_url: str) -> str:
    async with session.get(api_url) as response:
        if response.status == 404:
            return ""
        response.raise_for_status()
        data = await response.json()
        if isinstance(data, dict):
            return data.get("content", "")
        return ""


def _fetch_readme_requests(api_url: str, headers: dict[str, str]) -> str:
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests is not installed")
    response = requests.get(api_url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        return data.get("content", "")
    return ""


def normalize_skill(skill: str) -> str:
    key = skill.strip().lower()
    return SKILL_KEYWORDS.get(key, skill.strip().title())


def extract_skills_from_text(text: str) -> list[str]:
    if not text:
        return []
    normalized_text = text.lower()
    matches: set[str] = set()

    for phrase, expanded_skills in SPECIAL_SKILL_EXPANSIONS.items():
        if re.search(r"\b" + re.escape(phrase) + r"\b", normalized_text):
            matches.update(expanded_skills)
            normalized_text = re.sub(r"\b" + re.escape(phrase) + r"\b", " ", normalized_text)

    for phrase in SKILL_PHRASES:
        if re.search(r"\b" + re.escape(phrase) + r"\b", normalized_text):
            matches.add(SKILL_KEYWORDS[phrase])
            normalized_text = re.sub(r"\b" + re.escape(phrase) + r"\b", " ", normalized_text)

    for phrase, expanded_skills in SPECIAL_SKILL_EXPANSIONS.items():
        if re.search(r"\b" + re.escape(phrase) + r"\b", text.lower()):
            matches.update(expanded_skills)

    words = set(match.group(1).lower() for match in SKILL_PATTERN.finditer(normalized_text))
    for word in words:
        if word in SKILL_KEYWORDS:
            matches.add(SKILL_KEYWORDS[word])
    return sorted(matches)


def parse_github_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if "github.com" not in cleaned:
        raise ValueError("Only GitHub repository URLs are supported")
    parts = cleaned.split("github.com/")[-1].split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[0], parts[1]
    return f"https://api.github.com/repos/{owner}/{repo}/readme"


async def fetch_github_skills(github_urls: Iterable[str], github_token: str | None = None) -> list[str]:
    github_urls = [url for url in github_urls if url.strip()]
    if not github_urls:
        return []
    if not AIOHTTP_AVAILABLE and not REQUESTS_AVAILABLE:
        logger.warning("Neither aiohttp nor requests is installed; GitHub skill extraction is disabled.")
        return []

    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    skills: set[str] = set()
    if AIOHTTP_AVAILABLE:
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = []
            for url in github_urls:
                try:
                    api_url = parse_github_url(url)
                    tasks.append(_fetch_readme(session, api_url))
                except ValueError as exc:
                    logger.warning("Skipping GitHub URL %s: %s", url, exc)
            texts = await asyncio.gather(*tasks, return_exceptions=True)
        for maybe_text in texts:
            if isinstance(maybe_text, Exception):
                logger.debug("GitHub fetch error: %s", maybe_text)
                continue
            decoded = maybe_text
            skills.update(extract_skills_from_text(decoded))
    else:
        for url in github_urls:
            try:
                api_url = parse_github_url(url)
                decoded = await asyncio.to_thread(_fetch_readme_requests, api_url, headers)
                skills.update(extract_skills_from_text(decoded))
            except ValueError as exc:
                logger.warning("Skipping GitHub URL %s: %s", url, exc)
            except Exception as exc:
                logger.debug("GitHub fetch error: %s", exc)
    return sorted(skills)


def merge_skill_sets(manual_skills: Iterable[str], extracted_skills: Iterable[str]) -> list[str]:
    normalized = [normalize_skill(skill) for skill in manual_skills if skill.strip()]
    normalized.extend(normalize_skill(skill) for skill in extracted_skills)
    return sorted({skill for skill in normalized if skill})
