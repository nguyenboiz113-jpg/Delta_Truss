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
from engine.runner import launch_studios, finish_studios, cleanup, kill_all
from comparator.compare_file import compare_many
from report.excel_writer import write_report
from tools.extract import extract_files
from parse import parse_version, get_version_number
from gui.gui import setup_gui, get_selected_base_dir
from tkinter import messagebox
from parser.tdl_parser import parse_tdl

load_config()

# Global references to GUI elements (populated by setup_gui)
gui_root = None
gui_refs = {}

# Stop flag
_stop_event = threading.Event()

# Track copy dirs để cleanup khi stop
_active_copy_dirs: list[tuple] = []
_active_copy_dirs_lock = threading.Lock()

MAX_RETRY = 3
NO_PROGRESS_TIMEOUT = 60  # giây


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


def _get_done_stems(output_dir):
    """Trả về set tên file .txt (không có extension) trong output_dir"""
    if not os.path.isdir(output_dir):
        return set()
    return {os.path.splitext(f)[0] for f in os.listdir(output_dir) if f.endswith(".txt")}


def _txt_name(truss_filename):
    """Chuyển tên file tdlTruss → tên txt output. VD: 0039.TDLtRUSS → project_0039.TDLtRUSS.txt"""
    return f"project_{truss_filename}.txt"


