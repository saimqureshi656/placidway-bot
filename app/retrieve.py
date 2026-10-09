"""Hybrid retrieval: BM25, FAISS, RRF, treatment boost, sigmoid rerank."""

from __future__ import annotations

import json
import math
import pickle
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np

from ingest.build_index import BGE_QUERY_PREFIX, INDEX_DIR, load_env, load_reranker, tokenize, _embed
from ingest.prices import PRICES_PATH

ROOT = Path(__file__).resolve().parents[1]
RRF_K = 60
CANDIDATES = 20
RERANK_POOL = 8
RERANK_CHARS = 650
FLAG_WEIGHT = 0.25
TREATMENT_BOOST = 0.08
COUNTRY_BOOST = 0.04

TREATMENT_TERMS = (
    "adenocarcinoma",
    "adrenal",
    "anal",
    "ozone",
    "acupuncture",
    "panchakarma",
    "naturopathic",
    "stem cell",
    "live cell",
)
COUNTRY_TERMS = ("turkey", "mexico", "thailand", "croatia", "georgia", "india")


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


@dataclass
class Hit:
    chunk_id: str
    url: str
    page_type: str
    section: str
    section_type: str
    clinic: str
    treatment: str
    country: str
    flagged: bool
    text: str
    score: float
    rerank_score: float = 0.0


@dataclass
class RetrievalResult:
    hits: list[Hit] = field(default_factory=list)
    prices: list[dict] = field(default_factory=list)
    best_score: float = 0.0
    below_threshold: bool = False
    timings: dict = field(default_factory=dict)


