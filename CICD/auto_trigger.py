# auto_trigger.py - Replace flag, chạy ClrCK/FixSecurity, swap V1/V2
import ctypes
import shutil
from pathlib import Path

FLAG_FILE = Path(__file__).parent / "it.flg"


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
    Không đổi tên folder, chỉ lưu path V1/V2 vào studio_paths.json.
    V2 cũ → thành V1, bản mới → thành V2.
    Trả về (v1_path, v2_path) hoặc (None, None) nếu lỗi.
    """
    import json
    input_dir  = Path(input_dir)
    paths_file = input_dir / "studio_paths.json"
    new_path   = input_dir / new_version

    if not new_path.exists():
        log_fn(f"[Swap] ❌ New version folder not found: {new_path}")
        return None, None

    try:
        # Đọc V2 hiện tại → sẽ thành V1
        old_v2 = None
        if paths_file.exists():
            data   = json.loads(paths_file.read_text(encoding="utf-8"))
            old_v2 = data.get("v2")

        # Xóa V1 cũ nếu có
        if old_v2:
            old_v1_path = Path(data.get("v1", "")) if data.get("v1") else None
            if old_v1_path and old_v1_path.exists():
                log_fn(f"[Swap] Removing old V1: {old_v1_path.name}")
                shutil.rmtree(old_v1_path)

        v1_path = Path(old_v2) if old_v2 else None
        v2_path = new_path

        paths = {
            "v1": str(v1_path) if v1_path else None,
            "v2": str(v2_path),
        }
        paths_file.write_text(json.dumps(paths, indent=2), encoding="utf-8")

        log_fn(f"[Swap] ✓ V1={v1_path.name if v1_path else None}, V2={v2_path.name}")
        return v1_path, v2_path

    except Exception as e:
        log_fn(f"[Swap] ❌ Error: {e}")
        return None, None