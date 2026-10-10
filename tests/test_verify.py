from app.verify import premise_correction, premise_ok, unlisted_fact_reason, verify

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
        "claims": [{"text": answer, "chunk_ids": ["1"]}],
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
        _draft("The out-patient program is $18,995 starting from for 3 weeks at ITC Immunity Therapy Center."),
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
        _draft("The out-patient program is $18,995 starting from for 3 weeks."),
        [cited, other],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is True
    assert reason == ""


PROGRAM = {
    "chunk_id": "package_7903:4:0",
    "text": "Why is the treatment period three weeks? The program lasts three weeks and the follow-up is after three months.",
}


def test_recovery_program_length_is_rejected():
    reason = unlisted_fact_reason(
        "And what about recovery time?",
        "The recovery period is three weeks.",
        [PROGRAM],
    )
    assert "not listed" in reason or "program length" in reason
    ok, verify_reason = verify(
        _draft("The recovery period is three weeks."),
        [PROGRAM],
        [PRICE],
        clinic_names=CLINICS,
        query="And what about recovery time?",
    )
    assert ok is False
    assert "recovery" in verify_reason


def test_recovery_not_listed_passes():
    answer = (
        "Recovery time is not listed. The listed program duration is 3 weeks "
        "and a follow-up consultation is listed after 3 months."
    )
    assert unlisted_fact_reason("What is the recovery time?", answer, [PROGRAM]) == ""
    ok, reason = verify(
        _draft(answer),
        [PROGRAM],
        [PRICE],
        clinic_names=CLINICS,
        query="What is the recovery time?",
    )
    assert ok is True
    assert reason == ""


def test_success_rate_must_not_be_inferred():
    chunk = {"chunk_id": "package_7903:1:0", "text": "The program includes lab work and meals."}
    inferred = unlisted_fact_reason(
        "What is the success rate?",
        "The success rate is 80 percent.",
        [chunk],
    )
    assert inferred
    stated = unlisted_fact_reason(
        "What is the success rate?",
        "The success rate is not listed.",
        [chunk],
    )
    assert stated == ""


def test_rectal_cancer_price_must_say_not_listed():
    chunk = {"chunk_id": "package_7901:1:0", "text": "Anal cancer treatment starts from $18,995."}
    missing = unlisted_fact_reason(
        "How much does rectal cancer treatment cost?",
        "Rectal cancer treatment starts from $18,995.",
        [chunk],
    )
    assert missing == "rectal cancer is not listed"
    stated = unlisted_fact_reason(
        "How much does rectal cancer treatment cost?",
        "Rectal cancer treatment is not listed.",
        [chunk],
    )
    assert stated == ""


def test_citation_marker_does_not_fail_number_check():
    ok, reason = verify(
        _draft("The out-patient program is $18,995 starting from [2]."),
        [CHUNK],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is True
    assert reason == ""


def test_displayed_answer_drops_citation_marker():
    draft = _draft("The out-patient program is $18,995 starting from [2].")
    ok, reason = verify(draft, [CHUNK], [PRICE], clinic_names=CLINICS)
    assert ok is True
    assert reason == ""
    assert "[2]" not in draft["answer"]
    assert "18,995" in draft["answer"]


def test_spanish_qualifiers_count_as_starting_from():
    for phrase in ("desde", "a partir de", "comienza en"):
        ok, reason = verify(
            _draft(f"El programa ambulatorio cuesta $18,995 {phrase} por 3 semanas."),
            [CHUNK],
            [PRICE],
            clinic_names=CLINICS,
        )
        assert ok is True, phrase
        assert reason == ""


def test_arabic_qualifiers_count_as_starting_from():
    for phrase in ("يبدأ من", "تبدأ من", "ابتداءً من"):
        ok, reason = verify(
            _draft(f"البرنامج الخارجي {phrase} $18,995 لمدة 3 أسابيع."),
            [CHUNK],
            [PRICE],
            clinic_names=CLINICS,
        )
        assert ok is True, phrase
        assert reason == ""


def test_spanish_and_arabic_approximate_qualifiers():
    price = {
        **PRICE,
        "price_low": 200,
        "price_high": 200,
        "qualifier": "approximately",
        "raw_text": "Specialist consultations approximately $200",
    }
    chunk = {"chunk_id": "package_7903:8:0", "text": "Specialist consultations approximately $200"}
    for phrase in ("aproximadamente", "حوالي", "تقريبا"):
        ok, reason = verify(
            _draft(f"Specialist consultations {phrase} $200."),
            [chunk],
            [price],
            clinic_names=CLINICS,
        )
        assert ok is True, phrase
        assert reason == ""


def test_cost_question_must_include_every_program_price():
    programs = [
        {
            **PRICE,
            "qualifier": "",
            "category": "package_program",
            "program": "Out-Patient Program",
            "duration": "3 Weeks",
        },
        {
            **PRICE,
            "id": "p_7903_inpatient",
            "price_low": 30000,
            "price_high": 30000,
            "qualifier": "",
            "category": "package_program",
            "program": "In-Patient Program",
            "duration": "3 Weeks",
            "raw_text": "In-Patient Program | 3 Weeks | $30,000",
        },
    ]
    missing, reason = verify(
        _draft("The out-patient program is $18,995 for 3 weeks."),
        [CHUNK],
        programs,
        clinic_names=CLINICS,
        query="How much does adenocarcinoma treatment cost?",
    )
    assert missing is False
    assert "In-Patient" in reason
    ok, reason = verify(
        _draft(
            "Out-Patient is $18,995 for 3 weeks and In-Patient is $30,000 for 3 weeks."
        ),
        [CHUNK],
        programs,
        clinic_names=CLINICS,
        query="How much does adenocarcinoma treatment cost?",
    )
    assert ok is True
    assert reason == ""


def test_cited_price_record_is_recorded():
    draft = _draft("The out-patient program is $18,995 starting from.")
    draft["claims"] = [{"text": "price", "chunk_ids": ["P1", "1"]}]
    ok, reason = verify(draft, [CHUNK], [PRICE], clinic_names=CLINICS)
    assert ok is True
    assert reason == ""
    assert draft["cited_price_indexes"] == [0]


def test_missing_qualifier_is_rejected():
    ok, reason = verify(
        _draft("The out-patient program is $18,995 for 3 weeks."),
        [CHUNK],
        [PRICE],
        clinic_names=CLINICS,
    )
    assert ok is False
    assert "starting from" in reason


def test_invalid_passage_number_is_rejected():
    draft = _draft("The out-patient program is $18,995 for 3 weeks.")
    draft["claims"] = [{"text": "price", "chunk_ids": ["9"]}]
    ok, reason = verify(draft, [CHUNK], [PRICE], clinic_names=CLINICS)
    assert ok is False
    assert "invalid citation" in reason


def test_unknown_price_id_does_not_fail():
    draft = _draft("The out-patient program is $18,995 starting from for 3 weeks.")
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
