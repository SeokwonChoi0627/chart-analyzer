from core.market_sentiment import _brief_from_closes


def _uptrend(n=60):
    return [1000 + i * 10 for i in range(n)]


def _downtrend(n=60):
    return [2000 - i * 10 for i in range(n)]


def test_uptrend_above_sma20():
    brief = _brief_from_closes(_uptrend())
    assert brief is not None
    assert brief["above_sma20"] is True
    assert "20일선 위" in brief["note"]


def test_downtrend_below_sma20():
    brief = _brief_from_closes(_downtrend())
    assert brief["above_sma20"] is False
    assert "20일선 아래" in brief["note"]


def test_change_pct_computed_from_last_two_closes():
    closes = [100.0] * 59 + [102.0]
    brief = _brief_from_closes(closes)
    assert brief["change_pct"] == 2.0


def test_value_is_last_close():
    brief = _brief_from_closes(_uptrend())
    assert brief["value"] == 1590  # 1000 + 59×10


def test_pullback_in_uptrend_notes_breather():
    """20일선 위인데 최근 5일 하락 — 숨고르기."""
    closes = [1000 + i * 10 for i in range(55)] + [1540 - i * 2 for i in range(5)]
    brief = _brief_from_closes(closes)
    assert brief["above_sma20"] is True
    assert "숨고르기" in brief["note"]


def test_rebound_in_downtrend_notes_attempt():
    """20일선 아래인데 최근 5일 상승 — 반등 시도."""
    closes = [2000 - i * 10 for i in range(55)] + [1460 + i * 2 for i in range(5)]
    brief = _brief_from_closes(closes)
    assert brief["above_sma20"] is False
    assert "반등 시도" in brief["note"]


def test_insufficient_data_returns_none():
    assert _brief_from_closes([100.0] * 10) is None
    assert _brief_from_closes([]) is None
