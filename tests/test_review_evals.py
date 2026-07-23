from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRIGGER_SCRIPT = (
    ROOT
    / ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py"
)
FIXTURES = ROOT / "evals/conditional-reviewer-triggers.json"


def load_classifier():
    spec = importlib.util.spec_from_file_location("reviewer_triggers", TRIGGER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("reviewer trigger module을 불러올 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify


class ConditionalReviewerEvalTest(unittest.TestCase):
    def test_golden_trigger_cases(self) -> None:
        classify = load_classifier()
        cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 7)

        for case in cases:
            with self.subTest(case=case["name"]):
                result = classify(case["paths"], case["context"])
                self.assertEqual(
                    sorted(case["expected_active"]),
                    result["active"],
                )

    def test_classifier_declares_minimum_floor_policy(self) -> None:
        classify = load_classifier()
        result = classify(["src/service.py"], "")
        self.assertEqual(
            "minimum-floor-main-agent-may-add-semantic-triggers",
            result["policy"],
        )


if __name__ == "__main__":
    unittest.main()