def stop():
    """Kill tất cả TrussStudio + dọn dẹp copy dirs + xml"""
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
    entry_v1     = gui_refs.get("entry_v1")
    entry_v2     = gui_refs.get("entry_v2")
    var_patch_v1 = gui_refs.get("var_patch_v1")
    var_patch    = gui_refs.get("var_patch")
    btn_run      = gui_refs.get("btn_run")
    btn_stop     = gui_refs.get("btn_stop")
    base_rows    = gui_refs.get("base_rows", [])

    studio_v1 = entry_v1.get().strip()
    studio_v2 = entry_v2.get().strip()
    base_dirs = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]

    if not base_dirs or not studio_v1 or not studio_v2:
        messagebox.showerror("Error", "Please fill in all paths.")
        return

    config.CONFIG["studio_dir_v1"] = studio_v1
    config.CONFIG["studio_dir_v2"] = studio_v2
    config.CONFIG["base_dirs"]     = base_dirs
    save_config()

    _stop_event.clear()
    btn_run.config(state=tk.DISABLED)
    if btn_stop:
        btn_stop.config(state=tk.NORMAL)

    def _run():
        try:
            ver_v1 = parse_version(studio_v1)
            ver_v2 = parse_version(studio_v2)

            log(f"Running {len(base_dirs)} base(s), max 5 at a time...")
            base_all_results = {}
            base_profiles    = {}

            def run_one(bd, idx):
                copy_v1 = copy_v2 = None
                xml_v1  = os.path.join(bd, "project_v1.xml")
                xml_v2  = os.path.join(bd, "project_v2.xml")
                p1 = p2 = None
                try:
                    if _stop_event.is_set():
                        return bd, [], {}, set()

                    output_dir = os.path.join(bd, "output")
                    if os.path.exists(output_dir):
                        shutil.rmtree(output_dir)
                    output_v1 = os.path.join(output_dir, (ver_v1 + "_patched") if var_patch_v1.get() else ver_v1)
                    output_v2 = os.path.join(output_dir, (ver_v2 + "_patched") if var_patch.get() else ver_v2)
                    os.makedirs(output_v1, exist_ok=True)
                    os.makedirs(output_v2, exist_ok=True)

                    log(f"[Base Dir {idx}] Copying project...")
                    copy_v1, copy_v2 = copy_project(bd)
                    _register_copy(copy_v1, copy_v2)

                    if _stop_event.is_set():
                        return bd, [], {}, set()

                    if var_patch_v1.get():
                        patch_compatibility_version(os.path.join(copy_v1, "Trusses"), get_version_number(ver_v1))
                    if var_patch.get():
                        patch_compatibility_version(os.path.join(copy_v2, "Trusses"), get_version_number(ver_v2))

                    # Lấy danh sách tất cả file tdlTruss (giữ nguyên tên gốc)
                    trusses_dir_v1 = os.path.join(copy_v1, "Trusses")
                    trusses_dir_v2 = os.path.join(copy_v2, "Trusses")
                    all_truss_files = sorted(
                        f for f in os.listdir(trusses_dir_v1)
                        if f.lower().endswith(".tdltruss")
                    )
                    all_txt_names = [_txt_name(f) for f in all_truss_files]
                    expected = len(all_truss_files)

                    # current_files: file cần chạy lần này (lần đầu = tất cả)
                    current_files = list(all_truss_files)
                    not_responded = set()
                    retry_count = 0

                    while True:
                        if _stop_event.is_set():
                            return bd, [], {}, set()

                        log(f"[Base Dir {idx}] Building XML ({len(current_files)} file(s))...")
                        only_files = current_files if retry_count > 0 else None
                        build_xml("project", trusses_dir_v1, os.path.join(copy_v1, "Presets"), output_v1, xml_v1, only_files=only_files)
                        build_xml("project", trusses_dir_v2, os.path.join(copy_v2, "Presets"), output_v2, xml_v2, only_files=only_files)

                        log(f"[Base Dir {idx}] Launching TrussStudio {ver_v1} & {ver_v2}{'  [retry ' + str(retry_count) + ']' if retry_count > 0 else ''}...")
                        p1, p2 = launch_studios(studio_v1, xml_v1, studio_v2, xml_v2)

                        # Poll loop — vừa chờ process thoát vừa detect timeout
                        last_total = -1
                        last_change_time = time.time()
                        last_log_time = time.time()

                        while True:
                            if _stop_event.is_set():
                                return bd, [], {}, set()

                            done_v1 = len([f for f in os.listdir(output_v1) if f.endswith(".txt")])
                            done_v2 = len([f for f in os.listdir(output_v2) if f.endswith(".txt")])
                            current_total = done_v1 + done_v2

                            if current_total != last_total:
                                last_total = current_total
                                last_change_time = time.time()

                            # Log progress mỗi 30s
                            if time.time() - last_log_time >= 30:
                                log(f"[Base Dir {idx}] Waiting... v1={done_v1}/{expected}, v2={done_v2}/{expected}")
                                last_log_time = time.time()

                            # Cả 2 process đã thoát
                            both_done = p1.poll() is not None and p2.poll() is not None
                            if both_done:
                                break

                            # Timeout — không có file mới trong 60s
                            if time.time() - last_change_time >= NO_PROGRESS_TIMEOUT:
                                log(f"[Base Dir {idx}] ⚠️ No progress for {NO_PROGRESS_TIMEOUT}s (v1={done_v1}/{expected}, v2={done_v2}/{expected})")
                                kill_all()
                                break

                            time.sleep(0.5)

                        finish_studios(p1, p2)
                        p1 = p2 = None

                        # Xóa xml sau mỗi lần chạy
                        for xml in [xml_v1, xml_v2]:
                            if os.path.exists(xml):
                                os.remove(xml)

                        if _stop_event.is_set():
                            return bd, [], {}, set()

                        # Check missing
                        done_stems_v1 = _get_done_stems(output_v1)
                        done_stems_v2 = _get_done_stems(output_v2)
                        all_stems = {_strip_extensions(f) for f in all_truss_files}

                        missing_v1 = all_stems - done_stems_v1
                        missing_v2 = all_stems - done_stems_v2
                        missing = missing_v1 | missing_v2

                        if not missing:
                            log(f"[Base Dir {idx}] ✅ All {expected} file(s) done.")
                            break

                        # Tìm cây bị stuck đầu tiên
                        stuck_stem = min(missing)
                        stuck_filename = next(
                            (f for f in all_truss_files if _strip_extensions(f).lower() == stuck_stem.lower()),
                            None
                        )
                        if stuck_filename:
                            not_responded.add(_txt_name(stuck_filename))
                            log(f"[Base Dir {idx}] ⚠️ Not responded: {stuck_filename}")

                        if retry_count >= MAX_RETRY:
                            # Sau 3 lần retry vẫn còn missing → mark tất cả not responded
                            for stem in missing:
                                fn = next(
                                    (f for f in all_truss_files if _strip_extensions(f).lower() == stem.lower()),
                                    None
                                )
                                if fn:
                                    not_responded.add(_txt_name(fn))
                            log(f"[Base Dir {idx}] ❌ Max retries reached. {len(not_responded)} file(s) not responded.")
                            break

                        # Build retry_files = missing - stuck, theo thứ tự gốc
                        retry_files = [
                            f for f in all_truss_files
                            if _strip_extensions(f).lower() in missing
                            and f != stuck_filename
                        ]
                        if not retry_files:
                            log(f"[Base Dir {idx}] No more files to retry.")
                            break

                        current_files = retry_files
                        retry_count += 1
                        log(f"[Base Dir {idx}] Retrying {len(retry_files)} file(s) (attempt {retry_count}/{MAX_RETRY})...")

                    # Cleanup copy dirs
                    cleanup(copy_v1, copy_v2)
                    _unregister_copy(copy_v1, copy_v2)
                    copy_v1 = copy_v2 = None

                    if _stop_event.is_set():
                        return bd, [], {}, set()

                    # Compare — chỉ file có đủ cả v1 lẫn v2, dùng compare_many
                    log(f"[Base Dir {idx}] Comparing...")
                    file_pairs = []
                    for txt_name in all_txt_names:
                        if txt_name in not_responded:
                            continue
                        fv1 = os.path.join(output_v1, txt_name)
                        fv2 = os.path.join(output_v2, txt_name)
                        if os.path.exists(fv1) and os.path.exists(fv2):
                            file_pairs.append((fv1, fv2))

                    compare_results = compare_many(file_pairs)

                    all_results = []
                    for txt_name in all_txt_names:
                        fv1 = os.path.join(output_v1, txt_name)
                        fv2 = os.path.join(output_v2, txt_name)
                        if txt_name in not_responded:
                            all_results.append((txt_name, [{"section": "Not Responded", "diff_count": -1, "diff_pct": -1, "lines_v1": 0, "lines_v2": 0}]))
                        elif (fv1, fv2) in compare_results:
                            all_results.append((txt_name, compare_results[(fv1, fv2)]))

                    log(f"[Base Dir {idx}] Parsing truss profiles...")
                    filenames = [f for f, _ in all_results]
                    profiles = _parse_profiles(bd, filenames)

                    log(f"[Base Dir {idx}] ✅ Done: {len(all_results)} file(s), {len(not_responded)} not responded.")
                    return bd, all_results, profiles, not_responded

                except Exception as e:
                    log(f"[Base Dir {idx}] ❌ ERROR: {e}")
                    try:
                        if p1 or p2:
                            kill_all()
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
                    return bd, [], {}, set()

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

            base_not_responded = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(sorted_base_dirs))) as executor:
                futures = {
                    executor.submit(run_one, bd, base_dirs.index(bd) + 1): bd
                    for bd in sorted_base_dirs
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bd_result, results, profiles, not_responded = future.result()
                        base_all_results[bd_result]    = results
                        base_profiles[bd_result]       = profiles
                        base_not_responded[bd_result]  = not_responded
                        if not results and not _stop_event.is_set():
                            log(f"⚠️ [{os.path.basename(bd_result)}] Failed or no results.")
                    except Exception as e:
                        log(f"❌ Unexpected error: {e}")

            if _stop_event.is_set():
                return

            base_all_results   = {bd: base_all_results[bd] for bd in base_dirs if bd in base_all_results}
            base_profiles      = {bd: base_profiles.get(bd, {}) for bd in base_dirs if bd in base_all_results}
            base_not_responded = {bd: base_not_responded.get(bd, set()) for bd in base_dirs if bd in base_all_results}

            parent_dir = os.path.dirname(base_dirs[0])
            xlsx_path  = os.path.join(parent_dir, "compare_results.xlsx")
            write_report(base_all_results, xlsx_path, base_profiles, base_not_responded)
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
    entry_v1     = gui_refs.get("entry_v1")
    entry_v2     = gui_refs.get("entry_v2")
    var_patch_v1 = gui_refs.get("var_patch_v1")
    var_patch    = gui_refs.get("var_patch")
    btn_extract  = gui_refs.get("btn_extract")
    var_extract_base = gui_refs.get("var_extract_base")
    txt_extract  = gui_refs.get("txt_extract")
    base_rows    = gui_refs.get("base_rows", [])

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


# Setup GUI and run
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