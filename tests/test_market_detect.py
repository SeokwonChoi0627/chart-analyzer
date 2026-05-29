from core.data.base import detect_market


def test_korean_6digit_code():
    assert detect_market("005930") == "KR"


def test_korean_hangul_name():
    assert detect_market("삼성전자") == "KR"


def test_us_ticker_uppercase():
    assert detect_market("AAPL") == "US"


def test_us_ticker_lowercase_normalized():
    assert detect_market("aapl") == "US"


def test_strips_whitespace():
    assert detect_market("  005930  ") == "KR"
