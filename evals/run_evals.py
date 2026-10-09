"""Run golden questions against the local API and write test_results.md."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import yaml

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


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


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


def main() -> None:
    cases = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    rows = []
    latencies = []
    with httpx.Client(timeout=180) as client:
        for case in cases:
            started = time.perf_counter()
            response = client.post(
                f"{API}/api/chat",
                json={
                    "session_id": f"eval-{case['id']}",
                    "message": case["question"],
                    "history": case.get("history") or [],
                },
            )
            latency_ms = (time.perf_counter() - started) * 1000
            latencies.append(latency_ms)
            payload = response.json()
            passed, reasons = check(case, payload)
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
                }
            )
            print(f"{'PASS' if passed else 'FAIL'} {case['id']} {latency_ms:.0f}ms {reasons}")
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
