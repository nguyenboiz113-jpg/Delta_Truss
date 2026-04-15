import os
import xml.etree.ElementTree as ET
from typing import Callable

CONFIG_FILENAME = "TrussStudio.exe.config"

FF_PARALLEL_CHORD   = "FF_ParallelChord"
FF_ANALYSIS_TRIGGER = "FF_PRMP_AnalysisTrigger"


def _get_config_path(studio_path: str) -> str:
    return os.path.join(os.path.dirname(studio_path), CONFIG_FILENAME)


def read_feature_flags(studio_path: str) -> dict:
    """
    Đọc FF_ParallelChord và FF_PRMP_AnalysisTrigger từ TrussStudio.exe.config.
    Trả về dict: {"FF_ParallelChord": bool, "FF_PRMP_AnalysisTrigger": bool}
    """
    config_path = _get_config_path(studio_path)
    result = {
        FF_PARALLEL_CHORD:   False,
        FF_ANALYSIS_TRIGGER: False,
    }
    if not os.path.exists(config_path):
        return result

    tree = ET.parse(config_path)
    app_settings = tree.getroot().find("appSettings")
    if app_settings is None:
        return result

    for add in app_settings.findall("add"):
        key = add.get("key", "")
        if key in result:
            result[key] = add.get("value", "false").strip().lower() == "true"

    return result


def write_feature_flags(studio_path: str, parallel: bool, trigger: bool):
    """
    Ghi FF_ParallelChord và FF_PRMP_AnalysisTrigger vào TrussStudio.exe.config.
    """
    config_path = _get_config_path(studio_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")

    tree = ET.parse(config_path)
    app_settings = tree.getroot().find("appSettings")
    if app_settings is None:
        raise ValueError(f"<appSettings> not found in {config_path}")

    flags = {
        FF_PARALLEL_CHORD:   str(parallel).lower(),
        FF_ANALYSIS_TRIGGER: str(trigger).lower(),
    }
    for add in app_settings.findall("add"):
        key = add.get("key", "")
        if key in flags:
            add.set("value", flags[key])

    tree.write(config_path, encoding="utf-8", xml_declaration=True)


def apply_and_restore_feature_flags(studio_path: str, parallel: bool, trigger: bool) -> Callable:
    """
    Backup giá trị cũ, ghi giá trị mới vào config.
    Trả về hàm restore() để gọi sau khi chạy xong (hoặc trong finally).
    """
    old = read_feature_flags(studio_path)
    write_feature_flags(studio_path, parallel, trigger)

    def restore():
        try:
            write_feature_flags(studio_path, old[FF_PARALLEL_CHORD], old[FF_ANALYSIS_TRIGGER])
        except Exception:
            pass

    return restore


def build_output_suffix(patched: bool, parallel: bool, trigger: bool) -> str:
    """
    Tạo suffix cho tên thư mục output.
    Ví dụ: patched=True, parallel=True, trigger=False → "_patched_parallel"
    """
    suffix = ""
    if patched:  suffix += "_patched"
    if parallel: suffix += "_parallel"
    if trigger:  suffix += "_trigger"
    return suffix


def build_output_name(ver: str, patched: bool, parallel: bool, trigger: bool) -> str:
    """
    Tạo tên thư mục output hoàn chỉnh.
    Ví dụ: "4.2.1_patched_parallel_trigger"
    """
    return ver + build_output_suffix(patched, parallel, trigger)