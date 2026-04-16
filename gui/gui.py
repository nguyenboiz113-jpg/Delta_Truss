# gui.py - GUI setup for DeltaTruss
import tkinter as tk
from tkinter import ttk
import config

# Color scheme
BG      = "#f8faff"
PANEL   = "#ffffff"
ACCENT  = "#2a5298"
ACCENT2 = "#1e3d7a"
TEXT    = "#2a3550"
SUBTEXT = "#7a8aaa"
BORDER  = "#c5d0e8"

# Global GUI variables
root = None
txt_log = None
txt_extract = None
entry_v1 = None
entry_v2 = None
var_patch_v1 = None
var_patch = None
var_parallel_v1 = None
var_trigger_v1  = None
var_parallel_v2 = None
var_trigger_v2  = None
var_output_base = None
var_extract_base = None
btn_run = None
btn_stop = None
btn_extract = None
dd_output = None
dd_extract = None
base_rows = []
bases_canvas = None
bases_scrollbar = None
bases_frame = None
bases_frame_id = None


def browse_dir(entry):
    from tkinter import filedialog
    path = filedialog.askdirectory()
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)


def log(msg):
    if txt_log:
        txt_log.insert(tk.END, msg + "\n")
        txt_log.see(tk.END)
        if root:
            root.update()


def get_base_dirs():
    return [row["entry"].get().strip() for row in base_rows if row["entry"].get().strip()]


def get_selected_base_dir(label_text):
    dirs = get_base_dirs()
    if not label_text or label_text == "-":
        return dirs[0] if dirs else None
    try:
        idx = int(label_text.replace("Base Dir ", "")) - 1
        if 0 <= idx < len(dirs):
            return dirs[idx]
    except (ValueError, IndexError):
        pass
    return dirs[0] if dirs else None


def refresh_dropdowns():
    if dd_output is None or dd_extract is None:
        return
    n = len(base_rows)
    labels = [f"Base Dir {i+1}" for i in range(n)] if n > 0 else ["-"]
    for var, dd in [(var_output_base, dd_output), (var_extract_base, dd_extract)]:
        if list(dd["values"]) != labels:
            dd.config(values=labels)
        if var.get() not in labels:
            var.set(labels[0])


def add_base_row(value=""):
    idx = len(base_rows) + 1
    row_frame = tk.Frame(bases_frame, bg=BG)
    row_frame.pack(fill=tk.X, pady=1)

    lbl = tk.Label(row_frame, text=f"Base Dir {idx}", bg=BG, fg=TEXT,
                   font=("Segoe UI", 8), width=10, anchor="w")
    lbl.pack(side=tk.LEFT, padx=(0, 4))

    entry = ttk.Entry(row_frame, style="Small.TEntry", font=("Segoe UI", 8))
    entry.insert(0, value)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

    ttk.Button(row_frame, text="Browse", style="Small.TButton",
               command=lambda e=entry: browse_dir(e)).pack(side=tk.LEFT, padx=(0, 3))

    def remove_row():
        base_rows.remove(row_data)
        row_frame.destroy()
        for i, r in enumerate(base_rows):
            r["label"].config(text=f"Base Dir {i+1}")
        refresh_dropdowns()

    btn_remove = ttk.Button(row_frame, text="✕", style="Small.TButton", width=2,
                            command=remove_row)
    btn_remove.pack(side=tk.LEFT)

    for w in (row_frame, entry, lbl):
        w.bind("<MouseWheel>", _on_mousewheel)

    row_data = {"entry": entry, "frame": row_frame, "label": lbl}
    base_rows.append(row_data)
    row_frame.after_idle(refresh_dropdowns)


def on_add_base():
    add_base_row()


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


def _on_mousewheel(event):
    bases_canvas.yview_scroll(int(-1*(event.delta/120)), "units")


