import re
import secrets

from .normalization import normalize_food_name, normalize_unit, strip_accents, to_base_unit


MEAL_HINTS = [
    "cafe da manha",
    "colacao",
    "almoco",
    "lanche",
    "jantar",
    "ceia",
    "refeicao pre ou pos treino",
    "pre treino",
    "pos treino",
]

IGNORE_SECTION_HINTS = [
    "suplementacao",
    "tabela de frutas",
    "ingestao de cha",
    "como faz o cha",
    "sugestao antes de dormir",
    "dicas",
    "nome:",
    "objetivo:",
    "data:",
    "validade:",
    "plano alimentar",
    "loiana brandao",
]

IGNORE_LINE_HINTS = [
    "verduras e legumes",
    "todas sao permitidas",
    "evitar sucos",
    "deixar o feijao",
    "absorcao de alguns nutrientes",
    "remolho",
    "misturar bem",
    "bata levemente",
    "depois de pronto",
    "despeje a massa",
    "leve ao microondas",
    "conte comigo",
    "seus resultados dependem",
    "ferva 500",
    "cubra e deixe",
    "coe e beba",
]


def parse_plan(input_text):
    text = str(input_text or "").replace("\r", "").strip()
    lines = preprocess_lines(text)

    current_meal = "Plano"
    current_option = None
    should_capture_current_option = True
    ignored_section = False
    meal_started = True
    items = []
    meal_templates = {}

    for raw_line in lines:
        normalized_line = strip_accents(raw_line)

        if is_ignored_section_header(normalized_line):
            ignored_section = True
            continue

        meal_candidate = parse_meal_header(raw_line)
        if meal_candidate:
            current_meal = meal_candidate
            current_option = None
            should_capture_current_option = True
            ignored_section = False
            meal_started = True
            continue

        if not meal_started or ignored_section:
            continue

        option_number = parse_option_number(normalized_line)
        if option_number is not None:
            current_option = option_number
            should_capture_current_option = option_number == 1
            continue

        if not should_capture_current_option:
            continue

        cloned_items = maybe_clone_meal_reference(raw_line, current_meal, meal_templates)
        if cloned_items:
            items.extend(cloned_items)
            register_meal_template(meal_templates, current_meal, cloned_items)
            continue

        if should_ignore_line(normalized_line):
            continue

        candidate_fragments = [
            normalize_fragment(select_primary_alternative(fragment))
            for fragment in split_line_into_fragments(raw_line)
        ]

        for fragment in [fragment for fragment in candidate_fragments if fragment]:
            parsed_item = parse_item_fragment(fragment, current_meal)
            if not parsed_item or should_discard_parsed_item(parsed_item):
                continue

            items.append(parsed_item)
            register_meal_template(meal_templates, current_meal, [parsed_item])

    return {
        "id": create_id(),
        "originalText": text,
        "basePeriod": "weekly",
        "status": "parsed",
        "items": items,
    }


def preprocess_lines(text):
    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
    merged = []

    for line in raw_lines:
        if not merged:
            merged.append(line)
            continue

        previous = merged[-1]
        if should_merge_line(previous, line):
            merged[-1] = re.sub(r"\s+", " ", f"{previous} {line}").strip()
        else:
            merged.append(line)

    return merged


def should_merge_line(previous, current):
    if re.match(r"^[A-Za-zÀ-ſ\s]+:?$", previous) and ":" in previous:
        return False

    if parse_option_number(strip_accents(previous)) is not None:
        return False

    if is_standalone_header(current) or is_bullet_like(current):
        return False

    if parse_option_number(strip_accents(current)) is not None:
        return False

    return bool(re.search(r"[-:(]$", previous) or is_bullet_like(previous) or re.search(r"\bou\b", previous, re.IGNORECASE))


def is_standalone_header(line):
    return bool(parse_meal_header(line) or is_ignored_section_header(strip_accents(line)))


def parse_meal_header(line):
    normalized = strip_accents(re.sub(r":$", "", line))
    if any(normalized.startswith(hint) for hint in MEAL_HINTS):
        return re.sub(r":$", "", line)

    return None


def is_ignored_section_header(normalized_line):
    return any(normalized_line.startswith(hint) for hint in IGNORE_SECTION_HINTS)


def should_ignore_line(normalized_line):
    if not normalized_line:
        return True

    if any(hint in normalized_line for hint in IGNORE_LINE_HINTS):
        return True

    if normalized_line.startswith("➔") or normalized_line.startswith("->"):
        return True

    if re.match(r"^(carboidrato|proteina|proteina:|carboidrato:)$", normalized_line):
        return True

    if re.match(r"^[a-z\s]+:$", normalized_line) and not parse_meal_header(normalized_line):
        return True

    return False


