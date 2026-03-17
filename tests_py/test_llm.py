import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.llm import normalize_llm_payload


class LlmTests(unittest.TestCase):
    def test_normalize_llm_payload_sanitizes_items(self):
        payload = {
            "warnings": ["item ambíguo", "", None],
            "items": [
                {
                    "mealLabel": "Cafe da manha",
                    "originalFood": "banana prata",
                    "normalizedFood": "banana",
                    "quantity": "2",
                    "unit": "unit",
                    "frequencyPerWeek": "14",
                    "notes": "priorizada a primeira alternativa",
                    "confidence": 1.4,
                    "ambiguityFlags": ["alternative_choice", ""],
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
        self.assertEqual(normalized["items"][0]["normalizedFood"], "banana")
        self.assertEqual(normalized["items"][0]["quantity"], 2)
        self.assertEqual(normalized["items"][0]["frequencyPerWeek"], 14)
        self.assertEqual(normalized["items"][0]["confidence"], 1.0)
        self.assertEqual(normalized["items"][0]["ambiguityFlags"], ["alternative_choice"])


if __name__ == "__main__":
    unittest.main()
