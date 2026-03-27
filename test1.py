# test_comparator.py
import os
from comparator import compare_file
from excel_writer import write_report

BASE_DIR   = r"C:\Users\ntrinh\Desktop\Assert Testbank 2025\US (1381) NEW 2025R3\US (1381) NEW\OTHER CUSTOMERS\10. Miyake (36)\1. Baseline"
OUTPUT_V1  = os.path.join(BASE_DIR, "output", "output_v1")
OUTPUT_V2  = os.path.join(BASE_DIR, "output", "output_v2")
EXCEL_PATH = os.path.join(BASE_DIR, "output", "compare_results.xlsx")

if __name__ == "__main__":
    files = sorted([f for f in os.listdir(OUTPUT_V1) if f.endswith(".txt")])
    print(f"Tìm thấy {len(files)} file\n")

    all_results = []
    for filename in files:
        file_v1 = os.path.join(OUTPUT_V1, filename)
        file_v2 = os.path.join(OUTPUT_V2, filename)

        if not os.path.exists(file_v2):
            print(f"[SKIP] {filename} — không có trong output_v2")
            continue

        results = compare_file(file_v1, file_v2)
        all_results.append((filename, results))
        print(f"  Done: {filename}")

    write_report(all_results, EXCEL_PATH)
    print(f"\nXem kết quả tại: {EXCEL_PATH}")