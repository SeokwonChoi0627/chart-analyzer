"""15분봉 OHLCV 조회 — Yahoo Finance REST API (requests 기반, SSL MITM 환경 대응)."""
import requests
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _to_yahoo_symbols(symbol: str, market: str) -> list[str]:
    """종목코드 → Yahoo Finance 심볼 후보 리스트."""
    if market == "KR":
        return [f"{symbol}.KS", f"{symbol}.KQ"]
    return [symbol.upper()]


def _fetch_one(yf_symbol: str, days: int) -> pd.DataFrame:
    range_ = f"{min(days, 7)}d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}"
    params = {"interval": "15m", "range": range_}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
    except requests.exceptions.SSLError:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10, verify=False)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("chart", {}).get("result") or []
    if not result:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    chart = result[0]
    timestamps = chart.get("timestamp") or []
    if not timestamps:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    quote = chart["indicators"]["quote"][0]
    tz_name = chart["meta"].get("exchangeTimezoneName", "UTC")

    idx = (
        pd.to_datetime(timestamps, unit="s", utc=True)
        .tz_convert(tz_name)
        .tz_localize(None)
    )
    df = pd.DataFrame(
        {
            "open":   quote["open"],
            "high":   quote["high"],
            "low":    quote["low"],
            "close":  quote["close"],
            "volume": quote["volume"],
        },
        index=idx,
    )
    return df.dropna().sort_index()


def fetch_15min(symbol: str, market: str, days: int = 5) -> pd.DataFrame:
    """
    15분봉 OHLCV 조회. 실패 시 빈 DataFrame 반환 (앱은 계속 동작).

    Args:
        symbol: 6자리 코드(KR) 또는 티커(US)
        market: 'KR' | 'US'
        days:   조회 기간 (최대 7일 — Yahoo 15분봉 제한)
    """
    for yf_sym in _to_yahoo_symbols(symbol, market):
        try:
            df = _fetch_one(yf_sym, days)
            if not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame(columns=OHLCV_COLUMNS)
