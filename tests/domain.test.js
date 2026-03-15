const test = require("node:test");
const assert = require("node:assert/strict");
const { parsePlan, inferFrequencyPerWeek } = require("../src/domain/parser");
const { generateWeeklyNeeds, resolvePackages } = require("../src/domain/packaging");

test("inferFrequencyPerWeek handles daily and business day rules", () => {
  assert.equal(inferFrequencyPerWeek("2x ao dia 1 banana"), 14);
  assert.equal(inferFrequencyPerWeek("somente dias uteis 100 g de feijao"), 5);
  assert.equal(inferFrequencyPerWeek("3x por semana 170 g de iogurte"), 3);
});

test("parsePlan extracts structured items", () => {
  const plan = parsePlan(`
Cafe da manha:
2 ovos
1 banana
200 ml de leite
Almoco:
150 g de arroz integral
120 g de peito de frango
somente dias uteis 100 g de feijao
  `);

  assert.equal(plan.items.length, 6);
  assert.equal(plan.items[0].normalizedFood, "ovo");
  assert.equal(plan.items[2].baseUnit, "ml");
  assert.equal(plan.items[5].frequencyPerWeek, 5);
});

test("parsePlan filters meal options and ignores support sections from nutrition PDF format", () => {
  const plan = parsePlan(`
PLANO ALIMENTAR
NOME: Andre Costa

CAFE DA MANHA
Opcao 1:
-1 iogurte natural (150ml)
- Meio medidor de whey protein (15g)

Opcao 2:
-1 fatia de pao integral
- 2 ovos inteiros ou 1 fatia de queijo minas

COLACAO:
-1 porcao de frutas (tabela)

ALMOCO:
Carboidrato:
-5 colheres de sopa de arroz branco ou integral ou quinoa (120g)
-5 colheres de sopa de batata inglesa ou pure de batata ou batata doce (150 g)

Proteina:
-1 concha pequena de feijao ou lentilha ou grao de bico
- 5 colheres de sopa cheia de carne moida ou bife de carne bovina (120g)
- ou 1 file de frango (120g)

JANTAR:
Opcao 1:
Refeicao completa (verduras e legumes preenchendo metade do prato). Se baseando com as mesmas opcoes e quantidades de alimentos descritos no almoco.

Tabela de frutas
- 1 banana prata

Suplementacao
- Creatina 5g
  `);

  const foods = plan.items.map((item) => item.normalizedFood);

  assert.deepEqual(foods, [
    "iogurte natural",
    "whey protein",
    "arroz",
    "batata inglesa",
    "feijao",
    "carne moida",
    "arroz",
    "batata inglesa",
    "feijao",
    "carne moida"
  ]);
});

test("generateWeeklyNeeds consolidates items by normalized food", () => {
  const plan = parsePlan(`
2 ovos
1 ovos
  `);

  const weeklyNeeds = generateWeeklyNeeds(plan.items);
  assert.equal(weeklyNeeds.length, 1);
  assert.equal(weeklyNeeds[0].normalizedFood, "ovo");
  assert.equal(weeklyNeeds[0].weeklyQuantity, 21);
});

test("resolvePackages rounds up to available packaging", () => {
  const result = resolvePackages([
    { normalizedFood: "ovo", baseUnit: "unit", weeklyQuantity: 9 }
  ]);

  assert.equal(result[0].status, "resolved");
  assert.equal(result[0].recommendation.totalQuantity, 12);
  assert.equal(result[0].overage, 3);
});
