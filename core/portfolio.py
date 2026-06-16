"""보유 종목 저장소: SQLAlchemy 기반 포지션 등록/삭제/조회 + 변경 이력.

같은 종목을 여러 행으로 등록할 수 있다 (분할 매수 = 매수 단가별 행).

백엔드 이중화:
- 로컬: SQLite 파일 (경로 문자열을 그대로 넘기면 sqlite로 동작)
- 웹(Streamlit Cloud): Supabase Postgres (postgresql+psycopg2://... URL)
  Streamlit Cloud는 디스크가 휘발성이라 SQLite 파일은 재시작 시 사라진다.
  외부 Postgres에 저장해야 영구 보존된다.

스키마 격리:
- 기존 Supabase 프로젝트를 공유할 때, 전용 스키마(예: chart_analyzer)로
  테이블을 완전 정규화(`chart_analyzer.positions`)해 다른 앱 테이블과 분리한다.
  Transaction 풀러(pgbouncer)에서도 안전하도록 search_path에 의존하지 않는다.

데이터 유실 방어:
- `position_history` 테이블에 모든 add/remove/import 이벤트를 영구 기록한다.
  포지션을 지워도 이력은 남는다 (Postgres에서는 재시작에도 생존).
- SQLite 로컬 모드에서는 `history.jsonl`(append-only)에도 같은 이벤트를 남긴다.
"""
import json
import os
import re
from datetime import datetime

from sqlalchemy import (
    Column, Float, Integer, MetaData, String, Table,
    create_engine, delete, insert, select, text,
)
from sqlalchemy.pool import NullPool

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _build_tables(schema: str | None) -> tuple[MetaData, Table, Table]:
    """주어진 스키마에 묶인 테이블 정의를 만든다 (schema=None이면 기본 스키마)."""
    md = MetaData()
    pos = Table(
        "positions", md,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("symbol", String, nullable=False),
        Column("entry_price", Float, nullable=False),
        Column("quantity", Float, nullable=False, server_default="0"),
        Column("created_at", String, nullable=False),
        schema=schema,
    )
    hist = Table(
        "position_history", md,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("action", String, nullable=False),    # 'add' | 'remove' | 'import'
        Column("position_id", Integer),
        Column("symbol", String, nullable=False),
        Column("entry_price", Float, nullable=False),
        Column("quantity", Float, nullable=False, server_default="0"),
        Column("recorded_at", String, nullable=False),
        schema=schema,
    )
    return md, pos, hist


def _resolve(conn: str) -> tuple[str, str | None]:
    """접속 문자열을 (SQLAlchemy URL, jsonl 로그 경로 또는 None)로 변환.

    '://'가 없으면 로컬 SQLite 파일 경로로 간주한다.
    """
    if "://" not in conn:
        path = os.path.abspath(conn)
        log = os.path.join(os.path.dirname(path) or ".", "history.jsonl")
        return f"sqlite:///{path}", log
    if conn.startswith("sqlite:///"):
        path = conn[len("sqlite:///"):]
        log = os.path.join(os.path.dirname(path) or ".", "history.jsonl")
        return conn, log
    return conn, None  # Postgres 등 — 외부 jsonl 없음 (history 테이블이 영구 기록)


