import secrets

from .normalization import normalize_food_name, normalize_unit, to_base_unit


def normalize_plan(plan, default_status="reviewed", parse_strategy="heuristic"):
    if not plan or not isinstance(plan.get("items"), list):
        raise ValueError("Plano invalido.")

    return {
        "id": plan.get("id") or create_id(),
        "originalText": plan.get("originalText") or "",
        "basePeriod": plan.get("basePeriod") or "weekly",
        "status": plan.get("status") or default_status,
        "parseStrategy": plan.get("parseStrategy") or parse_strategy,
        "parseWarnings": normalize_strings(plan.get("parseWarnings")),
        "parseMetadata": normalize_parse_metadata(plan.get("parseMetadata")),
        "items": [
            normalize_plan_item(item)
            for item in plan.get("items", [])
            if item and (item.get("normalizedFood") or item.get("originalFood"))
        ],
    }


def normalize_plan_item(item):
    normalized_food = normalize_food_name(item.get("normalizedFood") or item.get("originalFood") or "")
    unit = normalize_unit(item.get("unit") or item.get("baseUnit") or "unit")
    base = to_base_unit(item.get("quantity"), unit)

    return {
        "id": item.get("id") or create_id(),
        "mealLabel": item.get("mealLabel") or "Plano",
        "originalText": item.get("originalText") or item.get("originalFood") or normalized_food,
        "originalFood": item.get("originalFood") or normalized_food,
        "normalizedFood": normalized_food,
        "quantity": float(item.get("quantity") or 1),
        "unit": unit,
        "baseQuantity": base["quantity"],
        "baseUnit": base["unit"],
        "frequencyPerWeek": int(round(float(item.get("frequencyPerWeek") or 7))),
        "notes": item.get("notes") or "",
        "confidence": normalize_confidence(item.get("confidence")),
        "ambiguityFlags": normalize_strings(item.get("ambiguityFlags")),
    }


def normalize_strings(value):
    if not isinstance(value, list):
        return []

    return [str(entry).strip() for entry in value if str(entry).strip()]


def normalize_confidence(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    return round(max(0.0, min(1.0, numeric)), 2)


def normalize_parse_metadata(value):
    if not isinstance(value, dict):
        return {}

    normalized = {}
    for key, entry in value.items():
        if isinstance(entry, bool):
            normalized[key] = entry
            continue

        try:
            numeric = float(entry)
        except (TypeError, ValueError):
            if entry is None:
                continue
            normalized[key] = str(entry)
        else:
            normalized[key] = int(round(numeric)) if numeric.is_integer() else round(numeric, 2)

    return normalized


def create_id():
    return secrets.token_hex(4)
