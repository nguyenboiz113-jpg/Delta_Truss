# excel_writer.py
import os
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.series import SeriesLabel

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


def _write_summary_sheet(ws_summary, base_all_results, all_section_diff_counts):
    """Sheet 1: charts — Giống/Khác per base dir + Top sections bị diff."""

    # --- Data table for Chart 1 (hidden, used by chart) ---
    # Row 1: headers
    ws_summary.cell(row=1, column=1, value="Base Dir").font = BOLD
    ws_summary.cell(row=1, column=2, value="Same").font     = BOLD
    ws_summary.cell(row=1, column=3, value="Different").font = BOLD

    for i, (base_dir, all_results) in enumerate(base_all_results.items(), 2):
        name = os.path.basename(base_dir)
        same = sum(1 for _, results in all_results if all(r["diff_count"] == 0 for r in results))
        diff = len(all_results) - same
        ws_summary.cell(row=i, column=1, value=name)
        ws_summary.cell(row=i, column=2, value=same)
        ws_summary.cell(row=i, column=3, value=diff)

    n_bases = len(base_all_results)

    # Chart 1: Stacked bar — Giống vs Khác per base dir
    chart1 = BarChart()
    chart1.type    = "col"
    chart1.barDir  = "col"
    chart1.grouping = "stacked"
    chart1.overlap  = 100
    chart1.title   = "Same vs Different per Base Dir"
    chart1.y_axis.title = "Files"
    chart1.shape   = 4
    chart1.width   = 20
    chart1.height  = 14

    cats = Reference(ws_summary, min_col=1, min_row=2, max_row=1 + n_bases)

    data_same = Reference(ws_summary, min_col=2, min_row=1, max_row=1 + n_bases)
    s1 = openpyxl.chart.Series(data_same, title="Same")
    s1.graphicalProperties.solidFill = "C6EFCE"
    s1.graphicalProperties.line.solidFill = "70AD47"

    data_diff = Reference(ws_summary, min_col=3, min_row=1, max_row=1 + n_bases)
    s2 = openpyxl.chart.Series(data_diff, title="Different")
    s2.graphicalProperties.solidFill = "FFC7CE"
    s2.graphicalProperties.line.solidFill = "FF0000"

    chart1.append(s1)
    chart1.append(s2)
    chart1.set_categories(cats)
    chart1.shape = 4

    # Xoay label trục X 45°
    chart1.x_axis.txPr = None
    from openpyxl.chart.axis import TextBody
    chart1.x_axis.numFmt = "General"

    ws_summary.add_chart(chart1, "E1")

    # --- Data table for Chart 2 ---
    # Top 15 sections bị diff nhiều nhất
    sorted_sections = sorted(all_section_diff_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    sec_start_row = n_bases + 4
    ws_summary.cell(row=sec_start_row, column=1, value="Section").font     = BOLD
    ws_summary.cell(row=sec_start_row, column=2, value="Files with diff").font = BOLD

    for j, (section, count) in enumerate(sorted_sections, 1):
        ws_summary.cell(row=sec_start_row + j, column=1, value=section)
        ws_summary.cell(row=sec_start_row + j, column=2, value=count)

    # Chart 2: Horizontal bar — Top sections
    chart2 = BarChart()
    chart2.type     = "bar"
    chart2.barDir   = "bar"
    chart2.grouping = "clustered"
    chart2.title    = "Top Sections with Most Diffs"
    chart2.x_axis.title = "Files with diff"
    chart2.width    = 20
    chart2.height   = 14

    cats2  = Reference(ws_summary, min_col=1, min_row=sec_start_row + 1, max_row=sec_start_row + len(sorted_sections))
    data2  = Reference(ws_summary, min_col=2, min_row=sec_start_row,     max_row=sec_start_row + len(sorted_sections))
    s3 = openpyxl.chart.Series(data2, title="Files with diff")
    s3.graphicalProperties.solidFill = "DDEEFF"
    s3.graphicalProperties.line.solidFill = "4472C4"
    chart2.append(s3)
    chart2.set_categories(cats2)

    ws_summary.add_chart(chart2, "E16")

    ws_summary.column_dimensions["A"].width = 30
    ws_summary.column_dimensions["B"].width = 15
    ws_summary.column_dimensions["C"].width = 15


def write_detail_sheet(ws, base_all_results, base_profiles=None):
    """Sheet 2: tất cả base dir gộp vào 1 sheet, thêm cột Base Dir."""
    if base_profiles is None:
        base_profiles = {}

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
        base_name = os.path.basename(base_dir)
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
            row_idx += 1

    # Column widths
    ws.column_dimensions["A"].width = 20
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

    # Tính section diff counts cho chart 2
    all_section_diff_counts = {}
    for _, all_results in base_all_results.items():
        for _, results in all_results:
            for r in results:
                if r["diff_count"] > 0:
                    all_section_diff_counts[r["section"]] = all_section_diff_counts.get(r["section"], 0) + 1

    # Sheet 1: Summary + Charts
    ws_summary = wb.create_sheet(title="Summary")
    _write_summary_sheet(ws_summary, base_all_results, all_section_diff_counts)

    # Sheet 2: Detail — tất cả base dir gộp lại
    ws_detail = wb.create_sheet(title="Detail")
    write_detail_sheet(ws_detail, base_all_results, base_profiles)

    wb.save(output_path)
    print(f"Excel đã xuất: {output_path}")