import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.packaging import generate_weekly_needs, resolve_packages
from backend.parser import extract_relevant_meal_blocks, infer_frequency_per_week, parse_plan, prepare_llm_meal_blocks


class DomainTests(unittest.TestCase):
    def test_infer_frequency_per_week_handles_daily_and_business_day_rules(self):
        self.assertEqual(infer_frequency_per_week("2x ao dia 1 banana"), 14)
        self.assertEqual(infer_frequency_per_week("somente dias uteis 100 g de feijao"), 5)
        self.assertEqual(infer_frequency_per_week("3x por semana 170 g de iogurte"), 3)

    def test_parse_plan_extracts_structured_items(self):
        plan = parse_plan(
            """
Cafe da manha:
2 ovos
1 banana
200 ml de leite
Almoco:
150 g de arroz integral
120 g de peito de frango
somente dias uteis 100 g de feijao
            """
        )

        self.assertEqual(len(plan["items"]), 6)
        self.assertEqual(plan["items"][0]["normalizedFood"], "ovo")
        self.assertEqual(plan["items"][2]["baseUnit"], "ml")
        self.assertEqual(plan["items"][5]["frequencyPerWeek"], 5)

    def test_parse_plan_filters_options_and_ignores_support_sections(self):
        plan = parse_plan(
            """
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
            """
        )

        foods = [item["normalizedFood"] for item in plan["items"]]
        self.assertEqual(
            foods,
            [
                "iogurte natural",
                "whey protein",
                "arroz",
                "batata inglesa",
                "feijao",
                "carne moida",
                "arroz",
                "batata inglesa",
                "feijao",
                "carne moida",
            ],
        )

    def test_generate_weekly_needs_consolidates_items_by_food(self):
        plan = parse_plan(
            """
2 ovos
1 ovos
            """
        )

        weekly_needs = generate_weekly_needs(plan["items"])
        self.assertEqual(len(weekly_needs), 1)
        self.assertEqual(weekly_needs[0]["normalizedFood"], "ovo")
        self.assertEqual(weekly_needs[0]["weeklyQuantity"], 21)

    def test_resolve_packages_rounds_up_to_available_packaging(self):
        result = resolve_packages([{"normalizedFood": "ovo", "baseUnit": "unit", "weeklyQuantity": 9}])

        self.assertEqual(result[0]["status"], "resolved")
        self.assertEqual(result[0]["recommendation"]["totalQuantity"], 12)
        self.assertEqual(result[0]["overage"], 3)

    def test_parse_plan_detects_simple_equal_lunch_reference_locally(self):
        plan = parse_plan(
            """
Almoco:
150 g de arroz
120 g de frango

Jantar:
Igual almoco
            """
        )

        self.assertEqual(
            [item["mealLabel"] for item in plan["items"]],
            ["Almoco", "Almoco", "Jantar", "Jantar"],
        )

    def test_prepare_llm_meal_blocks_removes_irrelevant_sections_and_marks_complex_meals(self):
        text = """
PLANO ALIMENTAR
Nome: Teste

Cafe da manha:
2 ovos

Almoco:
Opcao 1:
- 5 colheres de arroz ou quinoa
- 1 concha de feijao

Jantar:
Igual almoco

Suplementacao:
- Creatina 5g
        """
        local_plan = parse_plan(text)
        prepared = prepare_llm_meal_blocks(text, local_plan["items"])
        relevant_meals = [block["mealLabel"] for block in extract_relevant_meal_blocks(text)]

        self.assertEqual(relevant_meals, ["Cafe da manha", "Almoco", "Jantar"])
        self.assertEqual([block["mealLabel"] for block in prepared["complexMeals"]], ["Almoco"])
        self.assertNotIn("Suplementacao", prepared["preprocessedText"])
        self.assertIn("Opcao 1:", prepared["preprocessedText"])
        self.assertNotIn("Igual almoco", prepared["preprocessedText"])


if __name__ == "__main__":
    unittest.main()
