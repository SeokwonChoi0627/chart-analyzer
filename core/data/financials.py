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
import unicodedata
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 한글 종목명 정적 맵 (네트워크 없이 즉시 변환) ─────────────────────────────
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
    "sk케미칼": "285130", "금호석유": "011780",
    "키움증권": "039490", "미래에셋증권": "006800",
}

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
_YF_MODULES = (
    "incomeStatementHistoryQuarterly,"
    "defaultKeyStatistics,"
    "financialData,"
    "summaryDetail,"
    "price"
)
_YF_QUOTE_URLS = [
    "https://finance.yahoo.com/quote/{sym}",
]


# ── 공통 유틸 ─────────────────────────────────────────────────────────────────

def _resolve_kr_code(symbol: str) -> str:
    """한글 종목명 → 6자리 코드. import 없이 독립 동작."""
    s = symbol.strip()
    if s.isdigit():
        return s
    key = unicodedata.normalize("NFC", s).strip().lower()
    # 1순위: 정적 맵
    if key in _KR_CODE_MAP:
        return _KR_CODE_MAP[key]
    for name, code in _KR_CODE_MAP.items():
        if key in name:
            return code
    # 2순위: FDR (실패해도 원본 반환)
    try:
        import FinanceDataReader as fdr
        import pandas as pd
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


