import pytest

from core.portfolio import PortfolioStore


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
