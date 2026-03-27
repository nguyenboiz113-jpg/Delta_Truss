# parse.py
import os
import re

def parse_version(studio_dir):
    """
    Extract version từ path, preserve suffix nếu có
    Examples:
    C:\SST\2026.3.0.49\TrussStudio → 2026.3.0.49
    C:\SST\2026.3.0.49 TC\TrussStudio → 2026.3.0.49 TC
    C:\SST\2026.3.0.49_RC1\TrussStudio → 2026.3.0.49_RC1
    """
    # Lấy tên folder cuối cùng (bỏ TrussStudio.exe nếu là file)
    path = studio_dir.rstrip("\\").rstrip("/")
    part = os.path.basename(path)
    
    # Nếu là file TrussStudio.exe, lấy parent folder
    if part.lower() == "trussstudio.exe":
        part = os.path.basename(os.path.dirname(path))
    elif part.lower() == "trussstudio":
        part = os.path.basename(os.path.dirname(path))
    
    # Match version (X.Y.Z.W) + giữ nguyên trailing content (space, underscore, etc)
    match = re.match(r"(\d+\.\d+\.\d+\.\d+.*)$", part)
    if match:
        return match.group(1).strip()
    
    return "unknown"


def get_version_number(version_string):
    """
    Extract only X.Y.Z.W từ version string (bỏ suffix)
    Examples:
    2026.3.0.49 → 2026.3.0.49
    2026.3.0.49 TC → 2026.3.0.49
    2026.3.0.49_RC1 → 2026.3.0.49
    """
    match = re.match(r"(\d+\.\d+\.\d+\.\d+)", version_string)
    return match.group(1) if match else "unknown"