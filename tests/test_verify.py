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
        "answer_status": "full" if grounded else "",
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


def test_missing_status_is_rejected():
    draft = _draft("The out-patient program is $18,995.")
    draft["answer_status"] = ""
    ok, reason = verify(draft, [CHUNK], [PRICE], clinic_names=CLINICS)
    assert ok is False
    assert "answer_status" in reason


def test_small_integer_from_any_retrieved_chunk():
    cited = {"chunk_id": "package_7903:4:0", "text": "Out-Patient Program | $18,995"}
    other = {"chunk_id": "package_7903:9:0", "text": "The program length is three weeks."}
    ok, reason = verify(
        _draft("The out-patient program is $18,995 for 3 weeks."),
        [cited, other],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is True
    assert reason == ""


def test_unknown_price_id_does_not_fail():
    draft = _draft("The out-patient program is $18,995 for 3 weeks.")
    draft["used_price_ids"] = ["not-a-real-id"]
    ok, reason = verify(draft, [CHUNK], [PRICE], clinic_names=CLINICS)
    assert ok is True
    assert reason == ""


def test_premise_rejects_fifty_dollars():
    result = premise_correction(
        ["$50"],
        [PRICE],
        "Alternative Adenocarcinoma Cancer Treatment",
    )
    assert result is not None
    correction, _url = result
    assert correction.startswith("I can't confirm that.")
    assert "$18,995 USD (starting from)" in correction
    assert "listed program" not in correction
    assert premise_ok("Yes, it costs $50.", correction) is False
    assert premise_ok(correction + " The page lists the out-patient program.", correction) is True


def test_premise_without_topic_uses_starting_price():
    starting = {
        "id": "p_profile_starting",
        "category": "package_starting_from",
        "price_low": 18995,
        "price_high": 18995,
        "currency": "USD",
        "qualifier": "starting from",
        "program": "",
        "treatment": "Alternative Cancer Treatment",
        "clinic": "ITC Immunity Therapy Center",
        "url": "https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
        "answerable": True,
    }
    correction, url = premise_correction(["$50"], [PRICE, starting], "", "")
    assert "does not match any listed ITC package price" in correction
    assert "$18,995 USD (starting from)" in correction
    assert "profile/5" in url
    assert "the listed program" not in correction
