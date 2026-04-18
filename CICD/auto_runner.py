# auto_runner.py - Orchestrator chính
import threading
import time
from datetime import datetime
from pathlib import Path

from .auto_poll import has_new_build, get_latest_zip
from .auto_download import download_latest
from .auto_rename import rename_by_version
from .auto_trigger import run_trigger, swap_v1_v2
from .auto_cases import run_all_cases

# ── CONFIG ─────────────────────────────────────────────────────────────────────
SOURCE_DIR     = r"\\105sync\bld"
INPUT_DIR      = Path(__file__).parent.parent / "input"
TARGET_VERSION = "2026.05"
POLL_INTERVAL  = 30 * 60   # 30 phút
LOG_SAVE_INTERVAL = 24 * 60 * 60  # 24 giờ
LOG_DIR        = Path(__file__).parent / "logs"
# ──────────────────────────────────────────────────────────────────────────────

_stop_event   = threading.Event()
_gui_refs     = {}
_last_mtime   = 0
_last_log_save = time.time()


def _log(msg):
    """Log ra GUI và console."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_msg  = f"[{timestamp}] {msg}"
    print(full_msg)

    txt_log = _gui_refs.get("txt_log")
    if txt_log:
        try:
            import tkinter as tk
            txt_log.insert(tk.END, full_msg + "\n")
            txt_log.see(tk.END)
            root = _gui_refs.get("root")
            if root:
                root.update()
        except Exception:
            pass


def _save_and_clear_log():
    """Lưu log ra file, xóa sạch log trên GUI."""
    txt_log = _gui_refs.get("txt_log")
    if not txt_log:
        return

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"log_{datetime.now().strftime('%Y-%m-%d')}.txt"
        content  = txt_log.get("1.0", "end")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(content)

        import tkinter as tk
        txt_log.delete("1.0", tk.END)
        _log(f"📁 Log saved to: {log_file.name}")
    except Exception as e:
        _log(f"❌ Save log error: {e}")


def _get_studio_paths():
    """Lấy path V1 và V2 từ GUI entries."""
    entry_v1 = _gui_refs.get("entry_v1")
    entry_v2 = _gui_refs.get("entry_v2")
    if not entry_v1 or not entry_v2:
        return None, None
    return entry_v1.get().strip(), entry_v2.get().strip()


def _get_base_dirs():
    """Lấy base dirs từ GUI."""
    base_rows = _gui_refs.get("base_rows", [])
    return [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]


def _run_pipeline(new_version):
    """Chạy toàn bộ pipeline khi có build mới."""
    _log(f"\n{'='*60}")
    _log(f"🚀 New build detected: {new_version}")
    _log(f"{'='*60}")

    # 1. Download
    _log("\n[1/5] Downloading...")
    zip_path, _ = get_latest_zip(SOURCE_DIR, TARGET_VERSION)
    if not zip_path:
        _log("❌ No zip found, aborting.")
        return

    extract_folder = download_latest(SOURCE_DIR, INPUT_DIR, TARGET_VERSION, log_fn=_log)
    if not extract_folder:
        _log("❌ Download failed, aborting.")
        return

    # 2. Rename
    _log("\n[2/5] Renaming by version...")
    renamed = rename_by_version(INPUT_DIR, log_fn=_log)
    if not renamed:
        _log("❌ Rename failed, aborting.")
        return

    actual_version = list(renamed.values())[0]
    _log(f"✓ Renamed to: {actual_version}")

    # 3. Trigger
    _log("\n[3/5] Running trigger...")
    run_trigger(INPUT_DIR, log_fn=_log)

    # 4. Swap V1/V2
    _log("\n[4/5] Swapping V1/V2...")
    v1_path, v2_path = swap_v1_v2(INPUT_DIR, actual_version, log_fn=_log)
    if not v1_path or not v2_path:
        _log("❌ Swap failed, aborting.")
        return

    # Update GUI entries
    entry_v1 = _gui_refs.get("entry_v1")
    entry_v2 = _gui_refs.get("entry_v2")
    if entry_v1 and entry_v2:
        import tkinter as tk
        entry_v1.delete(0, tk.END)
        entry_v1.insert(0, str(v1_path))
        entry_v2.delete(0, tk.END)
        entry_v2.insert(0, str(v2_path))

    studio_v1, studio_v2 = str(v1_path), str(v2_path)

    # 5. Run 6 cases
    _log("\n[5/5] Running 6 cases...")
    base_dirs  = _get_base_dirs()
    if not base_dirs:
        _log("❌ No base dirs configured, aborting.")
        return

    output_dir = Path(base_dirs[0]).parent
    run_all_cases(
        studio_v1=studio_v1,
        studio_v2=studio_v2,
        base_dirs=base_dirs,
        output_dir=str(output_dir),
        log_fn=_log,
        stop_event=_stop_event,
    )

    _log(f"\n✅ Pipeline done for {actual_version}")


def _auto_loop():
    """Loop chính: poll → pipeline → save log."""
    global _last_mtime, _last_log_save

    _log("🤖 Auto runner started")
    _log(f"  Source : {SOURCE_DIR}")
    _log(f"  Version: {TARGET_VERSION}")
    _log(f"  Poll   : every {POLL_INTERVAL//60} min")

    while not _stop_event.is_set():
        now = time.time()

        # Check save log mỗi 24h
        if now - _last_log_save >= LOG_SAVE_INTERVAL:
            _save_and_clear_log()
            _last_log_save = now

        # Poll build mới
        _log(f"🔍 Checking for new build...")
        try:
            is_new, new_mtime = has_new_build(SOURCE_DIR, _last_mtime, TARGET_VERSION)
            if is_new:
                _last_mtime = new_mtime
                zip_path, _ = get_latest_zip(SOURCE_DIR, TARGET_VERSION)
                new_version  = zip_path.stem if zip_path else TARGET_VERSION
                _run_pipeline(new_version)
            else:
                _log(f"  No new build. Next check in {POLL_INTERVAL//60} min.")
        except Exception as e:
            _log(f"❌ Poll error: {e}")

        # Chờ POLL_INTERVAL, nhưng check stop mỗi 10s
        for _ in range(POLL_INTERVAL // 10):
            if _stop_event.is_set():
                break
            time.sleep(10)

    _log("⛔ Auto runner stopped.")


def _set_buttons(started):
    """Enable/disable Auto Start và Auto Stop buttons."""
    import tkinter as tk
    btn_start = _gui_refs.get("btn_auto_start")
    btn_stop  = _gui_refs.get("btn_auto_stop")
    if btn_start:
        btn_start.config(state=tk.DISABLED if started else tk.NORMAL)
    if btn_stop:
        btn_stop.config(state=tk.NORMAL if started else tk.DISABLED)


def start(gui_refs):
    """Gọi từ GUI để bắt đầu auto runner."""
    global _gui_refs
    _gui_refs = gui_refs
    _stop_event.clear()
    _set_buttons(started=True)
    threading.Thread(target=_auto_loop, daemon=True).start()


def stop():
    """Dừng auto runner."""
    _stop_event.set()
    _set_buttons(started=False)