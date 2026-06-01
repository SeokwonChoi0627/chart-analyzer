"""15분봉 OHLCV 조회 — Yahoo Finance REST / Naver Finance 폴백 (SSL MITM 환경 완전 대응)."""
import json
from datetime import date, timedelta

import pandas as pd
import requests
import urllib3

# 회사 SSL MITM 프록시 환경에서 InsecureRequestWarning 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

_HEADERS_YF = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_HEADERS_NAVER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com",
    "Accept": "application/json, text/plain, */*",
}

# Yahoo Finance 시도 순서 (query1 → query2)
_YF_BASE_URLS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{sym}",
]


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def _to_yahoo_symbols(symbol: str, market: str) -> list[str]:
    """종목코드 → Yahoo Finance 심볼 후보 리스트."""
    if market == "KR":
        return [f"{symbol}.KS", f"{symbol}.KQ"]
    return [symbol.upper()]


def _fetch_yahoo(yf_symbol: str, days: int) -> pd.DataFrame:
    """Yahoo Finance v8 chart API로 15분봉 조회. verify=False로 SSL MITM 우회."""
    range_ = f"{min(days, 7)}d"
    params = {"interval": "15m", "range": range_}

    for url_tpl in _YF_BASE_URLS:
        url = url_tpl.format(sym=yf_symbol)
        try:
            resp = requests.get(
                url, params=params, headers=_HEADERS_YF,
                timeout=12, verify=False,
            )
            resp.raise_for_status()
            data = resp.json()
            result = (data.get("chart") or {}).get("result") or []
            if not result:
                continue

            chart = result[0]
            timestamps = chart.get("timestamp") or []
            if not timestamps:
                continue

            quote = chart["indicators"]["quote"][0]
            tz_name = chart["meta"].get("exchangeTimezoneName", "UTC")
            idx = (
                pd.to_datetime(timestamps, unit="s", utc=True)
                .tz_convert(tz_name)
                .tz_localize(None)
            )
            df = pd.DataFrame(
                {
                    "open":   quote.get("open"),
                    "high":   quote.get("high"),
                    "low":    quote.get("low"),
                    "close":  quote.get("close"),
                    "volume": quote.get("volume"),
                },
                index=idx,
            )
            df = df.dropna().sort_index()
            if not df.empty:
                return df
        except Exception:
            continue

    return pd.DataFrame(columns=OHLCV_COLUMNS)


# ── Naver Finance (한국 주식 폴백) ────────────────────────────────────────────

def _fetch_naver_kr(symbol: str, days: int) -> pd.DataFrame:
    """
    Naver Finance API로 1분봉 조회 후 15분봉으로 리샘플.
    한국 주식 전용 — Yahoo Finance 실패 시 폴백으로 사용.
    """
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=days + 2)
    count = min(days * 8 * 60, 2000)  # 하루 약 400봉 기준, 최대 2000

    url = "https://api.finance.naver.com/siseJson.naver"
    params = {
        "symbol": symbol,
        "requestType": "1",
        "startTime": start_dt.strftime("%Y%m%d"),
        "endTime": end_dt.strftime("%Y%m%d"),
        "timeframe": "minute",
        "count": count,
    }
    try:
        resp = requests.get(
            url, params=params, headers=_HEADERS_NAVER,
            timeout=12, verify=False,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        rows = json.loads(text)
        if not rows or not isinstance(rows, list):
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        # 응답 형식: [[날짜시간, 시가, 고가, 저가, 종가, 거래량], ...]
        df = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close", "volume"])
        df["dt"] = pd.to_datetime(df["dt"].astype(str), format="%Y%m%d%H%M%S", errors="coerce")
        df = df.dropna(subset=["dt"]).set_index("dt").sort_index()
        df = df.apply(pd.to_numeric, errors="coerce").dropna()

        # 1분봉 → 15분봉 리샘플
        df_15m = df.resample("15min", label="left").agg({
            "open":   "first",
            "high":   "max",
            "low":    "min",
            "close":  "last",
            "volume": "sum",
        }).dropna(subset=["open", "close"])

        return df_15m[df_15m["volume"] > 0]

    except Exception:
        return pd.DataFrame(columns=OHLCV_COLUMNS)


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def fetch_15min(symbol: str, market: str, days: int = 5) -> pd.DataFrame:
    """
    15분봉 OHLCV 조회. 실패 시 빈 DataFrame 반환 (앱은 계속 동작).

    조회 순서:
      KR: Yahoo Finance (.KS → .KQ) → Naver Finance
      US: Yahoo Finance

    Args:
        symbol: 6자리 코드(KR) 또는 티커(US)
        market: 'KR' | 'US'
        days:   조회 기간 (Yahoo 최대 7일)
    """
    # 1차: Yahoo Finance
    for yf_sym in _to_yahoo_symbols(symbol, market):
        df = _fetch_yahoo(yf_sym, days)
        if not df.empty:
            return df

    # 2차: Naver Finance (KR 전용 폴백)
    if market == "KR":
        df = _fetch_naver_kr(symbol, days)
        if not df.empty:
            return df

    return pd.DataFrame(columns=OHLCV_COLUMNS)
