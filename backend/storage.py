import json
from pathlib import Path


DATA_DIR = Path.cwd() / "data"
LAST_PLAN_FILE = DATA_DIR / "last-plan.json"
PACKAGE_OVERRIDES_FILE = DATA_DIR / "package-overrides.json"


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_json(file_path, fallback):
    try:
        if not file_path.exists():
            return fallback
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(file_path, value):
    ensure_data_dir()
    file_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state():
    return {
        "lastPlan": read_json(LAST_PLAN_FILE, None),
        "packageOverrides": read_json(PACKAGE_OVERRIDES_FILE, {}),
    }


def save_plan(plan):
    write_json(LAST_PLAN_FILE, plan)


def save_package_overrides(overrides):
    write_json(PACKAGE_OVERRIDES_FILE, overrides)
