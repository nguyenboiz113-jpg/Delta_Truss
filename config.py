import json
import os

CONFIG_FILE = "delta_truss_config.json"

CONFIG = {
    "base_dir":      "",
    "studio_dir_v1": "",
    "studio_dir_v2": "",
    "patch_v1":      False,
    "patch_v2":      False,
    "parallel_v1":   False,
    "trigger_v1":    False,
    "parallel_v2":   False,
    "trigger_v2":    False,
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            CONFIG.update(json.load(f))

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)