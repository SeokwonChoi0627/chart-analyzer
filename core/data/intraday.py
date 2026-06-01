"""15분봉 OHLCV 조회 — Yahoo Finance REST / Naver Finance 폴백 (SSL MITM 환경 완전 대응)."""
import json
import unicodedata
from datetime import date, timedelta

import pandas as pd
import requests
import urllib3

# 회사 SSL MITM 프록시 환경에서 InsecureRequestWarning 억제
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_KR_CODE_MAP: dict[str, str] = {
    "삼성전자": "005930", "sk하이닉스": "000660",
    "lg에너지솔루션": "373220", "삼성바이오로직스": "207940",
    "현대차": "005380", "현대자동차": "005380",
    "기아": "000270", "셀트리온": "068270",
    "포스코홀딩스": "005490", "kb금융": "105560",
    "신한지주": "055550", "삼성sdi": "006400",
    "lg화학": "051910", "하나금융지주": "086790",
    "현대모비스": "012330", "카카오": "035720",
    "네이버": "035420", "naver": "035420",
    "sk이노베이션": "096770", "삼성물산": "028260",
    "크래프톤": "259960", "카카오뱅크": "323410",
    "카카오페이": "377300", "두산에너빌리티": "034020",
    "한국전력": "015760", "고려아연": "010130",
    "아모레퍼시픽": "090430", "한화에어로스페이스": "012450",
    "에코프로비엠": "247540", "에코프로": "086520",
    "포스코퓨처엠": "003670", "엘앤에프": "066970",
    "넷마블": "251270", "sk텔레콤": "017670",
    "kt": "030200", "lg전자": "066570",
    "삼성생명": "032830", "삼성화재": "000810",
    "현대건설": "000720", "대한항공": "003490",
    "하이브": "352820", "한미약품": "128940",
}

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
    s = symbol.strip()
    if s.isdigit():
        return s
    key = unicodedata.normalize("NFC", s).strip().lower()
    if key in _KR_CODE_MAP:
        return _KR_CODE_MAP[key]
    for name, code in _KR_CODE_MAP.items():
        if key in name:
            return code
    try:
        import FinanceDataReader as fdr
        listing = fdr.StockListing("KRX").copy()
        listing["_k"] = listing["Name"].apply(
            lambda x: unicodedata.normalize("NFC", str(x)).lower() if pd.notna(x) else ""
        )
        matched = listing[listing["_k"] == key]
        if not matched.empty:
            return str(matched.iloc[0]["Code"])
        matched = listing[listing["_k"].str.contains(key, na=False, regex=False)]
        if not matched.empty:
            matched = matched.copy()
            matched["_l"] = matched["_k"].str.len()
            return str(matched.sort_values("_l").iloc[0]["Code"])
    except Exception:
        pass
    return s


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
