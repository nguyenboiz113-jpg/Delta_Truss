# excel_writer.py
import os
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment

GREEN       = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
RED         = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
YELLOW      = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
BLUE_LIGHT  = PatternFill(start_color="DDEEFF", end_color="DDEEFF", fill_type="solid")
GRAY_LIGHT  = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
BOLD        = Font(bold=True)

PROFILE_COLS = [
    ("Truss Label",   "truss_label"),
    ("Plys",          "plys"),
    ("Wind",          "wind"),
    ("Snow",          "snow"),
    ("Status",        "analysis_status"),
    ("Version",       "version"),
    ("Load Template", "load_template"),
]
N_PROFILE = len(PROFILE_COLS)  # 7


def _profile_fill(key, value):
    if key == "analysis_status":
        return GREEN if value == "Passed" else RED
    if key in ("wind", "snow"):
        return YELLOW if value == "Yes" else GRAY_LIGHT
    return BLUE_LIGHT


def write_sheet(ws, all_results, profiles=None):
    if profiles is None:
        profiles = {}

    if not all_results:
        ws.cell(row=1, column=1, value="No results (base dir failed or missing Trusses/Presets folder)").font = BOLD
        return

    seen = set()
    sections = []
    for _, results in all_results:
        for r in results:
            if r["section"] not in seen:
                seen.add(r["section"])
                sections.append(r["section"])

    # Header row 1
    c = ws.cell(row=1, column=1, value="File")
    c.font = BOLD
    c.fill = GRAY_LIGHT

    for i, (label, _) in enumerate(PROFILE_COLS):
        col = 2 + i
        c = ws.cell(row=1, column=col, value=label)
        c.font = BOLD
        c.fill = BLUE_LIGHT
        c.alignment = Alignment(horizontal="center", wrap_text=True)

    section_start_col = 2 + N_PROFILE
    col = section_start_col
    for section in sections:
        ws.cell(row=1, column=col, value=section).font = BOLD
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 1)
        ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")
        col += 2
    ws.cell(row=1, column=col, value="Sections with diff").font = BOLD

    # Header row 2
    for i in range(N_PROFILE + 1):
        ws.cell(row=2, column=1 + i, value="")

    col = section_start_col
    for _ in sections:
        ws.cell(row=2, column=col,     value="Diff").font = BOLD
        ws.cell(row=2, column=col + 1, value="%").font    = BOLD
        col += 2

    # Data rows
    for row_idx, (filename, results) in enumerate(all_results, 3):
        file_cell = ws.cell(row=row_idx, column=1, value=filename)

        profile = profiles.get(filename, {})
        for i, (_, key) in enumerate(PROFILE_COLS):
            col = 2 + i
            value = profile.get(key, "-") if profile else "-"
            c = ws.cell(row=row_idx, column=col, value=value)
            if profile:
                c.fill = _profile_fill(key, value)

        result_map = {r["section"]: r for r in results}
        diff_sections = []
        has_any_diff = False
        col = section_start_col

        for section in sections:
            r = result_map.get(section)
            if r:
                diff_cell = ws.cell(row=row_idx, column=col,     value=r["diff_count"])
                pct_cell  = ws.cell(row=row_idx, column=col + 1, value=f"{r['diff_pct']}%")
                if r["diff_count"] > 0:
                    diff_cell.fill = RED
                    pct_cell.fill  = RED
                    diff_sections.append(r["section"])
                    has_any_diff = True
                else:
                    diff_cell.fill = GREEN
                    pct_cell.fill  = GREEN
            else:
                ws.cell(row=row_idx, column=col,     value="-")
                ws.cell(row=row_idx, column=col + 1, value="-")
            col += 2

        file_cell.fill = RED if has_any_diff else GREEN
        ws.cell(row=row_idx, column=col, value=", ".join(diff_sections) if diff_sections else "-")

    # Column widths
    ws.column_dimensions["A"].width = 25
    profile_widths = [30, 6, 6, 6, 10, 15, 60]
    for i, w in enumerate(profile_widths):
        ws.column_dimensions[openpyxl.utils.get_column_letter(2 + i)].width = w

    col = section_start_col
    for _ in sections:
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width     = 10
        ws.column_dimensions[openpyxl.utils.get_column_letter(col + 1)].width = 8
        col += 2
    ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 40

    ws.freeze_panes = ws.cell(row=3, column=2)


def write_report(base_all_results, output_path, base_profiles=None):
    if base_profiles is None:
        base_profiles = {}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for i, (base_dir, all_results) in enumerate(base_all_results.items()):
        sheet_name = f"Base Dir {i + 1} - {os.path.basename(base_dir)}"
        sheet_name = sheet_name[:31]
        ws = wb.create_sheet(title=sheet_name)
        profiles = base_profiles.get(base_dir, {})
        write_sheet(ws, all_results, profiles)

    wb.save(output_path)
    print(f"Excel đã xuất: {output_path}")