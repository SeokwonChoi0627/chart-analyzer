import sqlite3
import io
from datetime import date
import pandas as pd


class OhlcvCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv_cache (
                    symbol TEXT PRIMARY KEY,
                    saved_date TEXT NOT NULL,
                    payload BLOB NOT NULL
                )
            """)

    def save(self, symbol: str, df: pd.DataFrame) -> None:
        buf = io.BytesIO()
        df.to_pickle(buf)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ohlcv_cache (symbol, saved_date, payload) VALUES (?, ?, ?)",
                (symbol, date.today().isoformat(), buf.getvalue()),
            )

    def load(self, symbol: str, max_age_date: date) -> pd.DataFrame | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT saved_date, payload FROM ohlcv_cache WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        if row is None:
            return None
        saved_date, payload = row
        if saved_date != max_age_date.isoformat():
            return None
        return pd.read_pickle(io.BytesIO(payload))
