import re

from app.db import cache_key
from app.generate import finish_clinical_answer
from app.security import client_ip
from app.templates import medical_advice


def test_cache_key_includes_version():
    history = [{"role": "user", "content": "How much does it cost?"}]
    first = cache_key("How much?", history, version="aaa")
    second = cache_key("How much?", history, version="bbb")
    assert first != second


def test_clinical_answer_leads_with_the_page_and_drops_the_template():
    raw = (
        medical_advice()
        + " According to the clinic's page, the therapies are safe and effective with a colostomy. "
        + "They are safe and effective."
    )
    text = finish_clinical_answer(raw)
    assert text.startswith("According to the clinic's page")
    assert text.endswith("Please discuss this with your doctor.")
    assert "I can't tell you whether a treatment is safe" not in text
    assert len(re.findall(r"safe and effective", text, flags=re.IGNORECASE)) == 1
    assert "colostomy" in text


class _Client:
    def __init__(self, host: str) -> None:
        self.host = host


class _Request:
    def __init__(self, host: str, forwarded: str = "") -> None:
        self.client = _Client(host)
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_rate_limit_uses_forwarded_client_behind_local_proxy():
    request = _Request("127.0.0.1", "203.0.113.8, 10.0.0.2")
    assert client_ip(request) == "203.0.113.8"
    assert client_ip(_Request("198.51.100.4", "203.0.113.8")) == "198.51.100.4"
