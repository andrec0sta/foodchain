const FOOD_SYNONYMS = {
  ovos: "ovo",
  "ovo cozido": "ovo",
  bananas: "banana",
  macas: "maca",
  "arroz branco": "arroz",
  "arroz integral cozido": "arroz integral",
  "peito frango": "peito de frango",
  "frango grelhado": "frango",
  "frango desfiado": "frango",
  "leite desnatado": "leite",
  "iogurte grego": "iogurte",
  "pao de forma integral": "pao integral",
  "queijo branco": "queijo"
};

const UNIT_ALIASES = {
  g: "g",
  grama: "g",
  gramas: "g",
  kg: "kg",
  kilo: "kg",
  kilos: "kg",
  quilo: "kg",
  quilos: "kg",
  ml: "ml",
  l: "l",
  litro: "l",
  litros: "l",
  unidade: "unit",
  unidades: "unit",
  un: "unit",
  und: "unit",
  ovo: "unit",
  ovos: "unit",
  banana: "unit",
  bananas: "unit",
  maca: "unit",
  macas: "unit",
  fatia: "unit",
  fatias: "unit",
  colher: "unit",
  colheres: "unit",
  copo: "unit",
  copos: "unit",
  pote: "unit",
  potes: "unit"
};

function stripAccents(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function normalizeFoodName(food) {
  const cleaned = stripAccents(food).replace(/\s+/g, " ");
  return FOOD_SYNONYMS[cleaned] || cleaned;
}

function normalizeUnit(unit) {
  if (!unit) {
    return "unit";
  }

  const cleaned = stripAccents(unit);
  return UNIT_ALIASES[cleaned] || cleaned;
}

function toBaseUnit(quantity, unit) {
  const normalizedUnit = normalizeUnit(unit);
  const numericQuantity = Number(quantity) || 0;

  if (normalizedUnit === "kg") {
    return { quantity: numericQuantity * 1000, unit: "g" };
  }

  if (normalizedUnit === "l") {
    return { quantity: numericQuantity * 1000, unit: "ml" };
  }

  return { quantity: numericQuantity, unit: normalizedUnit };
}

module.exports = {
  FOOD_SYNONYMS,
  stripAccents,
  normalizeFoodName,
  normalizeUnit,
  toBaseUnit
};
