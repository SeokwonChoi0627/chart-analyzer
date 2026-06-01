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


# ── 한글 종목명 → 종목코드 변환 ──────────────────────────────────────────────

def _resolve_kr_code(symbol: str) -> str:
    """한글 종목명 → 6자리 코드. pykrx_kr 3단계 폴백(정적맵→Naver→FDR) 재사용."""
    if symbol.isdigit():
        return symbol
    try:
        from .pykrx_kr import PykrxProvider
        code = PykrxProvider._name_to_ticker(symbol)
        if code:
            return code
    except Exception:
        pass
    return symbol


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def _to_yahoo_symbols(symbol: str, market: str) -> list[str]:
    """종목코드(또는 한글명) → Yahoo Finance 심볼 후보 리스트."""
    if market == "KR":
        code = _resolve_kr_code(symbol)
        return [f"{code}.KS", f"{code}.KQ"]
    return [symbol.upper()]


def _fetch_yahoo(yf_symbol: str, days: int) -> tuple[pd.DataFrame, str]:
    """Yahoo Finance v8 chart API로 15분봉 조회. (df, error_msg) 반환."""
    range_ = f"{min(days, 7)}d"
    params = {"interval": "15m", "range": range_}
    last_err = ""

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
                last_err = f"Yahoo({yf_symbol}): 데이터 없음 (result empty)"
                continue

            chart = result[0]
            timestamps = chart.get("timestamp") or []
            if not timestamps:
                last_err = f"Yahoo({yf_symbol}): timestamp 없음"
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
                return df, ""
            last_err = f"Yahoo({yf_symbol}): dropna 후 빈 데이터"

        except Exception as e:
            last_err = f"Yahoo({yf_symbol}): {type(e).__name__}: {e}"

    return pd.DataFrame(columns=OHLCV_COLUMNS), last_err


# ── Naver Finance (한국 주식 폴백) ────────────────────────────────────────────

def _fetch_naver_kr(symbol: str, days: int) -> tuple[pd.DataFrame, str]:
    """
    Naver Finance API로 1분봉 조회 후 15분봉으로 리샘플.
    한국 주식 전용 — Yahoo Finance 실패 시 폴백.
    """
    code = _resolve_kr_code(symbol)  # 한글명 → 종목코드
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=days + 2)
    count = min(days * 8 * 60, 2000)

    url = "https://api.finance.naver.com/siseJson.naver"
    params = {
        "symbol": code,
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
            return pd.DataFrame(columns=OHLCV_COLUMNS), "Naver: 빈 응답"

        df = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close", "volume"])
        df["dt"] = pd.to_datetime(df["dt"].astype(str), format="%Y%m%d%H%M%S", errors="coerce")
        df = df.dropna(subset=["dt"]).set_index("dt").sort_index()
        df = df.apply(pd.to_numeric, errors="coerce").dropna()

        df_15m = df.resample("15min", label="left").agg({
            "open":   "first",
            "high":   "max",
            "low":    "min",
            "close":  "last",
            "volume": "sum",
        }).dropna(subset=["open", "close"])
        df_15m = df_15m[df_15m["volume"] > 0]

        if df_15m.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS), "Naver: 리샘플 후 빈 데이터"
        return df_15m, ""

    except Exception as e:
        return pd.DataFrame(columns=OHLCV_COLUMNS), f"Naver: {type(e).__name__}: {e}"


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def fetch_15min(
    symbol: str, market: str, days: int = 5
) -> tuple[pd.DataFrame, str]:
    """
    15분봉 OHLCV 조회. (DataFrame, 오류메시지) 반환.
    성공 시 오류메시지는 빈 문자열.

    조회 순서:
      KR: Yahoo Finance (.KS → .KQ) → Naver Finance
      US: Yahoo Finance
    """
    errors: list[str] = []

    # 1차: Yahoo Finance
    for yf_sym in _to_yahoo_symbols(symbol, market):
        df, err = _fetch_yahoo(yf_sym, days)
        if not df.empty:
            return df, ""
        if err:
            errors.append(err)

    # 2차: Naver Finance (KR 전용 폴백)
    if market == "KR":
        df, err = _fetch_naver_kr(symbol, days)
        if not df.empty:
            return df, ""
        if err:
            errors.append(err)

    return pd.DataFrame(columns=OHLCV_COLUMNS), " | ".join(errors)
