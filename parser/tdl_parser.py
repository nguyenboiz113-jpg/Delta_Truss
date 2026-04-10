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


def _parse_ac_subtypes(script_text):
    subtypes = set()
    in_ac = False
    script_key_re = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*:")

    for line in script_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith("ac:"):
            in_ac = True
            token = stripped[3:].strip().split()[0].lower() if stripped[3:].strip() else ""
            if token in KNOWN_SUBTYPES:
                subtypes.add(token)
            continue

        if in_ac:
            if script_key_re.match(stripped):
                in_ac = False
                continue
            token = stripped.split()[0].lower()
            if token in KNOWN_SUBTYPES:
                subtypes.add(token)

    return subtypes


def _build_label(type_raw, subtypes, has_bp):
    collected = set(subtypes)
    if has_bp:
        collected.add("beampk")
    ordered = [s for s in SUBTYPE_ORDER if s in collected]
    parts = [SUBTYPE_LABELS[s] for s in ordered]
    base = TYPE_MAP.get(type_raw.lower(), type_raw.capitalize())
    parts.append(base)
    return " ".join(parts)


def _get_script_field(script_text, key):
    pattern = re.compile(rf"^{re.escape(key)}:(.*)$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(script_text)
    return m.group(1).strip() if m else None


def _parse_wind(load_template):
    return "Yes" if "MPH" in load_template.upper() else "No"


def _parse_snow(load_template):
    return "Yes" if "Pg=" in load_template else "No"


def _trim_load_template(load_template):
    # Bỏ phần load numbers + wind/snow, lấy từ building code trở đi
    # Pattern: sau chuỗi dạng "...MPH-xxx/" hoặc "No Wind/"
    m = re.search(r'(?:MPH-[^/]+|No Wind|No Snow)/([A-Z])', load_template)
    if m:
        return load_template[m.start(1):]
    m = re.search(r'[A-Z]+-\d{4}/', load_template)
    return load_template[m.start():] if m else load_template


def parse_tdl(filepath):
    try:
        tree = ET.parse(filepath)
    except ET.ParseError:
        return None

    root = tree.getroot()

    script_el   = root.find("Script")
    script_text = script_el.text or "" if script_el is not None else ""

    # truss_label
    type_raw    = _get_script_field(script_text, "type") or "t"
    subtypes    = _parse_ac_subtypes(script_text)
    has_bp      = bool(_get_script_field(script_text, "bp"))
    truss_label = _build_label(type_raw, subtypes, has_bp)

    # plys
    plys_raw = _get_script_field(script_text, "plys") or "1"
    try:
        plys = int(plys_raw.split()[0])
    except ValueError:
        plys = 1

    # load_template
    loading_el    = root.find("Loading")
    template_el   = loading_el.find("LoadTemplate") if loading_el is not None else None
    raw_template  = template_el.get("Description", "") if template_el is not None else ""

    # wind / snow từ raw template trước khi trim
    wind = _parse_wind(raw_template)
    snow = _parse_snow(raw_template)

    load_template = _trim_load_template(raw_template)

    # analysis_status
    state_el        = root.find("State")
    status_el       = state_el.find("AnalysisStatus") if state_el is not None else None
    analysis_status = status_el.get("Val", "") if status_el is not None else ""

    # version
    version = root.get("Version", "")

    return {
        "truss_label":     truss_label,
        "plys":            plys,
        "wind":            wind,
        "snow":            snow,
        "analysis_status": analysis_status,
        "version":         version,
        "load_template":   load_template,
    }