# xml_builder.py
import os
import re
import uuid
import shutil
from pathlib import Path


def copy_project(base_dir):
    trusses_dir = os.path.join(base_dir, "Trusses")
    presets_dir = os.path.join(base_dir, "Presets")

    copy_v1 = os.path.join(base_dir, "copy_v1")
    copy_v2 = os.path.join(base_dir, "copy_v2")

    for dest in [copy_v1, copy_v2]:
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(trusses_dir, os.path.join(dest, "Trusses"))
        shutil.copytree(presets_dir, os.path.join(dest, "Presets"))

    # Xóa file backup (*.v69, *.v68, ...) mà TrussStudio tạo ra lần trước
    for dest in [copy_v1, copy_v2]:
        for f in Path(os.path.join(dest, "Trusses")).glob("*.v*"):
            f.unlink()

    print("Đã copy xong 2 bản")
    return copy_v1, copy_v2


def patch_compatibility_version(trusses_dir, target_version):
    """Patch CompatibilityVersion cho thư mục Trusses theo version chỉ định"""
    parts = target_version.split(".")
    val_version = f"{parts[0]}.{parts[1]}.{parts[2]}.0"

    truss_files = list(Path(trusses_dir).glob("*.tdlTruss"))

    for f in truss_files:
        content = f.read_text(encoding="utf-8")

        content = re.sub(
            r'(CompatibilityVersion=")[^"]*(")',
            rf'\g<1>{target_version}\2',
            content,
            count=1
        )

        content = re.sub(
            r'(<CompatibilityVersion Val=")[^"]*(")',
            rf'\g<1>{val_version}\2',
            content
        )

        f.write_text(content, encoding="utf-8")

    print(f"✓ Đã patch {len(truss_files)} file → CompatibilityVersion = {target_version}")


def build_xml(project_name, trusses_dir, presets_dir, output_dir, xml_path, only_files=None):
    """
    Build xml để TrussStudio chạy.
    only_files: list tên file cụ thể (dùng cho retry). None = glob toàn bộ thư mục.
    """
    if only_files is not None:
        truss_files = sorted([Path(trusses_dir) / f for f in only_files])
    else:
        truss_files = sorted(Path(trusses_dir).glob("*.tdlTruss"))

    trusses_xml = ""
    for f in truss_files:
        trusses_xml += f"""
        <truss>
            <guid>{uuid.uuid4()}</guid>
            <truss_file>{f.name}</truss_file>
        </truss>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<job>
  <job_info>
    <customer_info>
      <customer_name>SST QA VN</customer_name>
      <user_name>SST QA VN</user_name>
    </customer_info>
    <command>TXT-Output</command>
    <output_dir>{output_dir}</output_dir>
    <job_name>{project_name}</job_name>
    <job_desc> </job_desc>
    <preset_dir>{presets_dir}</preset_dir>
    <trusses_dir>{trusses_dir}</trusses_dir>
    <trusses>{trusses_xml}
    </trusses>
  </job_info>
</job>"""

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"XML đã tạo: {xml_path} ({len(truss_files)} file(s))")