def parse_option_number(normalized_line):
    match = re.search(r"opcao\s*(\d+)", normalized_line)
    return int(match.group(1)) if match else None


def maybe_clone_meal_reference(line, current_meal, meal_templates):
    normalized_line = strip_accents(line)
    if "mesmas opcoes" not in normalized_line and "mesmas opcoes e quantidades" not in normalized_line:
        return []

    if "almoco" not in normalized_line:
        return []

    source_items = meal_templates.get("almoco", [])
    return [
        {
            **item,
            "id": create_id(),
            "mealLabel": current_meal,
            "notes": "Copiado automaticamente do almoco.",
        }
        for item in source_items
    ]


def register_meal_template(meal_templates, meal_label, entries):
    key = strip_accents(meal_label)
    meal_templates.setdefault(key, [])
    meal_templates[key].extend({**entry} for entry in entries)


def split_line_into_fragments(line):
    return [fragment.strip() for fragment in re.split(r"(?<!\d),(?!\d)", line) if fragment.strip()]


def select_primary_alternative(fragment):
    primary = re.split(r"\s+\bou\b\s+", fragment, maxsplit=1, flags=re.IGNORECASE)[0]
    primary = re.sub(r"\s*\+\s*.*", "", primary).strip()

    parenthetical = re.search(r"\((\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\)", fragment, re.IGNORECASE)
    if parenthetical and parenthetical.group(0) not in primary:
        return f"{primary} {parenthetical.group(0)}".strip()

    return primary


def normalize_fragment(fragment):
    return re.sub(r"\s+", " ", re.sub(r"^[\-•]\s*", "", fragment)).strip()


def parse_item_fragment(fragment, meal_label):
    frequency_per_week = infer_frequency_per_week(fragment)
    cleaned_fragment = cleanup_frequency_text(fragment)
    explicit_parenthetical = parse_parenthetical_amount(cleaned_fragment)

    if explicit_parenthetical:
        normalized_food = normalize_food_name(explicit_parenthetical["food"])
        return create_item(
            meal_label=meal_label,
            fragment=fragment,
            original_food=explicit_parenthetical["food"],
            normalized_food=normalized_food,
            quantity=explicit_parenthetical["quantity"],
            unit=explicit_parenthetical["unit"],
            frequency_per_week=frequency_per_week,
            notes=explicit_parenthetical["notes"],
        )

    quantity_only_match = re.match(r"^(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<food>ovos?|bananas?|macas?)$", cleaned_fragment, re.IGNORECASE)
    if quantity_only_match:
        raw_quantity = float(quantity_only_match.group("quantity").replace(",", "."))
        food = cleanup_food_label(quantity_only_match.group("food"))
        return create_item(
            meal_label=meal_label,
            fragment=fragment,
            original_food=food,
            normalized_food=normalize_food_name(food),
            quantity=raw_quantity,
            unit="unit",
            frequency_per_week=frequency_per_week,
            notes="",
        )

    regexes = [
        re.compile(r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l|unidades?|un|und|ovos?|bananas?|macas?|fatias?|colheres?|conchas?|copos?|potes?|pedacos?|file|dose|lata)\s+de\s+(?P<food>.+)", re.IGNORECASE),
        re.compile(r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l|unidades?|un|und|ovos?|bananas?|macas?|fatias?|colheres?|conchas?|copos?|potes?|pedacos?|file|dose|lata)\s+(?P<food>.+)", re.IGNORECASE),
        re.compile(r"(?P<food>[A-Za-zÀ-ſ\s]+)\s+(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l|unidades?|un|und)", re.IGNORECASE),
    ]

    for regex in regexes:
        match = regex.match(cleaned_fragment)
        if not match:
            continue

        food = cleanup_food_label(match.group("food"))
        if not food:
            continue

        unit = normalize_unit(match.group("unit"))
        return create_item(
            meal_label=meal_label,
            fragment=fragment,
            original_food=food,
            normalized_food=normalize_food_name(food),
            quantity=float(match.group("quantity").replace(",", ".")),
            unit=unit,
            frequency_per_week=frequency_per_week,
            notes=infer_notes(fragment, food, unit),
        )

    fallback_food = cleanup_food_label(cleaned_fragment)
    if not fallback_food or is_obviously_instruction(fallback_food):
        return None

    return create_item(
        meal_label=meal_label,
        fragment=fragment,
        original_food=fallback_food,
        normalized_food=normalize_food_name(fallback_food),
        quantity=1,
        unit="unit",
        frequency_per_week=frequency_per_week,
        notes="Quantidade inferida automaticamente; revise este item.",
    )


