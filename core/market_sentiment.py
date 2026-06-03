"""시장 분위기 지표: 미국 10년물 국채금리 + CNN Fear & Greed Index."""
import requests


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
    """yfinance로 미국 10년물 국채금리(^TNX) 조회."""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^TNX")
        hist = ticker.history(period="5d")
        if hist.empty:
            return {"value": None, "error": "데이터 없음"}
        value = round(float(hist["Close"].iloc[-1]), 3)
        prev  = round(float(hist["Close"].iloc[-2]), 3) if len(hist) >= 2 else value
        return {"value": value, "prev": prev, "change": round(value - prev, 3), "error": None}
    except Exception as e:
        return {"value": None, "error": str(e)}


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
