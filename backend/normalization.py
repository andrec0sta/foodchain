import re
import unicodedata


FOOD_SYNONYMS = {
    "ovos": "ovo",
    "ovo cozido": "ovo",
    "bananas": "banana",
    "macas": "maca",
    "arroz branco": "arroz",
    "arroz integral cozido": "arroz integral",
    "peito frango": "peito de frango",
    "frango grelhado": "frango",
    "frango desfiado": "frango",
    "leite desnatado": "leite",
    "iogurte grego": "iogurte",
    "pao de forma integral": "pao integral",
    "queijo branco": "queijo",
}

UNIT_ALIASES = {
    "g": "g",
    "grama": "g",
    "gramas": "g",
    "kg": "kg",
    "kilo": "kg",
    "kilos": "kg",
    "quilo": "kg",
    "quilos": "kg",
    "ml": "ml",
    "l": "l",
    "litro": "l",
    "litros": "l",
    "unidade": "unit",
    "unidades": "unit",
    "un": "unit",
    "und": "unit",
    "ovo": "unit",
    "ovos": "unit",
    "banana": "unit",
    "bananas": "unit",
    "maca": "unit",
    "macas": "unit",
    "fatia": "unit",
    "fatias": "unit",
    "colher": "unit",
    "colheres": "unit",
    "copo": "unit",
    "copos": "unit",
    "pote": "unit",
    "potes": "unit",
}


def strip_accents(value):
    normalized = unicodedata.normalize("NFD", str(value or ""))
    no_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return no_accents.lower().strip()


def normalize_food_name(food):
    cleaned = re.sub(r"\s+", " ", strip_accents(food))
    return FOOD_SYNONYMS.get(cleaned, cleaned)


def normalize_unit(unit):
    if not unit:
        return "unit"

    cleaned = strip_accents(unit)
    return UNIT_ALIASES.get(cleaned, cleaned)


def to_base_unit(quantity, unit):
    normalized_unit = normalize_unit(unit)
    numeric_quantity = float(quantity or 0)

    if normalized_unit == "kg":
        return {"quantity": numeric_quantity * 1000, "unit": "g"}

    if normalized_unit == "l":
        return {"quantity": numeric_quantity * 1000, "unit": "ml"}

    return {"quantity": numeric_quantity, "unit": normalized_unit}