def parse_parenthetical_amount(fragment):
    match = re.match(r"^(?P<food>.+?)\s*\((?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l)\)$", fragment, re.IGNORECASE)
    if not match:
        return None

    food = cleanup_food_label(match.group("food"))
    if not food:
        return None

    return {
        "food": food,
        "quantity": float(match.group("quantity").replace(",", ".")),
        "unit": normalize_unit(match.group("unit")),
        "notes": "",
    }


def create_item(meal_label, fragment, original_food, normalized_food, quantity, unit, frequency_per_week, notes):
    base_amount = to_base_unit(quantity, unit)
    return {
        "id": create_id(),
        "mealLabel": meal_label,
        "originalText": fragment,
        "originalFood": original_food,
        "normalizedFood": normalized_food,
        "quantity": quantity,
        "unit": unit,
        "baseQuantity": base_amount["quantity"],
        "baseUnit": base_amount["unit"],
        "frequencyPerWeek": frequency_per_week,
        "notes": notes,
    }


def cleanup_food_label(food):
    cleaned = str(food or "")
    substitutions = [
        (r"\(.*?\)", ""),
        (r"^\d+(?:[.,]\d+)?\s+", ""),
        (r"^(um|uma|meio|meia)\s+", ""),
        (r"^(colheres?|conchas?|fatias?|pegadores?|pedacos?|file|dose|lata)\s+(de\s+)?", ""),
        (r"^sopa\s+(cheia\s+)?de\s+", ""),
        (r"^de\s+", ""),
        (r"\b(todo os dias|somente dias uteis|dias uteis|x ao dia|x/dia|x por semana)\b", ""),
        (r"\b(opcao\s*\d+|carboidrato|proteina|colacao)\b", ""),
        (r"\b(meio|meia)\s+(medidor|scoop|lata|dose)\b", ""),
        (r"\b(medidor|scoop|colher|colheres|concha|conchas|fatia|fatias|file|pegadores|pedacos)\b", ""),
        (r"\b(inteiros?|inteiras?|medio|media|medios|medias|pequena|pequeno|cheia|cheio|amassada)\b", ""),
        (r"\bde sobremesa\b", ""),
        (r"\bsopa\b", ""),
    ]

    for pattern, replacement in substitutions:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^\s*de\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\-: ]+|[\-: ]+$", "", cleaned)
    return cleaned.strip()


def should_discard_parsed_item(item):
    normalized_food = strip_accents(item.get("normalizedFood"))
    if not normalized_food or len(normalized_food) < 2:
        return True

    if "tabela" in normalized_food or "fruta" in normalized_food:
        return True

    return is_obviously_instruction(normalized_food)


def is_obviously_instruction(text):
    normalized = strip_accents(text)
    hints = [
        "a gosto",
        "temperos",
        "sal",
        "agua",
        "cha",
        "limonada",
        "maracuja",
        "adocante",
        "metade do prato",
        "colorido",
    ]
    return any(hint in normalized for hint in hints)


def infer_frequency_per_week(line):
    normalized = strip_accents(line)

    daily = re.search(r"(\d+(?:[.,]\d+)?)\s*x\s*(ao dia|/dia)", normalized)
    if daily:
        return round(float(daily.group(1).replace(",", ".")) * 7)

    weekly = re.search(r"(\d+(?:[.,]\d+)?)\s*x\s*(por semana|na semana)", normalized)
    if weekly:
        return round(float(weekly.group(1).replace(",", ".")))

    if "somente dias uteis" in normalized or "dias uteis" in normalized:
        return 5

    if "fim de semana" in normalized:
        return 2

    return 7


def cleanup_frequency_text(line):
    cleaned = re.sub(r"\b\d+(?:[.,]\d+)?\s*x\s*(ao dia|/dia|por semana|na semana)\b", "", line, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bsomente dias uteis\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdias uteis\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfim de semana\b", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def infer_notes(fragment, original_food, normalized_unit):
    if not original_food:
        return "Alimento nao identificado com confianca."

    if normalized_unit not in {"g", "ml", "unit"}:
        return "Unidade convertida para base automaticamente."

    if len(fragment) > 80:
        return "Linha complexa; primeira alternativa foi priorizada automaticamente."

    return ""


def is_bullet_like(line):
    return bool(re.match(r"^[-•]", line))


def create_id():
    return secrets.token_hex(4)
