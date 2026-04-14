import os
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.chart.label import DataLabelList
from openpyxl.drawing.spreadsheet_drawing import AbsoluteAnchor
from openpyxl.drawing.xdr import XDRPoint2D, XDRPositiveSize2D
from openpyxl.utils.units import cm_to_EMU

GREEN_LIGHT = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
RED_LIGHT   = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
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

PIE_COLS      = 8
PIE_CHART_W   = 5 * 0.95  # cm
PIE_CHART_H   = 5 * 0.95  # cm


def _profile_fill(key, value):
    if key == "analysis_status":
        return GREEN_LIGHT if value == "Passed" else RED_LIGHT
    if key in ("wind", "snow"):
        return YELLOW if value == "Yes" else GRAY_LIGHT
    return BLUE_LIGHT


def _base_dir_names(base_all_results):
    """Trả về dict {base_dir: 'Base Dir N - tên_folder'}"""
    return {
        bd: f"Base Dir {i + 1} - {os.path.basename(bd)}"
        for i, bd in enumerate(base_all_results)
    }


def _write_summary_sheet(ws_summary, ws_data, base_all_results):
    """Sheet Summary: pie chart % Different cho từng base dir."""

    base_names = _base_dir_names(base_all_results)

    # Ghi data vào ws_data (sheet ẩn)
    ws_data.cell(row=1, column=1, value="Same")
    ws_data.cell(row=2, column=1, value="Different")

    bases = []
    for base_dir, all_results in base_all_results.items():
        name = base_names[base_dir]
        same = sum(1 for _, results in all_results if all(r["diff_count"] == 0 for r in results))
        diff = len(all_results) - same
        bases.append((name, same, diff))

    for i, (name, same, diff) in enumerate(bases):
        ws_data.cell(row=1, column=2 + i, value=same)
        ws_data.cell(row=2, column=2 + i, value=diff)

    # Vẽ pie chart cho từng base dir
    for i, (name, same, diff) in enumerate(bases):
        col_idx = i % PIE_COLS
        row_idx = i // PIE_COLS

        x = cm_to_EMU(col_idx * PIE_CHART_W)
        y = cm_to_EMU(row_idx * PIE_CHART_H)
        w = cm_to_EMU(PIE_CHART_W)
        h = cm_to_EMU(PIE_CHART_H)

        pie = PieChart()
        pie.title = name
        pie.width = PIE_CHART_W
        pie.height = PIE_CHART_H

        data_pie = Reference(ws_data, min_col=2 + i, min_row=1, max_row=2)
        cats_pie = Reference(ws_data, min_col=1, min_row=1, max_row=2)
        pie.add_data(data_pie)
        pie.set_categories(cats_pie)

        pt_same = DataPoint(idx=0)
        pt_same.graphicalProperties.solidFill = "70AD47"
        pt_diff = DataPoint(idx=1)
        pt_diff.graphicalProperties.solidFill = "FF4444"
        pie.series[0].dPt = [pt_same, pt_diff]

        pie.series[0].dLbls = DataLabelList()
        pie.series[0].dLbls.showPercent = True
        pie.series[0].dLbls.showVal = False
        pie.series[0].dLbls.showCatName = False
        pie.series[0].dLbls.showSerName = False
        pie.series[0].dLbls.showLegendKey = False

        anchor = AbsoluteAnchor(pos=XDRPoint2D(x, y), ext=XDRPositiveSize2D(w, h))
        pie.anchor = anchor
        ws_summary.add_chart(pie)


