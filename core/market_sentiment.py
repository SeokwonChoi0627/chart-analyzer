"""시장 분위기 지표: 미국 10년물 국채금리 + CNN Fear & Greed Index."""
import requests
import pandas as pd


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


def fetch_fear_greed() -> dict:
    """CNN Fear & Greed Index 조회 (비공식 엔드포인트)."""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        fg = data.get("fear_and_greed", {})
        score  = fg.get("score")
        rating = fg.get("rating", "")
        if score is None:
            return {"score": None, "rating": "", "error": "파싱 실패"}
        return {"score": round(float(score), 1), "rating": rating, "error": None}
    except Exception as e:
        return {"score": None, "rating": "", "error": str(e)}


_RATING_KO = {
    "extreme fear":  "극단적 공포",
    "fear":          "공포",
    "neutral":       "중립",
    "greed":         "탐욕",
    "extreme greed": "극단적 탐욕",
}


def rating_ko(rating: str) -> str:
    return _RATING_KO.get(rating.lower(), rating)
