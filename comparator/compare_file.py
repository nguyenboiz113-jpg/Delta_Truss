# compare_file.py
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed


def split_sections(filepath):
    sections = {}
    current_section = None
    current_lines = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.startswith("=============="):
                if current_section is not None:
                    sections[current_section] = current_lines
                current_section = line.strip("= ")
                current_lines = []
            elif current_section is not None:
                current_lines.append(line)

    if current_section is not None:
        sections[current_section] = current_lines

    return sections


def _compare_section_hash(lines_v1, lines_v2):
    """
    O(n) hash-based diff: đếm dòng không khớp giữa 2 multiset.
    Không quan tâm thứ tự, chỉ quan tâm nội dung — phù hợp cho báo cáo.
    """
    if lines_v1 == lines_v2:
        return 0

    c1 = Counter(lines_v1)
    c2 = Counter(lines_v2)

    # Dòng có ở v1 nhưng không đủ ở v2
    only_in_v1 = sum((c1 - c2).values())
    # Dòng có ở v2 nhưng không đủ ở v1
    only_in_v2 = sum((c2 - c1).values())

    return max(only_in_v1, only_in_v2)


def _compare_file_worker(args):
    """Worker chạy trong subprocess — nhận tuple để dùng với ProcessPoolExecutor."""
    filepath_v1, filepath_v2 = args
    sections_v1 = split_sections(filepath_v1)
    sections_v2 = split_sections(filepath_v2)

    results = []
    for section in sorted(sections_v1.keys() | sections_v2.keys()):
        lines_v1 = sections_v1.get(section, [])
        lines_v2 = sections_v2.get(section, [])
        total_lines = max(len(lines_v1), len(lines_v2))
        diff_count = _compare_section_hash(lines_v1, lines_v2)
        pct = round(diff_count / total_lines * 100, 2) if total_lines > 0 else 0.0
        results.append({
            "section":    section,
            "lines_v1":   len(lines_v1),
            "lines_v2":   len(lines_v2),
            "diff_count": diff_count,
            "diff_pct":   pct,
        })
    return filepath_v1, filepath_v2, results


def compare_file(filepath_v1, filepath_v2):
    """So sánh 1 cặp file — dùng trực tiếp hoặc gọi từ compare_many."""
    _, _, results = _compare_file_worker((filepath_v1, filepath_v2))
    return results


def compare_many(file_pairs, max_workers=None):
    """
    So sánh nhiều cặp file song song.
    file_pairs: list of (filepath_v1, filepath_v2)
    Trả về dict {(filepath_v1, filepath_v2): [results]}
    """
    all_results = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_compare_file_worker, pair): pair for pair in file_pairs}
        for future in as_completed(futures):
            fp1, fp2, results = future.result()
            all_results[(fp1, fp2)] = results
    return all_results