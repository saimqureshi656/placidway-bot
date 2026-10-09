from app.verify import premise_correction, premise_ok, verify

CHUNK = {
    "chunk_id": "package_7903:4:0",
    "text": "Out-Patient Program | 3 Weeks | $18,995\nIn-Patient Program | 3 Weeks | $30,000",
}
PRICE = {
    "id": "p_7903_outpatient",
    "price_low": 18995,
    "price_high": 18995,
    "currency": "USD",
    "qualifier": "starting from",
    "program": "Out-Patient Program",
    "treatment": "Alternative Adenocarcinoma Cancer Treatment",
    "raw_text": "Out-Patient Program | 3 Weeks | $18,995",
    "answerable": True,
}
CLINICS = ["ITC Immunity Therapy Center"]


def _draft(answer: str, grounded: bool = True, price_ids: list[str] | None = None) -> dict:
    return {
        "answer": answer,
        "claims": [{"text": answer, "chunk_ids": ["package_7903:4:0"]}],
        "used_price_ids": price_ids if price_ids is not None else ["p_7903_outpatient"],
        "grounded": grounded,
    }


def test_fabricated_price_is_rejected():
    ok, reason = verify(
        _draft("The program costs $50."),
        [CHUNK],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is False
    assert "50" in reason


def test_listed_price_passes():
    ok, reason = verify(
        _draft("The out-patient program is $18,995 for 3 weeks at ITC Immunity Therapy Center."),
        [CHUNK],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is True
    assert reason == ""


def test_bad_url_is_rejected():
    ok, reason = verify(
        _draft("See https://evil.example/offer for the $18,995 program."),
        [CHUNK],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is False
    assert "url" in reason


def test_premise_rejects_fifty_dollars():
    correction = premise_correction(
        ["$50"],
        [PRICE],
        "Alternative Adenocarcinoma Cancer Treatment",
    )
    assert correction is not None
    assert correction.startswith("I can't confirm that.")
    assert premise_ok("Yes, it costs $50.", correction) is False
    assert premise_ok(correction + " The page lists the out-patient program.", correction) is True
