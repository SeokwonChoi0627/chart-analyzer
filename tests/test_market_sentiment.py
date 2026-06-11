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


def test_explicit_prev_close_fixes_missing_bar_gap():
    """어제 봉이 결손(None 필터)이어도 공식 전일 종가로 정확한 등락률.

    실사례: KOSPI 06-10 봉 None → closes[-2]가 그저께(8096.93)로 밀려
    -4.11%로 오계산. 실제 전일 종가 7730.7 기준 +0.43%가 맞다.
    """
    closes = [8000.0] * 58 + [8096.93, 7763.95]
    brief = _brief_from_closes(closes, prev_close=7730.7)
    assert brief["change_pct"] == 0.43


def test_explicit_value_overrides_last_close():
    brief = _brief_from_closes([100.0] * 60, value=105.0, prev_close=100.0)
    assert brief["value"] == 105.0
    assert brief["change_pct"] == 5.0


def test_without_explicit_args_falls_back_to_closes():
    closes = [100.0] * 59 + [102.0]
    assert _brief_from_closes(closes)["change_pct"] == 2.0
