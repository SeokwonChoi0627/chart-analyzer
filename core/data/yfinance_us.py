import pandas as pd
import yfinance as yf
from .base import DataProvider, OHLCV_COLUMNS


class YFinanceProvider(DataProvider):
    """미국 주식 무료 데이터 (yfinance)."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        period = self._to_period(period_days)
        raw = yf.Ticker(symbol).history(period=period, interval="1d")
        if raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        raw = raw.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        out = raw[OHLCV_COLUMNS].copy()
        out.index = pd.to_datetime(out.index).tz_localize(None)
        out.index.name = None
        return out.sort_index()

    @staticmethod
    def _to_period(days: int) -> str:
        if days <= 95:
            return "3mo"
        if days <= 190:
            return "6mo"
        return "1y"
