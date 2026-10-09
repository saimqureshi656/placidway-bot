"""FastAPI routes for chat, leads, feedback, admin, and health."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import db
from app.config import ROOT, get_settings
from app.diagnostics import log_turn
from app.generate import generate_checked
from app.retrieve import get_retriever
from app.rewrite import rewrite
from app.router import route
from app.security import enforce_admin, enforce_rate_limit
from app.templates import booking, fallback, friendly_error, greeting, medical_advice, out_of_scope
from ingest.build_index import INDEX_DIR
from ingest.prices import PRICES_PATH

app = FastAPI(title="PlacidWay Assistant")
logger = logging.getLogger("placidway.chat")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TREATMENTS = (
    ("adenocarcinoma", "Alternative Adenocarcinoma Cancer Treatment"),
    ("adrenal", "Alternative Adrenal Cancer Treatment"),
    ("anal", "Alternative Anal Cancer Treatment"),
    ("ozone", "Ozone Therapy"),
)


class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(max_length=1000)
    history: list[Turn] = Field(default_factory=list)


class LeadRequest(BaseModel):
    session_id: str
    name: str
    email: str
    interest: str


class FeedbackRequest(BaseModel):
    log_id: int
    rating: str
    comment: str | None = None


def _trace(record: dict) -> None:
    log_turn(record)
    if record.get("fallback"):
        logger.warning(
            "fallback reason=%s raw=%s",
            record.get("verifier_reason"),
            json.dumps(record.get("raw_llm"), ensure_ascii=False)[:4000],
        )


def _sources(hits: list[dict]) -> list[dict]:
    seen: set[str] = set()
    sources = []
    for hit in hits:
        if hit["url"] in seen:
            continue
        seen.add(hit["url"])
        snippet = hit["text"].replace("\n", " ")[:200]
        sources.append(
            {
                "url": hit["url"],
                "title": hit.get("section") or "",
                "section": hit.get("section") or "",
                "snippet": snippet,
            }
        )
    return sources


def _clinic_names() -> list[str]:
    records = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    names = {record.get("clinic") or "" for record in records}
    names.add("ITC Immunity Therapy Center")
    return [name for name in names if name]


def _treatment(query: str, entities: dict) -> str:
    if entities.get("treatment"):
        return entities["treatment"]
    lowered = query.lower()
    for needle, name in _TREATMENTS:
        if needle in lowered:
            return name
    return ""


def _index_status() -> dict:
    pointer = INDEX_DIR / "current"
    if not pointer.exists():
        return {"status": "degraded", "index_version": None, "last_refresh": None, "chunks": 0}
    version = pointer.read_text(encoding="utf-8").strip()
    manifest_path = INDEX_DIR / version / "manifest.json"
    if not manifest_path.exists():
        return {"status": "degraded", "index_version": version, "last_refresh": None, "chunks": 0}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    refreshed = datetime.fromtimestamp(pointer.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "status": "ok",
        "index_version": version,
        "last_refresh": refreshed,
        "chunks": manifest.get("chunks", 0),
    }


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/health")
def health() -> dict:
    return _index_status()


@app.get("/")
def index():
    page = ROOT / "web" / "index.html"
    if page.exists():
        return FileResponse(page)
    return {"status": "ok", "message": "Chat UI is not built yet."}


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request) -> dict:
    enforce_rate_limit(request)
    started = time.perf_counter()
    timings: dict[str, int] = {}
    stage = time.perf_counter()
    routed = route(body.message)
    timings["router_ms"] = int((time.perf_counter() - stage) * 1000)
    language = "en"
    rewritten = body.message
    entities: dict = {}
    hits: list[dict] = []
    verifier_status = "template"
    grounded = True
    raw_llm = None
    verifier_reason = ""
    if routed.intent == "greeting":
        answer = greeting()
    elif routed.intent == "booking":
        answer = booking()
    elif routed.intent == "out_of_scope":
        answer = out_of_scope()
        grounded = False
    else:
        try:
            stage = time.perf_counter()
            rewritten_obj = rewrite(body.message, [turn.model_dump() for turn in body.history][-6:])
            timings["rewrite_ms"] = int((time.perf_counter() - stage) * 1000)
            language = rewritten_obj["language"]
            rewritten = rewritten_obj["standalone_query_en"]
            entities = rewritten_obj["entities"]
            result = get_retriever().search(rewritten, intent=routed.intent, entities=entities)
            timings.update(result.timings)
            hits = [hit.__dict__ for hit in result.hits]
            if result.below_threshold or not hits:
                answer = medical_advice() if routed.intent == "medical_advice" else fallback()
                grounded = routed.intent == "medical_advice"
                verifier_status = "below_threshold"
                verifier_reason = "below_threshold"
                db.log_unanswered(body.message, "below_threshold")
            else:
                draft, verifier_status, attempts, stage_timings = generate_checked(
                    rewritten,
                    hits,
                    result.prices,
                    language=language,
                    user_numbers=routed.user_numbers,
                    treatment=_treatment(rewritten, entities),
                    clinic_names=_clinic_names(),
                )
                timings.update(stage_timings)
                raw_llm = [item.get("raw") for item in attempts]
                verifier_reason = attempts[-1].get("verifier_reason") or ""
                answer = draft["answer"]
                grounded = bool(draft.get("grounded"))
            if routed.intent == "medical_advice":
                answer = medical_advice() if answer == fallback() else f"{medical_advice()} {answer}"
                grounded = True
        except Exception:
            answer = friendly_error()
            grounded = False
            verifier_status = "error"
            if routed.intent == "medical_advice":
                answer = medical_advice()
                grounded = True
    show_disclaimer = False
    if routed.intent in {"price", "comparison", "info", "medical_advice"} and grounded:
        show_disclaimer = db.claim_disclaimer(body.session_id)
    latency_ms = int((time.perf_counter() - started) * 1000)
    timings["total_ms"] = latency_ms
    is_fallback = answer.startswith("I couldn't find that") or verifier_status not in {"pass", "template"}
    if is_fallback:
        _trace(
            {
                "question": body.message,
                "rewritten": rewritten,
                "intent": routed.intent,
                "timings": timings,
                "verifier_reason": verifier_reason or verifier_status,
                "raw_llm": raw_llm,
                "fallback": True,
            }
        )
    logger.info("chat timings %s", json.dumps(timings))
    log_id = db.log_chat(
        session_id=body.session_id,
        question=body.message,
        language=language,
        intent=routed.intent,
        rewritten_query=rewritten,
        top_chunk_ids=",".join(hit["chunk_id"] for hit in hits[:5]),
        rerank_top_score=hits[0]["score"] if hits else None,
        answer=answer,
        grounded=grounded,
        verifier_status=verifier_status,
        latency_ms=latency_ms,
    )
    return {
        "answer": answer,
        "sources": _sources(hits),
        "intent": routed.intent,
        "grounded": grounded,
        "language": language,
        "show_disclaimer": show_disclaimer,
        "offer_lead_form": routed.intent in {"price", "comparison", "lead"},
        "log_id": log_id,
        "debug": {"timings": timings, "verifier_reason": verifier_reason, "verifier_status": verifier_status},
    }


@app.post("/api/lead")
def lead(body: LeadRequest) -> dict:
    if not _EMAIL.match(body.email):
        raise HTTPException(status_code=422, detail="Invalid email")
    db.save_lead(body.session_id, body.name, body.email, body.interest)
    return {"thanks": "Thank you. The PlacidWay team will follow up."}


@app.post("/api/feedback")
def feedback(body: FeedbackRequest) -> dict:
    if body.rating not in {"up", "down"}:
        raise HTTPException(status_code=422, detail="Rating must be up or down")
    db.save_feedback(body.log_id, body.rating, body.comment)
    return {"ok": True}


@app.post("/admin/refresh")
def refresh(request: Request) -> dict:
    enforce_admin(request)
    from ingest.build_index import build_index
    from ingest.fetch import MANIFEST_PATH, fetch_all
    from ingest.extract import extract_all
    from ingest.prices import build_prices

    before = {}
    if MANIFEST_PATH.exists():
        before = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fetch_all()
    after = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    extract_all()
    build_prices()
    version = build_index()
    changed = [
        page_id
        for page_id, entry in after.items()
        if before.get(page_id, {}).get("sha256") != entry.get("sha256")
    ]
    return {"index_version": version.name, "changed_pages": changed}


@app.get("/admin/gaps")
def gaps(request: Request) -> dict:
    enforce_admin(request)
    return {"groups": db.unanswered_groups()}


@app.get("/admin/leads")
def leads(request: Request) -> dict:
    enforce_admin(request)
    return {"leads": db.list_leads()}
