"""Settings loaded from .env. Secrets stay out of logs and source."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def _read_env(path: Path = ENV_PATH) -> dict[str, str]:
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


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    groq_api_key: str
    groq_model: str
    cerebras_api_key: str
    cerebras_model: str
    router_model: str
    gen_model: str
    gen_fallback_model: str
    rerank_threshold: float
    top_k: int
    admin_token: str
    quote_url: str
    db_path: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = _read_env()
    return Settings(
        llm_provider=env.get("LLM_PROVIDER", "groq"),
        groq_api_key=env.get("GROQ_API_KEY", ""),
        groq_model=env.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        cerebras_api_key=env.get("CEREBRAS_API_KEY") or env.get("CEREBRA_API_KEY", ""),
        cerebras_model=env.get("CEREBRAS_MODEL", ""),
        router_model=env.get("ROUTER_MODEL", "qwen-3.8-27b"),
        gen_model=env.get("GEN_MODEL", "gpt-oss-120b"),
        gen_fallback_model=env.get("GEN_FALLBACK_MODEL", "qwen-3.8-27b"),
        rerank_threshold=float(env.get("RERANK_THRESHOLD", "0.005")),
        top_k=int(env.get("TOP_K", "5")),
        admin_token=env.get("ADMIN_TOKEN", ""),
        quote_url=env.get("QUOTE_URL", "https://www.placidway.com/request-info"),
        db_path=env.get("DB_PATH", "data/app.db"),
    )
