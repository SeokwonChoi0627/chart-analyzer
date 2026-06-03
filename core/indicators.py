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


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD/시그널/히스토그램 컬럼 추가. 원본 불변."""
    out = df.copy()
    ema_fast = out["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = out["close"].ewm(span=slow, adjust=False).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out


def add_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """볼린저밴드(중심/상단/하단) 컬럼 추가. 원본 불변."""
    out = df.copy()
    mid = out["close"].rolling(window=window).mean()
    std = out["close"].rolling(window=window).std()
    out["bb_mid"] = mid
    out["bb_upper"] = mid + num_std * std
    out["bb_lower"] = mid - num_std * std
    return out


def add_volume_ratio(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """당일 거래량 / 직전 window일 평균 거래량(당일 제외) 비율. 원본 불변."""
    out = df.copy()
    prev_avg = out["volume"].rolling(window=window).mean().shift(1)
    out["vol_ratio"] = out["volume"] / prev_avg
    return out


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ATR(Average True Range) 컬럼 추가. 원본 불변."""
    out = df.copy()
    high = out["high"]
    low  = out["low"]
    prev_close = out["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return out


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """모든 지표를 순서대로 적용한 DataFrame 반환. 원본 불변."""
    out = add_sma(df, windows=(5, 20, 60))
    out = add_rsi(out, period=14)
    out = add_macd(out, fast=12, slow=26, signal=9)
    out = add_bollinger(out, window=20, num_std=2.0)
    out = add_volume_ratio(out, window=20)
    out = add_atr(out, period=14)
    return out
