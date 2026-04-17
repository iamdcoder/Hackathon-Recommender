# Hackathon Aggregator + Recommendation System

A production-grade Python system for scraping hackathons, normalizing data, extracting skills from GitHub, and recommending the best hackathons for a user.

## Features

- Async scraping of Devpost and Kaggle
- NLP skill inference and normalization
- SQLite persistence and Pandas pipeline
- GitHub README skill extraction
- TF-IDF + cosine similarity recommendation
- Command-line filtering and recommendations
- Optional Streamlit dashboard

## Project Structure

- `scraper/` - platform-specific scraping modules
- `processing/` - cleaning and dataset normalization
- `recommender/` - skill extraction and ranking logic
- `database/` - SQLite persistence
- `utils/` - shared models and HTTP helpers
- `main.py` - CLI entrypoint
- `app.py` - Streamlit dashboard

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Run the CLI

```bash
python main.py --skills "Python, ML" --github-urls "https://github.com/owner/repo" --mode online --top-k 5
```

Optional flags:

- `--only-open`
- `--min-prize "$500"`
- `--start-date 2026-05-01`
- `--end-date 2026-06-30`
- `--location "Remote"`
- `--sample-csv sample_data/hackathons_sample.csv`
- `--database hackathons.db`

## Run the Streamlit App

```bash
streamlit run app.py
```

> First run `python main.py` once to populate `hackathons.db`.

## Notes

- Devpost scraping uses Playwright to handle JS-heavy content.
- Kaggle scraping uses `aiohttp` and `BeautifulSoup`.
- Skills are merged from manual input and GitHub README extraction.
- Recommendation uses TF-IDF on skill lists and cosine similarity.

## Sample Data

A small sample dataset is provided in `sample_data/hackathons_sample.csv`.
