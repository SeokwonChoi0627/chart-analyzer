import pandas as pd

from core.dashboard import analyze_positions, merge_positions, summarize


def _make_df(closes):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * n,
    }, index=idx)


def _fake_fetch(symbol):
    if symbol == "UP":       # 100 → 219 상승
        return _make_df([100 + i for i in range(120)]), "테스트"
    if symbol == "DOWN":     # 300 → 181 하락
        return _make_df([300 - i for i in range(120)]), "테스트"
    raise ValueError("조회 실패")


def _pos(symbol, entry, qty=0, pid=1):
    return {"id": pid, "symbol": symbol, "entry_price": entry, "quantity": qty}


def test_row_has_required_fields():
    rows = analyze_positions([_pos("UP", entry=200)], fetch_fn=_fake_fetch)
    row = rows[0]
    for key in ("id", "symbol", "entry_price", "quantity", "current",
                "pnl_pct", "verdict", "score", "effective_stop",
                "status", "market", "error"):
        assert key in row, f"누락 필드: {key}"
    assert row["error"] is None
    assert row["current"] == 219
    assert row["pnl_pct"] > 0


def test_losing_position_below_stop_flags_exit():
    """300에 매수했는데 181까지 하락 — 손절 이탈 상태."""
    rows = analyze_positions([_pos("DOWN", entry=300)], fetch_fn=_fake_fetch)
    assert rows[0]["status"] == "손절 이탈"
    assert rows[0]["pnl_pct"] < 0


def test_error_position_kept_with_message():
    rows = analyze_positions([_pos("ERR", entry=100)], fetch_fn=_fake_fetch)
    assert rows[0]["error"] is not None
    assert rows[0]["status"] == "조회 실패"


def test_dangerous_positions_sorted_first():
    """손절 이탈이 보유 유지보다 위에 오도록 정렬."""
    rows = analyze_positions(
        [_pos("UP", entry=100, pid=1), _pos("DOWN", entry=300, pid=2)],
        fetch_fn=_fake_fetch,
    )
    assert rows[0]["symbol"] == "DOWN"  # 손절 이탈 먼저


def test_summarize_splits_by_currency():
    rows = analyze_positions(
        [_pos("UP", entry=200, qty=10, pid=1),    # US (영문) — 평가 2190, 매입 2000
         _pos("DOWN", entry=300, qty=5, pid=2)],  # US — 평가 905, 매입 1500
        fetch_fn=_fake_fetch,
    )
    s = summarize(rows)
    us = s["US"]
    assert us["invested"] == 200 * 10 + 300 * 5
    assert us["value"] == 219 * 10 + 181 * 5
    assert us["pnl"] == us["value"] - us["invested"]
    assert "KR" not in s  # KR 포지션 없음


def test_summarize_skips_zero_quantity_and_errors():
    rows = analyze_positions(
        [_pos("UP", entry=200, qty=0, pid=1),   # 수량 미입력 → 금액 합산 제외
         _pos("ERR", entry=100, qty=10, pid=2)],
        fetch_fn=_fake_fetch,
    )
    assert summarize(rows) == {}


# ── merge_positions: 동일 종목 물타기 병합 ────────────────────────────────────

def test_merge_same_symbol_weighted_average():
    lots = [_pos("UP", entry=100, qty=10, pid=1),
            _pos("UP", entry=200, qty=10, pid=2)]
    merged = merge_positions(lots)
    assert len(merged) == 1
    assert merged[0]["entry_price"] == 150.0   # (100×10 + 200×10) / 20
    assert merged[0]["quantity"] == 20
    assert merged[0]["lots"] == 2


def test_merge_weighted_by_unequal_quantity():
    lots = [_pos("UP", entry=100, qty=30, pid=1),
            _pos("UP", entry=200, qty=10, pid=2)]
    merged = merge_positions(lots)[0]
    assert merged["entry_price"] == 125.0      # (3000 + 2000) / 40


def test_merge_without_quantity_uses_simple_mean():
    lots = [_pos("UP", entry=100, qty=0, pid=1),
            _pos("UP", entry=200, qty=0, pid=2)]
    merged = merge_positions(lots)[0]
    assert merged["entry_price"] == 150.0
    assert merged["quantity"] == 0


def test_merge_mixed_quantity_falls_back_to_simple_mean():
    """일부 lot만 수량 입력 — 가중평균 불가, 단순 평균 + 입력된 수량 합."""
    lots = [_pos("UP", entry=100, qty=10, pid=1),
            _pos("UP", entry=200, qty=0, pid=2)]
    merged = merge_positions(lots)[0]
    assert merged["entry_price"] == 150.0
    assert merged["quantity"] == 10


def test_different_symbols_not_merged():
    lots = [_pos("UP", entry=100, pid=1), _pos("DOWN", entry=300, pid=2)]
    assert len(merge_positions(lots)) == 2


def test_single_lot_passes_through():
    merged = merge_positions([_pos("UP", entry=100, qty=5, pid=7)])
    assert merged[0]["lots"] == 1
    assert merged[0]["entry_price"] == 100
    assert merged[0]["id"] == 7


def test_analyze_merges_lots_into_single_row():
    """물타기 2건 → 대시보드에는 평단 기준 1개 카드 (손절/목표 통합)."""
    lots = [_pos("UP", entry=100, qty=10, pid=1),
            _pos("UP", entry=200, qty=10, pid=2)]
    rows = analyze_positions(lots, fetch_fn=_fake_fetch)
    assert len(rows) == 1
    assert rows[0]["entry_price"] == 150.0
    assert rows[0]["quantity"] == 20
    assert rows[0]["lots"] == 2
    assert rows[0]["effective_stop"] is not None  # 평단 기준 통합 청산선
