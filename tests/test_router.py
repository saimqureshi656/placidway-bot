from app.llm import TokenBucket
from app.router import choose_intent, is_followup, route


def test_followup_is_rewritten_before_rules():
    assert is_followup("And what about recovery time?", [{"role": "user", "content": "cost"}]) is True
    assert is_followup("And what about recovery time?", []) is False
    assert is_followup("I heard it costs $50. Confirm that.", [{"role": "user", "content": "cost"}]) is True


def test_booking_uses_template_intent():
    result = route("Can you book me an appointment for tomorrow?")
    assert result.intent == "booking"
    assert result.method == "rule"


def test_weather_is_out_of_scope():
    result = route("What is the weather in Cancun?")
    assert result.intent == "out_of_scope"


def test_medical_advice_for_diabetes():
    result = route("Is this surgery safe for my diabetes?")
    assert result.intent == "medical_advice"


def test_price_premise_keeps_the_number():
    result = route("I heard it costs $50. Confirm that.")
    assert result.intent == "price"
    assert any("50" in number for number in result.user_numbers)


def test_ozone_comparison():
    result = route("Is ozone therapy cheaper in Turkey or Mexico?")
    assert result.intent == "comparison"


def test_cure_is_medical_advice():
    assert route("Will this cure my cancer?").intent == "medical_advice"
    assert route("What is the success rate?").intent == "medical_advice"
    assert route("Is it effective for me?").intent == "medical_advice"


def test_safety_intent_wins_a_disagreement():
    assert choose_intent("price", "medical_advice") == "medical_advice"
    assert choose_intent("info", "booking") == "booking"
    assert choose_intent("price", "out_of_scope") == "out_of_scope"
    assert choose_intent("medical_advice", "booking") == "medical_advice"
    assert choose_intent("price", "info") == "info"


def test_gen_bucket_skips_when_empty():
    bucket = TokenBucket(rate=1, per_seconds=60)
    assert bucket.take() is True
    assert bucket.take() is False
