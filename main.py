# main.py
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import threading
import concurrent.futures
import config
from config import load_config, save_config
from xml_builder import copy_project, build_xml, patch_compatibility_version
from runner import run_studios_parallel, cleanup
from comparator import compare_file
from excel_writer import write_report
from extract import extract_files
from parse import parse_version

load_config()


def browse_dir(entry):
    path = filedialog.askdirectory()
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)


def log(msg):
    txt_log.insert(tk.END, msg + "\n")
    txt_log.see(tk.END)
    root.update()


def get_base_dirs():
    return [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]


def refresh_dropdowns():
    if "var_output_base" not in globals() or "dd_output" not in globals():
        return
    dirs = get_base_dirs()
    for var, menu_btn in [(var_output_base, dd_output), (var_extract_base, dd_extract)]:
        current_val = var.get()
        menu = menu_btn["menu"]
        menu.delete(0, "end")
        for i, d in enumerate(dirs):
            label = f"Base Dir {i+1}"
            menu.add_command(label=label, command=lambda v=d, lbl=label, mb=menu_btn, _var=var: (_var.set(v), mb.config(text=lbl)))
        if dirs:
            if current_val in dirs:
                idx = dirs.index(current_val)
                menu_btn.config(text=f"Base Dir {idx+1}")
            else:
                var.set(dirs[0])
                menu_btn.config(text="Base Dir 1")
        else:
            var.set("")
            menu_btn.config(text="-")


def add_base_row(value=""):
    idx = len(base_rows) + 1
    row_frame = tk.Frame(bases_frame, bg=BG)
    row_frame.pack(fill=tk.X, pady=1)

    tk.Label(row_frame, text=f"Base Dir {idx}", bg=BG, fg=TEXT,
             font=("Segoe UI", 8), width=10, anchor="w").pack(side=tk.LEFT, padx=(0, 4))

    entry = ttk.Entry(row_frame, style="Small.TEntry", font=("Segoe UI", 8))
    entry.insert(0, value)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

    ttk.Button(row_frame, text="Browse", style="Small.TButton",
               command=lambda e=entry: browse_dir(e)).pack(side=tk.LEFT, padx=(0, 3))

    def remove_row():
        base_rows.remove(row_data)
        row_frame.destroy()
        # Relabel remaining rows
        for i, r in enumerate(base_rows):
            r["label"].config(text=f"Base Dir {i+1}")
        refresh_dropdowns()

    btn_remove = ttk.Button(row_frame, text="✕", style="Small.TButton", width=2,
                            command=remove_row)
    btn_remove.pack(side=tk.LEFT)

    # Bind mousewheel cho row mới để scroll hoạt động khi hover vào row
    def _bind_mw(widget):
        try:
            widget.bind("<MouseWheel>", _on_mousewheel)
        except Exception:
            pass
        for child in widget.winfo_children():
            _bind_mw(child)

    if "bases_canvas" in globals():
        _bind_mw(row_frame)

    row_data = {"entry": entry, "frame": row_frame, "label": row_frame.winfo_children()[0]}
    base_rows.append(row_data)
    refresh_dropdowns()


def on_add_base():
    add_base_row()


