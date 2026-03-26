# runner.py
import os
import shutil
import subprocess


def run_studio(studio_dir, xml_path):
    print(f"Đang chạy TrussStudio: {studio_dir}")
    exe = os.path.join(studio_dir, "TrussStudio.exe")
    subprocess.run(
        [exe, f"/E:{xml_path}"],
        cwd=studio_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print(f"Xong: {studio_dir}")


def cleanup(copy_v1, copy_v2):
    shutil.rmtree(copy_v1)
    shutil.rmtree(copy_v2)
    print("Cleanup xong")

import concurrent.futures
import threading
import time

# Global lock + timestamp để stagger tất cả lần gọi studio trên toàn app
_studio_launch_lock = threading.Lock()
_last_launch_time = [0.0]
STUDIO_LAUNCH_DELAY = 3.0  # giây giữa mỗi lần mở studio

def _launch_studio(studio_dir, xml_path):
    """Mở studio với stagger toàn cục"""
    global _last_launch_time
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
    return p

def run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2):
    """Launch v1 trước, đợi STUDIO_LAUNCH_DELAY, rồi launch v2, sau đó chờ cả 2 xong"""
    p1 = _launch_studio(studio_v1, xml_v1)
    p2 = _launch_studio(studio_v2, xml_v2)
    p1.wait()
    p2.wait()