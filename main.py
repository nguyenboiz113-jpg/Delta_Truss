# main.py - Core logic and entry point
import tkinter as tk
import os
import shutil
import threading
import concurrent.futures
import time
import config
from config import load_config, save_config
from engine.xml_builder import copy_project, build_xml, patch_compatibility_version
from engine.runner import run_studios_parallel, cleanup, kill_all
from comparator.compare_file import compare_file
from report.excel_writer import write_report
from tools.extract import extract_files
from parse import parse_version, get_version_number
from gui.gui import setup_gui, get_selected_base_dir
from tkinter import messagebox
from parser.tdl_parser import parse_tdl
from parser.studio_config_parser import (
    apply_and_restore_feature_flags,
    build_output_name,
)

load_config()

gui_root = None
gui_refs = {}

_stop_event = threading.Event()
_active_copy_dirs = []
_active_copy_dirs_lock = threading.Lock()

MAX_RETRY_PER_FILE  = 1
NO_PROGRESS_TIMEOUT = 60


# =====================
# Helpers
# =====================
def _register_copy(copy_v1, copy_v2):
    with _active_copy_dirs_lock:
        _active_copy_dirs.append((copy_v1, copy_v2))


def _unregister_copy(copy_v1, copy_v2):
    with _active_copy_dirs_lock:
        try:
            _active_copy_dirs.remove((copy_v1, copy_v2))
        except ValueError:
            pass


def log(msg):
    txt_log = gui_refs.get("txt_log")
    prefix  = gui_refs.get("log_prefix", "")
    if txt_log:
        txt_log.insert(tk.END, f"{prefix}{msg}\n")
        txt_log.see(tk.END)
        if gui_root:
            gui_root.update()


def _strip_extensions(name):
    while True:
        base, ext = os.path.splitext(name)
        if not ext:
            return name
        name = base


def _txt_name(truss_filename):
    return f"project_{truss_filename}.txt"


def _parse_profiles(base_dir, filenames):
    profiles = {}
    trusses_dir = os.path.join(base_dir, "Trusses")

    stem_to_path = {}
    if os.path.isdir(trusses_dir):
        for f in os.listdir(trusses_dir):
            if f.lower().endswith(".tdltruss"):
                stem = _strip_extensions(f).lower()
                stem_to_path[stem] = os.path.join(trusses_dir, f)

    for filename in filenames:
        name = filename.replace("project_", "")
        stem = _strip_extensions(name).lower()
        tdl_path = stem_to_path.get(stem)
        if tdl_path:
            profile = parse_tdl(tdl_path)
            if profile:
                profiles[filename] = profile
    return profiles


# =====================
# Stop
# =====================
def stop():
    _stop_event.set()
    log("⛔ Stopping...")

    kill_all()

    with _active_copy_dirs_lock:
        for copy_v1, copy_v2 in _active_copy_dirs:
            for path in (copy_v1, copy_v2):
                if path and os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)
        _active_copy_dirs.clear()

    base_rows = gui_refs.get("base_rows", [])
    for row in base_rows:
        bd = row["entry"].get().strip()
        if bd:
            for xml in ("project_v1.xml", "project_v2.xml"):
                p = os.path.join(bd, xml)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    log("⛔ Stopped. Cleaned up.")

    gui_refs["btn_stop"].config(state=tk.DISABLED)
    gui_refs["btn_run"].config(state=tk.NORMAL)


