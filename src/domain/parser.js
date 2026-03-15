const { normalizeFoodName, normalizeUnit, stripAccents, toBaseUnit } = require("./normalization");

const MEAL_HINTS = [
  "cafe da manha",
  "colacao",
  "almoco",
  "lanche",
  "jantar",
  "ceia",
  "refeicao pre ou pos treino",
  "pre treino",
  "pos treino"
];

const IGNORE_SECTION_HINTS = [
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
  "plano alimentar",
  "loiana brandao"
];

const IGNORE_LINE_HINTS = [
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
  "coe e beba"
];

function parsePlan(inputText) {
  const text = (inputText || "").replace(/\r/g, "").trim();
  const lines = preprocessLines(text);

  let currentMeal = "Plano";
  let currentOption = null;
  let shouldCaptureCurrentOption = true;
  let ignoredSection = false;
  let mealStarted = true;
  const items = [];
  const mealTemplates = new Map();

  for (const rawLine of lines) {
    const normalizedLine = stripAccents(rawLine);

    if (isIgnoredSectionHeader(normalizedLine)) {
      ignoredSection = true;
      continue;
    }

    const mealCandidate = parseMealHeader(rawLine);
    if (mealCandidate) {
      currentMeal = mealCandidate;
      currentOption = null;
      shouldCaptureCurrentOption = true;
      ignoredSection = false;
      mealStarted = true;
      continue;
    }

    if (!mealStarted || ignoredSection) {
      continue;
    }

    const optionNumber = parseOptionNumber(normalizedLine);
    if (optionNumber !== null) {
      currentOption = optionNumber;
      shouldCaptureCurrentOption = optionNumber === 1;
      continue;
    }

    if (!shouldCaptureCurrentOption) {
      continue;
    }

    const clonedItems = maybeCloneMealReference(rawLine, currentMeal, mealTemplates);
    if (clonedItems.length) {
      items.push(...clonedItems);
      registerMealTemplate(mealTemplates, currentMeal, clonedItems);
      continue;
    }

    if (shouldIgnoreLine(normalizedLine)) {
      continue;
    }

    const candidateFragments = splitLineIntoFragments(rawLine)
      .map(selectPrimaryAlternative)
      .map(normalizeFragment)
      .filter(Boolean);

    for (const fragment of candidateFragments) {
      const parsedItem = parseItemFragment(fragment, currentMeal);
      if (!parsedItem || shouldDiscardParsedItem(parsedItem)) {
        continue;
      }

      items.push(parsedItem);
      registerMealTemplate(mealTemplates, currentMeal, [parsedItem]);
    }
  }

  return {
    id: createId(),
    originalText: text,
    basePeriod: "weekly",
    status: "parsed",
    items
  };
}

function preprocessLines(text) {
  const rawLines = text.split("\n").map((line) => line.trim()).filter(Boolean);
  const merged = [];

  for (const line of rawLines) {
    if (!merged.length) {
      merged.push(line);
      continue;
    }

    const previous = merged[merged.length - 1];
    if (shouldMergeLine(previous, line)) {
      merged[merged.length - 1] = `${previous} ${line}`.replace(/\s+/g, " ").trim();
    } else {
      merged.push(line);
    }
  }

  return merged;
}

