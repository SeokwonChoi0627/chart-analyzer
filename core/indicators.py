import pandas as pd


def add_sma(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    """단순이동평균(SMA) 컬럼 추가. 원본 불변, 새 DataFrame 반환."""
    out = df.copy()
    for w in windows:
        out[f"sma{w}"] = out["close"].rolling(window=w).mean()
    return out
