"""주요 재무지표 조회.

우선순위 (KR):
  1) Naver 모바일 API  m.stock.naver.com/api/stock/{code}/integration
  2) Naver itemSummary  api.finance.naver.com/service/itemSummary.naver
  3) Yahoo Finance v10 quoteSummary (분기 실적 추가 시도)

우선순위 (US):
  1) Yahoo Finance v7 quote  + crumb 인증
  2) Yahoo Finance v10 quoteSummary + crumb 인증
  3) Yahoo Finance v8 chart meta (항상 동작 — 현재가·52주범위·시총)
"""
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
_HEADERS_YF = {
    "User-Agent": _UA,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
_HEADERS_NAVER = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.stock.naver.com",
    "Accept": "application/json, text/plain, */*",
}

_YF_SUMMARY_URLS = [
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
]
_YF_MODULES = "incomeStatementHistoryQuarterly,defaultKeyStatistics,price"


# ── 공통 유틸 ─────────────────────────────────────────────────────────────────

def _resolve_kr_code(symbol: str) -> str:
    if symbol.isdigit():
        return symbol
    try:
        import FinanceDataReader as fdr
        listing = fdr.StockListing("KRX")
        m = listing[listing["Name"] == symbol]
        if not m.empty:
            return str(m.iloc[0]["Code"])
        m = listing[listing["Name"].str.contains(symbol, na=False)]
        if not m.empty:
            m = m.copy(); m["_l"] = m["Name"].str.len()
            return str(m.sort_values("_l").iloc[0]["Code"])
    except Exception:
        pass
    return symbol


def _fmt_ratio(v) -> str:
    try:
        return f"{float(str(v).replace(',', '')):.2f}배" if v else "—"
    except Exception:
        return str(v) if v else "—"


def _fmt_amount(val, currency: str) -> str:
    if val is None:
        return "—"
    if currency == "KRW":
        t = val / 1e12
        return f"{t:.1f}조" if abs(t) >= 1 else f"{val / 1e8:.0f}억"
    b = val / 1e9
    return f"${b:.1f}B" if abs(b) >= 1 else f"${val / 1e6:.0f}M"


# ── Yahoo Finance 세션 + crumb ────────────────────────────────────────────────

def _get_yf_session() -> tuple[requests.Session, str]:
    """세션 쿠키 + crumb 취득. 여러 쿠키 소스를 순차 시도."""
    session = requests.Session()
    session.headers.update(_HEADERS_YF)

    # 쿠키 취득 소스 (여러 개 시도해 더 많은 쿠키 확보)
    for cookie_url in [
        "https://fc.yahoo.com/",
        "https://finance.yahoo.com/",
        "https://finance.yahoo.com/quote/AAPL",
    ]:
        try:
            session.get(cookie_url, timeout=6, verify=False)
        except Exception:
            pass

    # crumb 취득
    crumb = ""
    for url in [
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        "https://query2.finance.yahoo.com/v1/test/getcrumb",
    ]:
        try:
            r = session.get(url, timeout=6, verify=False)
            text = r.text.strip()
            if r.status_code == 200 and text and len(text) < 50:
                crumb = text
                break
        except Exception:
            continue
    return session, crumb


# ── Naver Finance (KR 전용) ───────────────────────────────────────────────────