def _fmt_ratio(v) -> str:
    try:
        return f"{float(str(v).replace(',', '')):.1f}배" if v else "—"
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
    company_name = str(data.get("stockName") or data.get("name") or "")
    return {
        "quarters":     [],
        "per":          _fmt_ratio(per_v),
        "pbr":          _fmt_ratio(pbr_v),
        "extras":       extras,
        "currency":     "KRW",
        "company_name": company_name,
        "source":       "Naver Finance",
        "yf_symbol":    f"{code}.KS",
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
            # ── 각 모듈 헬퍼 ──────────────────────────────────────────────
            def _raw(d: dict, key: str):
                v = d.get(key)
                return v.get("raw") if isinstance(v, dict) else v

            ks = r.get("defaultKeyStatistics") or {}
            fd = r.get("financialData") or {}
            sd = r.get("summaryDetail") or {}

            def _ks(k): return _raw(ks, k)
            def _fd(k): return _raw(fd, k)
            def _sd(k): return _raw(sd, k)

            def _pct(v):   return f"{v * 100:.1f}%" if v is not None else None
            def _x(v):     return f"{v:.1f}배" if v is not None else None
            def _price(v): return f"${v:,.2f}" if v is not None else None

            # 밸류에이션
            per_r    = _ks("trailingPE") or _sd("trailingPE")
            fpe_r    = _ks("forwardPE")  or _sd("forwardPE")
            pbr_r    = _ks("priceToBook")
            eps_r    = _ks("trailingEps")
            feps_r   = _ks("forwardEps")
            peg_r    = _ks("pegRatio")
            div_r    = _sd("dividendYield")
            tgt_r    = _fd("targetMeanPrice")
            rec_key  = fd.get("recommendationKey") or ""
            rec_n    = _fd("numberOfAnalystOpinions")

            _REC = {"buy":"매수","strongBuy":"강력매수","hold":"중립",
                    "sell":"매도","strongSell":"강력매도"}
            rec_str = _REC.get(rec_key, rec_key)
            if rec_n: rec_str += f" ({int(rec_n)}명)"

            valuation: dict[str, str] = {}
            if per_r:  valuation["PER(후행)"]  = _x(per_r)
            if fpe_r:  valuation["PER(선행)"]  = _x(fpe_r)
            if pbr_r:  valuation["PBR"]         = _x(pbr_r)
            if peg_r:  valuation["PEG"]         = f"{peg_r:.2f}"
            if eps_r:  valuation["EPS(후행)"]   = _price(eps_r) if currency != "KRW" else f"{eps_r:,.0f}원"
            if feps_r: valuation["EPS(선행)"]   = _price(feps_r) if currency != "KRW" else f"{feps_r:,.0f}원"
            if div_r:  valuation["배당수익률"]   = _pct(div_r)
            if tgt_r:  valuation["목표주가"]     = _price(tgt_r) if currency != "KRW" else f"{tgt_r:,.0f}원"
            if rec_str: valuation["투자의견"]   = rec_str

            # 수익성
            roe_r  = _fd("returnOnEquity")
            roa_r  = _fd("returnOnAssets")
            opm_r  = _fd("operatingMargins")
            npm_r  = _fd("profitMargins")
            rev_g  = _fd("revenueGrowth")
            earn_g = _fd("earningsGrowth")
            fcf_r  = _fd("freeCashflow")

            profitability: dict[str, str] = {}
            if roe_r:  profitability["ROE"]           = _pct(roe_r)
            if roa_r:  profitability["ROA"]           = _pct(roa_r)
            if opm_r:  profitability["영업이익률"]     = _pct(opm_r)
            if npm_r:  profitability["순이익률"]       = _pct(npm_r)
            if rev_g:  profitability["매출성장(YoY)"]  = _pct(rev_g)
            if earn_g: profitability["이익성장(YoY)"]  = _pct(earn_g)
            if fcf_r:  profitability["잉여현금흐름"]    = _fmt_amount(fcf_r, currency)

            # 시장 정보
            mktcap_r = _sd("marketCap") or _raw(r.get("price") or {}, "marketCap")
            beta_r   = _ks("beta") or _sd("beta")
            high52_r = _sd("fiftyTwoWeekHigh")
            low52_r  = _sd("fiftyTwoWeekLow")
            cr_r     = _fd("currentRatio")
            de_r     = _fd("debtToEquity")

            market: dict[str, str] = {}
            if mktcap_r: market["시가총액"]  = _fmt_amount(mktcap_r, currency)
            if beta_r:   market["베타"]      = f"{beta_r:.2f}"
            if high52_r: market["52주 최고"] = _price(high52_r) if currency != "KRW" else f"{high52_r:,.0f}원"
            if low52_r:  market["52주 최저"] = _price(low52_r)  if currency != "KRW" else f"{low52_r:,.0f}원"
            if cr_r:     market["유동비율"]  = f"{cr_r:.2f}"
            if de_r:     market["부채비율"]  = f"{de_r:.1f}%"

            if not quarters and not valuation and not market:
                errors.append(f"v10 {url}: 유효 데이터 없음")
                continue

            return {
                "quarters":      quarters,
                "valuation":     valuation,
                "profitability": profitability,
                "market":        market,
                "per":           f"{per_r:.1f}배" if per_r else "—",
                "pbr":           f"{pbr_r:.1f}배" if pbr_r else "—",
                "extras":        [],
                "currency":      currency,
                "source":        "Yahoo Finance",
                "yf_symbol":     yf_sym,
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


# ── Yahoo Finance HTML 파싱 (crumb 불필요, 주요 지표 추출) ───────────────────────

def _fetch_yahoo_html(sym: str, session: requests.Session) -> tuple[dict, str]:
    """
    finance.yahoo.com 페이지 HTML에서 직접 재무지표 추출.
    crumb/쿠키 불필요 — SSL MITM 환경에서도 동작.
    PER·PBR·시총·EPS·배당률·매출(TTM) 등 반환.
    """
    import re as _re

    url = f"https://finance.yahoo.com/quote/{sym}"
    try:
        resp = session.get(url, timeout=15, verify=False,
                           headers={**_HEADERS_YF, "Accept": "text/html,application/xhtml+xml,*/*"})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        return {}, f"HTML fetch {sym}: {type(e).__name__}: {e}"

    def _extract(key: str) -> float | None:
        # escaped JSON: \"key\":{\"raw\":12.34
        m = _re.search(rf'\\"(?:{key})\\".*?\\"raw\\":([\d.eE+\-]+)', text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        # unescaped JSON: "key":{"raw":12.34
        m2 = _re.search(rf'"{key}"\s*:\s*\{{"raw"\s*:\s*([\d.eE+\-]+)', text)
        if m2:
            try:
                return float(m2.group(1))
            except ValueError:
                pass
        return None

    def _extract_str(key: str) -> str | None:
        # HTML tag: <fin-streamer data-field="key">value</fin-streamer>
        m = _re.search(
            rf'data-field="{key}"[^>]*class="[^"]*"[^>]*>([^<]+)<',
            text,
        )
        if m:
            return m.group(1).strip()
        return None

    # 회사명
    name_m = _re.search(r'<h1[^>]*class="[^"]*yf-xxbei9[^"]*"[^>]*>([^<]+)</h1>', text)
    company_name = name_m.group(1).strip() if name_m else ""

    per_r  = _extract("trailingPE")
    fpe_r  = _extract("forwardPE")
    pbr_r  = _extract("priceToBook")
    eps_r  = _extract("trailingEps")
    div_r  = _extract("dividendYield")
    cap_r  = _extract("marketCap")
    rev_r  = _extract("totalRevenue")
    npm_r  = _extract("profitMargins")
    beta_r = _extract("beta")
    h52_r  = _extract("fiftyTwoWeekHigh")
    l52_r  = _extract("fiftyTwoWeekLow")

    if not per_r and not cap_r and not pbr_r:
        return {}, f"HTML {sym}: 재무지표 없음 (page len={len(text)})"

    def _x(v):     return f"{v:.1f}배" if v is not None else None
    def _pct(v):   return f"{v * 100:.2f}%" if v is not None else None
    def _price(v): return f"${v:,.2f}" if v is not None else None

    valuation: dict[str, str] = {}
    if per_r:  valuation["PER(후행)"] = _x(per_r)
    if fpe_r:  valuation["PER(선행)"] = _x(fpe_r)
    if pbr_r:  valuation["PBR"]       = _x(pbr_r)
    if eps_r:  valuation["EPS"]       = _price(eps_r)
    if div_r:  valuation["배당수익률"] = _pct(div_r)

    profitability: dict[str, str] = {}
    if npm_r:  profitability["순이익률"] = _pct(npm_r)
    if rev_r:  profitability["연매출(TTM)"] = _fmt_amount(rev_r, "USD")

    market: dict[str, str] = {}
    if cap_r:  market["시가총액"]  = _fmt_amount(cap_r, "USD")
    if beta_r: market["베타"]      = f"{beta_r:.2f}"
    if h52_r:  market["52주 최고"] = _price(h52_r)
    if l52_r:  market["52주 최저"] = _price(l52_r)

    return {
        "quarters":      [],
        "valuation":     valuation,
        "profitability": profitability,
        "market":        market,
        "per":           _x(per_r) or "—",
        "pbr":           _x(pbr_r) or "—",
        "extras":        [],
        "currency":      "USD",
        "company_name":  company_name,
        "source":        "Yahoo Finance",
        "yf_symbol":     sym,
    }, ""


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
            company_name = meta.get("longName") or meta.get("shortName") or sym

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
                "quarters":    [],
                "per":         "—",
                "pbr":         "—",
                "extras":      extras,
                "currency":    currency,
                "company_name": company_name,
                "source":      "Yahoo Finance (시세 기본, PER/PBR 조회 불가)",
                "yf_symbol":   sym,
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

        # 코드가 여전히 한글이면 변환 실패 — 빈 코드 경고
        if not code.isdigit():
            all_errors.append(f"[코드변환] '{symbol}' → 코드 변환 실패, 6자리 코드로 입력하세요")
            return {}, all_errors

        session = requests.Session()
        session.headers.update(_HEADERS_YF)

        # 1차: Naver 모바일
        fin, err = _fetch_naver_mobile(code)
        if not fin:
            all_errors.append(f"[Naver 모바일] {err}")
            # 2차: Naver 요약
            fin, err = _fetch_naver_summary(code)
            if not fin:
                all_errors.append(f"[Naver 요약] {err}")

        if fin:
            # Yahoo v10 분기 실적 병행 시도
            try:
                _, crumb = _get_yf_session()
                for suffix in [".KS", ".KQ"]:
                    yf_fin, _ = _fetch_yahoo_v10(f"{code}{suffix}", session, crumb)
                    if yf_fin.get("quarters"):
                        fin["quarters"] = yf_fin["quarters"]
                        fin["source"] += " + Yahoo(분기)"
                        break
            except Exception:
                pass
            return fin, []

        # 3차: Yahoo v8 chart meta (인증 불필요 — 서버에서도 항상 동작)
        for suffix in [".KS", ".KQ"]:
            fin, err = _fetch_yahoo_v8_meta(f"{code}{suffix}", session)
            if fin:
                fin["source"] = f"Yahoo Finance (시세만, Naver 조회 실패)"
                return fin, []
            all_errors.append(f"[Yahoo v8 {code}{suffix}] {err}")

        return {}, all_errors

    # ── 미국 주식 ──────────────────────────────────────────────────────────────
    from .yfinance_us import resolve_us_symbol
    sym = resolve_us_symbol(symbol)
    session, crumb = _get_yf_session()

    # 1차: HTML 파싱 (crumb 불필요 — SSL MITM 환경에서도 동작)
    fin, err = _fetch_yahoo_html(sym, session)
    if fin:
        # v8에서 종목명 보완 (HTML 파싱 실패 시 대비)
        if not fin.get("company_name"):
            v8fin, _ = _fetch_yahoo_v8_meta(sym, session)
            fin["company_name"] = v8fin.get("company_name", "")
        return fin, []
    all_errors.append(f"[Yahoo HTML] {err}")

    # 2차: v10 quoteSummary + crumb
    fin, err = _fetch_yahoo_v10(sym, session, crumb)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v10] {err}")

    # 3차: v7 + crumb
    fin, err = _fetch_yahoo_v7(sym, session, crumb)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v7] {err}")

    # 4차: v8 chart meta (현재가·52주범위·시총만)
    fin, err = _fetch_yahoo_v8_meta(sym, session)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v8 meta] {err}")

    return {}, all_errors
