"""포트폴리오 DB 자동 백업: 시작 시 스냅샷 + 오래된 백업 정리.

DB 파일이 통째로 롤백/유실되는 사고에 대비해, 타임스탬프가 찍힌
복사본을 남긴다. 최근 `keep`개만 유지한다.
"""
import glob
import os
import shutil
from datetime import datetime

_PREFIX = "portfolio_"


def make_backup(db_path: str, backup_dir: str | None = None,
                keep: int = 30, stamp: str | None = None) -> str | None:
    """DB 파일을 타임스탬프 복사본으로 백업하고 경로를 반환.

    DB 파일이 없으면 None. 백업 실패는 앱을 막지 않도록 None 반환.
    `stamp`는 테스트용 고정 타임스탬프 주입구.
    """
    if not os.path.exists(db_path):
        return None
    backup_dir = backup_dir or os.path.join(
        os.path.dirname(db_path) or ".", "backups")
    try:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(backup_dir, f"{_PREFIX}{stamp}.db")
        shutil.copy2(db_path, dst)
        _prune(backup_dir, keep)
        return dst
    except OSError:
        return None


def _prune(backup_dir: str, keep: int) -> None:
    """이름순(=시간순) 정렬 후 오래된 백업 삭제, 최신 keep개 유지."""
    files = sorted(glob.glob(os.path.join(backup_dir, f"{_PREFIX}*.db")))
    for old in files[:-keep] if keep > 0 else files:
        try:
            os.remove(old)
        except OSError:
            pass
