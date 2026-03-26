# parse.py
import re

def parse_version(studio_dir):
    # C:\SST\2026R3\2026.3.0.49\TrussStudio → 2026.3.0.49
    parts = studio_dir.replace("\\", "/").rstrip("/").split("/")
    for part in reversed(parts):
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", part):
            return part
    return "unknown"