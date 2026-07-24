from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GATE = (
    ROOT
    / ".claude/skills/_git-atomic-core/scripts/cr_edit_gate.py"
)


class CrEditGateTest(unittest.TestCase):
    def invoke(self, command_args: str | None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="commitforge-cr-gate-") as temp:
            transcript = Path(temp) / "transcript.jsonl"
            events = [
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": "일반 사용자 메시지",
                    },
                }
            ]
            if command_args is not None:
                events.append(
                    {
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": (
                                "<command-message>cr</command-message>\n"
                                "<command-name>/cr</command-name>\n"
                                f"<command-args>{command_args}</command-args>"
                            ),
                        },
                    }
                )
            transcript.write_text(
                "\n".join(json.dumps(item) for item in events) + "\n",
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, str(GATE)],
                input=json.dumps(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Edit",
                        "tool_input": {"file_path": "target.py"},
                        "transcript_path": str(transcript),
                    }
                ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

    def test_default_cr_denies_edit(self) -> None:
        result = self.invoke("today --timezone +09:00")
        self.assertEqual(result.returncode, 2)
        self.assertIn("read-only", result.stderr)

    def test_exact_fix_token_allows_edit_permission_evaluation(self) -> None:
        self.assertEqual(self.invoke("--fix today").returncode, 0)
        self.assertEqual(self.invoke('today "--fix"').returncode, 0)

    def test_natural_language_fix_does_not_enable_edit(self) -> None:
        self.assertEqual(self.invoke("fix 해줘").returncode, 2)
        self.assertEqual(self.invoke("--fixed").returncode, 2)
        self.assertEqual(self.invoke(None).returncode, 2)


if __name__ == "__main__":
    unittest.main()