def setup_gui(callbacks):
    global root, txt_log, txt_extract, entry_v1, entry_v2, var_patch_v1, var_patch
    global var_parallel_v1, var_trigger_v1, var_parallel_v2, var_trigger_v2
    global var_output_base, var_extract_base, btn_run, btn_stop, btn_extract
    global dd_output, dd_extract
    global bases_canvas, bases_scrollbar, bases_frame, bases_frame_id

    base_rows.clear()

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
    style.configure("Red.TButton", background="#c0392b", foreground="white",
                    font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat", padding=(16, 7))
    style.map("Red.TButton",
              background=[("active", "#922b21"), ("disabled", "#a0aec0")],
              foreground=[("active", "white"), ("disabled", "white")])
    style.configure("Green.TButton", background="#217346", foreground="white",
                    font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat", padding=(16, 7))
    style.map("Green.TButton",
              background=[("active", "#185a34"), ("disabled", "#a0aec0")],
              foreground=[("active", "white")])
    style.configure("Small.TButton", background=ACCENT, foreground="white",
                    font=("Segoe UI", 8), borderwidth=0, relief="flat", padding=(6, 3))
    style.configure("Small.TEntry", fieldbackground=PANEL, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    insertcolor=TEXT, padding=(4, 2))
    style.map("Small.TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 9))
    style.map("TCheckbutton", background=[("active", BG)])

    # Title bar
    title_frame = tk.Frame(root, bg=ACCENT, pady=13)
    title_frame.pack(fill=tk.X)
    tk.Label(title_frame, text="DeltaTruss", bg=ACCENT, fg="white",
             font=("Segoe UI", 13, "bold")).pack()

    content = tk.Frame(root, bg=BG)
    content.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
    content.columnconfigure(1, weight=1)
    content.rowconfigure(1, weight=1)
    content.rowconfigure(11, weight=1)

    # Base dirs section
    bases_label_frame = tk.Frame(content, bg=BG)
    bases_label_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(4, 0))
    tk.Label(bases_label_frame, text="Base Directories", bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
    ttk.Button(bases_label_frame, text="+ Add Base", style="Blue.TButton",
               command=on_add_base, width=12).pack(side=tk.RIGHT)

    # Scrollable bases
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

    bases_frame.bind("<Configure>", _on_bases_frame_configure)
    bases_canvas.bind("<Configure>", _on_canvas_resize)
    bases_canvas.bind("<MouseWheel>", _on_mousewheel)
    bases_frame.bind("<MouseWheel>", _on_mousewheel)

    # Separator
    tk.Frame(content, height=1, bg=BORDER).grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

    # Studio entries
    entry_v1 = add_field(content, 3, "Studio Dir V1", "studio_dir_v1")
    entry_v2 = add_field(content, 4, "Studio Dir V2", "studio_dir_v2")

    # Patch checkboxes — load từ config
    var_patch_v1    = tk.BooleanVar(value=config.CONFIG.get("patch_v1",    False))
    var_patch       = tk.BooleanVar(value=config.CONFIG.get("patch_v2",    False))
    var_parallel_v1 = tk.BooleanVar(value=config.CONFIG.get("parallel_v1", False))
    var_trigger_v1  = tk.BooleanVar(value=config.CONFIG.get("trigger_v1",  False))
    var_parallel_v2 = tk.BooleanVar(value=config.CONFIG.get("parallel_v2", False))
    var_trigger_v2  = tk.BooleanVar(value=config.CONFIG.get("trigger_v2",  False))

    chk_frame = tk.Frame(content, bg=BG)
    chk_frame.grid(row=5, column=1, sticky="w", padx=4, pady=4)

    chk_row1 = tk.Frame(chk_frame, bg=BG)
    chk_row1.grid(row=0, column=0, sticky="w")
    ttk.Checkbutton(chk_row1, text="Patch CompatibilityVersion (V1)",
                    variable=var_patch_v1, style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 16))
    ttk.Checkbutton(chk_row1, text="Patch CompatibilityVersion (V2)",
                    variable=var_patch, style="TCheckbutton").pack(side=tk.LEFT)

    chk_row2 = tk.Frame(chk_frame, bg=BG)
    chk_row2.grid(row=1, column=0, sticky="w", pady=(2, 0))
    tk.Label(chk_row2, text="V1:", bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Checkbutton(chk_row2, text="ParallelChord",
                    variable=var_parallel_v1, style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 12))
    ttk.Checkbutton(chk_row2, text="AnalysisTrigger",
                    variable=var_trigger_v1,  style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 24))
    tk.Label(chk_row2, text="V2:", bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
    ttk.Checkbutton(chk_row2, text="ParallelChord",
                    variable=var_parallel_v2, style="TCheckbutton").pack(side=tk.LEFT, padx=(0, 12))
    ttk.Checkbutton(chk_row2, text="AnalysisTrigger",
                    variable=var_trigger_v2,  style="TCheckbutton").pack(side=tk.LEFT)

    # RUN ROW
    run_frame = tk.Frame(content, bg=BG)
    run_frame.grid(row=6, column=0, columnspan=3, pady=14)

    btn_run = ttk.Button(run_frame, text="▶  Run", style="Blue.TButton",
                         command=callbacks["run"], width=20)
    btn_run.pack(side=tk.LEFT, padx=(0, 8))

    btn_stop = ttk.Button(run_frame, text="⏹  Stop", style="Red.TButton",
                          command=callbacks["stop"], width=14, state=tk.DISABLED)
    btn_stop.pack(side=tk.LEFT, padx=(0, 8))

    var_output_base = tk.StringVar()
    dd_output = ttk.Combobox(run_frame, textvariable=var_output_base,
                             state="readonly", font=("Segoe UI", 9), width=16)
    dd_output.pack(side=tk.LEFT, padx=(0, 8))

    ttk.Button(run_frame, text="📁  Output", style="Blue.TButton",
               command=callbacks["open_output"], width=14).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(run_frame, text="📊  Excel", style="Green.TButton",
               command=callbacks["open_excel"], width=14).pack(side=tk.LEFT)

    # Separator
    tk.Frame(content, height=1, bg=BORDER).grid(row=7, column=0, columnspan=3, sticky="ew", pady=6)

    # EXTRACT SECTION
    tk.Label(content, text="Extract files:", bg=BG, fg=TEXT,
             font=("Segoe UI", 9, "bold")).grid(row=8, column=0, padx=(0, 6), pady=5, sticky="nw")

    txt_extract = tk.Text(content, height=4, bg=PANEL, fg=TEXT,
                          relief="solid", bd=1, font=("Segoe UI", 9),
                          insertbackground=TEXT, padx=6, pady=5)
    txt_extract.grid(row=8, column=1, columnspan=2, padx=4, pady=5, sticky="ew")

    extract_frame = tk.Frame(content, bg=BG)
    extract_frame.grid(row=9, column=0, columnspan=3, pady=10)

    btn_extract = ttk.Button(extract_frame, text="⬇  Extract", style="Blue.TButton",
                             command=callbacks["extract"], width=20)
    btn_extract.pack(side=tk.LEFT, padx=(0, 8))

    var_extract_base = tk.StringVar()
    dd_extract = ttk.Combobox(extract_frame, textvariable=var_extract_base,
                              state="readonly", font=("Segoe UI", 9), width=16)
    dd_extract.pack(side=tk.LEFT, padx=(0, 8))

    ttk.Button(extract_frame, text="📁  Extracted", style="Blue.TButton",
               command=callbacks["open_extract_dir"], width=14).pack(side=tk.LEFT)

    # Log area
    tk.Label(content, text="Log", bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 8)).grid(row=10, column=0, columnspan=3, sticky="sw", pady=(6, 0))
    txt_log = tk.Text(content, height=10, bg=PANEL, fg=TEXT,
                      relief="solid", bd=1, font=("Consolas", 9),
                      insertbackground=TEXT, padx=8, pady=6)
    txt_log.grid(row=11, column=0, columnspan=3, pady=(2, 16), sticky="nsew")

    # Load base dirs
    saved_bases = config.CONFIG.get("base_dirs") or [config.CONFIG.get("base_dir", "")]
    for val in saved_bases:
        add_base_row(val)
    if not base_rows:
        add_base_row()

    refresh_dropdowns()

    return root, {
        "txt_log":          txt_log,
        "txt_extract":      txt_extract,
        "entry_v1":         entry_v1,
        "entry_v2":         entry_v2,
        "var_patch_v1":     var_patch_v1,
        "var_patch":        var_patch,
        "var_parallel_v1":  var_parallel_v1,
        "var_trigger_v1":   var_trigger_v1,
        "var_parallel_v2":  var_parallel_v2,
        "var_trigger_v2":   var_trigger_v2,
        "var_output_base":  var_output_base,
        "var_extract_base": var_extract_base,
        "btn_run":          btn_run,
        "btn_stop":         btn_stop,
        "btn_extract":      btn_extract,
        "dd_output":        dd_output,
        "dd_extract":       dd_extract,
        "base_rows":        base_rows,
    }