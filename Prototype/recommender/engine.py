from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    title: str
    url: str
    score: float
    matched_skills: list[str]
    explanation: str
    registration_status: str
    start_date: str
    end_date: str


class Recommender:
    def __init__(self, hackathons: list[dict[str, object]]):
        self.hackathons = hackathons
        self.skill_matrix = None
        self.skill_corpus = []
        self.vocabulary: list[str] = []
        self.idf: dict[str, float] = {}
        self._build_matrix()

    def _tokenize_text(self, text: str) -> list[str]:
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        return [token for token in normalized.split() if token]

    def _format_text(self, item: dict[str, object]) -> str:
        tokens: list[str] = []
        tokens.extend(item.get("required_skills", []) or [])
        tokens.extend(item.get("tags", []) or [])
        title = item.get("title", "")
        description = item.get("description", "")
        if title:
            tokens.append(title)
        if description:
            tokens.append(description)
        tokenized: list[str] = []
        for token in tokens:
            tokenized.extend(self._tokenize_text(str(token)))
        return " ".join(tokenized)

    def _build_matrix(self) -> None:
        self.skill_corpus = [self._format_text(item) for item in self.hackathons]
        if not self.skill_corpus:
            self.skill_matrix = None
            self.vocabulary = []
            self.idf = {}
            return

        corpus_token_lists = [self._tokenize_text(text) for text in self.skill_corpus]
        self.vocabulary = sorted({token for tokens in corpus_token_lists for token in tokens})
        if not self.vocabulary:
            self.skill_matrix = None
            self.idf = {}
            return

        document_counts = {token: 0 for token in self.vocabulary}
        for tokens in corpus_token_lists:
            for token in set(tokens):
                document_counts[token] += 1

        self.idf = {
            token: math.log((len(corpus_token_lists) + 1) / (1 + document_counts[token])) + 1.0
            for token in self.vocabulary
        }

        self.skill_matrix = np.vstack([self._tfidf_vector(tokens) for tokens in corpus_token_lists])
        logger.debug("Built custom TF-IDF skill matrix with shape %s", self.skill_matrix.shape)

    def _tfidf_vector(self, tokens: list[str]) -> np.ndarray:
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        total_terms = sum(counts.values()) or 1
        vector = np.zeros(len(self.vocabulary), dtype=float)
        for idx, token in enumerate(self.vocabulary):
            if token in counts:
                tf = counts[token] / total_terms
                vector[idx] = tf * self.idf.get(token, 0.0)
        return vector

    def _vector_norm(self, vector: np.ndarray) -> float:
        norm = np.linalg.norm(vector)
        return float(norm if norm > 0 else 1.0)

    def _similarity(self, query_vec: np.ndarray, doc_vec: np.ndarray) -> float:
        return float(np.dot(query_vec, doc_vec) / (self._vector_norm(query_vec) * self._vector_norm(doc_vec)))

    def _extract_terms(self, text: str) -> set[str]:
        return set(self._tokenize_text(text))

    def _match_skills(self, hack: dict[str, object], user_skills: list[str]) -> list[str]:
        user_terms = set()
        for skill in user_skills:
            user_terms.update(self._extract_terms(skill))

        candidate_terms = set()
        candidate_terms.update(self._extract_terms(" ".join(hack.get("required_skills", []) or [])))
        candidate_terms.update(self._extract_terms(" ".join(hack.get("tags", []) or [])))
        candidate_terms.update(self._extract_terms(str(hack.get("title", ""))))
        candidate_terms.update(self._extract_terms(str(hack.get("description", ""))))

        matched: list[str] = []
        for skill in user_skills:
            normalized_skill_terms = self._extract_terms(skill)
            if normalized_skill_terms & candidate_terms:
                matched.append(skill)
        return sorted(set(matched), key=lambda x: user_skills.index(x) if x in user_skills else 0)

    def rank(self, user_skills: list[str], top_k: int = 10) -> list[Recommendation]:
        if self.skill_matrix is None or not user_skills:
            return []

        query_text = self._format_text(
            {"required_skills": user_skills, "tags": user_skills, "title": "", "description": ""}
        )
        query_vector = self._tfidf_vector(self._tokenize_text(query_text))
        similarity = np.array([self._similarity(query_vector, doc_vec) for doc_vec in self.skill_matrix])
        ranked_indexes = similarity.argsort()[::-1][:top_k]

        recommendations: list[Recommendation] = []
        for idx in ranked_indexes:
            score = float(similarity[idx])
            if score <= 0:
                continue
            hack = self.hackathons[idx]
            matched = self._match_skills(hack, user_skills)
            explanation = (
                f"Matches {len(matched)} skills: {', '.join(matched)}"
                if matched
                else "Similar domain keywords detected from hackathon tags or title."
            )
            recommendations.append(
                Recommendation(
                    title=hack.get("title", ""),
                    url=hack.get("url", ""),
                    score=round(score, 4),
                    matched_skills=matched,
                    explanation=explanation,
                    registration_status=str(hack.get("registration_status", "")),
                    start_date=str(hack.get("start_date", "")),
                    end_date=str(hack.get("end_date", "")),
                )
            )
        if not recommendations:
            for hack in self.hackathons:
                matched = self._match_skills(hack, user_skills)
                if matched:
                    recommendations.append(
                        Recommendation(
                            title=hack.get("title", ""),
                            url=hack.get("url", ""),
                            score=0.0,
                            matched_skills=matched,
                            explanation=f"Direct tag or title match: {', '.join(matched)}",
                            registration_status=str(hack.get("registration_status", "")),
                            start_date=str(hack.get("start_date", "")),
                            end_date=str(hack.get("end_date", "")),
                        )
                    )
                    if len(recommendations) >= top_k:
                        break
        return recommendations[:top_k]