function shouldMergeLine(previous, current) {
  if (/^[A-Za-z\u00C0-\u017F\s]+:?$/.test(previous) && previous.includes(":")) {
    return false;
  }

  if (parseOptionNumber(stripAccents(previous)) !== null) {
    return false;
  }

  if (isStandaloneHeader(current) || isBulletLike(current)) {
    return false;
  }

  if (parseOptionNumber(stripAccents(current)) !== null) {
    return false;
  }

  return /[-:(]$/.test(previous) || isBulletLike(previous) || /\bou\b/i.test(previous);
}

function isStandaloneHeader(line) {
  return Boolean(parseMealHeader(line)) || isIgnoredSectionHeader(stripAccents(line));
}

function parseMealHeader(line) {
  const normalized = stripAccents(line.replace(/:$/, ""));
  if (MEAL_HINTS.some((hint) => normalized.startsWith(hint))) {
    return line.replace(/:$/, "");
  }

  return null;
}

function isIgnoredSectionHeader(normalizedLine) {
  return IGNORE_SECTION_HINTS.some((hint) => normalizedLine.startsWith(hint));
}

function shouldIgnoreLine(normalizedLine) {
  if (!normalizedLine) {
    return true;
  }

  if (IGNORE_LINE_HINTS.some((hint) => normalizedLine.includes(hint))) {
    return true;
  }

  if (normalizedLine.startsWith("➔") || normalizedLine.startsWith("->")) {
    return true;
  }

  if (/^(carboidrato|proteina|proteina:|carboidrato:)$/.test(normalizedLine)) {
    return true;
  }

  if (/^[a-z\s]+:$/.test(normalizedLine) && !parseMealHeader(normalizedLine)) {
    return true;
  }

  return false;
}

function parseOptionNumber(normalizedLine) {
  const match = normalizedLine.match(/opcao\s*(\d+)/);
  return match ? Number(match[1]) : null;
}

function maybeCloneMealReference(line, currentMeal, mealTemplates) {
  const normalizedLine = stripAccents(line);
  if (!normalizedLine.includes("mesmas opcoes") && !normalizedLine.includes("mesmas opcoes e quantidades")) {
    return [];
  }

  if (!normalizedLine.includes("almoco")) {
    return [];
  }

  const sourceItems = mealTemplates.get("almoco") || [];
  return sourceItems.map((item) => ({
    ...item,
    id: createId(),
    mealLabel: currentMeal,
    notes: "Copiado automaticamente do almoco."
  }));
}

function registerMealTemplate(mealTemplates, mealLabel, entries) {
  const key = stripAccents(mealLabel);
  if (!mealTemplates.has(key)) {
    mealTemplates.set(key, []);
  }

  mealTemplates.get(key).push(...entries.map((entry) => ({ ...entry })));
}

function splitLineIntoFragments(line) {
  return line
    .split(/(?<!\d),(?!\d)/)
    .map((fragment) => fragment.trim())
    .filter(Boolean);
}

function selectPrimaryAlternative(fragment) {
  const primary = fragment
    .split(/\s+\bou\b\s+/i)[0]
    .replace(/\s*\+\s*.*/g, "")
    .trim();

  const parenthetical = fragment.match(/\((\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\)/i);
  if (parenthetical && !primary.includes(parenthetical[0])) {
    return `${primary} ${parenthetical[0]}`.trim();
  }

  return primary;
}

function normalizeFragment(fragment) {
  return fragment
    .replace(/^[\-•]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function parseItemFragment(fragment, mealLabel) {
  const frequencyPerWeek = inferFrequencyPerWeek(fragment);
  const cleanedFragment = cleanupFrequencyText(fragment);
  const explicitParenthetical = parseParentheticalAmount(cleanedFragment);

  if (explicitParenthetical) {
    const normalizedFood = normalizeFoodName(explicitParenthetical.food);
    return createItem({
      mealLabel,
      fragment,
      originalFood: explicitParenthetical.food,
      normalizedFood,
      quantity: explicitParenthetical.quantity,
      unit: explicitParenthetical.unit,
      frequencyPerWeek,
      notes: explicitParenthetical.notes
    });
  }

  const quantityOnlyMatch = cleanedFragment.match(/^(?<quantity>\d+(?:[.,]\d+)?)\s*(?<food>ovos?|bananas?|macas?)$/i);
  if (quantityOnlyMatch && quantityOnlyMatch.groups) {
    const rawQuantity = Number(quantityOnlyMatch.groups.quantity.replace(",", "."));
    const food = cleanupFoodLabel(quantityOnlyMatch.groups.food);
    return createItem({
      mealLabel,
      fragment,
      originalFood: food,
      normalizedFood: normalizeFoodName(food),
      quantity: rawQuantity,
      unit: "unit",
      frequencyPerWeek,
      notes: ""
    });
  }

  const regexes = [
    /(?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>kg|g|ml|l|unidades?|un|und|ovos?|bananas?|macas?|fatias?|colheres?|conchas?|copos?|potes?|pedacos?|file|dose|lata)\s+de\s+(?<food>.+)/i,
    /(?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>kg|g|ml|l|unidades?|un|und|ovos?|bananas?|macas?|fatias?|colheres?|conchas?|copos?|potes?|pedacos?|file|dose|lata)\s+(?<food>.+)/i,
    /(?<food>[A-Za-z\u00C0-\u017F\s]+)\s+(?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>kg|g|ml|l|unidades?|un|und)/i
  ];

  for (const regex of regexes) {
    const match = cleanedFragment.match(regex);
    if (!match || !match.groups) {
      continue;
    }

    const food = cleanupFoodLabel(match.groups.food);
    if (!food) {
      continue;
    }

    return createItem({
      mealLabel,
      fragment,
      originalFood: food,
      normalizedFood: normalizeFoodName(food),
      quantity: Number(match.groups.quantity.replace(",", ".")),
      unit: normalizeUnit(match.groups.unit),
      frequencyPerWeek,
      notes: inferNotes(fragment, food, normalizeUnit(match.groups.unit))
    });
  }

  const fallbackFood = cleanupFoodLabel(cleanedFragment);
  if (!fallbackFood || isObviouslyInstruction(fallbackFood)) {
    return null;
  }

  return createItem({
    mealLabel,
    fragment,
    originalFood: fallbackFood,
    normalizedFood: normalizeFoodName(fallbackFood),
    quantity: 1,
    unit: "unit",
    frequencyPerWeek,
    notes: "Quantidade inferida automaticamente; revise este item."
  });
}

function parseParentheticalAmount(fragment) {
  const match = fragment.match(/^(?<food>.+?)\s*\((?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>kg|g|ml|l)\)$/i);
  if (!match || !match.groups) {
    return null;
  }

  const food = cleanupFoodLabel(match.groups.food);
  if (!food) {
    return null;
  }

  return {
    food,
    quantity: Number(match.groups.quantity.replace(",", ".")),
    unit: normalizeUnit(match.groups.unit),
    notes: ""
  };
}

function createItem({ mealLabel, fragment, originalFood, normalizedFood, quantity, unit, frequencyPerWeek, notes }) {
  const baseAmount = toBaseUnit(quantity, unit);
  return {
    id: createId(),
    mealLabel,
    originalText: fragment,
    originalFood,
    normalizedFood,
    quantity,
    unit,
    baseQuantity: baseAmount.quantity,
    baseUnit: baseAmount.unit,
    frequencyPerWeek,
    notes
  };
}

function cleanupFoodLabel(food) {
  return (food || "")
    .replace(/\(.*?\)/g, "")
    .replace(/^\d+(?:[.,]\d+)?\s+/g, "")
    .replace(/^(um|uma|meio|meia)\s+/gi, "")
    .replace(/^(colheres?|conchas?|fatias?|pegadores?|pedacos?|file|dose|lata)\s+(de\s+)?/gi, "")
    .replace(/^sopa\s+(cheia\s+)?de\s+/gi, "")
    .replace(/^de\s+/gi, "")
    .replace(/\b(todo os dias|somente dias uteis|dias uteis|x ao dia|x\/dia|x por semana)\b/gi, "")
    .replace(/\b(opcao\s*\d+|carboidrato|proteina|colacao)\b/gi, "")
    .replace(/\b(meio|meia)\s+(medidor|scoop|lata|dose)\b/gi, "")
    .replace(/\b(medidor|scoop|colher|colheres|concha|conchas|fatia|fatias|file|pegadores|pedacos)\b/gi, "")
    .replace(/\b(inteiros?|inteiras?|medio|media|medios|medias|pequena|pequeno|cheia|cheio|amassada)\b/gi, "")
    .replace(/\bde sobremesa\b/gi, "")
    .replace(/\bsopa\b/gi, "")
    .replace(/\s+/g, " ")
    .replace(/^\s*de\s+/gi, "")
    .replace(/^[\-: ]+|[\-: ]+$/g, "")
    .trim();
}

function shouldDiscardParsedItem(item) {
  const normalizedFood = stripAccents(item.normalizedFood);
  if (!normalizedFood || normalizedFood.length < 2) {
    return true;
  }

  if (normalizedFood.includes("tabela")) {
    return true;
  }

  if (normalizedFood.includes("fruta")) {
    return true;
  }

  return isObviouslyInstruction(normalizedFood);
}

function isObviouslyInstruction(text) {
  const normalized = stripAccents(text);
  return [
    "a gosto",
    "temperos",
    "sal",
    "agua",
    "cha",
    "limonada",
    "maracuja",
    "adocante",
    "metade do prato",
    "colorido"
  ].some((hint) => normalized.includes(hint));
}

function inferFrequencyPerWeek(line) {
  const normalized = stripAccents(line);

  const daily = normalized.match(/(\d+(?:[.,]\d+)?)\s*x\s*(ao dia|\/dia)/);
  if (daily) {
    return Math.round(Number(daily[1].replace(",", ".")) * 7);
  }

  const weekly = normalized.match(/(\d+(?:[.,]\d+)?)\s*x\s*(por semana|na semana)/);
  if (weekly) {
    return Math.round(Number(weekly[1].replace(",", ".")));
  }

  if (normalized.includes("somente dias uteis") || normalized.includes("dias uteis")) {
    return 5;
  }

  if (normalized.includes("fim de semana")) {
    return 2;
  }

  return 7;
}

function cleanupFrequencyText(line) {
  return line
    .replace(/\b\d+(?:[.,]\d+)?\s*x\s*(ao dia|\/dia|por semana|na semana)\b/gi, "")
    .replace(/\bsomente dias uteis\b/gi, "")
    .replace(/\bdias uteis\b/gi, "")
    .replace(/\bfim de semana\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function inferNotes(fragment, originalFood, normalizedUnit) {
  if (!originalFood) {
    return "Alimento nao identificado com confianca.";
  }

  if (!["g", "ml", "unit"].includes(normalizedUnit)) {
    return "Unidade convertida para base automaticamente.";
  }

  if (fragment.length > 80) {
    return "Linha complexa; primeira alternativa foi priorizada automaticamente.";
  }

  return "";
}

function isBulletLike(line) {
  return /^[-•]/.test(line);
}

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

module.exports = {
  parsePlan,
  inferFrequencyPerWeek
};
