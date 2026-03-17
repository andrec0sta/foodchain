import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.llm import normalize_llm_payload, parse_plan_with_mode


class LlmTests(unittest.TestCase):
    def test_normalize_llm_payload_sanitizes_items(self):
        payload = {
            "warnings": ["item ambíguo", "", None],
            "items": [
                {
                    "mealLabel": "Cafe da manha",
                    "originalFood": "banana prata",
                    "quantity": "2",
                    "unit": "unit",
                    "frequencyPerWeek": "14",
                    "notes": "priorizada a primeira alternativa",
                },
                {
                    "mealLabel": "Ignorar",
                    "quantity": 1,
                },
            ],
        }

        normalized = normalize_llm_payload(payload)

        self.assertEqual(normalized["warnings"], ["item ambíguo"])
        self.assertEqual(len(normalized["items"]), 1)
        self.assertEqual(normalized["items"][0]["originalFood"], "banana prata")
        self.assertEqual(normalized["items"][0]["quantity"], 2)
        self.assertEqual(normalized["items"][0]["frequencyPerWeek"], 14)
        self.assertEqual(normalized["items"][0]["notes"], "priorizada a primeira alternativa")

    def test_parse_plan_with_mode_uses_hybrid_merge_with_mocked_llm(self):
        text = """
Cafe da manha:
2 ovos

Almoco:
Opcao 1:
- 150 g de arroz ou quinoa
- 120 g de frango
        """

        def fake_llm_client(**kwargs):
            self.assertIn("Almoco:", kwargs["user_prompt"])
            self.assertNotIn("Cafe da manha:\n2 ovos", kwargs["user_prompt"])
            return {
                "items": [
                    {
                        "mealLabel": "Almoco",
                        "originalFood": "arroz",
                        "quantity": 150,
                        "unit": "g",
                        "frequencyPerWeek": 7,
                        "notes": "primeira opcao priorizada",
                    },
                    {
                        "mealLabel": "Almoco",
                        "originalFood": "frango",
                        "quantity": 120,
                        "unit": "g",
                        "frequencyPerWeek": 7,
                        "notes": "",
                    },
                ]
            }

        plan = parse_plan_with_mode(
            text,
            mode="llm",
            env={"GEMINI_API_KEY": "test-key", "LLM_MODEL": "gemini-2.5-flash-lite"},
            llm_client=fake_llm_client,
        )

        self.assertEqual(plan["parseStrategy"], "llm:gemini")
        self.assertEqual([item["mealLabel"] for item in plan["items"]], ["Cafe da manha", "Almoco", "Almoco"])
        self.assertEqual(plan["items"][0]["normalizedFood"], "ovo")
        self.assertEqual(plan["items"][1]["normalizedFood"], "arroz")
        self.assertEqual(plan["parseMetadata"]["complexMealCount"], 1)
        self.assertEqual(plan["parseMetadata"]["thinkingBudget"], 0)

    def test_parse_plan_with_mode_falls_back_to_stronger_model_when_lite_is_poor(self):
        calls = []

        def fake_llm_client(**kwargs):
            calls.append(kwargs["model"])
            if kwargs["model"] == "gemini-2.5-flash-lite":
                return {"items": []}
            return {
                "items": [
                    {
                        "mealLabel": "Almoco",
                        "originalFood": "frango",
                        "quantity": 120,
                        "unit": "g",
                        "frequencyPerWeek": 7,
                        "notes": "",
                    }
                ]
            }

        plan = parse_plan_with_mode(
            """
Almoco:
Opcao 1:
- 120 g de frango
            """,
            mode="llm",
            env={"GEMINI_API_KEY": "test-key", "LLM_MODEL": "gemini-2.5-flash-lite", "LLM_FALLBACK_MODEL": "gemini-2.5-flash"},
            llm_client=fake_llm_client,
        )

        self.assertEqual(calls, ["gemini-2.5-flash-lite", "gemini-2.5-flash"])
        self.assertTrue(plan["parseMetadata"]["usedFallbackModel"])
        self.assertEqual(plan["parseMetadata"]["llmModel"], "gemini-2.5-flash")


if __name__ == "__main__":
    unittest.main()
