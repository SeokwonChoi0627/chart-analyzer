"""시장 분위기 지표: 미국 10년물 국채금리 + CNN Fear & Greed + 주요 지수 브리프."""
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _yahoo_chart_closes(symbol: str, range_: str = "3mo",
                        interval: str = "1d") -> tuple[list[float], str]:
    """Yahoo v8 chart API에서 종가 목록 조회.

    yfinance(curl-cffi)는 사내망 SSL MITM에서 인증서 오류로 실패하므로
    requests 직접 호출 + verify=False 폴백 사용 (intraday/financials와 동일 패턴).
    """
    errors: list[str] = []
    for base in ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"):
        url = f"{base}/v8/finance/chart/{symbol}"
        params = {"interval": interval, "range": range_}
        for verify in (True, False):
            try:
                resp = requests.get(url, params=params, timeout=8,
                                    headers=_YF_HEADERS, verify=verify)
                resp.raise_for_status()
                result = (resp.json().get("chart") or {}).get("result") or []
                if not result:
                    errors.append(f"{base}: result 없음")
                    break
                quote = (result[0].get("indicators", {}).get("quote") or [{}])[0]
                closes = [c for c in (quote.get("close") or []) if c is not None]
                if closes:
                    return closes, ""
                errors.append(f"{base}: close 없음")
                break
            except requests.exceptions.SSLError:
                continue  # verify=False로 재시도
            except Exception as e:
                errors.append(f"{base}: {type(e).__name__}: {str(e)[:60]}")
                break
    return [], " | ".join(errors[:3]) or "SSL 오류"


_CNN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://edition.cnn.com",
}

_CNN_URLS = [
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/current",
]


def fetch_10y_yield() -> dict:
    """미국 10년물 국채금리(^TNX) 조회 — Yahoo v8 REST (yfinance 미사용)."""
    closes, err = _yahoo_chart_closes("^TNX", range_="5d")
    if not closes:
        return {"value": None, "error": err or "데이터 없음"}
    value = round(float(closes[-1]), 3)
    prev = round(float(closes[-2]), 3) if len(closes) >= 2 else value
    return {"value": value, "prev": prev, "change": round(value - prev, 3), "error": None}


# ── 주요 지수 브리프 (KOSPI · NASDAQ) ────────────────────────────────────────

def _brief_from_closes(closes: list[float]) -> dict | None:
    """종가 목록으로 지수 간이 분석: 현재값·등락률·20일선 위치·단기 흐름."""
    if not closes or len(closes) < 21:
        return None
    value = float(closes[-1])
    prev = float(closes[-2])
    change_pct = round((value / prev - 1) * 100, 2) if prev else 0.0
    sma20 = sum(closes[-20:]) / 20
    ret5 = (value / float(closes[-6]) - 1) * 100 if len(closes) >= 6 else 0.0
    above = value >= sma20

    if above and ret5 >= 0:
        note = "20일선 위 · 단기 상승 흐름"
    elif above:
        note = "20일선 위 · 단기 숨고르기"
    elif ret5 > 0:
        note = "20일선 아래 · 반등 시도"
    else:
        note = "20일선 아래 · 조정 구간"

    return {
        "value":       round(value, 2),
        "change_pct":  change_pct,
        "sma20":       round(sma20, 2),
        "above_sma20": above,
        "note":        note,
    }


def fetch_index_brief(symbol: str, name: str) -> dict:
    """지수 간이 분석 조회. 실패 시 {name, value: None, error}."""
    closes, err = _yahoo_chart_closes(symbol, range_="3mo")
    brief = _brief_from_closes(closes)
    if brief is None:
        return {"name": name, "value": None, "error": err or "데이터 부족"}
    return {"name": name, **brief, "error": None}


def _parse_fg(data: dict) -> dict | None:
    """CNN JSON에서 score/rating 추출. 구조가 다를 수 있어 두 경로 모두 시도."""
    # graphdata 형식: {"fear_and_greed": {"score": ..., "rating": ...}}
    fg = data.get("fear_and_greed") or data.get("fearAndGreed") or data
    if isinstance(fg, dict):
        score = fg.get("score") or fg.get("now", {}).get("score") if isinstance(fg.get("now"), dict) else fg.get("score")
        rating = fg.get("rating") or fg.get("now", {}).get("rating", "") if isinstance(fg.get("now"), dict) else fg.get("rating", "")
        if score is not None:
            return {"score": round(float(score), 1), "rating": str(rating), "error": None}
    return None


def fetch_fear_greed() -> dict:
    """CNN Fear & Greed Index 조회. 여러 엔드포인트 순차 시도."""
    last_err = "알 수 없는 오류"
    for url in _CNN_URLS:
        try:
            resp = requests.get(url, timeout=8, headers=_CNN_HEADERS)
            resp.raise_for_status()
            result = _parse_fg(resp.json())
            if result:
                return result
            last_err = "파싱 실패"
        except Exception as e:
            last_err = str(e)
    return {"score": None, "rating": "", "error": last_err}


_RATING_KO = {
    "extreme fear":  "극단적 공포",
    "fear":          "공포",
    "neutral":       "중립",
    "greed":         "탐욕",
    "extreme greed": "극단적 탐욕",
}


def rating_ko(rating: str) -> str:
    return _RATING_KO.get(rating.lower(), rating)
