# auto_download.py - Tải zip mới nhất về và giải nén
import shutil
import zipfile
from pathlib import Path
from .auto_poll import get_latest_zip


def download_latest(source_dir, dest_dir, target_version="2026.05", log_fn=print):
    """
    Copy zip mới nhất của target_version về dest_dir, giải nén.
    Trả về Path folder giải nén hoặc None nếu lỗi.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_path, _ = get_latest_zip(source_dir, target_version)
    if not zip_path:
        log_fn(f"[Download] No zip found for version {target_version}")
        return None

    dest_zip = dest_dir / zip_path.name
    extract_folder = dest_dir / zip_path.stem

    try:
        # Copy
        total = zip_path.stat().st_size
        log_fn(f"[Download] {zip_path.name} ({total / (1024*1024):.1f} MB)")
        copied = 0
        with open(zip_path, "rb") as fsrc, open(dest_zip, "wb") as fdst:
            chunk_size = 1024 * 1024
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)
                log_fn(f"  Copying... {copied * 100 / total:.1f}%")
        log_fn("  Copy done")

        # Giải nén
        if extract_folder.exists():
            log_fn(f"  Cleaning old folder: {extract_folder.name}")
            shutil.rmtree(extract_folder)
        extract_folder.mkdir(parents=True, exist_ok=True)

        log_fn("  Extracting...")
        with zipfile.ZipFile(dest_zip, "r") as zf:
            zf.extractall(extract_folder)
        log_fn("  Extract done")

        # Xóa zip
        dest_zip.unlink()
        log_fn(f"[Download] ✓ Done: {extract_folder.name}")
        return extract_folder

    except Exception as e:
        log_fn(f"[Download] ❌ Error: {e}")
        if dest_zip.exists():
            dest_zip.unlink()
        return None