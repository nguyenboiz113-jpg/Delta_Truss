# extract.py
import os
import shutil
from parse import parse_version


def extract_files(base_dir, studio_v1, studio_v2, filenames_raw, patched_v1=False, patched_v2=False):
    """
    base_dir: thư mục gốc
    studio_v1, studio_v2: path studio để parse version
    filenames_raw: string paste từ GUI
    patched_v1: nếu True thì dùng thư mục ver_v1_patched
    patched_v2: nếu True thì dùng thư mục ver_v2_patched
    """
    ver_v1      = parse_version(studio_v1)
    ver_v2      = parse_version(studio_v2)
    ver_v1_dir  = ver_v1 + "_patched" if patched_v1 else ver_v1
    ver_v2_dir  = ver_v2 + "_patched" if patched_v2 else ver_v2
    output_v1   = os.path.join(base_dir, "output", ver_v1_dir)
    output_v2   = os.path.join(base_dir, "output", ver_v2_dir)
    extract_dir = os.path.join(base_dir, "output", "diff_files")
    extract_v1  = os.path.join(extract_dir, ver_v1_dir)
    extract_v2  = os.path.join(extract_dir, ver_v2_dir)

    if os.path.exists(extract_v1):
        shutil.rmtree(extract_v1)
    if os.path.exists(extract_v2):
        shutil.rmtree(extract_v2)
    os.makedirs(extract_v1)
    os.makedirs(extract_v2)

    filenames = [f.strip() for f in filenames_raw.replace("\n", " ").split() if f.strip()]

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

        results.append({
            "filename": filename,
            "ok_v1":    ok_v1,
            "ok_v2":    ok_v2,
        })

    return extract_dir, results