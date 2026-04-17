from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from database.db import HackathonDatabase
from processing.cleaning import build_dataframe, merge_datasets
from recommender.engine import Recommender
from recommender.skills import fetch_github_skills, merge_skill_sets
from scraper.devpost import scrape_devpost
from scraper.kaggle import scrape_kaggle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_hackathons(db_path: str) -> pd.DataFrame:
    db = HackathonDatabase(db_path)
    df = db.load_dataframe()
    db.close()
    return df


def render_recommendations(df: pd.DataFrame, manual_skills: list[str], github_urls: list[str], github_token: str) -> list:
    user_skills = merge_skill_sets(manual_skills, asyncio.run(fetch_github_skills(github_urls, github_token)))
    recommender = Recommender(df.to_dict(orient="records"))
    return recommender.rank(user_skills, top_k=10)


def main() -> None:
    st.title("Hackathon Aggregator & Recommender")
    with st.sidebar:
        st.header("Filters")
        only_open = st.checkbox("Only open hackathons", value=True)
        mode = st.selectbox("Mode", ["online", "offline", "hybrid"], index=0)
        location = st.text_input("Location")
        start_date = st.date_input("Start date", value=None)
        end_date = st.date_input("End date", value=None)
        manual_skills = st.text_area("Manual skills (comma-separated)").split(",")
        github_urls = st.text_area("GitHub repo URLs (comma-separated)").split(",")
        github_token = st.text_input("GitHub token (optional)")
        if st.button("Refresh hackathons"):
            st.rerun()

    db_path = "hackathons.db"
    if not Path(db_path).exists():
        st.warning("Run main.py once to populate hackathons.db before using the dashboard.")
        return
    df = load_hackathons(db_path)
    filtered = df.copy()
    if only_open:
        filtered = filtered[filtered["registration_status"] == "open"]
    if mode:
        filtered = filtered[filtered["mode"] == mode]
    if location:
        filtered = filtered[filtered["location"].str.contains(location, case=False, na=False)]
    if start_date:
        filtered = filtered[filtered["start_date"] >= start_date.isoformat()]
    if end_date:
        filtered = filtered[filtered["end_date"] <= end_date.isoformat()]
    st.write(f"### {len(filtered)} hackathons found")
    st.dataframe(filtered)

    if st.button("Recommend hackathons"):
        recommendations = render_recommendations(filtered, manual_skills, github_urls, github_token)
        if not recommendations:
            st.info("No matches found. Add more skills or try a wider search.")
            return
        for rec in recommendations:
            st.write(f"**{rec.title}**")
            st.write(f"Score: {rec.score}")
            st.write(f"URL: {rec.url}")
            st.write(f"Matched skills: {', '.join(rec.matched_skills) if rec.matched_skills else 'None'}")
            st.write(f"Explanation: {rec.explanation}")
            st.write("---")


if __name__ == "__main__":
    main()
