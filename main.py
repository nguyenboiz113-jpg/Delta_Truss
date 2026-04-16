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

_active_copy_dirs: list[tuple] = []
_active_copy_dirs_lock = threading.Lock()

MAX_RETRY_PER_FILE  = 1
NO_PROGRESS_TIMEOUT = 60


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
    if txt_log:
        txt_log.insert(tk.END, msg + "\n")
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


def stop():
    _stop_event.set()
    log("⛔ Stopping...")

    kill_all()

    with _active_copy_dirs_lock:
        for copy_v1, copy_v2 in _active_copy_dirs:
            for path in [copy_v1, copy_v2]:
                if path and os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)
        _active_copy_dirs.clear()

    base_rows = gui_refs.get("base_rows", [])
    for row in base_rows:
        bd = row["entry"].get().strip()
        if bd:
            for xml in ["project_v1.xml", "project_v2.xml"]:
                p = os.path.join(bd, xml)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    log("⛔ Stopped. Cleaned up.")

    btn_stop = gui_refs.get("btn_stop")
    btn_run  = gui_refs.get("btn_run")
    if btn_stop:
        btn_stop.config(state=tk.DISABLED)
    if btn_run:
        btn_run.config(state=tk.NORMAL)


def run():
    entry_v1        = gui_refs.get("entry_v1")
    entry_v2        = gui_refs.get("entry_v2")
    var_patch_v1    = gui_refs.get("var_patch_v1")
    var_patch       = gui_refs.get("var_patch")
    var_parallel_v1 = gui_refs.get("var_parallel_v1")
    var_trigger_v1  = gui_refs.get("var_trigger_v1")
    var_parallel_v2 = gui_refs.get("var_parallel_v2")
    var_trigger_v2  = gui_refs.get("var_trigger_v2")
    btn_run         = gui_refs.get("btn_run")
    btn_stop        = gui_refs.get("btn_stop")
    base_rows       = gui_refs.get("base_rows", [])

    studio_v1 = entry_v1.get().strip()
    studio_v2 = entry_v2.get().strip()
    base_dirs = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]

    if not base_dirs or not studio_v1 or not studio_v2:
        messagebox.showerror("Error", "Please fill in all paths.")
        return

    config.CONFIG["studio_dir_v1"] = studio_v1
    config.CONFIG["studio_dir_v2"] = studio_v2
    config.CONFIG["base_dirs"]     = base_dirs
    config.CONFIG["patch_v1"]      = var_patch_v1.get()
    config.CONFIG["patch_v2"]      = var_patch.get()
    config.CONFIG["parallel_v1"]   = var_parallel_v1.get()
    config.CONFIG["trigger_v1"]    = var_trigger_v1.get()
    config.CONFIG["parallel_v2"]   = var_parallel_v2.get()
    config.CONFIG["trigger_v2"]    = var_trigger_v2.get()
    save_config()

    _stop_event.clear()
    btn_run.config(state=tk.DISABLED)
    if btn_stop:
        btn_stop.config(state=tk.NORMAL)

    def _run():
        try:
            p1 = var_parallel_v1.get()
            t1 = var_trigger_v1.get()
            p2 = var_parallel_v2.get()
            t2 = var_trigger_v2.get()

            ver_v1 = parse_version(studio_v1)
            ver_v2 = parse_version(studio_v2)

            log(f"Running {len(base_dirs)} base(s), max 5 at a time...")
            base_all_results = {}
            base_profiles    = {}

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
                    output_v1 = os.path.join(output_dir, build_output_name(ver_v1, var_patch_v1.get(), p1, t1))
                    output_v2 = os.path.join(output_dir, build_output_name(ver_v2, var_patch.get(),    p2, t2))
                    os.makedirs(output_v1, exist_ok=True)
                    os.makedirs(output_v2, exist_ok=True)

                    log(f"[Base Dir {idx}] Copying project...")
                    copy_v1, copy_v2 = copy_project(bd)
                    _register_copy(copy_v1, copy_v2)

                    if _stop_event.is_set():
                        return bd, [], {}

                    if var_patch_v1.get():
                        patch_compatibility_version(os.path.join(copy_v1, "Trusses"), get_version_number(ver_v1))
                    if var_patch.get():
                        patch_compatibility_version(os.path.join(copy_v2, "Trusses"), get_version_number(ver_v2))

                    trusses_dir_v1 = os.path.join(copy_v1, "Trusses")
                    trusses_dir_v2 = os.path.join(copy_v2, "Trusses")

                    all_truss_files = sorted(
                        f for f in os.listdir(os.path.join(bd, "Trusses"))
                        if f.lower().endswith(".tdltruss")
                    )

                    log(f"[Base Dir {idx}] Found {len(all_truss_files)} truss file(s).")
                    if not all_truss_files:
                        log(f"[Base Dir {idx}] ❌ No .tdltruss files found, skipping.")
                        return bd, [], {}

                    file_retry_count: dict[str, int] = {}
                    not_responded: set[str] = set()
                    current_files = list(all_truss_files)

                    while current_files:
                        if _stop_event.is_set():
                            return bd, [], {}

                        is_retry    = any(file_retry_count.get(f, 0) > 0 for f in current_files)
                        retry_label = "  [retry batch]" if is_retry else ""

                        current_stems = {_strip_extensions(f).lower() for f in current_files}
                        already_done  = len([
                            f for f in os.listdir(output_v1)
                            if f.endswith(".txt")
                            and _strip_extensions(f.replace("project_", "")).lower() not in current_stems
                        ])
                        expected = already_done + len(current_files)

                        log(f"[Base Dir {idx}] Building XML ({len(current_files)} file(s)){retry_label}...")
                        build_xml("project", trusses_dir_v1, os.path.join(copy_v1, "Presets"), output_v1, xml_v1, only_files=current_files)
                        build_xml("project", trusses_dir_v2, os.path.join(copy_v2, "Presets"), output_v2, xml_v2, only_files=current_files)

                        log(f"[Base Dir {idx}] Launching TrussStudio {ver_v1} & {ver_v2}{retry_label}...")
                        restore_v1 = apply_and_restore_feature_flags(studio_v1, p1, t1)
                        restore_v2 = apply_and_restore_feature_flags(studio_v2, p2, t2)
                        try:
                            run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2)
                        finally:
                            restore_v1()
                            restore_v2()

                        for xml in [xml_v1, xml_v2]:
                            if os.path.exists(xml):
                                os.remove(xml)

                        if _stop_event.is_set():
                            return bd, [], {}

                        last_log         = time.time()
                        last_change_time = time.time()
                        last_total       = -1
                        while True:
                            if _stop_event.is_set():
                                return bd, [], {}
                            done_v1       = len([f for f in os.listdir(output_v1) if f.endswith(".txt")])
                            done_v2       = len([f for f in os.listdir(output_v2) if f.endswith(".txt")])
                            current_total = done_v1 + done_v2
                            if current_total != last_total:
                                last_total       = current_total
                                last_change_time = time.time()
                            if time.time() - last_change_time >= NO_PROGRESS_TIMEOUT:
                                log(f"[Base Dir {idx}] ⚠️ No progress for {NO_PROGRESS_TIMEOUT}s "
                                    f"(v1={done_v1}/{expected}, v2={done_v2}/{expected})")
                                break
                            if time.time() - last_log >= 30:
                                log(f"[Base Dir {idx}] Waiting... v1={done_v1}/{expected}, v2={done_v2}/{expected}")
                                last_log = time.time()
                            if done_v1 >= expected and done_v2 >= expected:
                                break
                            time.sleep(0.5)

                        if _stop_event.is_set():
                            return bd, [], {}

                        done_stems_v1 = {_strip_extensions(f.replace("project_", "")).lower() for f in os.listdir(output_v1) if f.endswith(".txt")}
                        done_stems_v2 = {_strip_extensions(f.replace("project_", "")).lower() for f in os.listdir(output_v2) if f.endswith(".txt")}

                        next_batch     = []
                        newly_marked   = []
                        newly_retrying = []
                        for f in current_files:
                            stem = _strip_extensions(f).lower()
                            txt  = _txt_name(f)
                            if stem in done_stems_v1 and stem in done_stems_v2:
                                continue
                            retries = file_retry_count.get(f, 0)
                            if retries >= MAX_RETRY_PER_FILE:
                                not_responded.add(txt)
                                newly_marked.append(f)
                            else:
                                file_retry_count[f] = retries + 1
                                newly_retrying.append((f, retries + 1))
                                next_batch.append(f)

                        if newly_marked:
                            log(f"[Base Dir {idx}] ❌ {len(newly_marked)} file(s) max retries reached, marked not responded: "
                                f"{', '.join(newly_marked[:5])}{'...' if len(newly_marked) > 5 else ''}")
                        if newly_retrying:
                            retry_num = newly_retrying[0][1]
                            sample    = [f for f, _ in newly_retrying[:5]]

                            last_v2 = None
                            for f in current_files:
                                stem = _strip_extensions(f).lower()
                                if stem in done_stems_v2 and f not in [x for x, _ in newly_retrying]:
                                    last_v2 = f

                            if last_v2:
                                log(f"[Base Dir {idx}] ⚠️ v2 stopped after {last_v2} (retry {retry_num}/{MAX_RETRY_PER_FILE}) — "
                                    f"{len(newly_retrying)} file(s) not reached: {', '.join(sample)}{'...' if len(newly_retrying) > 5 else ''}")
                            else:
                                log(f"[Base Dir {idx}] ⚠️ {len(newly_retrying)} file(s) not responded (retry {retry_num}/{MAX_RETRY_PER_FILE}): "
                                    f"{', '.join(sample)}{'...' if len(newly_retrying) > 5 else ''}")

                        if next_batch:
                            log(f"[Base Dir {idx}] Retrying {len(next_batch)} file(s)...")
                        else:
                            log(f"[Base Dir {idx}] ✅ All file(s) done or marked.")

                        current_files = next_batch

                    cleanup(copy_v1, copy_v2)
                    _unregister_copy(copy_v1, copy_v2)
                    copy_v1 = copy_v2 = None

                    if _stop_event.is_set():
                        return bd, [], {}

                    log(f"[Base Dir {idx}] Comparing...")
                    actual_files = sorted(f for f in os.listdir(output_v1) if f.endswith(".txt"))
                    seen_txt     = set()
                    all_results  = []

                    for txt_name in actual_files:
                        seen_txt.add(txt_name)
                        fv1 = os.path.join(output_v1, txt_name)
                        fv2 = os.path.join(output_v2, txt_name)
                        if txt_name in not_responded:
                            all_results.append((txt_name, [{"section": "Not Responded", "diff_count": -1, "diff_pct": -1, "lines_v1": 0, "lines_v2": 0}]))
                        elif os.path.exists(fv2):
                            results = compare_file(fv1, fv2)
                            all_results.append((txt_name, results))
                        else:
                            log(f"[Base Dir {idx}] [SKIP] {txt_name} — missing in v2 output")

                    for txt_name in not_responded:
                        if txt_name not in seen_txt:
                            all_results.append((txt_name, [{"section": "Not Responded", "diff_count": -1, "diff_pct": -1, "lines_v1": 0, "lines_v2": 0}]))

                    log(f"[Base Dir {idx}] Parsing truss profiles...")
                    filenames = [f for f, _ in all_results]
                    profiles  = _parse_profiles(bd, filenames)

                    log(f"[Base Dir {idx}] ✅ Done: {len(all_results)} file(s), {len(not_responded)} not responded.")
                    return bd, all_results, profiles

                except Exception as e:
                    log(f"[Base Dir {idx}] ❌ ERROR: {e}")
                    try:
                        if copy_v1 and os.path.exists(copy_v1):
                            shutil.rmtree(copy_v1)
                        if copy_v2 and os.path.exists(copy_v2):
                            shutil.rmtree(copy_v2)
                        if copy_v1 and copy_v2:
                            _unregister_copy(copy_v1, copy_v2)
                        for xml in [xml_v1, xml_v2]:
                            if os.path.exists(xml):
                                os.remove(xml)
                    except Exception:
                        pass
                    return bd, [], {}

            def count_trusses(bd):
                trusses_dir = os.path.join(bd, "Trusses")
                if not os.path.isdir(trusses_dir):
                    return 0
                return sum(1 for f in os.listdir(trusses_dir)
                           if f.lower().endswith(".tdltruss"))

            truss_counts     = {bd: count_trusses(bd) for bd in base_dirs}
            sorted_base_dirs = sorted(base_dirs, key=lambda bd: truss_counts[bd], reverse=True)
            for bd in sorted_base_dirs:
                orig_idx = base_dirs.index(bd) + 1
                log(f"  [Base Dir {orig_idx}] {os.path.basename(bd)} — {truss_counts[bd]} truss(es)")

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(sorted_base_dirs))) as executor:
                futures = {
                    executor.submit(run_one, bd, base_dirs.index(bd) + 1): bd
                    for bd in sorted_base_dirs
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bd_result, results, profiles = future.result()
                        base_all_results[bd_result] = results
                        base_profiles[bd_result]    = profiles
                        if not results and not _stop_event.is_set():
                            log(f"⚠️ [{os.path.basename(bd_result)}] Failed or no results.")
                    except Exception as e:
                        log(f"❌ Unexpected error: {e}")

            if _stop_event.is_set():
                return

            base_all_results = {bd: base_all_results[bd] for bd in base_dirs if bd in base_all_results}
            base_profiles    = {bd: base_profiles.get(bd, {}) for bd in base_dirs if bd in base_all_results}

            parent_dir = os.path.dirname(base_dirs[0])
            xlsx_path  = os.path.join(parent_dir, "compare_results.xlsx")
            write_report(base_all_results, xlsx_path, base_profiles)
            log(f"\nCompleted! Results saved to: {xlsx_path}")
            messagebox.showinfo("Done", f"Completed!\n{xlsx_path}")

        except Exception as e:
            log(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            if btn_stop:
                btn_stop.config(state=tk.DISABLED)
            btn_run.config(state=tk.NORMAL)

    threading.Thread(target=_run, daemon=True).start()


def extract():
    entry_v1         = gui_refs.get("entry_v1")
    entry_v2         = gui_refs.get("entry_v2")
    var_patch_v1     = gui_refs.get("var_patch_v1")
    var_patch        = gui_refs.get("var_patch")
    btn_extract      = gui_refs.get("btn_extract")
    var_extract_base = gui_refs.get("var_extract_base")
    txt_extract      = gui_refs.get("txt_extract")
    base_rows        = gui_refs.get("base_rows", [])

    all_base_dirs  = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]
    selected_label = var_extract_base.get() if var_extract_base else ""
    try:
        sel_idx   = int(selected_label.replace("Base Dir ", "")) - 1
        base_dirs = [all_base_dirs[sel_idx]] if 0 <= sel_idx < len(all_base_dirs) else all_base_dirs
    except (ValueError, IndexError):
        sel_idx   = 0
        base_dirs = all_base_dirs

    filenames_raw = txt_extract.get("1.0", tk.END).strip()

    if not base_dirs:
        messagebox.showerror("Error", "Please fill in Base Dir first.")
        return
    if not filenames_raw:
        messagebox.showerror("Error", "Please paste file names to extract.")
        return

    def _extract():
        try:
            btn_extract.config(state=tk.DISABLED)
            all_extract_dirs = []
            for i, bd in enumerate(base_dirs):
                idx = (sel_idx if len(base_dirs) == 1 else i) + 1
                log(f"[Base Dir {idx}] Extracting from {os.path.basename(bd)}...")
                try:
                    extract_dir, results = extract_files(bd, entry_v1.get(), entry_v2.get(), filenames_raw,
                                                         patched_v1=var_patch_v1.get(), patched_v2=var_patch.get())
                    for r in results:
                        v1 = "OK" if r["ok_v1"] else "NOT FOUND"
                        v2 = "OK" if r["ok_v2"] else "NOT FOUND"
                        log(f"  {r['filename']}  v1={v1}  v2={v2}")
                    log(f"[Base Dir {idx}] Extracted to: {extract_dir}")
                    all_extract_dirs.append(extract_dir)
                except Exception as e:
                    log(f"[Base Dir {idx}] ❌ ERROR: {e}")
            if all_extract_dirs:
                messagebox.showinfo("Done", "Extracted to:\n" + "\n".join(all_extract_dirs))
        except Exception as e:
            log(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            btn_extract.config(state=tk.NORMAL)

    threading.Thread(target=_extract, daemon=True).start()


def open_excel():
    base_rows = gui_refs.get("base_rows", [])
    base_dirs = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]
    if not base_dirs:
        messagebox.showerror("Error", "No base dir set.")
        return
    path = os.path.join(os.path.dirname(base_dirs[0]), "compare_results.xlsx")
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"File not found:\n{path}")


def open_output():
    selected = get_selected_base_dir(gui_refs.get("var_output_base").get())
    path = os.path.join(selected, "output") if selected else ""
    if path and os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"Folder not found:\n{path}")


def open_extract_dir():
    selected = get_selected_base_dir(gui_refs.get("var_extract_base").get())
    path = os.path.join(selected, "output", "diff_files") if selected else ""
    if path and os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"Folder not found:\n{path}")


if __name__ == "__main__":
    callbacks = {
        "run":              run,
        "stop":             stop,
        "extract":          extract,
        "open_excel":       open_excel,
        "open_output":      open_output,
        "open_extract_dir": open_extract_dir,
    }
    gui_root, gui_refs = setup_gui(callbacks)
    gui_root.mainloop()