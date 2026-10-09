from app.normalize import extract_numbers, parse_amount


def test_dollar_with_comma():
    assert parse_amount("$18,995") == 18995
    assert 18995 in extract_numbers("The program is $18,995 for 3 weeks.")


def test_usd_suffix():
    assert parse_amount("18995 USD") == 18995
    assert 18995 in extract_numbers("Listed as 18995 USD.")


def test_dot_thousands():
    assert parse_amount("18.995") == 18995
    assert 18995 in extract_numbers("Precio 18.995")


def test_arabic_digits():
    assert parse_amount("١٨٬٩٩٥") == 18995
    assert 18995 in extract_numbers("السعر ١٨٩٩٥ دولار")


def test_us_dollar_and_thousands_word():
    assert parse_amount("US$30,000") == 30000
    assert parse_amount("30k") == 30000