def _fetch_naver_mobile(code: str) -> tuple[dict, str]:
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    try:
        resp = requests.get(url, headers=_HEADERS_NAVER, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {}, f"Naver모바일: {type(e).__name__}: {e}"

    infos = data.get("totalInfos") or []
    info_map: dict[str, str] = {
        str(item.get("code") or item.get("name")): str(item.get("value"))
        for item in infos
        if (item.get("code") or item.get("name")) and item.get("value")
    }

    def _get(*keys):
        for k in keys:
            v = info_map.get(k)
            if v and v not in ("", "-", "N/A"):
                return v
        return None

    per_v = _get("per", "PER")
    pbr_v = _get("pbr", "PBR")
    if not per_v and not pbr_v:
        return {}, f"Naver모바일: per/pbr 없음 keys={list(info_map.keys())[:10]}"

    extras = [
        {"항목": label, "값": val}
        for label, val in [
            ("EPS",  _get("eps", "EPS")),
            ("BPS",  _get("bps", "BPS")),
            ("배당률", _get("dividendYield", "dividendRatio", "배당수익률")),
            ("시총",  _get("marketValue", "시가총액")),
        ]
        if val
    ]
    return {
        "quarters":  [],
        "per":       _fmt_ratio(per_v),
        "pbr":       _fmt_ratio(pbr_v),
        "extras":    extras,
        "currency":  "KRW",
        "source":    "Naver Finance",
        "yf_symbol": f"{code}.KS",
    }, ""


def _fetch_naver_summary(code: str) -> tuple[dict, str]:
    url = f"https://api.finance.naver.com/service/itemSummary.naver?itemCode={code}"
    try:
        resp = requests.get(url, headers=_HEADERS_NAVER, timeout=10, verify=False)
        resp.raise_for_status()
        d = resp.json()
    except Exception as e:
        return {}, f"NaverSummary: {type(e).__name__}: {e}"

    per_v = d.get("per") or d.get("PER")
    pbr_v = d.get("pbr") or d.get("PBR")
    if not per_v and not pbr_v:
        return {}, f"NaverSummary: per/pbr 없음 keys={list(d.keys())[:10]}"

    extras = [
        {"항목": label, "값": str(d[key])}
        for label, key in [("EPS", "eps"), ("BPS", "bps"), ("배당률", "dividendRatio")]
        if d.get(key)
    ]
    return {
        "quarters":  [],
        "per":       _fmt_ratio(per_v),
        "pbr":       _fmt_ratio(pbr_v),
        "extras":    extras,
        "currency":  "KRW",
        "source":    "Naver Finance",
        "yf_symbol": f"{code}.KS",
    }, ""


# ── Yahoo Finance v10 quoteSummary ────────────────────────────────────────────

def _fetch_yahoo_v10(yf_sym: str, session: requests.Session,
                     crumb: str) -> tuple[dict, str]:
    params = {"modules": _YF_MODULES}
    if crumb:
        params["crumb"] = crumb
    errors = []
    for url_tpl in _YF_SUMMARY_URLS:
        url = url_tpl.format(sym=yf_sym)
        try:
            resp = session.get(url, params=params, timeout=12, verify=False)
            resp.raise_for_status()
            data = resp.json()
            qs = data.get("quoteSummary") or {}
            qs_err = qs.get("error")
            if qs_err:
                errors.append(f"v10 {url}: {qs_err}")
                continue
            result = qs.get("result") or []
            if not result:
                errors.append(f"v10 {url}: result 없음")
                continue
            r = result[0]
            currency = (r.get("price") or {}).get("currency") or "USD"
            ish = ((r.get("incomeStatementHistoryQuarterly") or {})
                   .get("incomeStatementHistory") or [])
            quarters = []
            for item in ish[:4]:
                ed = item.get("endDate") or {}
                end_raw = ed.get("raw") if isinstance(ed, dict) else None
                try:
                    period = datetime.fromtimestamp(end_raw).strftime("%Y.%m") if end_raw else "?"
                except Exception:
                    period = "?"

                def _r(key, _i=item):
                    v = _i.get(key)
                    return v.get("raw") if isinstance(v, dict) else None

                quarters.append({
                    "기간":    period,
                    "매출":    _fmt_amount(_r("totalRevenue"),    currency),
                    "영업이익": _fmt_amount(_r("operatingIncome"), currency),
                    "순이익":   _fmt_amount(_r("netIncome"),       currency),
                })
            if not quarters:
                errors.append(f"v10 {url}: 분기 실적 없음")
                continue
            ks = r.get("defaultKeyStatistics") or {}

            def _ks(key):
                v = ks.get(key)
                return v.get("raw") if isinstance(v, dict) else v

            per_r, pbr_r = _ks("trailingPE"), _ks("priceToBook")
            return {
                "quarters":  quarters,
                "per":       f"{per_r:.1f}배" if per_r else "—",
                "pbr":       f"{pbr_r:.2f}배" if pbr_r else "—",
                "extras":    [],
                "currency":  currency,
                "source":    "Yahoo Finance",
                "yf_symbol": yf_sym,
            }, ""
        except Exception as e:
            errors.append(f"v10 {url}: {type(e).__name__}: {str(e)[:80]}")
    return {}, " | ".join(errors)


# ── Yahoo Finance v7 quote (PER·PBR·EPS·배당·시총) ────────────────────────────

def _fetch_yahoo_v7(sym: str, session: requests.Session,
                    crumb: str) -> tuple[dict, str]:
    """v7 quote API. crumb 포함 시 401 해결 가능."""
    params: dict = {"symbols": sym}
    if crumb:
        params["crumb"] = crumb
    errors = []
    for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
        url = f"{base}/v7/finance/quote"
        try:
            resp = session.get(url, params=params, timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()
            result = (data.get("quoteResponse") or {}).get("result") or []
            if not result:
                errors.append(f"v7 {base}: result 없음")
                continue
            r = result[0]
            currency = r.get("currency") or "USD"
            per_v = r.get("trailingPE")
            pbr_v = r.get("priceToBook")
            if not per_v and not pbr_v:
                errors.append(f"v7 {base}: per/pbr 없음")
                continue
            extras = []
            eps = r.get("epsTrailingTwelveMonths")
            div = r.get("dividendYield")
            cap = r.get("marketCap")
            if eps is not None:
                extras.append({"항목": "EPS", "값": f"${eps:.2f}"})
            if div is not None:
                extras.append({"항목": "배당률", "값": f"{div * 100:.2f}%"})
            if cap is not None:
                extras.append({"항목": "시총", "값": _fmt_amount(cap, currency)})
            return {
                "quarters":  [],
                "per":       f"{per_v:.1f}배" if per_v else "—",
                "pbr":       f"{pbr_v:.2f}배" if pbr_v else "—",
                "extras":    extras,
                "currency":  currency,
                "source":    "Yahoo Finance",
                "yf_symbol": sym,
            }, ""
        except Exception as e:
            errors.append(f"v7 {base}: {type(e).__name__}: {str(e)[:80]}")
    return {}, " | ".join(errors)


# ── Yahoo Finance v8 chart meta (항상 동작 폴백) ──────────────────────────────

def _fetch_yahoo_v8_meta(sym: str, session: requests.Session) -> tuple[dict, str]:
    """
    v8 chart meta 추출 — 인증 불필요, 항상 동작.
    PER/PBR 없음, 현재가·52주범위·시총·거래량 표시.
    """
    errors = []
    for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
        url = f"{base}/v8/finance/chart/{sym}"
        try:
            resp = session.get(
                url,
                params={"interval": "1d", "range": "5d"},
                timeout=10,
                verify=False,
            )
            resp.raise_for_status()
            data = resp.json()
            result = (data.get("chart") or {}).get("result") or []
            if not result:
                errors.append(f"v8 {base}: result 없음")
                continue
            meta = result[0].get("meta") or {}
            currency = meta.get("currency") or "USD"
            price = meta.get("regularMarketPrice")
            if not price:
                errors.append(f"v8 {base}: price 없음")
                continue

            extras = []
            high52  = meta.get("fiftyTwoWeekHigh")
            low52   = meta.get("fiftyTwoWeekLow")
            mktcap  = meta.get("marketCap")
            vol     = meta.get("regularMarketVolume")
            name    = meta.get("longName") or meta.get("shortName") or sym

            extras.append({"항목": "현재가", "값": f"${price:,.2f}"})
            if high52:
                extras.append({"항목": "52주 최고", "값": f"${high52:,.2f}"})
            if low52:
                extras.append({"항목": "52주 최저", "값": f"${low52:,.2f}"})
            if mktcap:
                extras.append({"항목": "시총", "값": _fmt_amount(mktcap, currency)})
            if vol:
                extras.append({"항목": "거래량", "값": f"{vol:,}"})

            return {
                "quarters":  [],
                "per":       "—",
                "pbr":       "—",
                "extras":    extras,
                "currency":  currency,
                "source":    f"Yahoo Finance (시세 기본, PER/PBR 조회 불가)",
                "yf_symbol": sym,
            }, ""
        except Exception as e:
            errors.append(f"v8 {base}: {type(e).__name__}: {str(e)[:80]}")
    return {}, " | ".join(errors)


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def fetch_financials(symbol: str, market: str) -> tuple[dict, list[str]]:
    """
    재무지표 조회. Returns: (result_dict, [error_messages])
    """
    all_errors: list[str] = []

    # ── 한국 주식 ──────────────────────────────────────────────────────────────
    if market == "KR":
        code = _resolve_kr_code(symbol)

        fin, err = _fetch_naver_mobile(code)
        if not fin:
            all_errors.append(f"[Naver 모바일] {err}")
            fin, err = _fetch_naver_summary(code)
            if not fin:
                all_errors.append(f"[Naver 요약] {err}")

        if fin:
            # 분기 실적 Yahoo v10 병행 시도
            try:
                session, crumb = _get_yf_session()
                for suffix in [".KS", ".KQ"]:
                    yf_fin, _ = _fetch_yahoo_v10(f"{code}{suffix}", session, crumb)
                    if yf_fin.get("quarters"):
                        fin["quarters"] = yf_fin["quarters"]
                        fin["source"] += " + Yahoo(분기)"
                        break
            except Exception:
                pass
            return fin, []

        session, crumb = _get_yf_session()
        for suffix in [".KS", ".KQ"]:
            fin, err = _fetch_yahoo_v10(f"{code}{suffix}", session, crumb)
            if fin:
                return fin, []
            all_errors.append(f"[Yahoo v10 {code}{suffix}] {err}")
        return {}, all_errors

    # ── 미국 주식 ──────────────────────────────────────────────────────────────
    sym = symbol.upper()
    session, crumb = _get_yf_session()

    # 1차: v7 + crumb (crumb 있으면 401 해결 가능)
    fin, err = _fetch_yahoo_v7(sym, session, crumb)
    if fin:
        # v10으로 분기 실적 추가 시도
        yf_fin, _ = _fetch_yahoo_v10(sym, session, crumb)
        if yf_fin.get("quarters"):
            fin["quarters"] = yf_fin["quarters"]
            fin["source"] += " + 분기실적"
        return fin, []
    all_errors.append(f"[Yahoo v7] {err}")

    # 2차: v10 quoteSummary + crumb
    fin, err = _fetch_yahoo_v10(sym, session, crumb)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v10] {err}")

    # 3차: v8 chart meta (항상 동작 — 현재가·52주범위·시총)
    fin, err = _fetch_yahoo_v8_meta(sym, session)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v8 meta] {err}")

    return {}, all_errors
