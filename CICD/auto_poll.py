# auto_poll.py - Poll detect build mới từ network share
import re
from pathlib import Path

TARGET_VERSION = "2026.05"


def _parse_version(filename):
    match = re.search(r'_(\d{4})\.(\d{2})\.', filename, re.IGNORECASE)
    if not match:
        match = re.search(r'_(\d{4})\.(\d{1,2})\.', filename, re.IGNORECASE)
    if match:
        major = match.group(1)
        minor = match.group(2).zfill(2)
        return f"{major}.{minor}"
    return None


def get_latest_zip(source_dir, target_version=TARGET_VERSION):
    """Tìm file zip mới nhất cho target_version. Trả về (Path, mtime) hoặc (None, 0)."""
    src = Path(source_dir)
    if not src.exists():
        return None, 0

    latest_file  = None
    latest_mtime = 0

    for f in src.iterdir():
        if not f.is_file() or f.suffix.lower() != ".zip":
            continue
        ver = _parse_version(f.name)
        if ver != target_version:
            continue
        mtime = f.stat().st_mtime
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_file  = f

    return latest_file, latest_mtime


def has_new_build(source_dir, last_mtime, target_version=TARGET_VERSION):
    """Trả về (True, new_mtime) nếu có build mới hơn last_mtime, ngược lại (False, last_mtime)."""
    _, mtime = get_latest_zip(source_dir, target_version)
    if mtime > last_mtime:
        return True, mtime
    return False, last_mtime