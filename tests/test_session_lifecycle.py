from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude/skills/_git-atomic-core/scripts/guard.py"
LIFECYCLE = ROOT / ".claude/skills/_git-atomic-core/scripts/session_lifecycle.py"
INSTALLER = ROOT / "install.py"
UNINSTALLER = ROOT / "uninstall.py"
POWERSHELL_ENCODED_PREFIX = (
    "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand "
)


def decoded_command(command: str) -> str:
    if not command.startswith(POWERSHELL_ENCODED_PREFIX):
        return command
    encoded = command.removeprefix(POWERSHELL_ENCODED_PREFIX)
    return base64.b64decode(encoded, validate=True).decode("utf-16-le")


def run(cmd: list[str], cwd: Path, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        **kwargs,
    )


class SessionLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="commitforge-session-hook-"))
        run(["git", "init"], self.tmp)
        run(["git", "config", "user.name", "CommitForge Test"], self.tmp)
        run(["git", "config", "user.email", "test@example.invalid"], self.tmp)
        (self.tmp / "tracked.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: initial"], self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def guard(self, *args: str) -> dict:
        result = run([sys.executable, str(GUARD), *args], self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def lifecycle(self, payload: dict, env: dict[str, str] | None = None) -> None:
        result = run(
            [sys.executable, str(LIFECYCLE)],
            self.tmp,
            input=json.dumps(payload),
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def event(self, name: str, session: str, **extra: str) -> dict:
        return {
            "session_id": session,
            "transcript_path": str(self.tmp / "transcript.jsonl"),
            "cwd": str(self.tmp),
            "hook_event_name": name,
            **extra,
        }

    def test_session_start_persists_real_claude_session(self) -> None:
        env_file = self.tmp / "claude-env"
        env_file.write_text("export EXISTING=value\n", encoding="utf-8")
        env = os.environ.copy()
        env["CLAUDE_ENV_FILE"] = str(env_file)

        self.lifecycle(
            self.event("SessionStart", "claude-session-123", source="startup"),
            env,
        )

        self.assertEqual(
            env_file.read_text(encoding="utf-8").splitlines(),
            [
                "export EXISTING=value",
                "export COMMITFORGE_SESSION_ID=claude-session-123",
            ],
        )

    def test_compact_keeps_lock_and_rebinds_same_session(self) -> None:
        started = self.guard("begin", "--session", "claude-session-compact")
        env_file = self.tmp / "claude-env"
        env = os.environ.copy()
        env["CLAUDE_ENV_FILE"] = str(env_file)

        self.lifecycle(
            self.event("SessionStart", "claude-session-compact", source="compact"),
            env,
        )

        self.assertTrue(self.tmp.joinpath(".git/claude-atomic.lock").is_dir())
        self.assertTrue(Path(started["snapshot"]).is_dir())
        self.assertIn(
            "COMMITFORGE_SESSION_ID=claude-session-compact",
            env_file.read_text(encoding="utf-8"),
        )

    def test_session_end_releases_matching_lock_and_preserves_snapshot(self) -> None:
        started = self.guard("begin", "--session", "claude-session-end")

        self.lifecycle(
            self.event(
                "SessionEnd",
                "claude-session-end",
                reason="prompt_input_exit",
            )
        )

        self.assertFalse(self.tmp.joinpath(".git/claude-atomic.lock").exists())
        self.assertTrue(Path(started["snapshot"]).is_dir())

    def test_stop_releases_unfinished_matching_lock(self) -> None:
        started = self.guard("begin", "--session", "claude-session-stop")

        self.lifecycle(self.event("Stop", "claude-session-stop"))

        self.assertFalse(self.tmp.joinpath(".git/claude-atomic.lock").exists())
        self.assertTrue(Path(started["snapshot"]).is_dir())

    def test_session_end_never_releases_another_sessions_lock(self) -> None:
        started = self.guard("begin", "--session", "lock-owner")

        self.lifecycle(
            self.event("SessionEnd", "different-session", reason="clear")
        )

        self.assertTrue(self.tmp.joinpath(".git/claude-atomic.lock").is_dir())
        self.assertTrue(Path(started["snapshot"]).is_dir())


class LifecycleInstallerTest(unittest.TestCase):
    def test_install_and_uninstall_preserve_unrelated_project_hooks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="commitforge-install-hooks-") as temp:
            project = Path(temp)
            settings_path = project / ".claude/settings.local.json"
            settings_path.parent.mkdir(parents=True)
            unrelated = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "startup",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python unrelated.py",
                                }
                            ],
                        }
                    ]
                },
                "permissions": {"allow": ["Read"]},
            }
            settings_path.write_text(
                json.dumps(unrelated, indent=2) + "\n",
                encoding="utf-8",
            )

            installed = run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--scope",
                    "project",
                    "--target",
                    str(project),
                ],
                ROOT,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(settings["permissions"], unrelated["permissions"])
            self.assertEqual(len(settings["hooks"]["SessionStart"]), 2)
            for event in ("SessionEnd", "Stop", "StopFailure"):
                self.assertEqual(len(settings["hooks"][event]), 1)
            lifecycle_commands = [
                handler["command"]
                for event in ("SessionStart", "SessionEnd", "Stop", "StopFailure")
                for group in settings["hooks"][event]
                for handler in group["hooks"]
                if "session_lifecycle.py"
                in decoded_command(handler.get("command", ""))
            ]
            self.assertEqual(len(lifecycle_commands), 4)
            expected_claude_dir = (project / ".claude").resolve().as_posix()
            self.assertTrue(
                all(
                    expected_claude_dir.replace("/", os.sep)
                    in decoded_command(command)
                    for command in lifecycle_commands
                )
            )
            if sys.platform == "win32":
                self.assertTrue(
                    all(
                        command.startswith(POWERSHELL_ENCODED_PREFIX)
                        for command in lifecycle_commands
                    )
                )
                self.assertNotIn("\\", lifecycle_commands[0])
                payload = self._session_start_payload(project)
                shell_commands = [
                    (
                        "cmd",
                        ["cmd.exe", "/d", "/s", "/c", lifecycle_commands[0]],
                    ),
                    (
                        "powershell",
                        [
                            "powershell.exe",
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            lifecycle_commands[0],
                        ],
                    ),
                ]
                git_bash_candidates = [
                    os.environ.get("CLAUDE_CODE_GIT_BASH_PATH"),
                    str(
                        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
                        / "Git/bin/bash.exe"
                    ),
                ]
                bash = next(
                    (
                        candidate
                        for candidate in git_bash_candidates
                        if candidate and Path(candidate).is_file()
                    ),
                    None,
                )
                if bash is not None:
                    shell_commands.append(
                        ("bash", [bash, "-lc", lifecycle_commands[0]])
                    )
                for shell_name, shell_argv in shell_commands:
                    env_file = project / f"{shell_name}-claude-env"
                    env = os.environ.copy()
                    env["CLAUDE_ENV_FILE"] = str(env_file)
                    result = run(
                        shell_argv,
                        project,
                        input=json.dumps(payload),
                        env=env,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{shell_name}: {result.stderr or result.stdout}",
                    )
                    self.assertIn(
                        "COMMITFORGE_SESSION_ID=cross-shell-session",
                        env_file.read_text(encoding="utf-8"),
                    )

            reinstalled = run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--scope",
                    "project",
                    "--target",
                    str(project),
                ],
                ROOT,
            )
            self.assertEqual(reinstalled.returncode, 0, reinstalled.stderr)
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(len(settings["hooks"]["SessionStart"]), 2)
            for event in ("SessionEnd", "Stop", "StopFailure"):
                self.assertEqual(len(settings["hooks"][event]), 1)

            removed = run(
                [
                    sys.executable,
                    str(UNINSTALLER),
                    "--scope",
                    "project",
                    "--target",
                    str(project),
                ],
                ROOT,
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            restored = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(restored, unrelated)

    @staticmethod
    def _session_start_payload(project: Path) -> dict[str, str]:
        return {
            "session_id": "cross-shell-session",
            "transcript_path": str(project / "transcript.jsonl"),
            "cwd": str(project),
            "hook_event_name": "SessionStart",
            "source": "startup",
        }


if __name__ == "__main__":
    unittest.main()
