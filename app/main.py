"""FastAPI routes for chat, leads, feedback, admin, and health."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import db
from app.config import ROOT, get_settings
from app.diagnostics import log_turn
from app.generate import generate_checked
from app.verify import premise_correction
from app.llm import LLMError, llm_calls, start_llm_log, warm_http
from app.retrieve import get_retriever
from app.router import resolve
from app.security import enforce_admin, enforce_rate_limit
from app.templates import (
    booking,
    fallback,
    friendly_error,
    greeting,
    medical_advice,
    out_of_scope,
    unavailable,
)
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


def _cited_ids(draft: dict) -> set[str]:
    cited: set[str] = set()
    for claim in draft.get("claims") or []:
        for chunk_id in claim.get("chunk_ids") or []:
            cited.add(str(chunk_id))
    return cited


def _sources(hits: list[dict], cited: set[str], premise_url: str = "") -> list[dict]:
    seen: set[str] = set()
    sources = []
    for hit in hits:
        if hit["chunk_id"] not in cited or hit["url"] in seen:
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
    if premise_url and premise_url not in seen:
        sources.append(
            {
                "url": premise_url,
                "title": "Listed price",
                "section": "Listed price",
                "snippet": "",
            }
        )
    return sources


def _clinic_names() -> list[str]:
    records = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    names = {record.get("clinic") or "" for record in records}
    names.add("ITC Immunity Therapy Center")
    return [name for name in names if name]


def _blob(query: str, history: list[Turn]) -> str:
    parts = [query]
    parts.extend(turn.content for turn in history)
    return " ".join(parts).lower()


def _treatment(query: str, entities: dict, history: list[Turn]) -> str:
    if entities.get("treatment"):
        return entities["treatment"]
    lowered = _blob(query, history)
    for needle, name in _TREATMENTS:
        if needle in lowered:
            return name
    return ""


def _clinic(query: str, entities: dict, history: list[Turn]) -> str:
    if entities.get("clinic"):
        return str(entities["clinic"])
    lowered = _blob(query, history)
    if "itc" in lowered or "immunity therapy" in lowered:
        return "ITC Immunity Therapy Center"
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
    from ingest.build_index import configure_threads

    configure_threads()
    get_retriever().warm()
    warm_http()


@app.get("/health")
def health() -> dict:
    return _index_status()


@app.get("/")
def index():
    page = ROOT / "web" / "index.html"
    if page.exists():
        return FileResponse(page)
    return {"status": "ok", "message": "Chat UI is not built yet."}


def _finish(
    *,
    body: ChatRequest,
    answer: str,
    sources: list[dict],
    intent: str,
    answer_status: str,
    grounded: bool,
    language: str,
    rewritten: str,
    hits: list[dict],
    verifier_status: str,
    verifier_reason: str,
    timings: dict,
    started: float,
    show_disclaimer: bool,
    raw_llm,
    cache: bool = False,
    retries: list[str] | None = None,
) -> dict:
    latency_ms = int((time.perf_counter() - started) * 1000)
    timings["total_ms"] = latency_ms
    calls = [] if cache else llm_calls()
    is_fallback = answer.startswith("I couldn't find that") or verifier_status not in {"pass", "template", "premise"}
    if is_fallback and verifier_status != "error":
        _trace(
            {
                "question": body.message,
                "rewritten": rewritten,
                "intent": intent,
                "timings": timings,
                "verifier_reason": verifier_reason or verifier_status,
                "raw_llm": raw_llm,
                "fallback": True,
            }
        )
    logger.info("chat timings %s calls %s", json.dumps(timings), json.dumps(calls))
    log_id = db.log_chat(
        session_id=body.session_id,
        question=body.message,
        language=language,
        intent=intent,
        rewritten_query=rewritten,
        top_chunk_ids=",".join(hit["chunk_id"] for hit in hits[:5]),
        rerank_top_score=hits[0]["score"] if hits else None,
        answer=answer,
        grounded=grounded,
        verifier_status=verifier_status,
        latency_ms=latency_ms,
    )
    if not cache:
        db.log_llm_calls(log_id, calls)
    payload = {
        "answer": answer,
        "sources": sources,
        "intent": intent,
        "answer_status": answer_status,
        "grounded": grounded,
        "language": language,
        "show_disclaimer": show_disclaimer,
        "offer_lead_form": intent in {"price", "comparison", "lead"},
        "log_id": log_id,
        "debug": {
            "timings": timings,
            "verifier_reason": verifier_reason,
            "verifier_status": verifier_status,
            "llm_calls": calls,
            "cache": cache,
            "retries": retries or [],
            "top_chunks": timings.get("top_chunks") or [],
        },
    }
    return payload


@app.post("/api/chat")
def chat(body: ChatRequest, request: Request) -> dict:
    enforce_rate_limit(request)
    if db.questions_today() >= db.DAILY_QUESTION_CAP:
        raise HTTPException(status_code=429, detail="Daily question limit reached")
    started = time.perf_counter()
    history = [turn.model_dump() for turn in body.history][-6:]
    key = db.cache_key(body.message, history)
    cached = None if body.session_id.startswith("eval-") else db.get_cached_answer(key)
    if cached:
        cached_debug = dict(cached.get("debug") or {})
        cached_debug["cache"] = True
        cached["debug"] = cached_debug
        db.log_chat(
            session_id=body.session_id,
            question=body.message,
            language=cached.get("language"),
            intent=cached.get("intent"),
            rewritten_query="",
            top_chunk_ids="",
            rerank_top_score=None,
            answer=cached.get("answer"),
            grounded=bool(cached.get("grounded")),
            verifier_status="cache",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return cached
    start_llm_log()
    timings: dict[str, int] = {}
    try:
        routed, rewritten_obj = resolve(body.message, history)
    except (LLMError, ValueError, TypeError) as exc:
        return _finish(
            body=body,
            answer=unavailable(),
            sources=[],
            intent="info",
            answer_status="",
            grounded=False,
            language="en",
            rewritten=body.message,
            hits=[],
            verifier_status="error",
            verifier_reason=str(exc)[:300],
            timings=timings,
            started=started,
            show_disclaimer=False,
            raw_llm=None,
        )
    router_call = next((call for call in reversed(llm_calls()) if call.get("stage") == "router"), None)
    if router_call:
        timings["router_ms"] = int(router_call.get("latency_ms") or 0)
        timings["rewrite_ms"] = timings["router_ms"]
    language = rewritten_obj["language"]
    rewritten = rewritten_obj["standalone_query_en"]
    entities: dict = rewritten_obj["entities"]
    hits: list[dict] = []
    verifier_status = "template"
    grounded = True
    answer_status = "full"
    raw_llm = None
    verifier_reason = ""
    cited: set[str] = set()
    premise_url = ""
    retries: list[str] = []
    if routed.intent == "greeting":
        answer = greeting()
    elif routed.intent == "booking":
        answer = booking()
    elif routed.intent == "out_of_scope":
        answer = out_of_scope()
        grounded = False
        answer_status = ""
    elif routed.intent == "medical_advice":
        answer = medical_advice()
    else:
        try:
            result = get_retriever().search(rewritten, intent=routed.intent, entities=entities)
            timings.update(result.timings)
            hits = [hit.__dict__ for hit in result.hits]
            topic = _treatment(rewritten, entities, body.history)
            clinic_name = _clinic(rewritten, entities, body.history)
            correction = None
            if routed.user_numbers:
                pool = [
                    record for record in get_retriever().price_records if record.get("answerable", True)
                ]
                correction = premise_correction(routed.user_numbers, pool, topic, clinic_name)
            if correction:
                answer, premise_url = correction
                answer_status = "partial"
                grounded = True
                verifier_status = "premise"
            elif result.below_threshold or not hits:
                answer = medical_advice() if routed.intent == "medical_advice" else fallback()
                grounded = routed.intent == "medical_advice"
                answer_status = "full" if routed.intent == "medical_advice" else ""
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
                    treatment=topic,
                    clinic=clinic_name,
                    clinic_names=_clinic_names(),
                )
                timings.update(stage_timings)
                retries = list(stage_timings.get("retries") or [])
                premise_url = str(draft.get("premise_url") or "")
                raw_llm = [item.get("raw") for item in attempts]
                verifier_reason = attempts[-1].get("verifier_reason") or ""
                answer = draft["answer"]
                answer_status = str(draft.get("answer_status") or "")
                grounded = answer_status in {"full", "partial", "not_listed"}
                cited = _cited_ids(draft)
            if routed.intent == "medical_advice":
                advice = medical_advice()
                rest = answer
                while rest.startswith(advice):
                    rest = rest[len(advice) :].strip()
                if not rest or rest == fallback():
                    answer = advice
                    cited = set()
                    answer_status = "full"
                else:
                    answer = f"{advice} {rest}"
                grounded = True
        except LLMError as exc:
            answer = unavailable()
            grounded = False
            answer_status = ""
            verifier_status = "error"
            verifier_reason = str(exc)[:300]
        except Exception as exc:
            logger.exception("chat failed")
            answer = friendly_error()
            grounded = False
            answer_status = ""
            verifier_status = "error"
            verifier_reason = f"{type(exc).__name__}: {exc}"[:300]
    show_disclaimer = False
    if routed.intent in {"price", "comparison", "info", "medical_advice"} and grounded:
        show_disclaimer = db.claim_disclaimer(body.session_id)
    payload = _finish(
        body=body,
        answer=answer,
        sources=_sources(hits, cited, premise_url),
        intent=routed.intent,
        answer_status=answer_status,
        grounded=grounded,
        language=language,
        rewritten=rewritten,
        hits=hits,
        verifier_status=verifier_status,
        verifier_reason=verifier_reason,
        timings=timings,
        started=started,
        show_disclaimer=show_disclaimer,
        raw_llm=raw_llm,
        retries=retries,
    )
    if verifier_status in {"pass", "template", "premise"} and not body.session_id.startswith("eval-"):
        db.save_cached_answer(key, payload)
    return payload


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(body: ChatRequest, request: Request):
    def events():
        yield _sse({"type": "status", "text": "Checking sources..."})
        yield _sse({"type": "answer", "payload": chat(body, request)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