class PortfolioStore:
    def __init__(self, conn: str, schema: str | None = None):
        url, self._log_path = _resolve(conn)
        is_pg = url.startswith("postgresql")
        # 스키마 격리는 Postgres에서만 의미가 있다 (기존 프로젝트 테이블과 분리)
        self._schema = schema if (is_pg and schema) else None
        if self._schema and not _IDENT_RE.match(self._schema):
            raise ValueError(f"잘못된 스키마 이름: {self._schema}")

        self._md, self._positions, self._history = _build_tables(self._schema)
        self._engine = create_engine(url, poolclass=NullPool, future=True)

        if self._schema:
            with self._engine.begin() as c:
                c.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}"'))
        self._md.create_all(self._engine)

    def add(self, symbol: str, entry_price: float, quantity: float = 0.0) -> int:
        """포지션 등록. 등록된 행의 id 반환."""
        symbol = (symbol or "").strip()
        if not symbol:
            raise ValueError("종목을 입력하세요")
        if entry_price is None or entry_price <= 0:
            raise ValueError("매수가는 0보다 커야 합니다")
        if quantity is None or quantity < 0:
            raise ValueError("수량은 0 이상이어야 합니다")
        with self._engine.begin() as conn:
            pid = self._insert(conn, symbol, float(entry_price), float(quantity))
            self._record(conn, "add", pid, symbol,
                         float(entry_price), float(quantity))
            return pid

    def remove(self, position_id: int) -> None:
        """포지션 삭제. 없는 id면 무시. 삭제된 경우 이력 기록."""
        pos = self._positions
        with self._engine.begin() as conn:
            row = conn.execute(
                select(pos.c.symbol, pos.c.entry_price, pos.c.quantity)
                .where(pos.c.id == position_id)
            ).first()
            if row is None:
                return
            conn.execute(delete(pos).where(pos.c.id == position_id))
            self._record(conn, "remove", position_id, row[0], row[1], row[2])

    def import_positions(self, items: list[dict], replace: bool = False) -> int:
        """여러 포지션을 일괄 등록(복원). replace=True면 기존 포지션 전체 교체.

        각 항목은 {"symbol", "entry_price", "quantity"} 형태. 등록 건수 반환.
        이력에는 action='import'로 남는다 (replace 여부와 무관하게 영구 보존).
        """
        count = 0
        with self._engine.begin() as conn:
            if replace:
                conn.execute(delete(self._positions))
            for p in items:
                symbol = (p.get("symbol") or "").strip()
                entry_price = p.get("entry_price")
                quantity = p.get("quantity") or 0.0
                if not symbol or entry_price is None or float(entry_price) <= 0:
                    continue
                pid = self._insert(conn, symbol,
                                   float(entry_price), float(quantity))
                self._record(conn, "import", pid, symbol,
                             float(entry_price), float(quantity))
                count += 1
        return count

    def list_positions(self) -> list[dict]:
        """등록 순서대로 전체 포지션 반환."""
        pos = self._positions
        with self._engine.connect() as conn:
            rows = conn.execute(select(pos).order_by(pos.c.id)).fetchall()
        return [
            {"id": r.id, "symbol": r.symbol, "entry_price": r.entry_price,
             "quantity": r.quantity, "created_at": r.created_at}
            for r in rows
        ]

    def history(self, limit: int = 200) -> list[dict]:
        """변경 이력을 최신순으로 반환."""
        h = self._history
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(h).order_by(h.c.id.desc()).limit(limit)
            ).fetchall()
        return [
            {"id": r.id, "action": r.action, "position_id": r.position_id,
             "symbol": r.symbol, "entry_price": r.entry_price,
             "quantity": r.quantity, "recorded_at": r.recorded_at}
            for r in rows
        ]

    # ── 내부 헬퍼 ────────────────────────────────────────────────────

    def _insert(self, conn, symbol: str, entry_price: float,
                quantity: float) -> int:
        result = conn.execute(
            insert(self._positions).values(
                symbol=symbol, entry_price=entry_price, quantity=quantity,
                created_at=datetime.now().isoformat(timespec="seconds"),
            )
        )
        return int(result.inserted_primary_key[0])

    def _record(self, conn, action: str, position_id: int, symbol: str,
                entry_price: float, quantity: float) -> None:
        recorded_at = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            insert(self._history).values(
                action=action, position_id=position_id, symbol=symbol,
                entry_price=entry_price, quantity=quantity,
                recorded_at=recorded_at,
            )
        )
        self._append_log({
            "action": action, "position_id": position_id, "symbol": symbol,
            "entry_price": entry_price, "quantity": quantity,
            "recorded_at": recorded_at,
        })

    def _append_log(self, entry: dict) -> None:
        """외부 append-only 로그 (SQLite 로컬 모드 전용). 실패해도 앱 안 막음."""
        if not self._log_path:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
