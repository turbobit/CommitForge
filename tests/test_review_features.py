from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_SCRIPTS = ROOT / ".claude/skills/_git-atomic-core/scripts"


class ReviewFeatureTest(unittest.TestCase):
    def run_python(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_live_eval_contracts(self) -> None:
        result = self.run_python(ROOT / "evals/run_evals.py", "--check")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["scenarios"], 3)
        scenarios = json.loads(
            (ROOT / "evals/live-review-scenarios.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all("--fix" not in item["prompt"] for item in scenarios))

    def test_baseline_example_is_valid(self) -> None:
        result = self.run_python(
            CORE_SCRIPTS / "baseline.py",
            "examples/review-baseline.json",
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(1, payload["entries"])
        self.assertEqual([], payload["expired"])

    def test_json_and_sarif_reports_validate(self) -> None:
        finding = {
            "id": "reviewer:file:symbol:category",
            "reviewer": "cca-correctness-reviewer",
            "fingerprint": "abc",
            "severity": "MAJOR",
            "status": "OPEN",
            "file": "src/example.py",
            "line_or_hunk": "10",
            "category": "correctness",
            "evidence": "example",
            "failure_scenario": "example",
            "suggested_fix": "example",
            "validation": "example",
            "blocking": True,
        }
        json_report = {
            "schema": "commitforge-review/v1",
            "mode": "cr",
            "fingerprint": "abc",
            "findings": [finding],
        }
        sarif_report = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "CommitForge"}},
                    "results": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory(prefix="commitforge-report-") as temp:
            for name, payload in (
                ("report.json", json_report),
                ("report.sarif", sarif_report),
            ):
                path = Path(temp) / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                result = self.run_python(
                    CORE_SCRIPTS / "report_validator.py",
                    str(path),
                )
                self.assertTrue(json.loads(result.stdout)["ok"])

    def test_review_policy_and_large_diff_are_connected(self) -> None:
        for command in ("cr", "cca"):
            text = (
                ROOT / f".claude/skills/{command}/SKILL.md"
            ).read_text(encoding="utf-8")
            for reference in (
                "review-policy.md",
                "reporting-formats.md",
                "baseline-and-suppressions.md",
                "large-diff-review.md",
            ):
                self.assertIn(reference, text)
        self.assertTrue((ROOT / "examples/review.yml").is_file())

    def test_cr_supports_base_range_pr_and_machine_reports(self) -> None:
        text = (ROOT / ".claude/skills/cr/SKILL.md").read_text(encoding="utf-8")
        for contract in (
            "--base <ref>",
            "--range <A..B>",
            "gh pr view",
            "git merge-base",
            "--format human|json|sarif",
            "--output <경로>",
        ):
            self.assertIn(contract, text)
        self.assertIn("Atomic Commit 계획", text)
        self.assertIn("- 금지: Atomic Commit 계획", text)

    def test_workflow_is_cross_platform_and_sha_pinned(self) -> None:
        text = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
        for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
            self.assertIn(runner, text)
        self.assertNotRegex(text, r"uses:\s+[^\s]+@v\d")
        self.assertRegex(text, r"actions/checkout@[0-9a-f]{40}")
        self.assertRegex(text, r"actions/setup-python@[0-9a-f]{40}")
        self.assertIn('PYTHONUTF8: "1"', text)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes)

    def test_period_range_uses_calendar_boundaries(self) -> None:
        script = CORE_SCRIPTS / "period_range.py"
        today = self.run_python(
            script,
            "today",
            "--timezone",
            "+09:00",
            "--now",
            "2026-07-24T13:45:00+09:00",
        )
        weekly = self.run_python(
            script,
            "weekly",
            "--timezone",
            "+09:00",
            "--now",
            "2026-07-24T13:45:00+09:00",
        )
        three_days = self.run_python(
            script,
            "3days",
            "--timezone",
            "+09:00",
            "--now",
            "2026-07-24T13:45:00+09:00",
        )
        sunday = self.run_python(
            script,
            "weekly",
            "--timezone",
            "+09:00",
            "--week-start",
            "sunday",
            "--now",
            "2026-07-24T13:45:00+09:00",
        )
        today_payload = json.loads(today.stdout)
        self.assertEqual(
            "2026-07-24T00:00:00+09:00",
            today_payload["start"],
        )
        self.assertEqual("+09:00", today_payload["utc_offset"])
        self.assertEqual(
            "2026-07-20T00:00:00+09:00",
            json.loads(weekly.stdout)["start"],
        )
        self.assertEqual(
            "2026-07-22T00:00:00+09:00",
            json.loads(three_days.stdout)["start"],
        )
        self.assertEqual("3days", json.loads(three_days.stdout)["mode"])
        self.assertEqual(
            "2026-07-19T00:00:00+09:00",
            json.loads(sunday.stdout)["start"],
        )

    def test_readme_option_tables_escape_pipe_separators(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("`today|weekly`", readme)
        self.assertNotIn("`--week-start monday|sunday`", readme)
        self.assertIn("`--week-start <monday\\|sunday>`", readme)
        self.assertIn("`--timezone <IANA\\|±HH:MM>`", readme)
        self.assertIn(
            "`--from <ref>` | `/cr release`, `/cca release`",
            readme,
        )
        self.assertIn(
            "`--tag` | `/cca release --prepare`",
            readme,
        )
        self.assertIn("│   ├── cr/SKILL.md", readme)
        self.assertIn("│           ├── cr_edit_gate.py", readme)


if __name__ == "__main__":
    unittest.main()
