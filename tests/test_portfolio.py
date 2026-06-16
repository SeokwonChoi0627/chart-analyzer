import pytest

from core.portfolio import PortfolioStore, _resolve


@pytest.fixture
def store(tmp_path):
    return PortfolioStore(str(tmp_path / "portfolio.db"))


def test_add_and_list_position(store):
    pid = store.add("삼성전자", entry_price=270000, quantity=10)
    rows = store.list_positions()
    assert len(rows) == 1
    assert rows[0]["id"] == pid
    assert rows[0]["symbol"] == "삼성전자"
    assert rows[0]["entry_price"] == 270000
    assert rows[0]["quantity"] == 10


def test_quantity_optional_defaults_zero(store):
    store.add("AAPL", entry_price=210.5)
    assert store.list_positions()[0]["quantity"] == 0


def test_same_symbol_multiple_lots_allowed(store):
    """분할 매수: 같은 종목 여러 행 등록 가능."""
    store.add("삼성전자", entry_price=270000)
    store.add("삼성전자", entry_price=290000)
    assert len(store.list_positions()) == 2


def test_remove_position(store):
    pid = store.add("AAPL", entry_price=210.5)
    store.add("TSLA", entry_price=300.0)
    store.remove(pid)
    rows = store.list_positions()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "TSLA"


def test_remove_nonexistent_id_is_noop(store):
    store.add("AAPL", entry_price=210.5)
    store.remove(99999)
    assert len(store.list_positions()) == 1


def test_invalid_inputs_rejected(store):
    with pytest.raises(ValueError):
        store.add("", entry_price=100)
    with pytest.raises(ValueError):
        store.add("AAPL", entry_price=0)
    with pytest.raises(ValueError):
        store.add("AAPL", entry_price=-10)


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "portfolio.db")
    PortfolioStore(path).add("AAPL", entry_price=210.5)
    assert len(PortfolioStore(path).list_positions()) == 1


# ── 변경 이력 (audit) ────────────────────────────────────────────────


def test_add_records_history(store):
    store.add("AAPL", entry_price=210.5, quantity=3)
    hist = store.history()
    assert len(hist) == 1
    assert hist[0]["action"] == "add"
    assert hist[0]["symbol"] == "AAPL"
    assert hist[0]["entry_price"] == 210.5
    assert hist[0]["quantity"] == 3


def test_remove_records_history(store):
    pid = store.add("AAPL", entry_price=210.5)
    store.remove(pid)
    actions = [h["action"] for h in store.history()]
    assert actions == ["remove", "add"]  # 최신순


def test_history_survives_position_deletion(store):
    """포지션을 삭제해도 이력은 영구 보존된다 (핵심: 조용한 유실 방지)."""
    pid = store.add("삼성전자", entry_price=70000, quantity=5)
    store.remove(pid)
    assert store.list_positions() == []
    hist = store.history()
    assert any(h["action"] == "add" and h["symbol"] == "삼성전자" for h in hist)
    assert any(h["action"] == "remove" and h["symbol"] == "삼성전자" for h in hist)


def test_remove_nonexistent_records_no_history(store):
    store.add("AAPL", entry_price=210.5)
    store.remove(99999)
    assert [h["action"] for h in store.history()] == ["add"]


def test_import_positions_replace(store):
    store.add("OLD", entry_price=100)
    n = store.import_positions(
        [{"symbol": "AAPL", "entry_price": 210.5, "quantity": 10},
         {"symbol": "삼성전자", "entry_price": 70000, "quantity": 5}],
        replace=True,
    )
    assert n == 2
    symbols = {p["symbol"] for p in store.list_positions()}
    assert symbols == {"AAPL", "삼성전자"}


def test_import_positions_logs_history(store):
    store.import_positions(
        [{"symbol": "AAPL", "entry_price": 210.5, "quantity": 10}], replace=True)
    assert any(h["action"] == "import" for h in store.history())


def test_external_log_appended(tmp_path):
    path = str(tmp_path / "portfolio.db")
    store = PortfolioStore(path)
    store.add("AAPL", entry_price=210.5)
    log_path = tmp_path / "history.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"AAPL"' in lines[0]


def test_external_log_survives_db_reset(tmp_path):
    """DB 파일을 지워도(롤백 시뮬레이션) 외부 로그는 남아있다."""
    path = tmp_path / "portfolio.db"
    store = PortfolioStore(str(path))
    store.add("AAPL", entry_price=210.5)
    store.add("삼성전자", entry_price=70000)
    path.unlink()  # DB 파일 통째 유실
    log_path = tmp_path / "history.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # 외부 로그는 그대로


# ── 이중 백엔드 (로컬 SQLite / 웹 Postgres) ──────────────────────────


def test_resolve_bare_path_is_sqlite(tmp_path):
    url, log = _resolve(str(tmp_path / "portfolio.db"))
    assert url.startswith("sqlite:///")
    assert log.endswith("history.jsonl")


def test_resolve_postgres_url_has_no_jsonl():
    url, log = _resolve(
        "postgresql+psycopg2://user:pw@host.pooler.supabase.com:6543/postgres")
    assert url.startswith("postgresql")
    assert log is None  # Postgres는 history 테이블이 영구 기록 역할


def test_store_accepts_sqlite_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'p.db'}"
    store = PortfolioStore(url)
    store.add("AAPL", entry_price=210.5)
    assert len(store.list_positions()) == 1


def test_schema_ignored_for_sqlite(tmp_path):
    """schema 인자는 SQLite에선 무시되고 정상 동작한다."""
    store = PortfolioStore(str(tmp_path / "p.db"), schema="chart_analyzer")
    store.add("AAPL", entry_price=210.5)
    assert len(store.list_positions()) == 1


def test_invalid_schema_rejected(tmp_path):
    with pytest.raises(ValueError):
        PortfolioStore(
            "postgresql+psycopg2://u:p@h:6543/db", schema="bad; DROP TABLE")
