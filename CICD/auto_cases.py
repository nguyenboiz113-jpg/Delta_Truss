# auto_cases.py - Chạy 6 case tự động, xuất 6 Excel riêng
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import _run_core
from parse import parse_version

CASES = [
    {"name": "case1_all_false",     "patch": False, "parallel": False, "trigger": False},
    {"name": "case2_trigger",       "patch": False, "parallel": False, "trigger": True},
    {"name": "case3_parallel",      "patch": False, "parallel": True,  "trigger": False},
    {"name": "case4_patch",         "patch": True,  "parallel": False, "trigger": False},
    {"name": "case5_patch_trigger", "patch": True,  "parallel": False, "trigger": True},
    {"name": "case6_patch_parallel","patch": True,  "parallel": True,  "trigger": False},
]


def run_all_cases(
    studio_v1, studio_v2,
    base_dirs,
    output_dir,
    log_fn=print,
    stop_event=None,
):
    """
    Chạy 6 case so sánh V1 vs V2.
    Mỗi case xuất 1 file Excel vào output_dir.
    Tên file: compare_v1.{ver_v1}_v2.{ver_v2}_{case_name}.xlsx
    Trả về list các xlsx_path đã xuất thành công.
    """
    if stop_event is None:
        stop_event = threading.Event()

    ver_v1 = parse_version(studio_v1)
    ver_v2 = parse_version(studio_v2)

    # Tạo folder tên v1.X_v2.Y chứa 6 file Excel
    folder_name = f"v1.{ver_v1}_v2.{ver_v2}"
    case_output_dir = os.path.join(output_dir, folder_name)
    os.makedirs(case_output_dir, exist_ok=True)
    log_fn(f"[Cases] Output folder: {folder_name}")

    results = []

    for i, case in enumerate(CASES, start=1):
        if stop_event.is_set():
            log_fn(f"[Cases] ⛔ Stopped at case {i}")
            break

        log_fn(f"\n{'='*60}")
        log_fn(f"[Cases] ▶ Case {i}/6: {case['name']}")
        log_fn(f"  patch={case['patch']}  parallel={case['parallel']}  trigger={case['trigger']}")
        log_fn(f"{'='*60}")

        xlsx_name = f"{case['name']}.xlsx"
        xlsx_path = os.path.join(case_output_dir, xlsx_name)

        try:
            base_all_results, base_profiles = _run_core(
                studio_v1=studio_v1,
                studio_v2=studio_v2,
                base_dirs=base_dirs,
                patch_v1=case["patch"],
                patch_v2=case["patch"],
                parallel_v1=case["parallel"],
                trigger_v1=case["trigger"],
                parallel_v2=case["parallel"],
                trigger_v2=case["trigger"],
                xlsx_path=xlsx_path,
                log_fn=log_fn,
                stop_event=stop_event,
            )

            if base_all_results is not None:
                log_fn(f"[Cases] ✅ Case {i} done → {xlsx_name}")
                results.append(xlsx_path)
            else:
                log_fn(f"[Cases] ⛔ Case {i} stopped or failed")

        except Exception as e:
            log_fn(f"[Cases] ❌ Case {i} error: {e}")

    log_fn(f"\n[Cases] Finished {len(results)}/6 case(s)")
    return results