def run_single_base(base_dir, studio_v1, studio_v2, ver_v1, ver_v2):
    output_dir = os.path.join(base_dir, "output")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    output_v1 = os.path.join(output_dir, (ver_v1 + "_patched") if var_patch_v1.get() else ver_v1)
    output_v2 = os.path.join(output_dir, (ver_v2 + "_patched") if var_patch.get() else ver_v2)
    os.makedirs(output_v1, exist_ok=True)
    os.makedirs(output_v2, exist_ok=True)

    log(f"[{os.path.basename(base_dir)}] Copying project...")
    copy_v1, copy_v2 = copy_project(base_dir)

    if var_patch_v1.get():
        patch_compatibility_version(os.path.join(copy_v1, "Trusses"), ver_v1)
    if var_patch.get():
        patch_compatibility_version(os.path.join(copy_v2, "Trusses"), ver_v2)

    log(f"[{os.path.basename(base_dir)}] Building XML...")
    xml_v1 = os.path.join(base_dir, "project_v1.xml")
    xml_v2 = os.path.join(base_dir, "project_v2.xml")
    build_xml("project", os.path.join(copy_v1, "Trusses"), os.path.join(copy_v1, "Presets"), output_v1, xml_v1)
    build_xml("project", os.path.join(copy_v2, "Trusses"), os.path.join(copy_v2, "Presets"), output_v2, xml_v2)

    log(f"[{os.path.basename(base_dir)}] Running TrussStudio {ver_v1} & {ver_v2}...")
    run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2)

    os.remove(xml_v1)
    os.remove(xml_v2)
    cleanup(copy_v1, copy_v2)

    log(f"[{os.path.basename(base_dir)}] Comparing...")
    files = sorted([f for f in os.listdir(output_v1) if f.endswith(".txt")])
    all_results = []
    for filename in files:
        fv1 = os.path.join(output_v1, filename)
        fv2 = os.path.join(output_v2, filename)
        if not os.path.exists(fv2):
            log(f"[{os.path.basename(base_dir)}] [SKIP] {filename}")
            continue
        results = compare_file(fv1, fv2)
        all_results.append((filename, results))

    log(f"[{os.path.basename(base_dir)}] Done: {len(all_results)} file(s)")
    return base_dir, all_results


