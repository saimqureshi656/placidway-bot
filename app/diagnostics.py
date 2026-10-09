"""Per-request stage timings and fallback details. No secrets."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import ROOT

LOG_PATH = ROOT / "data" / "diagnostics.jsonl"


def log_turn(record: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
