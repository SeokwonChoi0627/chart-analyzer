"""최근 분기 실적 조회 — Yahoo Finance quoteSummary API."""
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_YF_URLS = [
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
]

_MODULES = "incomeStatementHistoryQuarterly,defaultKeyStatistics,price"


def _resolve_yf_symbols(symbol: str, market: str) -> list[str]:
    """종목 → Yahoo Finance 심볼 후보 리스트."""
    if market == "KR":
        from core.data.intraday import _resolve_kr_code
        code = _resolve_kr_code(symbol)
        return [f"{code}.KS", f"{code}.KQ"]
    return [symbol.upper()]


def _fmt_amount(val, currency: str) -> str:
    """금액 → 읽기 쉬운 문자열 (KRW: 조/억, 외화: $XB/$XM)."""
    if val is None:
        return "—"
    if currency == "KRW":
        t = val / 1e12
        if abs(t) >= 1:
            return f"{t:.1f}조"
        b = val / 1e8
        return f"{b:.0f}억"
    b = val / 1e9
    if abs(b) >= 1:
        return f"${b:.1f}B"
    m = val / 1e6
    return f"${m:.0f}M"


def fetch_financials(symbol: str, market: str) -> dict:
    """
    최근 4분기 실적 + PER / PBR 반환.
    실패 시 빈 dict 반환.

    반환 형식:
    {
        "quarters": [
            {"기간": "2025.09", "매출": "79.1조", "영업이익": "9.2조", "순이익": "7.3조"},
            ...
        ],
        "per": "12.5배",
        "pbr": "1.10배",
        "currency": "KRW",
        "yf_symbol": "005930.KS",
    }
    """
    for yf_sym in _resolve_yf_symbols(symbol, market):
        for url_tpl in _YF_URLS:
            url = url_tpl.format(sym=yf_sym)
            try:
                resp = requests.get(
                    url,
                    params={"modules": _MODULES},
                    headers=_HEADERS,
                    timeout=12,
                    verify=False,
                )
                resp.raise_for_status()
                data = resp.json()
                result = (data.get("quoteSummary") or {}).get("result") or []
                if not result:
                    continue

                r = result[0]

                # 통화
                price_info = r.get("price") or {}
                currency = price_info.get("currency") or "USD"

                # 분기 실적
                ish = (
                    (r.get("incomeStatementHistoryQuarterly") or {})
                    .get("incomeStatementHistory") or []
                )
                quarters = []
                for item in ish[:4]:
                    end_date = item.get("endDate") or {}
                    end_raw  = end_date.get("raw") if isinstance(end_date, dict) else None
                    try:
                        period = datetime.fromtimestamp(end_raw).strftime("%Y.%m") if end_raw else "?"
                    except Exception:
                        period = "?"

                    def _get(key: str):
                        v = item.get(key)
                        return v.get("raw") if isinstance(v, dict) else None

                    quarters.append({
                        "기간":   period,
                        "매출":   _fmt_amount(_get("totalRevenue"),    currency),
                        "영업이익": _fmt_amount(_get("operatingIncome"), currency),
                        "순이익":  _fmt_amount(_get("netIncome"),        currency),
                    })

                if not quarters:
                    continue

                # PER / PBR
                ks = r.get("defaultKeyStatistics") or {}

                def _ks(key: str):
                    v = ks.get(key)
                    return v.get("raw") if isinstance(v, dict) else v

                per_raw = _ks("trailingPE")
                pbr_raw = _ks("priceToBook")
                per = f"{per_raw:.1f}배" if per_raw else "—"
                pbr = f"{pbr_raw:.2f}배" if pbr_raw else "—"

                return {
                    "quarters":  quarters,
                    "per":       per,
                    "pbr":       pbr,
                    "currency":  currency,
                    "yf_symbol": yf_sym,
                }

            except Exception:
                continue

    return {}