def run():
    studio_v1 = entry_v1.get().strip()
    studio_v2 = entry_v2.get().strip()
    base_dirs = get_base_dirs()

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

            import time
            log(f"Running {len(base_dirs)} base(s), max 4 at a time...")
            base_all_results = {}


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
                        patch_compatibility_version(os.path.join(copy_v1, "Trusses"), ver_v1)
                    if var_patch.get():
                        patch_compatibility_version(os.path.join(copy_v2, "Trusses"), ver_v2)

                    log(f"[Base Dir {idx}] Building XML...")
                    xml_v1 = os.path.join(bd, "project_v1.xml")
                    xml_v2 = os.path.join(bd, "project_v2.xml")
                    build_xml("project", os.path.join(copy_v1, "Trusses"), os.path.join(copy_v1, "Presets"), output_v1, xml_v1)
                    build_xml("project", os.path.join(copy_v2, "Trusses"), os.path.join(copy_v2, "Presets"), output_v2, xml_v2)

                    log(f"[Base Dir {idx}] Launching TrussStudio {ver_v1} & {ver_v2}...")
                    run_studios_parallel(studio_v1, xml_v1, studio_v2, xml_v2)

                    # Đợi TrussStudio ghi đủ file ra disk
                    # Thoát khi đủ file, hoặc khi số file không tăng trong 60s (TrussStudio đã xong/crash)
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

                    # Xóa XML và cleanup sau khi TrussStudio đã xong
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

                    log(f"[Base Dir {idx}] ✅ Done: {len(all_results)} file(s)")
                    return bd, all_results

                except Exception as e:
                    log(f"[Base Dir {idx}] ❌ ERROR: {e}")
                    # Cleanup nếu copy còn tồn tại
                    try:
                        if copy_v1 and os.path.exists(copy_v1):
                            shutil.rmtree(copy_v1)
                        if copy_v2 and os.path.exists(copy_v2):
                            shutil.rmtree(copy_v2)
                    except Exception:
                        pass
                    return bd, []

            # Sort base dirs: nặng nhất (nhiều .tdlTruss) chạy trước
            from pathlib import Path as _Path
            def count_trusses(bd):
                trusses_dir = os.path.join(bd, "Trusses")
                if not os.path.isdir(trusses_dir):
                    return 0
                return len(list(_Path(trusses_dir).glob("*.tdlTruss")))

            truss_counts = {bd: count_trusses(bd) for bd in base_dirs}
            sorted_base_dirs = sorted(base_dirs, key=lambda bd: truss_counts[bd], reverse=True)
            for i, bd in enumerate(sorted_base_dirs):
                log(f"  [{i+1}] {os.path.basename(bd)} — {truss_counts[bd]} truss(es)")

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(sorted_base_dirs))) as executor:
                futures = {
                    executor.submit(run_one, bd, i+1): bd
                    for i, bd in enumerate(sorted_base_dirs)
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        bd_result, results = future.result()
                        base_all_results[bd_result] = results
                        if not results:
                            log(f"⚠️ [{os.path.basename(bd_result)}] Failed or no results, sheet will be empty.")
                    except Exception as e:
                        log(f"❌ Unexpected error: {e}")

            # Giữ thứ tự Excel theo thứ tự user nhập ban đầu
            base_all_results = {bd: base_all_results[bd] for bd in base_dirs if bd in base_all_results}

            parent_dir = os.path.dirname(base_dirs[0])
            xlsx_path = os.path.join(parent_dir, "compare_results.xlsx")
            write_report(base_all_results, xlsx_path)
            log(f"\nCompleted! Results saved to: {xlsx_path}")
            messagebox.showinfo("Done", f"Completed!\n{xlsx_path}")

        except Exception as e:
            log(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            btn_run.config(state=tk.NORMAL)

    threading.Thread(target=_run, daemon=True).start()


def extract():
    base_dirs = get_base_dirs()
    filenames_raw = txt_extract.get("1.0", tk.END).strip()

    if not base_dirs:
        messagebox.showerror("Error", "Please fill in Base Dir first.")
        return
    if not filenames_raw:
        messagebox.showerror("Error", "Please paste file names to extract.")
        return

    base_dir = var_extract_base.get() or base_dirs[0]

    def _extract():
        try:
            btn_extract.config(state=tk.DISABLED)
            extract_dir, results = extract_files(base_dir, entry_v1.get(), entry_v2.get(), filenames_raw,
                                                  patched_v1=var_patch_v1.get(), patched_v2=var_patch.get())
            for r in results:
                v1 = "OK" if r["ok_v1"] else "NOT FOUND"
                v2 = "OK" if r["ok_v2"] else "NOT FOUND"
                log(f"  {r['filename']}  v1={v1}  v2={v2}")
            log(f"\nExtracted to: {extract_dir}")
            messagebox.showinfo("Done", f"Extracted to:\n{extract_dir}")
        except Exception as e:
            log(f"[ERROR] {e}")
            messagebox.showerror("Error", str(e))
        finally:
            btn_extract.config(state=tk.NORMAL)

    threading.Thread(target=_extract, daemon=True).start()


def open_excel():
    base_dirs = get_base_dirs()
    if not base_dirs:
        messagebox.showerror("Error", "No base dir set.")
        return
    path = os.path.join(os.path.dirname(base_dirs[0]), "compare_results.xlsx")
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"File not found:\n{path}")


def open_output():
    selected = var_output_base.get()
    path = os.path.join(selected, "output") if selected else ""
    if path and os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"Folder not found:\n{path}")


def open_extract_dir():
    selected = var_extract_base.get()
    path = os.path.join(selected, "output", "diff_files") if selected else ""
    if path and os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"Folder not found:\n{path}")


# ── GUI ────────────────────────────────────────────────────────────────────
from tkinter import ttk

BG      = "#f8faff"
PANEL   = "#ffffff"
ACCENT  = "#2a5298"
ACCENT2 = "#1e3d7a"
TEXT    = "#2a3550"
SUBTEXT = "#7a8aaa"
BORDER  = "#c5d0e8"

root = tk.Tk()
root.title("DeltaTruss")
root.configure(bg=BG)
root.resizable(True, True)
root.minsize(600, 500)
root.columnconfigure(0, weight=1)

