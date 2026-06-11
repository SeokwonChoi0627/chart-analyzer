"""미니 백테스트: 과거 구간에서 신호 발생 후 forward return을 집계해
현재 신호 체계의 적중률을 검증한다.

승리 기준:
- 매수 계열 판정("강력 매수"/"매수 고려") → h봉 후 수익률 > 0
- 매도 계열 판정("강력 매도"/"매도 고려") → h봉 후 수익률 < 0
"""
import pandas as pd

from .signals import generate_signal

MIN_HISTORY = 60  # 지표 안정화에 필요한 최소 봉 수


def run_backtest(df: pd.DataFrame, horizons: tuple[int, ...] = (5, 20),
                 min_history: int = MIN_HISTORY) -> dict:
    """지표가 채워진 일봉 DataFrame 전 구간을 순회하며 신호 성과 집계.

    Returns:
        {
          "horizons": {h: {verdict: {"count", "win_rate", "avg_return"}}},
          "total_signals": int,   # 중립 제외 신호 발생 횟수
          "evaluated_bars": int,  # 평가한 봉 수
        }
    """
    out: dict = {"horizons": {h: {} for h in horizons},
                 "total_signals": 0, "evaluated_bars": 0}
    if df.empty or "close" not in df.columns:
        return out

    max_h = max(horizons)
    n = len(df)
    if n < min_history + max_h + 1:
        return out

    closes = df["close"]
    records: list[tuple[str, dict[int, float]]] = []
    evaluated = 0

    for i in range(min_history, n - max_h):
        entry = closes.iloc[i]
        if pd.isna(entry) or float(entry) <= 0:
            continue
        evaluated += 1
        sig = generate_signal(df.iloc[: i + 1])
        verdict = sig["verdict"]
        if verdict == "중립/관망":
            continue
        entry_f = float(entry)
        rets = {}
        for h in horizons:
            fwd = closes.iloc[i + h]
            if pd.isna(fwd):
                break
            rets[h] = float(fwd) / entry_f - 1
        if len(rets) == len(horizons):
            records.append((verdict, rets))

    out["evaluated_bars"] = evaluated
    out["total_signals"] = len(records)

    for h in horizons:
        buckets: dict[str, dict] = {}
        grouped: dict[str, list[float]] = {}
        for verdict, rets in records:
            grouped.setdefault(verdict, []).append(rets[h])
        for verdict, ret_list in grouped.items():
            is_buy = "매수" in verdict
            wins = sum(1 for r in ret_list if (r > 0 if is_buy else r < 0))
            buckets[verdict] = {
                "count":      len(ret_list),
                "win_rate":   round(wins / len(ret_list) * 100, 1),
                "avg_return": round(sum(ret_list) / len(ret_list) * 100, 2),
            }
        out["horizons"][h] = buckets

    return out
