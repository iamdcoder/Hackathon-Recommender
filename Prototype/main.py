from __future__ import annotations

import argparse
import ast
import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd

from database.db import HackathonDatabase
from processing.cleaning import build_dataframe, merge_datasets
from recommender.engine import Recommender
from recommender.skills import fetch_github_skills, merge_skill_sets
from scraper.devpost import scrape_devpost
from scraper.kaggle import scrape_kaggle
from utils.models import Hackathon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_CSV = "sample_data/hackathons_sample.csv"


def _parse_list_field(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if pd.isna(value):
        return []
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def prompt_for_devpost_pages(default: int = 3) -> int:
    max_pages = 15
    while True:
        user_input = input(f"Enter the number of Devpost pages to scrape [preconfigured: {default}, max: {max_pages}]: ").strip()
        if not user_input:
            return default
        if user_input.isdigit() and int(user_input) >= 0:
            return min(int(user_input), max_pages)
        print("Please enter a non-negative integer.")


def load_sample_hackathons(path: str = DEFAULT_SAMPLE_CSV) -> pd.DataFrame:
    try:
        sample_df = pd.read_csv(path)
    except FileNotFoundError:
        logger.warning("Sample dataset %s not found", path)
        return pd.DataFrame(
            columns=[
                "title",
                "description",
                "required_skills",
                "registration_status",
                "start_date",
                "end_date",
                "location",
                "mode",
                "prize",
                "organizer",
                "tags",
                "url",
                "source",
            ]
        )

    hacks = []
    for _, row in sample_df.iterrows():
        hacks.append(
            Hackathon(
                title=str(row.get("title", "") or ""),
                description=str(row.get("description", "") or ""),
                required_skills=_parse_list_field(row.get("required_skills", "")),
                registration_status=str(row.get("registration_status", "") or ""),
                start_date=str(row.get("start_date", "") or ""),
                end_date=str(row.get("end_date", "") or ""),
                location=str(row.get("location", "") or ""),
                mode=str(row.get("mode", "") or ""),
                prize=str(row.get("prize", "") or ""),
                organizer=str(row.get("organizer", "") or ""),
                tags=_parse_list_field(row.get("tags", "")),
                url=str(row.get("url", "") or ""),
                source=str(row.get("source", "") or ""),
            )
        )
    return build_dataframe(hacks)


def filter_hackathons(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    filtered = df.copy()
    if args.only_open:
        filtered = filtered[filtered["registration_status"] == "open"]
    if args.mode:
        filtered = filtered[filtered["mode"] == args.mode.lower()]
    if args.min_prize:
        filtered = filtered[filtered["prize"].str.contains(str(args.min_prize), na=False, case=False)]
    if args.start_date:
        filtered = filtered[filtered["start_date"] >= args.start_date]
    if args.end_date:
        filtered = filtered[filtered["end_date"] <= args.end_date]
    if args.location:
        filtered = filtered[filtered["location"].str.contains(args.location, case=False, na=False)]
    return filtered.reset_index(drop=True)


def format_recommendations(recommendations: list, top_k: int) -> None:
    if not recommendations:
        print("No recommended hackathons found. Try a broader skill set.")
        return
    print(f"Top {min(top_k, len(recommendations))} hackathon recommendations:\n")
    for index, rec in enumerate(recommendations[:top_k], start=1):
        print(f"{index}. {rec.title}")
        print(f"   Score: {rec.score}")
        print(f"   Registration: {rec.registration_status.title() if rec.registration_status else 'Unknown'}")
        if rec.start_date or rec.end_date:
            date_range = f"{rec.start_date or 'N/A'} to {rec.end_date or 'N/A'}"
            print(f"   Date: {date_range}")
        print(f"   URL: {rec.url}")
        print(f"   Matched skills: {', '.join(rec.matched_skills) if rec.matched_skills else 'None'}")
        print(f"   Explanation: {rec.explanation}\n")


def write_sample_csv(df: pd.DataFrame, path: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    logger.info("Saved sample dataset to %s", output)


async def main_async(args: argparse.Namespace) -> None:
    devpost_data = await scrape_devpost(max_pages=args.devpost_pages)
    kaggle_data = await scrape_kaggle(max_pages=args.kaggle_pages)
    combined = merge_datasets(build_dataframe(devpost_data), build_dataframe(kaggle_data))
    if combined.empty:
        logger.warning("No hackathons were scraped from Devpost or Kaggle. Falling back to sample dataset.")
        print("Warning: scraping did not return hackathons; using fallback sample dataset.")
        combined = load_sample_hackathons(DEFAULT_SAMPLE_CSV)
        if combined.empty:
            logger.warning("No hackathons available after fallback. Exiting.")
            print("No hackathons are available right now. Please try again later or install the required dependencies.")
            return
    combined = filter_hackathons(combined, args)
    db = HackathonDatabase(args.database)
    db.insert_hackathons(combined)
    hackathons = combined.to_dict(orient="records")
    manual_skills = [skill.strip() for skill in args.skills.split(",") if skill.strip()] if args.skills else []
    github_urls = [url.strip() for url in args.github_urls.split(",") if url.strip()] if args.github_urls else []
    extracted = await fetch_github_skills(github_urls, args.github_token)
    user_skills = merge_skill_sets(manual_skills, extracted)
    recommender = Recommender(hackathons)
    recommendations = recommender.rank(user_skills, top_k=args.top_k)
    format_recommendations(recommendations, args.top_k)
    if args.sample_csv:
        write_sample_csv(combined, args.sample_csv)
    db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hackathon Aggregator and Recommendation CLI")
    parser.add_argument("--skills", type=str, default="", help="Comma-separated manual skills")
    parser.add_argument("--github-urls", type=str, default="", help="Comma-separated GitHub repo URLs")
    parser.add_argument("--github-token", type=str, default="", help="GitHub token for API rate limits")
    parser.add_argument("--mode", type=str, choices=["online", "offline", "hybrid"], default="online")
    parser.add_argument("--only-open", action="store_true", help="Show only open hackathons")
    parser.add_argument("--min-prize", type=str, default="", help="Filter hackathons by minimum prize keyword")
    parser.add_argument("--start-date", type=str, default="", help="Filter hackathons by start date ISO format")
    parser.add_argument("--end-date", type=str, default="", help="Filter hackathons by end date ISO format")
    parser.add_argument("--location", type=str, default="", help="Filter hackathons by location keyword")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top recommendations to display")
    parser.add_argument("--database", type=str, default="hackathons.db", help="SQLite database file")
    parser.add_argument("--sample-csv", type=str, default="sample_data/hackathons_sample.csv", help="Export sample dataset CSV")
    parser.add_argument("--devpost-pages", type=int, default=3, help="Number of Devpost pages to scrape")
    parser.add_argument("--kaggle-pages", type=int, default=1, help="Number of Kaggle pages to scrape")
    return parser.parse_args()


def prompt_for_user_input() -> tuple[str, str]:
    while True:
        print("\nHow would you like to provide your skills?")
        print("1. Enter manual skills")
        print("2. Enter GitHub repo URLs")
        choice = input("Choose 1 or 2: ").strip()
        if choice == "1":
            print("\nExample of the manual skills you can enter:\n")
            print("Game Development, Unreal Engine, Unity, Flask, Django, NLP, NLU, Computer Vision, Circuit, Web Development, AI, ML, Robotics, Programming, Python, Kubernetes, Docker, Blockchain, Data Science, FullStack, React, Node.js, Swift, Kotlin\n")
            print("You can enter any combination of these or your own skills, separated by commas.")
            skills = input("Enter your skills (comma-separated): ").strip()
            return skills, ""
        elif choice == "2":
            github_urls = input("Enter GitHub repository URLs (comma-separated): ").strip()
            return "", github_urls
        else:
            print("Invalid choice. Please enter 1 or 2.")


def main() -> None:
    args = parse_args()
    if not args.skills and not args.github_urls:
        args.skills, args.github_urls = prompt_for_user_input()
    if "--devpost-pages" not in sys.argv:
        args.devpost_pages = prompt_for_devpost_pages(args.devpost_pages)
    if args.devpost_pages > 15:
        print("Devpost page limit is 15; using 15 pages.")
        args.devpost_pages = 15
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
