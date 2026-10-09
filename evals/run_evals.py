"""Run golden questions against the local API and write test_results.md."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

from app.normalize import extract_numbers

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).parent / "golden.yaml"
RESULTS = ROOT / "test_results.md"
API = os.environ.get("EVAL_URL", "http://127.0.0.1:8000")
REQUIRED = [
    "q1-cost",
    "q2-ozone",
    "q2b-thailand",
    "q3-included",
    "q4-recovery",
    "q5-booking",
    "q6-weather",
    "q7-diabetes",
    "q8-premise",
]


_NUMBER_ONLY = re.compile(r"^[\d,.\s$]+(?:usd|dollars)?$", re.IGNORECASE)
PRIOR_HISTORY = {"q4-recovery": "q3-included", "q8-premise": "q1-cost"}


def _contains(text: str, needle: str) -> bool:
    if _NUMBER_ONLY.match(needle.strip()):
        wanted = extract_numbers(needle)
        if wanted:
            return set(wanted) <= set(extract_numbers(text))
    return needle.lower() in text.lower()


def _history(case: dict, produced: dict[str, dict]) -> list[dict]:
    prior_id = PRIOR_HISTORY.get(case["id"])
    if prior_id and prior_id in produced:
        prior = produced[prior_id]
        return [
            {"role": "user", "content": prior["question"]},
            {"role": "assistant", "content": prior["answer"]},
        ]
    return list(case.get("history") or [])


def check(case: dict, payload: dict) -> tuple[bool, list[str]]:
    expect = case["expect"]
    answer = payload.get("answer") or ""
    reasons = []
    if payload.get("intent") != expect["intent"]:
        reasons.append(f"intent {payload.get('intent')} != {expect['intent']}")
    if "grounded" in expect and bool(payload.get("grounded")) != bool(expect["grounded"]):
        reasons.append(f"grounded {payload.get('grounded')} != {expect['grounded']}")
    for needle in expect.get("must_contain") or []:
        if not _contains(answer, needle):
            reasons.append(f"missing {needle}")
    for needle in expect.get("must_not_contain") or []:
        if needle and _contains(answer, needle):
            reasons.append(f"forbidden {needle}")
    urls = " ".join(source.get("url") or "" for source in payload.get("sources") or [])
    for needle in expect.get("must_cite") or []:
        if needle not in urls:
            reasons.append(f"missing cite {needle}")
    return not reasons, reasons


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _provider_error(payload: dict) -> str:
    debug = payload.get("debug") or {}
    if debug.get("verifier_status") == "error":
        return str(debug.get("verifier_reason") or "provider error")
    for call in debug.get("llm_calls") or []:
        if call.get("error"):
            return f"{call.get('provider')} {call.get('model')}: {call.get('error')}"
    answer = payload.get("answer") or ""
    if answer.startswith("I'm temporarily unavailable"):
        return answer
    return ""


def _format_calls(payload: dict) -> str:
    calls = (payload.get("debug") or {}).get("llm_calls") or []
    if not calls:
        return "none"
    parts = []
    for call in calls:
        parts.append(
            f"{call.get('stage')} {call.get('provider')}/{call.get('model')} "
            f"in={call.get('tokens_in')} out={call.get('tokens_out')} {call.get('latency_ms')}ms"
            + (f" error={call.get('error')}" if call.get("error") else "")
        )
    return "; ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required", action="store_true", help="Run only the 9 required questions")
    args = parser.parse_args()
    cases = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    if args.required:
        cases = [case for case in cases if case["id"] in REQUIRED]
        cases.sort(key=lambda case: REQUIRED.index(case["id"]))
    rows = []
    latencies = []
    produced: dict[str, dict] = {}
    gap_seconds = 13 if args.required else 25
    with httpx.Client(timeout=180) as client:
        for index, case in enumerate(cases):
            started = time.perf_counter()
            response = client.post(
                f"{API}/api/chat",
                json={
                    "session_id": f"eval-{case['id']}",
                    "message": case["question"],
                    "history": _history(case, produced),
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            latencies.append(latency_ms)
            if response.status_code >= 400:
                print(f"ABORT {case['id']} HTTP {response.status_code}: {response.text[:500]}")
                sys.exit(1)
            payload = response.json()
            provider_error = _provider_error(payload)
            if provider_error:
                print(f"ABORT {case['id']} provider error: {provider_error}")
                print(_format_calls(payload))
                sys.exit(1)
            passed, reasons = check(case, payload)
            produced[case["id"]] = {
                "id": case["id"],
                "question": case["question"],
                "answer": payload.get("answer") or "",
            }
            rows.append(
                {
                    "id": case["id"],
                    "category": case.get("category", ""),
                    "question": case["question"],
                    "answer": payload.get("answer") or "",
                    "sources": payload.get("sources") or [],
                    "intent": payload.get("intent"),
                    "passed": passed,
                    "reasons": reasons,
                    "latency_ms": latency_ms,
                    "calls": _format_calls(payload),
                    "timings": (payload.get("debug") or {}).get("timings") or {},
                }
            )
            debug = payload.get("debug") or {}
            if not passed:
                print(
                    f"FAIL {case['id']} {latency_ms:.0f}ms {reasons} "
                    f"status={debug.get('verifier_status')} reason={debug.get('verifier_reason')} "
                    f"timings={debug.get('timings')}"
                )
            else:
                print(
                    f"PASS {case['id']} {latency_ms:.0f}ms timings={debug.get('timings')} "
                    f"calls={_format_calls(payload)}"
                )
            if index < len(cases) - 1:
                time.sleep(gap_seconds)
    by_category: dict[str, list[bool]] = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row["passed"])
    required_rows = [row for row in rows if row["id"] in REQUIRED]
    required_rows.sort(key=lambda row: REQUIRED.index(row["id"]))
    lines = [
        "# Test results",
        "",
        f"Pass rate: {sum(row['passed'] for row in rows)}/{len(rows)}.",
        f"Latency p50 {percentile(latencies, 0.50):.0f} ms, p95 {percentile(latencies, 0.95):.0f} ms.",
        "",
        "## Required questions",
        "",
    ]
    for row in required_rows:
        lines.append(f"### {row['id']}: {row['question']}")
        lines.append("")
        lines.append(row["answer"])
        lines.append("")
        lines.append("Sources:")
        if row["sources"]:
            for source in row["sources"]:
                lines.append(f"- {source.get('section')}: {source.get('url')}")
        else:
            lines.append("- none")
        lines.append("")
        lines.append(f"Result: {'pass' if row['passed'] else 'fail'}")
        if row["reasons"]:
            lines.append("Reasons: " + "; ".join(row["reasons"]))
        lines.append(f"Models: {row.get('calls') or 'none'}")
        timings = row.get("timings") or {}
        if timings:
            lines.append("Stage ms: " + ", ".join(f"{name}={value}" for name, value in timings.items()))
        lines.append("")
    lines.extend(["## Pass rate by category", ""])
    for category, flags in by_category.items():
        lines.append(f"- {category}: {sum(flags)}/{len(flags)}")
    lines.extend(["", "## All cases", "", "| id | pass | intent | latency ms |", "|---|---|---|---|"])
    for row in rows:
        lines.append(
            f"| {row['id']} | {'pass' if row['passed'] else 'fail'} | {row['intent']} | {row['latency_ms']:.0f} |"
        )
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
