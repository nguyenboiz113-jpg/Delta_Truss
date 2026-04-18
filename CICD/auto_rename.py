# auto_rename.py - Rename folder theo version exe zz
import shutil
import time
from pathlib import Path


def get_exe_version(exe_path):
    """Đọc version từ TrussStudio.exe bằng PowerShell."""
    import subprocess
    import re
    try:
        cmd = f'(Get-Item "{exe_path}").VersionInfo.FileVersion'
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, text=True
        )
        version = result.stdout.strip()
        if not version:
            return None

        # Handle "2026.5 [Build 32]" → "2026.5.0.32"
        match = re.search(r'(\d+)\.(\d+)\s*\[Build\s*(\d+)\]', version)
        if match:
            return f"{match.group(1)}.{match.group(2)}.0.{match.group(3)}"

        # Handle normal format
        return version.replace(", ", ".").replace(",", ".")
    except Exception:
        return None


def _rename_with_retry(src, dst, max_retries=3, delay=1):
    for i in range(max_retries):
        try:
            src.rename(dst)
            return True
        except PermissionError as e:
            if i < max_retries - 1:
                time.sleep(delay)
            else:
                return False
    return False


def rename_by_version(input_dir, log_fn=print):
    """
    Scan input_dir, tìm TrussStudio.exe trong mỗi subfolder,
    đọc version rồi rename folder theo version đó.
    Trả về dict {old_name: new_version} cho các folder đã rename thành công.
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        log_fn(f"[Rename] ❌ Input folder not found: {input_dir}")
        return {}

    renamed = {}

    for base in input_dir.iterdir():
        if not base.is_dir():
            continue

        log_fn(f"[Rename] Processing: {base.name}")

        exe_list = list(base.rglob("TrussStudio.exe"))
        if not exe_list:
            log_fn(f"[Rename]   ❌ Missing TrussStudio.exe")
            continue

        exe_path = exe_list[0]
        version  = get_exe_version(exe_path)
        if not version:
            log_fn(f"[Rename]   ❌ Cannot read version")
            continue

        log_fn(f"[Rename]   Version: {version}")
        dest = input_dir / version

        if dest == base:
            log_fn(f"[Rename]   Already correct name")
            renamed[base.name] = version
            continue

        if dest.exists():
            log_fn(f"[Rename]   Removing old: {dest.name}")
            shutil.rmtree(dest)

        if _rename_with_retry(base, dest):
            log_fn(f"[Rename]   ✓ {base.name} → {version}")
            renamed[base.name] = version
        else:
            log_fn(f"[Rename]   ❌ Failed to rename")

    return renamed