"""Fixed replies. Edit the strings here."""

from app.config import get_settings


def quote_url() -> str:
    return get_settings().quote_url


def greeting() -> str:
    return (
        "Hello. I can answer questions about ITC Immunity Therapy Center in Tijuana "
        "from the PlacidWay pages I have: package costs, what a program includes, "
        "and how listed alternative-medicine prices compare."
    )


def booking() -> str:
    return (
        "I can't book appointments. "
        f"Request a free quote: {quote_url()}"
    )


def out_of_scope() -> str:
    return (
        "I can only answer from the ITC PlacidWay pages I have, such as package costs, "
        "what those programs include, and listed price comparisons. "
        f"Request a free quote: {quote_url()}"
    )


def medical_advice() -> str:
    return (
        "I can't tell you whether a treatment is safe for you or give a diagnosis. "
        "Please talk to your doctor. I can still share what the clinic's page says about the program."
    )


def fallback() -> str:
    return (
        "I couldn't find that in the PlacidWay pages I have. "
        f"Request a free quote: {quote_url()}"
    )


def price_not_listed(subject: str) -> str:
    return (
        f"The price for {subject} isn't listed on our pages. "
        f"Request a free quote: {quote_url()}"
    )


def destination_not_listed(country: str, subject: str, listed: str = "") -> str:
    text = f"{country} isn't listed for {subject} in the PlacidWay pages I have."
    if listed:
        text += f" {listed}"
    return f"{text} Request a free quote: {quote_url()}"


def unavailable() -> str:
    return (
        "I'm temporarily unavailable. Please try again in a moment. "
        f"Request a free quote: {quote_url()}"
    )


def friendly_error() -> str:
    return (
        "I'm having trouble right now, please try again. "
        f"Request a free quote: {quote_url()}"
    )


DISCLAIMER = (
    "This is general information from PlacidWay's pages, not medical advice. "
    "Please consult your doctor before making treatment decisions."
)