style = ttk.Style()
style.theme_use("clam")
style.configure("Blue.TButton", background=ACCENT, foreground="white",
                font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat", padding=(16, 7))
style.map("Blue.TButton",
          background=[("active", ACCENT2), ("disabled", "#a0aec0")],
          foreground=[("active", "white"), ("disabled", "white")])
style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 9))
style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", ACCENT)])
style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                insertcolor=TEXT, padding=(6, 5))
style.map("TEntry", bordercolor=[("focus", ACCENT)])
style.configure("Green.TButton", background="#217346", foreground="white",
                font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat", padding=(16, 7))
style.map("Green.TButton",
          background=[("active", "#185a34"), ("disabled", "#a0aec0")],
          foreground=[("active", "white")])
style.configure("Small.TButton", background=ACCENT, foreground="white",
                font=("Segoe UI", 8), borderwidth=0, relief="flat", padding=(6, 3))
style.map("Small.TButton",
          background=[("active", ACCENT2), ("disabled", "#a0aec0")],
          foreground=[("active", "white")])
style.configure("Small.TEntry", fieldbackground=PANEL, foreground=TEXT,
                bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                insertcolor=TEXT, padding=(4, 2))
style.map("Small.TEntry", bordercolor=[("focus", ACCENT)])

# Title bar
title_frame = tk.Frame(root, bg=ACCENT, pady=13)
title_frame.pack(fill=tk.X)
tk.Label(title_frame, text="DeltaTruss", bg=ACCENT, fg="white",
         font=("Segoe UI", 13, "bold")).pack()

# Main content frame
content = tk.Frame(root, bg=BG)
content.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
content.columnconfigure(1, weight=1)
content.rowconfigure(1, weight=1)   # Bases area expand khi kéo dọc
content.rowconfigure(11, weight=1)  # Log area expand khi kéo dọc

def add_field(parent, row, label, key, saved_key=None):
    tk.Label(parent, text=label, bg=BG, fg=TEXT,
             font=("Segoe UI", 9, "bold")).grid(row=row, column=0, padx=(0, 6), pady=7, sticky="w")
    entry = ttk.Entry(parent, style="TEntry", font=("Segoe UI", 9))
    val = config.CONFIG.get(saved_key or key, "")
    entry.insert(0, val)
    entry.grid(row=row, column=1, padx=4, pady=7, sticky="ew")
    ttk.Button(parent, text="Browse", style="Blue.TButton",
               command=lambda e=entry: browse_dir(e)).grid(row=row, column=2, padx=(4, 0))
    return entry

# Base dirs section
bases_label_frame = tk.Frame(content, bg=BG)
bases_label_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(4, 0))
tk.Label(bases_label_frame, text="Base Directories", bg=BG, fg=SUBTEXT,
         font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
ttk.Button(bases_label_frame, text="+ Add Base", style="Blue.TButton",
           command=on_add_base, width=12).pack(side=tk.RIGHT)

# Scrollable bases container
bases_canvas_frame = tk.Frame(content, bg=BG)
bases_canvas_frame.grid(row=1, column=0, columnspan=3, sticky="nsew")
bases_canvas_frame.columnconfigure(0, weight=1)

bases_canvas = tk.Canvas(bases_canvas_frame, bg=BG, highlightthickness=0, height=120)
bases_scrollbar = ttk.Scrollbar(bases_canvas_frame, orient="vertical", command=bases_canvas.yview)
bases_canvas.configure(yscrollcommand=bases_scrollbar.set)

bases_canvas.grid(row=0, column=0, sticky="nsew")
bases_canvas_frame.rowconfigure(0, weight=1)
bases_scrollbar.grid(row=0, column=1, sticky="ns")

bases_frame = tk.Frame(bases_canvas, bg=BG)
bases_frame_id = bases_canvas.create_window((0, 0), window=bases_frame, anchor="nw")

def _on_bases_frame_configure(event):
    bases_canvas.configure(scrollregion=bases_canvas.bbox("all"))
    row_h = 24
    n = len(base_rows)
    if n <= 3:
        bases_canvas.configure(height=max(n, 1) * row_h)
        bases_scrollbar.grid_remove()
    else:
        bases_scrollbar.grid()

def _on_canvas_resize(event):
    bases_canvas.itemconfig(bases_frame_id, width=event.width)

bases_frame.bind("<Configure>", _on_bases_frame_configure)
bases_canvas.bind("<Configure>", _on_canvas_resize)

def _on_mousewheel(event):
    bases_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
bases_canvas.bind("<MouseWheel>", _on_mousewheel)
bases_frame.bind("<MouseWheel>", _on_mousewheel)

base_rows = []
saved_bases = config.CONFIG.get("base_dirs") or [config.CONFIG.get("base_dir", "")]
for val in saved_bases:
    add_base_row(val)

# Separator
tk.Frame(content, height=1, bg=BORDER).grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

# Studio entries
entry_v1 = add_field(content, 3, "Studio Dir V1", "studio_dir_v1")
entry_v2 = add_field(content, 4, "Studio Dir V2", "studio_dir_v2")

# Patch checkboxes
var_patch_v1 = tk.BooleanVar(value=False)
var_patch    = tk.BooleanVar(value=False)
chk_frame = tk.Frame(content, bg=BG)
chk_frame.grid(row=5, column=1, sticky="w", padx=4, pady=4)
ttk.Checkbutton(chk_frame, text="Patch CompatibilityVersion (V1)",
                variable=var_patch_v1, style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 16))