# =====================
# Run
# =====================
def run():
    entry_v1        = gui_refs["entry_v1"]
    entry_v2        = gui_refs["entry_v2"]
    var_patch_v1    = gui_refs["var_patch_v1"]
    var_patch_v2    = gui_refs["var_patch"]
    var_parallel_v1 = gui_refs["var_parallel_v1"]
    var_trigger_v1  = gui_refs["var_trigger_v1"]
    var_parallel_v2 = gui_refs["var_parallel_v2"]
    var_trigger_v2  = gui_refs["var_trigger_v2"]

    btn_run  = gui_refs["btn_run"]
    btn_stop = gui_refs["btn_stop"]

    base_rows = gui_refs.get("base_rows", [])

    studio_v1 = entry_v1.get().strip()
    studio_v2 = entry_v2.get().strip()
    base_dirs = [r["entry"].get().strip() for r in base_rows if r["entry"].get().strip()]

    if not studio_v1 or not studio_v2 or not base_dirs:
        messagebox.showerror("Error", "Please fill in all paths.")
        return

    save_config()

    _stop_event.clear()
    btn_run.config(state=tk.DISABLED)
    btn_stop.config(state=tk.NORMAL)

    # ===== 6 CASES =====
    test_cases = [
        {"name": "case1_all_off",       "patch": False, "trigger": False, "parallel": False},
        {"name": "case2_trigger",       "patch": False, "trigger": True,  "parallel": False},
        {"name": "case3_parallel",      "patch": False, "trigger": False, "parallel": True},
        {"name": "case4_patch",         "patch": True,  "trigger": False, "parallel": False},
        {"name": "case5_patch_trigger", "patch": True,  "trigger": True,  "parallel": False},
        {"name": "case6_patch_parallel","patch": True,  "trigger": False, "parallel": True},
    ]

    def _run():
        try:
            ver_v1 = parse_version(studio_v1)
            ver_v2 = parse_version(studio_v2)
            parent_dir = os.path.dirname(base_dirs[0])

            for ci, case in enumerate(test_cases, 1):
                if _stop_event.is_set():
                    return

                gui_refs["log_prefix"] = f"[CASE {ci}] "

                log("=" * 60)
                log(f"START {case['name']}")
                log(f"Options: patch={case['patch']} trigger={case['trigger']} parallel={case['parallel']}")
                log("=" * 60)

                var_patch_v1.set(case["patch"])
                var_patch_v2.set(case["patch"])
                var_trigger_v1.set(case["trigger"])
                var_trigger_v2.set(case["trigger"])
                var_parallel_v1.set(case["parallel"])
                var_parallel_v2.set(case["parallel"])

                base_all_results = {}
                base_profiles    = {}

                # ====== ORIGINAL CLAUDE run_one (GIỮ HẦU NHƯ NGUYÊN) ======
                def run_one(bd, idx):
                    copy_v1 = copy_v2 = None
                    xml_v1  = os.path.join(bd, "project_v1.xml")
                    xml_v2  = os.path.join(bd, "project_v2.xml")

                    try:
                        if _stop_event.is_set():
                            return bd, [], {}

                        output_dir = os.path.join(bd, "output")
                        if os.path.exists(output_dir):
                            shutil.rmtree(output_dir)

                        out_v1 = os.path.join(
                            output_dir,
                            build_output_name(ver_v1, case["patch"], case["parallel"], case["trigger"])
                        )
                        out_v2 = os.path.join(
                            output_dir,
                            build_output_name(ver_v2, case["patch"], case["parallel"], case["trigger"])
                        )
                        os.makedirs(out_v1, exist_ok=True)
                        os.makedirs(out_v2, exist_ok=True)

                        log(f"[Base {idx}] Copying project...")
                        copy_v1, copy_v2 = copy_project(bd)
                        _register_copy(copy_v1, copy_v2)

                        if case["patch"]:
                            patch_compatibility_version(os.path.join(copy_v1, "Trusses"), get_version_number(ver_v1))
                            patch_compatibility_version(os.path.join(copy_v2, "Trusses"), get_version_number(ver_v2))

                        truss_files = sorted(
                            f for f in os.listdir(os.path.join(bd, "Trusses"))
                            if f.lower().endswith(".tdltruss")
                        )

                        file_retry_count = {}
                        not_responded    = set()
                        current_files   = list(truss_files)

                        while current_files:
                            log(f"[Base {idx}] Building XML ({len(current_files)} file(s))...")
                            build_xml("project",
                                      os.path.join(copy_v1, "Trusses"),
                                      os.path.join(copy_v1, "Presets"),
                                      out_v1, xml_v1, only_files=current_files)

                            build_xml("project",
                                      os.path.join(copy_v2, "Trusses"),
                                      os.path.join(copy_v2, "Presets"),
                                      out_v2, xml_v2, only_files=current_files)

                            log(f"[Base {idx}] Launching Studio...")
                            r1 = apply_and_restore_feature_flags(studio_v1, case["parallel"], case["trigger"])
                            r2 = apply_and_restore_feature_flags(studio_v2, case["parallel"], case["trigger"])
                            try:
                                run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2)
                            finally:
                                r1(); r2()

                            last_change = time.time()
                            last_log    = time.time()
                            last_total  = -1

                            while True:
                                done_v1 = len([f for f in os.listdir(out_v1) if f.endswith(".txt")])
                                done_v2 = len([f for f in os.listdir(out_v2) if f.endswith(".txt")])
                                total   = done_v1 + done_v2

                                if total != last_total:
                                    last_total  = total
                                    last_change = time.time()

                                if time.time() - last_change >= NO_PROGRESS_TIMEOUT:
                                    log(f"[Base {idx}] ⚠️ No progress {NO_PROGRESS_TIMEOUT}s")
                                    break

                                if time.time() - last_log >= 30:
                                    log(f"[Base {idx}] Waiting... v1={done_v1}, v2={done_v2}")
                                    last_log = time.time()

                                if done_v1 >= len(truss_files) and done_v2 >= len(truss_files):
                                    break

                                time.sleep(0.5)

                            done_stems_v1 = {_strip_extensions(f.replace("project_", "")).lower()
                                             for f in os.listdir(out_v1) if f.endswith(".txt")}
                            done_stems_v2 = {_strip_extensions(f.replace("project_", "")).lower()
                                             for f in os.listdir(out_v2) if f.endswith(".txt")}

                            next_batch = []
                            for f in current_files:
                                stem = _strip_extensions(f).lower()
                                if stem in done_stems_v1 and stem in done_stems_v2:
                                    continue
                                cnt = file_retry_count.get(f, 0)
                                if cnt >= MAX_RETRY_PER_FILE:
                                    not_responded.add(_txt_name(f))
                                else:
                                    file_retry_count[f] = cnt + 1
                                    next_batch.append(f)

                            current_files = next_batch

                        cleanup(copy_v1, copy_v2)
                        _unregister_copy(copy_v1, copy_v2)

                        results = []
                        for f in os.listdir(out_v1):
                            if f.endswith(".txt"):
                                fv1 = os.path.join(out_v1, f)
                                fv2 = os.path.join(out_v2, f)
                                if f in not_responded:
                                    results.append((f, [{
                                        "section": "Not Responded",
                                        "diff_count": -1,
                                        "diff_pct": -1,
                                        "lines_v1": 0,
                                        "lines_v2": 0
                                    }]))
                                elif os.path.exists(fv2):
                                    results.append((f, compare_file(fv1, fv2)))

                        profiles = _parse_profiles(bd, [f for f, _ in results])
                        return bd, results, profiles

                    except Exception as e:
                        log(f"[Base {idx}] ❌ ERROR: {e}")
                        return bd, [], {}

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(base_dirs))) as exe:
                    futures = {
                        exe.submit(run_one, bd, i + 1): bd
                        for i, bd in enumerate(base_dirs)
                    }
                    for fut in concurrent.futures.as_completed(futures):
                        bd, res, prof = fut.result()
                        base_all_results[bd] = res
                        base_profiles[bd]    = prof

                excel_name = (
                    f"compare_v1_{ver_v1}_v2_{ver_v2}_"
                    f"{'patch' if case['patch'] else 'nopatch'}_"
                    f"{'trigger' if case['trigger'] else 'notrigger'}_"
                    f"{'parallel' if case['parallel'] else 'noparallel'}.xlsx"
                )

                xlsx_path = os.path.join(parent_dir, excel_name)
                write_report(base_all_results, xlsx_path, base_profiles)

                log(f"✅ DONE {case['name']}")
                log(f"Excel: {xlsx_path}")
                log("")

            messagebox.showinfo("Done", "All 6 cases completed.")

        finally:
            gui_refs["log_prefix"] = ""
            btn_stop.config(state=tk.DISABLED)
            btn_run.config(state=tk.NORMAL)

    threading.Thread(target=_run, daemon=True).start()


# =====================
# Entry
# =====================
if __name__ == "__main__":
    callbacks = {
        "run": run,
        "stop": stop,
    }
    gui_root, gui_refs = setup_gui(callbacks)
    gui_root.mainloop()
