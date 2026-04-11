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
from engine.runner import run_studios_parallel, cleanup
from comparator.compare_file import compare_file
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


def log(msg):
    """Log message to GUI, updating root window"""
    txt_log = gui_refs.get("txt_log")
    if txt_log:
        txt_log.insert(tk.END, msg + "\n")
        txt_log.see(tk.END)
        if gui_root:
            gui_root.update()


def _parse_profiles(base_dir, filenames):
    """
    Parse tdl profile cho từng file trong danh sách.
    filename format: "project_0031.txt" → "0031.tdlTruss"
    Trả về dict {filename: profile_dict}
    """
    profiles = {}
    trusses_dir = os.path.join(base_dir, "Trusses")
    for filename in filenames:
        # project_0031.txt → 0031.tdlTruss
        stem = filename.replace("project_", "").replace(".txt", "")
        tdl_path = os.path.join(trusses_dir, f"{stem}.tdlTruss")
        if os.path.exists(tdl_path):
            profile = parse_tdl(tdl_path)
            if profile:
                profiles[filename] = profile
    return profiles


def run():
    entry_v1 = gui_refs.get("entry_v1")
    entry_v2 = gui_refs.get("entry_v2")
    var_patch_v1 = gui_refs.get("var_patch_v1")
    var_patch = gui_refs.get("var_patch")
    btn_run = gui_refs.get("btn_run")
    base_rows = gui_refs.get("base_rows", [])
    
    studio_v1 = entry_v1.get().strip()
    studio_v2 = entry_v2.get().strip()
    base_dirs = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]

    if not base_dirs or not studio_v1 or not studio_v2:
        messagebox.showerror("Error", "Please fill in all paths.")
        return

    config.CONFIG["studio_dir_v1"] = studio_v1
    config.CONFIG["studio_dir_v2"] = studio_v2
    config.CONFIG["base_dirs"] = base_dirs
    save_config()
    btn_run.config(state=tk.DISABLED)

    def _run():
        try:
            ver_v1 = parse_version(studio_v1)
            ver_v2 = parse_version(studio_v2)

            log(f"Running {len(base_dirs)} base(s), max 5 at a time...")
            base_all_results = {}
            base_profiles    = {}

            def run_one(bd, idx):
                copy_v1 = copy_v2 = None
                try:
                    output_dir = os.path.join(bd, "output")
                    if os.path.exists(output_dir):
                        shutil.rmtree(output_dir)
                    output_v1 = os.path.join(output_dir, (ver_v1 + "_patched") if var_patch_v1.get() else ver_v1)
                    output_v2 = os.path.join(output_dir, (ver_v2 + "_patched") if var_patch.get() else ver_v2)
                    os.makedirs(output_v1, exist_ok=True)
                    os.makedirs(output_v2, exist_ok=True)

                    log(f"[Base Dir {idx}] Copying project...")
                    copy_v1, copy_v2 = copy_project(bd)

                    if var_patch_v1.get():
                        patch_compatibility_version(os.path.join(copy_v1, "Trusses"), get_version_number(ver_v1))
                    if var_patch.get():
                        patch_compatibility_version(os.path.join(copy_v2, "Trusses"), get_version_number(ver_v2))

                    log(f"[Base Dir {idx}] Building XML...")
                    xml_v1 = os.path.join(bd, "project_v1.xml")
                    xml_v2 = os.path.join(bd, "project_v2.xml")
                    build_xml("project", os.path.join(copy_v1, "Trusses"), os.path.join(copy_v1, "Presets"), output_v1, xml_v1)
                    build_xml("project", os.path.join(copy_v2, "Trusses"), os.path.join(copy_v2, "Presets"), output_v2, xml_v2)

                    log(f"[Base Dir {idx}] Launching TrussStudio {ver_v1} & {ver_v2}...")
                    run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2)

                    expected = len(list(__import__('pathlib').Path(os.path.join(bd, "Trusses")).glob("*.tdlTruss")))
                    done_v1 = done_v2 = 0
                    last_log = time.time()
                    last_change_time = time.time()
                    last_total = -1
                    while done_v1 < expected or done_v2 < expected:
                        done_v1 = len([f for f in os.listdir(output_v1) if f.endswith(".txt")])
                        done_v2 = len([f for f in os.listdir(output_v2) if f.endswith(".txt")])
                        current_total = done_v1 + done_v2
                        if current_total != last_total:
                            last_total = current_total
                            last_change_time = time.time()
                        if time.time() - last_change_time >= 60:
                            log(f"[Base Dir {idx}] ⚠️ No new files for 60s, assuming TrussStudio finished (v1={done_v1}/{expected}, v2={done_v2}/{expected})")
                            break
                        if time.time() - last_log >= 30:
                            log(f"[Base Dir {idx}] Waiting... v1={done_v1}/{expected}, v2={done_v2}/{expected}")
                            last_log = time.time()
                        time.sleep(0.5)

                    os.remove(xml_v1)
                    os.remove(xml_v2)
                    cleanup(copy_v1, copy_v2)
                    copy_v1 = copy_v2 = None

                    log(f"[Base Dir {idx}] Comparing...")
                    files = sorted([f for f in os.listdir(output_v1) if f.endswith(".txt")])
                    all_results = []
                    for filename in files:
                        fv1 = os.path.join(output_v1, filename)
                        fv2 = os.path.join(output_v2, filename)
                        if not os.path.exists(fv2):
                            log(f"[Base Dir {idx}] [SKIP] {filename}")
                            continue
                        results = compare_file(fv1, fv2)
                        all_results.append((filename, results))

                    # Parse tdl profiles
                    log(f"[Base Dir {idx}] Parsing truss profiles...")
                    filenames = [f for f, _ in all_results]
                    profiles = _parse_profiles(bd, filenames)

                    log(f"[Base Dir {idx}] ✅ Done: {len(all_results)} file(s)")
                    return bd, all_results, profiles

                except Exception as e:
                    log(f"[Base Dir {idx}] ❌ ERROR: {e}")
                    try:
                        if copy_v1 and os.path.exists(copy_v1):
                            shutil.rmtree(copy_v1)
                        if copy_v2 and os.path.exists(copy_v2):
                            shutil.rmtree(copy_v2)
                    except Exception:
                        pass
                    return bd, [], {}

            # Sort base dirs: nặng nhất chạy trước
            from pathlib import Path as _Path
            def count_trusses(bd):
                trusses_dir = os.path.join(bd, "Trusses")
                if not os.path.isdir(trusses_dir):
                    return 0
                return len(list(_Path(trusses_dir).glob("*.tdlTruss")))

            truss_counts = {bd: count_trusses(bd) for bd in base_dirs}
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
                        if not results:
                            log(f"⚠️ [{os.path.basename(bd_result)}] Failed or no results, sheet will be empty.")
                    except Exception as e:
                        log(f"❌ Unexpected error: {e}")

            # Giữ thứ tự Excel theo thứ tự user nhập ban đầu
            base_all_results = {bd: base_all_results[bd] for bd in base_dirs if bd in base_all_results}
            base_profiles    = {bd: base_profiles.get(bd, {}) for bd in base_dirs if bd in base_all_results}

            parent_dir = os.path.dirname(base_dirs[0])
            xlsx_path = os.path.join(parent_dir, "compare_results.xlsx")
            write_report(base_all_results, xlsx_path, base_profiles)
            log(f"\nCompleted! Results saved to: {xlsx_path}")
            messagebox.showinfo("Done", f"Completed!\n{xlsx_path}")

        except Exception as e:
            log(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            btn_run.config(state=tk.NORMAL)

    threading.Thread(target=_run, daemon=True).start()


def extract():
    entry_v1 = gui_refs.get("entry_v1")
    entry_v2 = gui_refs.get("entry_v2")
    var_patch_v1 = gui_refs.get("var_patch_v1")
    var_patch = gui_refs.get("var_patch")
    btn_extract = gui_refs.get("btn_extract")
    var_extract_base = gui_refs.get("var_extract_base")
    txt_extract = gui_refs.get("txt_extract")
    base_rows = gui_refs.get("base_rows", [])
    
    all_base_dirs = [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]
    selected_label = var_extract_base.get() if var_extract_base else ""
    try:
        sel_idx = int(selected_label.replace("Base Dir ", "")) - 1
        base_dirs = [all_base_dirs[sel_idx]] if 0 <= sel_idx < len(all_base_dirs) else all_base_dirs
    except (ValueError, IndexError):
        sel_idx = 0
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
        "run": run,
        "extract": extract,
        "open_excel": open_excel,
        "open_output": open_output,
        "open_extract_dir": open_extract_dir,
    }
    gui_root, gui_refs = setup_gui(callbacks)
    gui_root.mainloop()