from app.router import is_followup, route


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
