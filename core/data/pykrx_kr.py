from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from .base import DataProvider, OHLCV_COLUMNS


class PykrxProvider(DataProvider):
    """한국 주식 무료 데이터 (FinanceDataReader). 종목코드 6자리 또는 종목명 입력 가능."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        if not symbol.isdigit():
            ticker = self._name_to_ticker(symbol)
            if ticker is None:
                return pd.DataFrame(columns=OHLCV_COLUMNS)
            symbol = ticker
        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        raw = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if raw is None or raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        raw = raw.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        out = raw[OHLCV_COLUMNS].copy()
        out.index = pd.to_datetime(out.index)
        out.index.name = None
        return out.sort_index()

    @staticmethod
    def _name_to_ticker(name: str) -> str | None:
        try:
            listing = fdr.StockListing("KRX")
            # 1순위: 정확한 일치
            matched = listing[listing["Name"] == name]
            if not matched.empty:
                return matched.iloc[0]["Code"]
            # 2순위: 포함 검색 (예: "하이닉스" → "SK하이닉스")
            matched = listing[listing["Name"].str.contains(name, na=False)]
            if not matched.empty:
                # 이름이 짧을수록 더 정확한 매칭 → 최단 이름 우선
                matched = matched.copy()
                matched["_len"] = matched["Name"].str.len()
                return matched.sort_values("_len").iloc[0]["Code"]
        except Exception:
            pass
        return None
