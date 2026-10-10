"""Build a BM25 corpus and a normalized FAISS index for the chunks.

Reads EMBED_MODEL and RERANK_MODEL from .env. Embeddings use fastembed.
E5 models are embedded with the passage/query prefix. Vectors are L2-normalized
for IndexFlatIP.
"""

from __future__ import annotations

import json
import os
import pickle
import re
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from ingest.chunk import CHUNKS_PATH, build_chunks

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "index"
ENV_PATH = ROOT / ".env"

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# Official BGE v1.5 instruction. Applied to queries only, not to passages.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
FALLBACK_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOKEN_RE = re.compile(r"\$[\d,]+|[a-z0-9]+|\$", re.IGNORECASE)
PREVIEW_QUERIES = (
    "adenocarcinoma cost",
    "in-patient program includes",
    "ozone therapy Turkey",
    "recovery time",
)


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _model_names(items: list) -> set[str]:
    names: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            name = item.get("model") or item.get("model_name")
            if name:
                names.add(name)
        else:
            names.add(str(item))
    return names


def resolve_embed_model(requested: str) -> tuple[str, str]:
    """Return (model_name, note). Note is empty when the requested model is used."""
    from fastembed import TextEmbedding

    supported = _model_names(TextEmbedding.list_supported_models())
    if requested in supported:
        return requested, ""
    if FALLBACK_EMBED_MODEL in supported:
        return (
            FALLBACK_EMBED_MODEL,
            f"fastembed does not list {requested}; using {FALLBACK_EMBED_MODEL}",
        )
    short = "paraphrase-multilingual-MiniLM-L12-v2"
    match = next((name for name in supported if name.endswith(short)), "")
    if match:
        return match, f"fastembed does not list {requested}; using {match}"
    raise RuntimeError(f"Neither {requested} nor {FALLBACK_EMBED_MODEL} is supported by fastembed")


def resolve_rerank_model(requested: str) -> tuple[str, str]:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    supported = _model_names(TextCrossEncoder.list_supported_models())
    if requested in supported:
        return requested, ""
    fallback = "BAAI/bge-reranker-base"
    if fallback in supported:
        return fallback, f"fastembed does not list {requested}; using {fallback}"
    raise RuntimeError(f"Reranker {requested} is not supported by fastembed")


_EMBEDDERS: dict[str, object] = {}


def configure_threads() -> int:
    count = os.cpu_count() or 1
    value = str(count)
    os.environ["OMP_NUM_THREADS"] = value
    os.environ["ORT_INTRA_OP_NUM_THREADS"] = value
    os.environ["ORT_INTER_OP_NUM_THREADS"] = "1"
    return count


def _embed(model_name: str, texts: list[str], *, prefix: str) -> np.ndarray:
    from fastembed import TextEmbedding

    model = _EMBEDDERS.get(model_name)
    if model is None:
        model = TextEmbedding(model_name=model_name, threads=configure_threads())
        _EMBEDDERS[model_name] = model
    payload = [f"{prefix}{text}" if prefix else text for text in texts]
    vectors = np.vstack(list(model.embed(payload))).astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def load_reranker(model_name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=model_name, threads=configure_threads())


def build_index() -> Path:
    env = load_env()
    requested_rerank = env.get("RERANK_MODEL") or os.environ.get("RERANK_MODEL") or "BAAI/bge-reranker-base"
    embed_model, embed_note = resolve_embed_model(EMBED_MODEL)
    rerank_model, rerank_note = resolve_rerank_model(requested_rerank)
    use_bge_prefix = embed_model == EMBED_MODEL

    chunks = build_chunks()
    tokenized = [tokenize(chunk["text"]) for chunk in chunks]
    bm25 = BM25Okapi(tokenized)
    vectors = _embed(embed_model, [chunk["text"] for chunk in chunks], prefix="")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    version = datetime.now(timezone.utc).strftime("v%Y%m%d%H%M%S")
    version_dir = INDEX_DIR / version
    version_dir.mkdir(parents=True, exist_ok=False)
    (version_dir / "chunks.jsonl").write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )
    faiss.write_index(index, str(version_dir / "chunks.faiss"))
    with (version_dir / "bm25.pkl").open("wb") as handle:
        pickle.dump({"bm25": bm25, "tokenized": tokenized}, handle)

    manifest = {
        "embed_model": embed_model,
        "embed_note": embed_note,
        "rerank_model": rerank_model,
        "rerank_note": rerank_note,
        "query_prefix": BGE_QUERY_PREFIX if use_bge_prefix else "",
        "chunks": len(chunks),
        "dimension": int(vectors.shape[1]),
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    pointer = INDEX_DIR / "current"
    temporary = INDEX_DIR / "current.tmp"
    temporary.write_text(version + "\n", encoding="utf-8")
    temporary.replace(pointer)
    print(f"index {version_dir}", flush=True)
    print(f"embed_model {embed_model}", flush=True)
    if embed_note:
        print(f"embed_note {embed_note}", flush=True)

    reranker = load_reranker(rerank_model)
    manifest["rerank_class"] = type(reranker).__name__
    (version_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"rerank_model {rerank_model}", flush=True)
    if rerank_note:
        print(f"rerank_note {rerank_note}", flush=True)
    return version_dir


def top_chunks(query: str, limit: int = 3) -> dict[str, list[dict]]:
    version = (INDEX_DIR / "current").read_text(encoding="utf-8").strip()
    version_dir = INDEX_DIR / version
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    chunks = [json.loads(line) for line in (version_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    with (version_dir / "bm25.pkl").open("rb") as handle:
        bm25 = pickle.load(handle)["bm25"]
    scores = bm25.get_scores(tokenize(query))
    bm25_order = np.argsort(scores)[::-1][:limit]
    prefix = manifest.get("query_prefix") or ""
    query_vector = _embed(manifest["embed_model"], [query], prefix=prefix)
    index = faiss.read_index(str(version_dir / "chunks.faiss"))
    dense_scores, dense_ids = index.search(query_vector, limit)

    def pack(indexes, score_of) -> list[dict]:
        packed = []
        for index_id in indexes:
            chunk = chunks[int(index_id)]
            packed.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "section": chunk["section"],
                    "section_type": chunk["section_type"],
                    "page_type": chunk["page_type"],
                    "flagged": chunk["flagged"],
                    "score": float(score_of(int(index_id))),
                    "snippet": chunk["text"][:180].replace("\n", " "),
                }
            )
        return packed

    return {
        "bm25": pack(bm25_order, lambda item: scores[item]),
        "dense": pack(dense_ids[0], lambda item: dense_scores[0][list(dense_ids[0]).index(item)]),
    }


def main() -> None:
    build_index()


if __name__ == "__main__":
    main()
