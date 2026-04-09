# tdl_parser.py
import re
import xml.etree.ElementTree as ET


TYPE_MAP = {
    "t": "Truss",
    "j": "Jack",
    "r": "Roof",
    "g": "Girder",
}

KNOWN_SUBTYPES = {"attic", "hipdrop", "beampk", "gable", "filler"}
SUBTYPE_ORDER  = ["attic", "hipdrop", "beampk", "gable", "filler"]
SUBTYPE_LABELS = {
    "attic":   "Attic",
    "hipdrop": "Hip Drop",
    "beampk":  "Beam Pocket",
    "gable":   "Gable",
    "filler":  "Filler",
}


def _parse_script_lines(script_text):
    """Trả về dict {key: raw_value_string} từ Script block."""
    lines = {}
    for line in script_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            lines[key.strip().lower()] = val.strip()
        else:
            # dòng không có colon — bare token (filler, gable, attic trong ac block)
            lines.setdefault("_bare", []).append(line.strip().lower())
    return lines


def _parse_ac_subtypes(script_text):
    """
    Quét block sau dòng 'ac:' đến script key tiếp theo,
    thu thập các bare token nằm trong KNOWN_SUBTYPES.
    """
    subtypes = set()
    in_ac = False
    script_key_re = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*:")

    for line in script_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith("ac:"):
            in_ac = True
            # token ngay sau 'ac:' trên cùng dòng
            token = stripped[3:].strip().split()[0].lower() if stripped[3:].strip() else ""
            if token in KNOWN_SUBTYPES:
                subtypes.add(token)
            continue

        if in_ac:
            # nếu gặp script key mới thì kết thúc ac block
            if script_key_re.match(stripped):
                in_ac = False
                continue
            # bare token
            token = stripped.split()[0].lower()
            if token in KNOWN_SUBTYPES:
                subtypes.add(token)

    return subtypes


def _build_label(type_raw, subtypes, has_bp):
    """Ghép label theo thứ tự cố định."""
    collected = set(subtypes)
    if has_bp:
        collected.add("beampk")

    ordered = [s for s in SUBTYPE_ORDER if s in collected]
    parts = [SUBTYPE_LABELS[s] for s in ordered]
    base = TYPE_MAP.get(type_raw.lower(), type_raw.capitalize())
    parts.append(base)
    return " ".join(parts)


def _get_script_field(script_text, key):
    """Lấy value của một key trong Script, trả về string hoặc None."""
    pattern = re.compile(rf"^{re.escape(key)}:(.*)$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(script_text)
    return m.group(1).strip() if m else None


def _parse_wind(script_text):
    """Yes nếu wind speed (token 5, 0-indexed 4) > 0."""
    val = _get_script_field(script_text, "wind")
    if not val:
        return "No"
    tokens = val.split()
    try:
        speed = float(tokens[4])
        return "Yes" if speed > 0 else "No"
    except (IndexError, ValueError):
        return "No"


def _parse_snow(script_text):
    """Yes nếu snow ground load (token 4, 0-indexed 3) > 0."""
    val = _get_script_field(script_text, "snow")
    if not val:
        return "No"
    tokens = val.split()
    try:
        load = float(tokens[3])
        return "Yes" if load > 0 else "No"
    except (IndexError, ValueError):
        return "No"


def parse_tdl(filepath):
    """
    Parse một file .tdlTruss, trả về dict với 6 cột profile.
    """
    try:
        tree = ET.parse(filepath)
    except ET.ParseError:
        return None

    root = tree.getroot()

    script_el = root.find("Script")
    script_text = script_el.text or "" if script_el is not None else ""

    # --- truss_label ---
    type_raw   = _get_script_field(script_text, "type") or "t"
    subtypes   = _parse_ac_subtypes(script_text)
    has_bp     = bool(_get_script_field(script_text, "bp"))
    truss_label = _build_label(type_raw, subtypes, has_bp)

    # --- plys ---
    plys_raw = _get_script_field(script_text, "plys") or "1"
    try:
        plys = int(plys_raw.split()[0])
    except ValueError:
        plys = 1

    # --- wind / snow ---
    wind = _parse_wind(script_text)
    snow = _parse_snow(script_text)

    # --- analysis_status ---
    state_el  = root.find("State")
    status_el = state_el.find("AnalysisStatus") if state_el is not None else None
    analysis_status = status_el.get("Val", "") if status_el is not None else ""

    # --- load_template ---
    loading_el  = root.find("Loading")
    template_el = loading_el.find("LoadTemplate") if loading_el is not None else None
    load_template = template_el.get("Description", "") if template_el is not None else ""

    return {
        "truss_label":      truss_label,
        "plys":             plys,
        "wind":             wind,
        "snow":             snow,
        "analysis_status":  analysis_status,
        "load_template":    load_template,
    }