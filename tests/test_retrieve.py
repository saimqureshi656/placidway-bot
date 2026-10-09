"""Retrieval checks for five known queries."""

import pytest

from app.retrieve import get_retriever


@pytest.fixture(scope="module")
def retriever():
    return get_retriever()


def test_adenocarcinoma_cost_ranks_package_7903(retriever):
    result = retriever.search("adenocarcinoma cost", intent="price")
    assert result.hits
    assert result.hits[0].chunk_id.startswith("package_7903")
    assert "adenocarcinoma" in result.hits[0].treatment.lower()


def test_adrenal_cost_ranks_package_7902(retriever):
    result = retriever.search("how much does adrenal cancer treatment cost")
    assert result.hits[0].chunk_id.startswith("package_7902")


def test_anal_cost_ranks_package_7901(retriever):
    result = retriever.search("anal cancer treatment cost in tijuana")
    assert result.hits[0].chunk_id.startswith("package_7901")


def test_ozone_turkey_returns_comparison_clinic_table(retriever):
    result = retriever.search("ozone therapy Turkey", intent="comparison")
    top = result.hits[0]
    assert top.page_type == "price_comparison"
    assert "which clinics" in top.section.lower()
    assert "turkey" in top.text.lower()
    assert "fizikon" in top.text.lower()


def test_inpatient_includes_cites_inpatient_section(retriever):
    result = retriever.search("what is included in the in-patient program")
    assert "included in the in-patient" in result.hits[0].section.lower()


def test_weather_and_dental_score_below_known_treatment(retriever):
    known = retriever.search("adenocarcinoma cost").best_score
    weather = retriever.search("weather in Cancun").best_score
    dental = retriever.search("dental implants Mexico").best_score
    assert weather < known
    assert dental < known
    assert weather < 0.5
    assert dental < 0.5
