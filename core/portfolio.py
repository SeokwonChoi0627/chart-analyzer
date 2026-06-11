"""보유 종목 저장소: SQLite 기반 포지션 등록/삭제/조회.

같은 종목을 여러 행으로 등록할 수 있다 (분할 매수 = 매수 단가별 행).
"""
import sqlite3
from datetime import datetime

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT    NOT NULL,
    entry_price REAL    NOT NULL,
    quantity    REAL    NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
)
"""


class PortfolioStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def add(self, symbol: str, entry_price: float, quantity: float = 0.0) -> int:
        """포지션 등록. 등록된 행의 id 반환."""
        symbol = (symbol or "").strip()
        if not symbol:
            raise ValueError("종목을 입력하세요")
        if entry_price is None or entry_price <= 0:
            raise ValueError("매수가는 0보다 커야 합니다")
        if quantity is None or quantity < 0:
            raise ValueError("수량은 0 이상이어야 합니다")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO positions (symbol, entry_price, quantity, created_at) "
                "VALUES (?, ?, ?, ?)",
                (symbol, float(entry_price), float(quantity),
                 datetime.now().isoformat(timespec="seconds")),
            )
            return int(cur.lastrowid)

    def remove(self, position_id: int) -> None:
        """포지션 삭제. 없는 id면 무시."""
        with self._connect() as conn:
            conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))

    def list_positions(self) -> list[dict]:
        """등록 순서대로 전체 포지션 반환."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, symbol, entry_price, quantity, created_at "
                "FROM positions ORDER BY id"
            ).fetchall()
        return [
            {"id": r[0], "symbol": r[1], "entry_price": r[2],
             "quantity": r[3], "created_at": r[4]}
            for r in rows
        ]
