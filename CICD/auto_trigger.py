# auto_trigger.py - Replace flag, chạy ClrCK/FixSecurity, swap V1/V2
import sys
import ctypes
import shutil
from pathlib import Path

_BASE = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
FLAG_FILE = _BASE / "it.flg"




def replace_flag(base, log_fn=print):
    """Copy it.flg vào folder."""
    try:
        shutil.copy2(FLAG_FILE, base / "it.flg")
        log_fn(f"[Trigger] ✓ it.flg replaced → {base.name}")
    except Exception as e:
        log_fn(f"[Trigger] ❌ replace flag {base.name}: {e}")


def run_exe(exe, log_fn=print):
    """Chạy exe bằng ShellExecuteW."""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "open", str(exe), None, str(exe.parent), 1
        )
        log_fn(f"[Trigger] ✓ run {exe.name}")
    except Exception as e:
        log_fn(f"[Trigger] ❌ run {exe.name}: {e}")


def run_trigger(input_dir, log_fn=print):
    """
    Scan input_dir, với mỗi subfolder:
    - Replace it.flg
    - Chạy ClrCK.exe và FixSecurity.exe nếu có
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        log_fn(f"[Trigger] ❌ Input folder not found: {input_dir}")
        return

    if not FLAG_FILE.exists():
        log_fn(f"[Trigger] ❌ it.flg not found: {FLAG_FILE}")
        return

    for base in input_dir.iterdir():
        if not base.is_dir():
            continue
        log_fn(f"[Trigger] --- {base.name} ---")
        replace_flag(base, log_fn)
        for name in ["ClrCK.exe", "FixSecurity.exe"]:
            exe = base / name
            if exe.exists():
                run_exe(exe, log_fn)
            else:
                log_fn(f"[Trigger]   [!] missing {name}")


def swap_v1_v2(input_dir, new_version, log_fn=print):
    """
    - Xóa V1 cũ
    - Đổi V2 hiện tại → V1
    - Đổi folder new_version → V2
    Trả về (v1_path, v2_path) hoặc (None, None) nếu lỗi.
    """
    input_dir = Path(input_dir)
    v1_path   = input_dir / "v1"
    v2_path   = input_dir / "v2"
    new_path  = input_dir / new_version

    if not new_path.exists():
        log_fn(f"[Swap] ❌ New version folder not found: {new_path}")
        return None, None

    try:
        # Xóa V1 cũ
        if v1_path.exists():
            log_fn(f"[Swap] Removing old V1...")
            shutil.rmtree(v1_path)

        # V2 → V1
        if v2_path.exists():
            log_fn(f"[Swap] V2 → V1")
            v2_path.rename(v1_path)

        # new → V2
        log_fn(f"[Swap] {new_version} → V2")
        new_path.rename(v2_path)

        log_fn(f"[Swap] ✓ Done: V1={v1_path.name}, V2={v2_path.name}")
        return v1_path, v2_path

    except Exception as e:
        log_fn(f"[Swap] ❌ Error: {e}")
        return None, None