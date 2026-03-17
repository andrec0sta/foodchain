from copy import deepcopy

from .catalog import BASE_PACKAGE_CATALOG
from .normalization import normalize_food_name, to_base_unit


def build_effective_catalog(overrides=None):
    catalog = deepcopy(BASE_PACKAGE_CATALOG)
    overrides = overrides or {}

    for food, packages in overrides.items():
        catalog[normalize_food_name(food)] = [normalize_package(entry) for entry in packages]

    return catalog


def normalize_package(entry):
    base = to_base_unit(entry.get("quantity"), entry.get("unit"))
    return {
        "quantity": base["quantity"],
        "unit": base["unit"],
        "packageType": entry.get("packageType") or "embalagem",
        "source": entry.get("source") or "override",
        "confidence": entry.get("confidence") or "user",
    }


def generate_weekly_needs(plan_items):
    grouped = {}

    for item in plan_items:
        normalized_food = normalize_food_name(item.get("normalizedFood") or item.get("originalFood") or "")
        if item.get("baseQuantity") is not None and item.get("baseUnit"):
            base = {"quantity": float(item.get("baseQuantity")), "unit": item.get("baseUnit")}
        else:
            base = to_base_unit(item.get("quantity"), item.get("unit"))

        weekly_quantity = base["quantity"] * float(item.get("frequencyPerWeek") or 0)
        key = f"{normalized_food}::{base['unit']}"

        if key not in grouped:
            grouped[key] = {
                "normalizedFood": normalized_food,
                "baseUnit": base["unit"],
                "weeklyQuantity": 0,
                "sourceItems": [],
            }

        grouped[key]["weeklyQuantity"] += weekly_quantity
        grouped[key]["sourceItems"].append(item.get("id"))

    return sorted(grouped.values(), key=lambda entry: entry["normalizedFood"])


def resolve_packages(weekly_needs, overrides=None):
    catalog = build_effective_catalog(overrides)
    results = []

    for need in weekly_needs:
        packages = [pkg for pkg in catalog.get(need["normalizedFood"], []) if pkg["unit"] == need["baseUnit"]]
        if not packages:
            results.append(
                {
                    **need,
                    "status": "missing_package",
                    "recommendation": None,
                    "overage": 0,
                }
            )
            continue

        recommendation = choose_best_combination(need["weeklyQuantity"], packages)
        results.append(
            {
                **need,
                "status": "resolved",
                "recommendation": recommendation,
                "overage": recommendation["totalQuantity"] - need["weeklyQuantity"],
            }
        )

    return results


def choose_best_combination(target_quantity, packages):
    scale = detect_scale([target_quantity] + [pkg["quantity"] for pkg in packages])
    sorted_packages = sorted(
        [{**pkg, "_scaledQuantity": int(round(pkg["quantity"] * scale))} for pkg in packages],
        key=lambda entry: entry["_scaledQuantity"],
    )
    scaled_target = int(round(target_quantity * scale))
    smallest = sorted_packages[0]["_scaledQuantity"]
    max_quantity = scaled_target + smallest * 6
    dp = [None] * (max_quantity + 1)
    dp[0] = {"totalPackages": 0, "combination": []}

    for total in range(max_quantity + 1):
        if dp[total] is None:
            continue

        for pkg in sorted_packages:
            nxt = total + pkg["_scaledQuantity"]
            if nxt > max_quantity:
                continue

            candidate = {
                "totalPackages": dp[total]["totalPackages"] + 1,
                "combination": append_package(dp[total]["combination"], pkg),
            }

            if dp[nxt] is None or candidate["totalPackages"] < dp[nxt]["totalPackages"]:
                dp[nxt] = candidate

    best = None
    for total in range(scaled_target, max_quantity + 1):
        if dp[total] is None:
            continue

        candidate = {
            "totalQuantity": total / scale,
            "totalPackages": dp[total]["totalPackages"],
            "overage": (total - scaled_target) / scale,
            "packages": dp[total]["combination"],
        }

        if best is None or is_better_combination(candidate, best):
            best = candidate

    return best


def append_package(existing, pkg):
    for index, entry in enumerate(existing):
        if entry["packageType"] == pkg["packageType"] and entry["quantity"] == pkg["quantity"] and entry["unit"] == pkg["unit"]:
            updated = list(existing)
            updated[index] = {**entry, "count": entry["count"] + 1}
            return updated

    return existing + [
        {
            "quantity": pkg["quantity"],
            "unit": pkg["unit"],
            "packageType": pkg["packageType"],
            "source": pkg["source"],
            "confidence": pkg["confidence"],
            "count": 1,
        }
    ]


def is_better_combination(candidate, current_best):
    if candidate["overage"] != current_best["overage"]:
        return candidate["overage"] < current_best["overage"]

    if candidate["totalPackages"] != current_best["totalPackages"]:
        return candidate["totalPackages"] < current_best["totalPackages"]

    return candidate["totalQuantity"] < current_best["totalQuantity"]


def detect_scale(values):
    for multiplier in (1, 10, 100):
        if all(abs(round(float(value) * multiplier) - float(value) * multiplier) < 1e-9 for value in values):
            return multiplier

    return 100