def write_detail_sheet(ws, base_all_results, base_profiles=None):
    """Sheet Detail: tất cả base dir gộp vào 1 sheet."""
    if base_profiles is None:
        base_profiles = {}

    base_names = _base_dir_names(base_all_results)

    # Collect ALL sections
    seen = set()
    sections = []
    for _, all_results in base_all_results.items():
        for _, results in all_results:
            for r in results:
                if r["section"] not in seen:
                    seen.add(r["section"])
                    sections.append(r["section"])

    # Header row 1
    ws.cell(row=1, column=1, value="Base Dir").font = BOLD
    ws.cell(row=1, column=1).fill = GRAY_LIGHT
    ws.cell(row=1, column=2, value="File").font = BOLD
    ws.cell(row=1, column=2).fill = GRAY_LIGHT

    for i, (label, _) in enumerate(PROFILE_COLS):
        col = 3 + i
        c = ws.cell(row=1, column=col, value=label)
        c.font = BOLD
        c.fill = BLUE_LIGHT
        c.alignment = Alignment(horizontal="center", wrap_text=True)

    section_start_col = 3 + N_PROFILE
    col = section_start_col
    for section in sections:
        ws.cell(row=1, column=col, value=section).font = BOLD
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 1)
        ws.cell(row=1, column=col).alignment = Alignment(horizontal="center")
        col += 2
    ws.cell(row=1, column=col, value="Sections with diff").font = BOLD

    # Header row 2
    for i in range(N_PROFILE + 2):
        ws.cell(row=2, column=1 + i, value="")
    col = section_start_col
    for _ in sections:
        ws.cell(row=2, column=col,     value="Diff").font = BOLD
        ws.cell(row=2, column=col + 1, value="%").font    = BOLD
        col += 2

    # Data rows
    row_idx = 3
    for base_dir, all_results in base_all_results.items():
        base_name = base_names[base_dir]
        profiles  = base_profiles.get(base_dir, {})

        for filename, results in all_results:
            ws.cell(row=row_idx, column=1, value=base_name)

            file_cell = ws.cell(row=row_idx, column=2, value=filename)

            profile = profiles.get(filename, {})
            for i, (_, key) in enumerate(PROFILE_COLS):
                col   = 3 + i
                value = profile.get(key, "-") if profile else "-"
                c     = ws.cell(row=row_idx, column=col, value=value)
                if profile:
                    c.fill = _profile_fill(key, value)

            result_map    = {r["section"]: r for r in results}
            diff_sections = []
            has_any_diff  = False
            col = section_start_col

            for section in sections:
                r = result_map.get(section)
                if r:
                    diff_cell = ws.cell(row=row_idx, column=col,     value=r["diff_count"])
                    pct_cell  = ws.cell(row=row_idx, column=col + 1, value=f"{r['diff_pct']}%")
                    if r["diff_count"] > 0:
                        diff_cell.fill = RED_LIGHT
                        pct_cell.fill  = RED_LIGHT
                        diff_sections.append(r["section"])
                        has_any_diff = True
                    else:
                        diff_cell.fill = GREEN_LIGHT
                        pct_cell.fill  = GREEN_LIGHT
                else:
                    ws.cell(row=row_idx, column=col,     value="-")
                    ws.cell(row=row_idx, column=col + 1, value="-")
                col += 2

            file_cell.fill = RED_LIGHT if has_any_diff else GREEN_LIGHT
            ws.cell(row=row_idx, column=col, value=", ".join(diff_sections) if diff_sections else "-")
            row_idx += 1

    # Column widths
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 25
    profile_widths = [30, 6, 6, 6, 10, 15, 60]
    for i, w in enumerate(profile_widths):
        ws.column_dimensions[openpyxl.utils.get_column_letter(3 + i)].width = w

    col = section_start_col
    for _ in sections:
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width     = 10
        ws.column_dimensions[openpyxl.utils.get_column_letter(col + 1)].width = 8
        col += 2
    ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 40

    ws.freeze_panes = ws.cell(row=3, column=3)
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(section_start_col - 1)}1"


def write_report(base_all_results, output_path, base_profiles=None):
    if base_profiles is None:
        base_profiles = {}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet ẩn chứa data cho pie charts
    ws_data = wb.create_sheet(title="_data")
    ws_data.sheet_state = "hidden"

    # Sheet 1: Summary — pie charts
    ws_summary = wb.create_sheet(title="Summary")
    _write_summary_sheet(ws_summary, ws_data, base_all_results)

    # Sheet 2: Detail
    ws_detail = wb.create_sheet(title="Detail")
    write_detail_sheet(ws_detail, base_all_results, base_profiles)

    wb.save(output_path)
    print(f"Excel đã xuất: {output_path}")