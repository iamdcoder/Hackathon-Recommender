from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)


class HackathonDatabase:
    def __init__(self, path: str | Path = "hackathons.db"):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self._create_table()

    def _create_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS hackathons (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            required_skills TEXT,
            registration_status TEXT,
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            mode TEXT,
            prize TEXT,
            organizer TEXT,
            tags TEXT,
            url TEXT UNIQUE,
            source TEXT
        )
        """
        self.connection.execute(query)
        self.connection.commit()

    def insert_hackathons(self, df: pd.DataFrame) -> None:
        if df.empty:
            logger.info("No hackathons to insert")
            return
        rows = []
        for _, row in df.iterrows():
            rows.append(
                (
                    row["title"],
                    row["description"],
                    ",".join(row["required_skills"] if isinstance(row["required_skills"], list) else []),
                    row["registration_status"],
                    row["start_date"],
                    row["end_date"],
                    row["location"],
                    row["mode"],
                    row["prize"],
                    row["organizer"],
                    ",".join(row["tags"] if isinstance(row["tags"], list) else []),
                    row["url"],
                    row.get("source", ""),
                )
            )
        query = """
        INSERT OR IGNORE INTO hackathons (
            title, description, required_skills, registration_status,
            start_date, end_date, location, mode, prize, organizer, tags, url, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.connection.executemany(query, rows)
        self.connection.commit()
        logger.info("Inserted %s hackathons into SQLite", len(rows))

    def load_dataframe(self) -> pd.DataFrame:
        df = pd.read_sql_query("SELECT * FROM hackathons", self.connection)
        if df.empty:
            return df
        df["required_skills"] = df["required_skills"].fillna("").apply(lambda text: [item for item in text.split(",") if item])
        df["tags"] = df["tags"].fillna("").apply(lambda text: [item for item in text.split(",") if item])
        return df

    def close(self) -> None:
        self.connection.close()
