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


# Entity-price binding and grounding gaps

from app.verify import (  # noqa: E402
    attribution_reason,
    composite_reason,
    destination_gap,
    exclusion_reason,
    price_binding_reason,
    tidy_spacing,
    unpriced_terms,
)

PROFILE_LINE = {
    "chunk_id": "clinic_profile:6:0",
    "text": "Base Package Price: $18,995 | Cancer Types Treated at ITC: Prostate Cancer Liver & Kidney Cancer",
}
CENTER_DETAILS = {
    "chunk_id": "price_list:7:0",
    "text": "- Price Range: $18995 - $18995\n- Packages: Alternative Appendix Cancer Treatment Package in Tijuana",
}
CATALOG = [
    {**PRICE, "id": "p_7903_inpatient", "category": "package_program", "program": "In-Patient Program",
     "duration": "3 Weeks", "price_low": 30000, "price_high": 30000, "qualifier": "", "url": "u7903"},
    {**PRICE, "id": "p_list_prostate_cancer", "category": "price_list_row", "treatment": "Prostate Cancer",
     "program": "", "qualifier": ""},
]


def test_unlisted_package_price_is_rejected():
    reason = price_binding_reason(
        "How much is the appendix cancer package?",
        "The appendix cancer package costs $18,995.",
        [CENTER_DETAILS],
        CATALOG,
    )
    assert "18995" in reason and "appendix" in reason
    assert unpriced_terms("How much is the appendix cancer package?", CATALOG, [CENTER_DETAILS]) == ["appendix"]


def test_profile_line_binds_liver_price():
    answer = "ITC lists Liver & Kidney Cancer among the cancers it treats. The profile's base package price is $18,995."
    assert price_binding_reason("Does ITC treat liver cancer and how much?", answer, [PROFILE_LINE], CATALOG) == ""
    assert unpriced_terms("liver cancer cost", CATALOG, [PROFILE_LINE]) == []


def test_programs_are_not_applied_to_other_cancers():
    reason = price_binding_reason(
        "Does ITC treat liver cancer and how much?",
        "The Out-Patient program is $18,995.",
        [PROFILE_LINE],
        CATALOG,
    )
    assert "Out-Patient and In-Patient" in reason
    reason = price_binding_reason(
        "What does ITC charge for prostate cancer?",
        "The price list shows Prostate Cancer at $18995. A 3-week stay is $30,000.",
        [PROFILE_LINE],
        CATALOG,
    )
    assert "30000" in reason
    ok = price_binding_reason(
        "What does ITC charge for prostate cancer?",
        "The ITC price list shows Prostate Cancer at $18995.",
        [PROFILE_LINE],
        CATALOG,
    )
    assert ok == ""


def test_program_price_binds_without_a_treatment():
    answer = "The In-Patient Program is $30,000. LAK is $2,600."
    assert price_binding_reason("Total for in-patient plus LAK?", answer, [], CATALOG) == ""
    assert price_binding_reason("in-patient price", "The In-Patient Program is $18,995.", [], CATALOG)


def test_composite_total_must_say_not_listed():
    query = "Total for in-patient plus LAK plus two specialist visits?"
    assert composite_reason(query, "In-Patient $30,000 and LAK $2,600, so $32,600 total.")
    assert composite_reason(query, "In-Patient $30,000, LAK $2,600. A combined total is not listed.") == ""


def test_not_stated_is_not_excluded():
    chunk = {"chunk_id": "clinic_profile:6:0", "text": "Standard Inclusions: Local transportation assistance"}
    assert exclusion_reason("Flights are not included in the price.", [chunk])
    assert exclusion_reason("Flights are not listed as included.", [chunk]) == ""
    excluded = {"chunk_id": "package_7903:8:0", "text": "Excluded Services: Ambulance transfers ($950)"}
    assert exclusion_reason("Ambulance transfers are not included.", [excluded]) == ""


def test_clinical_claims_are_attributed():
    assert attribution_reason("These therapies are safe with a colostomy.")
    assert attribution_reason("According to the clinic's page, the therapies can be used with a colostomy.") == ""


def test_premise_uses_the_program_asked_about():
    correction, url = premise_correction(["$25,000"], CATALOG, "", "", "In-Patient Program")
    assert correction.startswith("I can't confirm that.")
    assert "$30,000 USD" in correction and "3 Weeks" in correction
    assert url == "u7903"


def test_unlisted_destination():
    corpus = [
        {"text": "Clinic / Surgeon: Form Recovery & Wellness in Bangkok Thailand | Physiotherapy/Massage"},
        {"text": "Alternative cancer treatment in Tijuana, Mexico"},
    ]
    assert destination_gap("Is Thailand cheaper for cancer treatment?", corpus, []) == ("Thailand", "cancer treatment")
    assert destination_gap("Is cancer treatment cheaper in Mexico or Thailand?", corpus, []) is None


def test_no_space_before_punctuation():
    assert tidy_spacing("It costs $18,995 . Request a quote , please !") == "It costs $18,995. Request a quote, please!"


def test_unpriced_item_answer_quotes_no_price():
    chunk = {"chunk_id": "price_list:7:0", "text": "- Packages: Alternative Appendix Cancer Treatment Package"}
    draft = _draft("The price for the appendix cancer package is not listed. The adenocarcinoma package starts from $18,995.")
    draft["claims"] = [{"text": "x", "chunk_ids": ["1"]}]
    ok, reason = verify(
        draft, [chunk, CHUNK], [], clinic_names=CLINICS,
        query="How much is the appendix cancer package?", catalog=CATALOG + [PRICE], unpriced=["appendix"],
    )
    assert ok is False and "do not quote other prices" in reason


def test_vague_missing_wording_is_rejected():
    ok, reason = verify(
        _draft("The pages do not mention flights."), [CHUNK], [], clinic_names=CLINICS,
        query="Does the price include flights?",
    )
    assert ok is False and "is not listed" in reason
