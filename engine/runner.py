# runner.py
import os
import subprocess
import threading
import time

# Global lock + timestamp để stagger tất cả lần gọi studio trên toàn app
_studio_launch_lock = threading.Lock()
_last_launch_time = [0.0]
STUDIO_LAUNCH_DELAY = 3.0  # giây giữa mỗi lần mở studio

# Track tất cả process đang chạy để có thể kill
_active_processes: list[subprocess.Popen] = []
_active_processes_lock = threading.Lock()


def cleanup(copy_v1, copy_v2):
    import shutil
    for path in [copy_v1, copy_v2]:
        if path and os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)


def kill_all():
    """Kill tất cả TrussStudio process đang chạy"""
    with _active_processes_lock:
        for p in _active_processes:
            try:
                p.kill()
            except Exception:
                pass
        _active_processes.clear()


def _launch_studio(studio_dir, xml_path):
    """Mở studio với stagger toàn cục"""
    with _studio_launch_lock:
        elapsed = time.time() - _last_launch_time[0]
        if elapsed < STUDIO_LAUNCH_DELAY:
            time.sleep(STUDIO_LAUNCH_DELAY - elapsed)
        exe = os.path.join(studio_dir, "TrussStudio.exe")
        p = subprocess.Popen(
            [exe, f"/E:{xml_path}"],
            cwd=studio_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        _last_launch_time[0] = time.time()

    with _active_processes_lock:
        _active_processes.append(p)

    return p


def _untrack(p):
    with _active_processes_lock:
        try:
            _active_processes.remove(p)
        except ValueError:
            pass


def launch_studios(studio_v1, xml_v1, studio_v2, xml_v2):
    """Launch cả 2 studio, trả về (p1, p2) để caller tự poll và quản lý"""
    p1 = _launch_studio(studio_v1, xml_v1)
    p2 = _launch_studio(studio_v2, xml_v2)
    return p1, p2


def finish_studios(p1, p2):
    """Untrack process sau khi caller xác nhận xong"""
    _untrack(p1)
    _untrack(p2)