ttk.Checkbutton(chk_frame, text="Patch CompatibilityVersion (V2)",
                variable=var_patch, style="TCheckbutton").pack(side=tk.LEFT)

# Run row
var_output_base = tk.StringVar()
run_frame = tk.Frame(content, bg=BG)
run_frame.grid(row=6, column=0, columnspan=3, pady=14)
btn_run = ttk.Button(run_frame, text="▶  Run", style="Blue.TButton", command=run, width=20)
btn_run.pack(side=tk.LEFT, padx=(0, 8))
dd_output = tk.OptionMenu(run_frame, var_output_base, "")
dd_output.config(bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"),
                 activebackground=ACCENT2, activeforeground="white",
                 relief="flat", bd=0, highlightthickness=0, width=16,
                 textvariable="")
dd_output.pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(run_frame, text="📁  Output", style="Blue.TButton",
           command=open_output, width=14).pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(run_frame, text="📊  Excel", style="Green.TButton",
           command=open_excel, width=14).pack(side=tk.LEFT)

# Separator
tk.Frame(content, height=1, bg=BORDER).grid(row=7, column=0, columnspan=3, sticky="ew", pady=6)

# Extract section
tk.Label(content, text="Extract files:", bg=BG, fg=TEXT,
         font=("Segoe UI", 9, "bold")).grid(row=8, column=0, padx=(0, 6), pady=5, sticky="nw")
txt_extract = tk.Text(content, height=4, bg=PANEL, fg=TEXT,
                      relief="solid", bd=1, font=("Segoe UI", 9),
                      insertbackground=TEXT, padx=6, pady=5)
txt_extract.grid(row=8, column=1, columnspan=2, padx=4, pady=5, sticky="ew")

var_extract_base = tk.StringVar()
extract_frame = tk.Frame(content, bg=BG)
extract_frame.grid(row=9, column=0, columnspan=3, pady=10)
btn_extract = ttk.Button(extract_frame, text="⬇  Extract", style="Blue.TButton", command=extract, width=20)
btn_extract.pack(side=tk.LEFT, padx=(0, 8))
dd_extract = tk.OptionMenu(extract_frame, var_extract_base, "")
dd_extract.config(bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"),
                  activebackground=ACCENT2, activeforeground="white",
                  relief="flat", bd=0, highlightthickness=0, width=16,
                  textvariable="")
dd_extract.pack(side=tk.LEFT, padx=(0, 8))
ttk.Button(extract_frame, text="📁  Extracted", style="Blue.TButton",
           command=open_extract_dir, width=14).pack(side=tk.LEFT)

# Log area
tk.Label(content, text="Log", bg=BG, fg=SUBTEXT,
         font=("Segoe UI", 8)).grid(row=10, column=0, columnspan=3, sticky="sw", pady=(6, 0))
txt_log = tk.Text(content, height=10, bg=PANEL, fg=TEXT,
                  relief="solid", bd=1, font=("Consolas", 9),
                  insertbackground=TEXT, padx=8, pady=6)
txt_log.grid(row=11, column=0, columnspan=3, pady=(2, 16), sticky="nsew")

refresh_dropdowns()
root.mainloop()