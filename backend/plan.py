import secrets

from .normalization import normalize_food_name, normalize_unit, strip_accents, to_base_unit


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
    ambiguity_flags = normalize_strings(item.get("ambiguityFlags")) or infer_ambiguity_flags(item, unit)
    confidence = normalize_confidence(item.get("confidence"))
    if confidence is None:
        confidence = infer_confidence(item, unit, ambiguity_flags)

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
        "confidence": confidence,
        "ambiguityFlags": ambiguity_flags,
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


def infer_ambiguity_flags(item, normalized_unit):
    text = strip_accents(f"{item.get('originalText', '')} {item.get('notes', '')}")
    flags = []

    if "primeira opcao" in text or "priorizada" in text or "alternativa" in text:
        flags.append("alternative_choice")

    if "igual almoco" in text or "igual ao almoco" in text or "mesmas opcoes" in text:
        flags.append("meal_reference")

    if normalized_unit not in {"g", "ml", "unit"}:
        flags.append("household_measure")

    if "quantidade inferida" in text:
        flags.append("inferred_quantity")

    return flags


def infer_confidence(item, normalized_unit, ambiguity_flags):
    confidence = 0.98
    notes = strip_accents(item.get("notes"))

    if normalized_unit not in {"g", "ml", "unit"}:
        confidence -= 0.25

    if ambiguity_flags:
        confidence -= 0.1 * len(ambiguity_flags)

    if "quantidade inferida" in notes:
        confidence -= 0.35

    if "unidade convertida" in notes or "linha complexa" in notes:
        confidence -= 0.15

    return round(max(0.3, min(1.0, confidence)), 2)


def create_id():
    return secrets.token_hex(4)
