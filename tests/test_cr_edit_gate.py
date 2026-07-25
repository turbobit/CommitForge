from __future__ import annotations

import json
import os
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
INSTALLER = ROOT / "install.py"


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

    def test_extended_analysis_modes_stay_read_only_with_fix(self) -> None:
        for arguments in (
            "release --fix",
            "--fix emergency --incident INC-142",
            "learn --fix --since v1.0.0",
            "--format json --fix release",
        ):
            with self.subTest(arguments=arguments):
                result = self.invoke(arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn("항상 read-only", result.stderr)

    def test_installed_hook_does_not_require_claude_skill_dir(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="commitforge hook's target "
        ) as temp:
            project = Path(temp).resolve()
            subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--scope",
                    "project",
                    "--target",
                    str(project),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            skill = (
                project / ".claude/skills/cr/SKILL.md"
            ).read_text(encoding="utf-8")
            hook_line = next(
                line.strip()
                for line in skill.splitlines()
                if line.strip().startswith("command:")
                and "cr_edit_gate.py" in line
            )
            scalar = hook_line.split("command:", 1)[1].strip()
            self.assertTrue(scalar.startswith("'") and scalar.endswith("'"))
            command = scalar[1:-1].replace("''", "'")
            self.assertNotIn("CLAUDE_SKILL_DIR", command)
            self.assertIn("cr_edit_gate.py", command)
            for name in ("cc", "ccr", "cr", "cca", "cp", "cpr"):
                installed_skill = (
                    project / f".claude/skills/{name}/SKILL.md"
                ).read_text(encoding="utf-8")
                frontmatter = installed_skill.split("\n---\n", 1)[0]
                self.assertNotIn("${", frontmatter)
                self.assertNotIn('Bash(bash ".claude/', frontmatter)
                self.assertNotIn('Bash(python3 ".claude/', frontmatter)
                self.assertIn(
                    str(project / ".claude/skills/_git-atomic-core"),
                    installed_skill,
                )

            transcript = project / "transcript.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": (
                                "<command-name>/cr</command-name>\n"
                                "<command-args></command-args>"
                            ),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.pop("CLAUDE_SKILL_DIR", None)
            result = subprocess.run(
                command,
                shell=True,
                cwd=project.parent,
                env=env,
                input=json.dumps({"transcript_path": str(transcript)}),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("read-only", result.stderr)


if __name__ == "__main__":
    unittest.main()
