# comparator.py
import re


def split_sections(filepath):
    """Đọc file TXT và tách thành dict {section_name: [lines]}"""
    sections = {}
    current_section = None
    current_lines = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if re.match(r"^==============", line):
                # Lưu section trước
                if current_section is not None:
                    sections[current_section] = current_lines
                # Bắt đầu section mới
                current_section = line.strip().strip("=").strip()
                current_lines = []
            else:
                if current_section is not None:
                    current_lines.append(line)

    # Lưu section cuối
    if current_section is not None:
        sections[current_section] = current_lines

    return sections


def compare_sections(sections_v1, sections_v2):
    """So sánh 2 dict sections, trả về list kết quả mỗi section"""
    results = []

    all_sections = sorted(set(list(sections_v1.keys()) + list(sections_v2.keys())))

    for section in all_sections:
        lines_v1 = sections_v1.get(section, [])
        lines_v2 = sections_v2.get(section, [])

        total_lines = max(len(lines_v1), len(lines_v2))

        # Đếm dòng khác nhau
        diff_count = 0
        for l1, l2 in zip(lines_v1, lines_v2):
            if l1 != l2:
                diff_count += 1

        # Dòng thừa ở file dài hơn tính là khác
        diff_count += abs(len(lines_v1) - len(lines_v2))

        pct = round(diff_count / total_lines * 100, 2) if total_lines > 0 else 0.0

        results.append({
            "section":    section,
            "lines_v1":   len(lines_v1),
            "lines_v2":   len(lines_v2),
            "diff_count": diff_count,
            "diff_pct":   pct,
        })

    return results


def compare_file(filepath_v1, filepath_v2):
    """So sánh 2 file TXT, trả về list kết quả theo section"""
    print(f"Đang so sánh:\n  v1: {filepath_v1}\n  v2: {filepath_v2}")
    sections_v1 = split_sections(filepath_v1)
    sections_v2 = split_sections(filepath_v2)
    results = compare_sections(sections_v1, sections_v2)
    print(f"Xong: {len(results)} sections")
    return results