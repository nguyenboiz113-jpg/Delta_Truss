# extract.py
import os
import shutil
from parse import parse_version


def extract_files(base_dir, studio_v1, studio_v2, filenames_raw, patched_v1=False, patched_v2=False):
    ver_v1      = parse_version(studio_v1)
    ver_v2      = parse_version(studio_v2)
    ver_v1_dir  = ver_v1 + "_patched" if patched_v1 else ver_v1
    ver_v2_dir  = ver_v2 + "_patched" if patched_v2 else ver_v2
    output_v1   = os.path.join(base_dir, "output", ver_v1_dir)
    output_v2   = os.path.join(base_dir, "output", ver_v2_dir)
    extract_dir = os.path.join(base_dir, "output", "diff_files")
    extract_v1  = os.path.join(extract_dir, ver_v1_dir)
    extract_v2  = os.path.join(extract_dir, ver_v2_dir)
    extract_truss = os.path.join(extract_dir, "Trusses")

    # Xóa sạch diff_files trước khi extract để đảm bảo ghi đè
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    os.makedirs(extract_v1, exist_ok=True)
    os.makedirs(extract_v2, exist_ok=True)
    os.makedirs(extract_truss, exist_ok=True)

    filenames = [f.strip() for f in filenames_raw.replace("\n", " ").split() if f.strip()]

    trusses_dir = os.path.join(base_dir, "Trusses")

    # Build map stem -> actual filename, ví dụ "0041" -> "0041.TDLtRUSS"
    truss_map = {}
    if os.path.isdir(trusses_dir):
        for f in os.listdir(trusses_dir):
            stem = f.split(".")[0]
            truss_map[stem] = f

    results = []
    for filename in filenames:
        src_v1 = os.path.join(output_v1, filename)
        src_v2 = os.path.join(output_v2, filename)
        ok_v1  = False
        ok_v2  = False

        if os.path.exists(src_v1):
            shutil.copy2(src_v1, os.path.join(extract_v1, filename))
            ok_v1 = True

        if os.path.exists(src_v2):
            shutil.copy2(src_v2, os.path.join(extract_v2, filename))
            ok_v2 = True

        # Bóc stem: "project_0041.TDLtRUSS.txt" -> "0041"
        stem = filename.replace("project_", "").split(".")[0]
        if stem in truss_map:
            truss_name = truss_map[stem]
            src_truss = os.path.join(trusses_dir, truss_name)
            shutil.copy2(src_truss, os.path.join(extract_truss, truss_name))

        results.append({
            "filename": filename,
            "ok_v1":    ok_v1,
            "ok_v2":    ok_v2,
        })

    return extract_dir, results