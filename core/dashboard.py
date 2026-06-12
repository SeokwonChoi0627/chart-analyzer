"""내 포트폴리오 대시보드: 등록 포지션 일괄 분석.

각 포지션에 대해 매수추천도(일봉 신호)와 권장 청산선(고정 손절 vs
트레일링 스탑)을 계산하고, 위험한 포지션(손절 이탈)부터 정렬한다.
"""
from collections.abc import Callable

import pandas as pd

from .data.base import detect_market
from .indicators import compute_all
from .regime import WEIGHTED_REGIMES, detect_regime
from .risk import evaluate_position, trailing_stop_from_df
from .signals import generate_signal

# 긴급한 상태 먼저 (대시보드 정렬 순서)
_STATUS_ORDER = {
    "손절 이탈":     0,
    "이익보호 청산": 1,
    "2차 목표 도달": 2,
    "1차 목표 도달": 3,
    "보유 유지":     4,
    "입력 오류":     8,
    "조회 실패":     9,
}


def merge_positions(positions: list[dict]) -> list[dict]:
    """동일 종목의 분할 매수(물타기) lot들을 평균 단가 포지션 하나로 병합.

    - 전 lot에 수량이 있으면 가중평균 단가 + 총 수량
    - 수량이 없거나 일부만 있으면 단순 평균 단가 (수량은 입력된 것만 합산)
    Returns: 병합된 포지션 목록 (각 항목에 "lots" = 병합된 건수 추가).
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for p in positions:
        key = p["symbol"].strip()
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(p)

    merged: list[dict] = []
    for key in order:
        lots = groups[key]
        if len(lots) == 1:
            merged.append({**lots[0], "lots": 1})
            continue
        total_qty = sum(lot.get("quantity") or 0 for lot in lots)
        if all((lot.get("quantity") or 0) > 0 for lot in lots):
            avg = sum(lot["entry_price"] * lot["quantity"] for lot in lots) / total_qty
        else:
            avg = sum(lot["entry_price"] for lot in lots) / len(lots)
        merged.append({
            "id":          lots[0]["id"],
            "symbol":      key,
            "entry_price": round(avg, 4),
            "quantity":    total_qty,
            "lots":        len(lots),
        })
    return merged


def _error_row(pos: dict, message: str) -> dict:
    return {
        "id":             pos["id"],
        "symbol":         pos["symbol"],
        "entry_price":    pos["entry_price"],
        "quantity":       pos.get("quantity", 0),
        "lots":           pos.get("lots", 1),
        "current":        None,
        "pnl_pct":        None,
        "verdict":        "—",
        "score":          None,
        "effective_stop": None,
        "trailing_stop":  None,
        "target1":        None,
        "status":         "조회 실패",
        "market":         detect_market(pos["symbol"]),
        "regime":         "",
        "source":         "",
        "error":          message,
    }


def analyze_positions(positions: list[dict],
                      fetch_fn: Callable[[str], tuple[pd.DataFrame, str]]) -> list[dict]:
    """등록 포지션 전체 분석. 같은 종목의 물타기 lot은 평단 기준 1건으로 병합."""
    rows: list[dict] = []
    for pos in merge_positions(positions):
        try:
            df, source = fetch_fn(pos["symbol"])
            if df is None or df.empty:
                raise ValueError("데이터가 비어 있습니다")
            enriched = compute_all(df)
            last_close = enriched["close"].iloc[-1]
            if pd.isna(last_close):
                raise ValueError("마지막 종가가 비어 있습니다 (NaN)")
            current = float(last_close)

            regime_info = detect_regime(enriched)
            regime = regime_info["regime"]
            sig = generate_signal(
                enriched,
                regime=regime if regime in WEIGHTED_REGIMES else None,
            )

            atr_val = enriched["atr"].iloc[-1]
            atr = float(atr_val) if pd.notna(atr_val) else 0.0
            trailing = trailing_stop_from_df(enriched, entry=pos["entry_price"])
            evaluated = evaluate_position(
                entry=pos["entry_price"], current=current,
                atr=atr, trailing_stop=trailing,
            )
            if evaluated is None:
                ep = pos["entry_price"]
                atr_str = f"{atr:,.0f}" if atr > 0 else "미상"
                min_entry = atr * 2 if atr > 0 else 0
                rows.append({
                    **_error_row(pos, (
                        f"매수가({ep:,.0f})가 너무 낮습니다 — "
                        f"ATR({atr_str})의 2배({min_entry:,.0f})보다 작아 손절가가 음수가 됩니다. "
                        f"현재가는 {current:,.0f}입니다. 삭제 후 실제 매수단가로 다시 등록하세요."
                    )),
                    "status": "입력 오류",
                    "current": current,
                })
                continue

            rows.append({
                "id":             pos["id"],
                "symbol":         pos["symbol"],
                "entry_price":    pos["entry_price"],
                "quantity":       pos.get("quantity", 0),
                "lots":           pos.get("lots", 1),
                "current":        current,
                "pnl_pct":        evaluated["pnl_pct"],
                "verdict":        sig["verdict"],
                "score":          sig["score"],
                "effective_stop": evaluated["effective_stop"],
                "trailing_stop":  evaluated["trailing_stop"],
                "target1":        evaluated["target1"],
                "status":         evaluated["status"],
                "market":         detect_market(pos["symbol"]),
                "regime":         regime,
                "source":         source,
                "error":          None,
            })
        except Exception as e:
            rows.append(_error_row(pos, str(e)))

    rows.sort(key=lambda r: (_STATUS_ORDER.get(r["status"], 9),
                             r["pnl_pct"] if r["pnl_pct"] is not None else 0))
    return rows


def summarize(rows: list[dict]) -> dict:
    """수량이 입력된 정상 포지션을 통화(시장)별로 합산.

    Returns: {"KR": {invested, value, pnl, pnl_pct}, "US": {...}}
    수량 미입력(0)·조회 실패 포지션은 제외. 합산 대상 없으면 빈 dict.
    """
    out: dict[str, dict] = {}
    for r in rows:
        qty = r.get("quantity") or 0
        if r["error"] or qty <= 0 or r["current"] is None:
            continue
        bucket = out.setdefault(r["market"], {"invested": 0.0, "value": 0.0})
        bucket["invested"] += r["entry_price"] * qty
        bucket["value"] += r["current"] * qty

    for bucket in out.values():
        bucket["invested"] = round(bucket["invested"], 2)
        bucket["value"] = round(bucket["value"], 2)
        bucket["pnl"] = round(bucket["value"] - bucket["invested"], 2)
        bucket["pnl_pct"] = (
            round(bucket["pnl"] / bucket["invested"] * 100, 2)
            if bucket["invested"] > 0 else 0.0
        )
    return out