class Retriever:
    def __init__(self, index_dir: Path | None = None) -> None:
        env = load_env()
        pointer = (index_dir or INDEX_DIR) / "current"
        version = pointer.read_text(encoding="utf-8").strip()
        self.version_dir = (index_dir or INDEX_DIR) / version
        self.manifest = json.loads((self.version_dir / "manifest.json").read_text(encoding="utf-8"))
        self.chunks = [
            json.loads(line)
            for line in (self.version_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        with (self.version_dir / "bm25.pkl").open("rb") as handle:
            self.bm25 = pickle.load(handle)["bm25"]
        self.faiss_index = faiss.read_index(str(self.version_dir / "chunks.faiss"))
        self.query_prefix = self.manifest.get("query_prefix") or BGE_QUERY_PREFIX
        self.embed_model = self.manifest["embed_model"]
        self.reranker = load_reranker(self.manifest.get("rerank_model") or "BAAI/bge-reranker-base")
        self.threshold = float(env.get("RERANK_THRESHOLD") or 0.30)
        self.top_k = int(env.get("TOP_K") or 5)
        self.price_records = json.loads(PRICES_PATH.read_text(encoding="utf-8"))

    def search(self, query: str, *, intent: str = "info", entities: dict | None = None) -> RetrievalResult:
        entities = entities or {}
        started = time.perf_counter()
        bm25_ids = self._bm25_top(query)
        dense_ids = self._dense_top(query)
        fused = self._rrf(bm25_ids, dense_ids)
        fused = self._metadata_boost(query, fused, entities)
        ranked = sorted(fused, key=fused.get, reverse=True)[:CANDIDATES]
        retrieve_ms = int((time.perf_counter() - started) * 1000)
        rerank_started = time.perf_counter()
        unflagged = [
            index
            for index in ranked
            if not self.chunks[index].get("flagged")
            and self.chunks[index].get("section_type") not in {"testimonial", "video_list"}
        ]
        flagged = [index for index in ranked if index not in unflagged]
        reranked = self._rerank(query, (unflagged + flagged)[:RERANK_POOL])
        rerank_ms = int((time.perf_counter() - rerank_started) * 1000)
        hits = reranked[: self.top_k]
        best = hits[0].score if hits else 0.0
        prices = []
        if intent in {"price", "comparison"}:
            prices = self.lookup_prices(query, entities)
        return RetrievalResult(
            hits=hits,
            prices=prices,
            best_score=best,
            below_threshold=best < self.threshold,
            timings={"retrieve_ms": retrieve_ms, "rerank_ms": rerank_ms},
        )

    def _bm25_top(self, query: str) -> list[int]:
        scores = self.bm25.get_scores(tokenize(query))
        order = np.argsort(scores)[::-1][:CANDIDATES]
        return [int(item) for item in order]

    def _dense_top(self, query: str) -> list[int]:
        vector = _embed(self.embed_model, [query], prefix=self.query_prefix)
        _scores, ids = self.faiss_index.search(vector, CANDIDATES)
        return [int(item) for item in ids[0] if item >= 0]

    def _rrf(self, *rankings: list[int]) -> dict[int, float]:
        scores: dict[int, float] = {}
        for ranking in rankings:
            for rank, chunk_index in enumerate(ranking):
                scores[chunk_index] = scores.get(chunk_index, 0.0) + 1.0 / (RRF_K + rank + 1)
        return scores

    def _metadata_boost(self, query: str, scores: dict[int, float], entities: dict) -> dict[int, float]:
        query_l = query.lower()
        treatments = [term for term in TREATMENT_TERMS if term in query_l]
        entity_treatment = str(entities.get("treatment") or "").lower()
        if entity_treatment:
            treatments.append(entity_treatment)
        countries = [term for term in COUNTRY_TERMS if term in query_l]
        entity_country = str(entities.get("country") or "").lower()
        if entity_country:
            countries.append(entity_country)
        page_type = ""
        if "video" in query_l:
            page_type = "clinic_videos"
        elif "price list" in query_l or "pricelist" in query_l:
            page_type = "price_list"
        elif any(word in query_l for word in ("cheaper", "compare", "versus", " vs ")):
            page_type = "price_comparison"
        boosted = dict(scores)
        for chunk_index in list(boosted):
            chunk = self.chunks[chunk_index]
            haystack = f"{chunk.get('treatment', '')} {chunk.get('text', '')}".lower()
            country_field = str(chunk.get("country") or "").lower()
            if any(term in haystack for term in treatments):
                boosted[chunk_index] += TREATMENT_BOOST
            if any(term in haystack or term in country_field for term in countries):
                boosted[chunk_index] += COUNTRY_BOOST
            if page_type and chunk.get("page_type") == page_type:
                boosted[chunk_index] += COUNTRY_BOOST
        return boosted

    def _rerank_text(self, query: str, text: str) -> str:
        if len(text) <= RERANK_CHARS:
            return text
        stop = {
            "therapy",
            "cheaper",
            "treatment",
            "cost",
            "price",
            "about",
            "what",
            "does",
            "much",
            "with",
            "from",
            "this",
            "that",
            "program",
            "package",
            "alternative",
            "medicine",
            "cancer",
            "included",
            "include",
        }
        terms = [word for word in re.findall(r"[a-z0-9]+", query.lower()) if len(word) > 3 and word not in stop]
        parts = re.split(r"(?=Clinic / Surgeon:)", text)
        chosen = sorted(
            (part.strip() for part in parts if any(term in part.lower() for term in terms)),
            key=lambda part: sum(term in part.lower() for term in terms),
            reverse=True,
        )[:2]
        head = text[:120]
        if not chosen:
            return text[:RERANK_CHARS]
        return (head + "\n" + "\n".join(chosen))[:RERANK_CHARS]

    def _rerank(self, query: str, indexes: list[int]) -> list[Hit]:
        if not indexes:
            return []
        documents = [self._rerank_text(query, self.chunks[index]["text"]) for index in indexes]
        logits = [float(score) for score in self.reranker.rerank(query, documents)]
        hits: list[Hit] = []
        for chunk_index, logit in zip(indexes, logits):
            chunk = self.chunks[chunk_index]
            score = sigmoid(logit)
            if chunk.get("flagged") or chunk.get("section_type") in {"testimonial", "video_list"}:
                score *= FLAG_WEIGHT
            hits.append(
                Hit(
                    chunk_id=chunk["chunk_id"],
                    url=chunk["url"],
                    page_type=chunk["page_type"],
                    section=chunk["section"],
                    section_type=chunk["section_type"],
                    clinic=chunk.get("clinic") or "",
                    treatment=chunk.get("treatment") or "",
                    country=chunk.get("country") or "",
                    flagged=bool(chunk.get("flagged")),
                    text=chunk["text"],
                    score=score,
                    rerank_score=score,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits

    def warm(self) -> None:
        _embed(self.embed_model, ["warmup"], prefix=self.query_prefix)
        if self.chunks:
            self._rerank("warmup", [0])

    def lookup_prices(self, query: str, entities: dict | None = None) -> list[dict]:
        entities = entities or {}
        query_l = f"{query} {entities.get('treatment', '')} {entities.get('country', '')}".lower()
        treatments = [term for term in TREATMENT_TERMS if term in query_l]
        entity_treatment = str(entities.get("treatment") or "").lower()
        if entity_treatment:
            treatments.append(entity_treatment)
        matched = []
        for record in self.price_records:
            if not record.get("answerable", True):
                continue
            blob = " ".join(
                str(record.get(key) or "")
                for key in ("treatment", "program", "clinic", "location", "category", "raw_text")
            ).lower()
            if treatments:
                if any(term in blob for term in treatments):
                    matched.append(record)
                continue
            if record["category"] == "comparison_summary" and any(
                word in query_l for word in ("average", "range", "how much", "cost")
            ):
                matched.append(record)
        return matched


_RETRIEVER: Retriever | None = None


def get_retriever() -> Retriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = Retriever()
    return _RETRIEVER


def preview(queries: list[str]) -> dict[str, list[dict]]:
    retriever = get_retriever()
    report = {}
    for query in queries:
        result = retriever.search(query)
        report[query] = [
            {
                "rank": rank,
                "score": round(hit.score, 4),
                "chunk_id": hit.chunk_id,
                "page_type": hit.page_type,
                "section": hit.section,
                "section_type": hit.section_type,
                "flagged": hit.flagged,
            }
            for rank, hit in enumerate(result.hits[:3], start=1)
        ]
    return report
