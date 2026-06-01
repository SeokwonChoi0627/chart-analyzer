import unicodedata
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from .base import DataProvider, OHLCV_COLUMNS


def _normalize(s: str) -> str:
    """NFC 정규화 + 공백 제거 — 환경별 한글 인코딩 차이 방지."""
    return unicodedata.normalize("NFC", s).strip()


class PykrxProvider(DataProvider):
    """한국 주식 무료 데이터 (FinanceDataReader). 종목코드 6자리 또는 종목명 입력 가능."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        symbol = _normalize(symbol)

        if not symbol.isdigit():
            ticker = self._name_to_ticker(symbol)
            if ticker is None:
                return pd.DataFrame(columns=OHLCV_COLUMNS)
            symbol = ticker

        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        try:
            raw = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except Exception:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

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
        name_nfc = _normalize(name)
        try:
            listing = fdr.StockListing("KRX")
            # Name 컬럼도 NFC 정규화해서 비교
            listing = listing.copy()
            listing["_name_nfc"] = listing["Name"].apply(
                lambda x: _normalize(str(x)) if pd.notna(x) else ""
            )

            # 1순위: 정확한 일치
            matched = listing[listing["_name_nfc"] == name_nfc]
            if not matched.empty:
                return matched.iloc[0]["Code"]

            # 2순위: 포함 검색 (예: "하이닉스" → "SK하이닉스")
            matched = listing[listing["_name_nfc"].str.contains(name_nfc, na=False, regex=False)]
            if not matched.empty:
                matched = matched.copy()
                matched["_len"] = matched["_name_nfc"].str.len()
                return matched.sort_values("_len").iloc[0]["Code"]

        except Exception:
            pass
        return None
