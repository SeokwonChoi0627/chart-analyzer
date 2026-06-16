import os

from core.backup import make_backup


def _make_db(path):
    with open(path, "wb") as f:
        f.write(b"sqlite-stub")


def test_make_backup_creates_timestamped_copy(tmp_path):
    db = tmp_path / "portfolio.db"
    _make_db(db)
    dst = make_backup(str(db))
    assert dst is not None
    assert os.path.exists(dst)
    assert os.path.basename(dst).startswith("portfolio_")
    assert dst.endswith(".db")


def test_make_backup_missing_db_returns_none(tmp_path):
    assert make_backup(str(tmp_path / "nope.db")) is None


def test_make_backup_prunes_to_keep(tmp_path):
    db = tmp_path / "portfolio.db"
    _make_db(db)
    backup_dir = tmp_path / "backups"
    for i in range(5):
        make_backup(str(db), backup_dir=str(backup_dir), keep=3,
                    stamp=f"20260101_0000{i}")
    remaining = sorted(p.name for p in backup_dir.glob("portfolio_*.db"))
    assert len(remaining) == 3
    # 가장 오래된 2개가 삭제되고 최신 3개가 남는다
    assert remaining == [
        "portfolio_20260101_00002.db",
        "portfolio_20260101_00003.db",
        "portfolio_20260101_00004.db",
    ]
