from core.context import sentiment_context, valuation_warning


# ── sentiment_context ─────────────────────────────────────────────────────────

def test_extreme_fear_with_buy_signal_is_contrarian_positive():
    ctx = sentiment_context(fg_score=20, daily_score=3.0)
    assert ctx is not None
    assert ctx["level"] == "기회"
    assert "공포" in ctx["message"]


def test_extreme_greed_with_buy_signal_warns_chasing():
    ctx = sentiment_context(fg_score=80, daily_score=3.0)
    assert ctx is not None
    assert ctx["level"] == "주의"
    assert "탐욕" in ctx["message"]


def test_extreme_fear_with_sell_signal_warns_panic():
    ctx = sentiment_context(fg_score=20, daily_score=-3.0)
    assert ctx is not None
    assert ctx["level"] == "주의"


def test_neutral_sentiment_returns_none():
    assert sentiment_context(fg_score=50, daily_score=3.0) is None


def test_missing_fg_score_returns_none():
    assert sentiment_context(fg_score=None, daily_score=3.0) is None


# ── valuation_warning ─────────────────────────────────────────────────────────

def test_negative_per_with_buy_verdict_warns():
    fin = {"per": "-5.2배", "valuation": {}}
    msg = valuation_warning(fin, "강력 매수")
    assert msg is not None
    assert "적자" in msg


def test_negative_per_in_valuation_dict_warns():
    fin = {"per": "—", "valuation": {"PER(후행)": "-12.3배"}}
    assert valuation_warning(fin, "매수 고려") is not None


def test_positive_per_returns_none():
    fin = {"per": "12.3배", "valuation": {}}
    assert valuation_warning(fin, "강력 매수") is None


def test_sell_verdict_returns_none_even_if_negative_per():
    fin = {"per": "-5.2배", "valuation": {}}
    assert valuation_warning(fin, "매도 고려") is None


def test_missing_per_returns_none():
    fin = {"per": "—", "valuation": {}}
    assert valuation_warning(fin, "강력 매수") is None
    assert valuation_warning(None, "강력 매수") is None
