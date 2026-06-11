"""관심종목 스크리너: 여러 종목을 일괄 분석해 점수순으로 정렬."""
from collections.abc import Callable

import pandas as pd

from .indicators import compute_all
from .regime import WEIGHTED_REGIMES, detect_regime
from .signals import generate_signal


def scan_symbols(symbols: list[str],
                 fetch_fn: Callable[[str], tuple[pd.DataFrame, str]]) -> list[dict]:
    """종목 목록을 일괄 분석. 점수 내림차순 정렬, 조회 실패는 맨 뒤.

    fetch_fn: symbol → (OHLCV DataFrame, source명). 실패 시 예외.
    Returns: [{symbol, score, verdict, close, regime, source, error}]
    """
    cleaned = [s.strip() for s in symbols]
    unique = list(dict.fromkeys(s for s in cleaned if s))

    results: list[dict] = []
    for sym in unique:
        try:
            df, source = fetch_fn(sym)
            if df is None or df.empty:
                raise ValueError("데이터가 비어 있습니다")
            enriched = compute_all(df)
            last_close = enriched["close"].iloc[-1]
            if pd.isna(last_close):
                raise ValueError("마지막 종가가 비어 있습니다 (NaN)")
            regime_info = detect_regime(enriched)
            regime = regime_info["regime"]
            sig = generate_signal(
                enriched,
                regime=regime if regime in WEIGHTED_REGIMES else None,
            )
            results.append({
                "symbol":  sym,
                "score":   sig["score"],
                "verdict": sig["verdict"],
                "close":   float(last_close),
                "regime":  regime,
                "source":  source,
                "error":   None,
            })
        except Exception as e:
            results.append({
                "symbol":  sym,
                "score":   None,
                "verdict": "조회 실패",
                "close":   None,
                "regime":  "",
                "source":  "",
                "error":   str(e),
            })

    ok = sorted((r for r in results if r["error"] is None),
                key=lambda r: r["score"], reverse=True)
    failed = [r for r in results if r["error"] is not None]
    return ok + failed
