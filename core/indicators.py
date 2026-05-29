import pandas as pd


def add_sma(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    """단순이동평균(SMA) 컬럼 추가. 원본 불변, 새 DataFrame 반환."""
    out = df.copy()
    for w in windows:
        out[f"sma{w}"] = out["close"].rolling(window=w).mean()
    return out


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI(0~100) 컬럼 추가. Wilder 평활(EMA) 방식. 원본 불변."""
    out = df.copy()
    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    out["rsi"] = 100 - (100 / (1 + rs))
    return out
