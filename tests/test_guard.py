#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
GUARD = PACKAGE_ROOT / ".claude/skills/_git-atomic-core/scripts/guard.py"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


class GuardIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cca-guard-test-"))
        run(["git", "init"], self.tmp)
        run(["git", "config", "user.name", "CCA Test"], self.tmp)
        run(["git", "config", "user.email", "cca@example.invalid"], self.tmp)
        (self.tmp / "tracked.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: initial"], self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def guard(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        proc = run([sys.executable, str(GUARD), *args], self.tmp, check=check)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid JSON: {proc.stdout}\n{proc.stderr}") from exc
        return proc, payload

    def test_snapshot_lock_fingerprint_abort_and_finish(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")
        (self.tmp / "untracked.txt").write_text("new\n", encoding="utf-8")

        _, started = self.guard("begin", "--session", "session-a")
        self.assertTrue(started["ok"])
        snapshot = Path(started["snapshot"])
        self.assertTrue((snapshot / "working.diff").is_file())
        self.assertTrue((snapshot / "staged.diff").is_file())
        self.assertTrue((snapshot / "untracked.tar.gz").is_file())
        self.assertTrue((snapshot / ".cca-snapshot.json").is_file())

        proc, blocked = self.guard("begin", "--session", "session-b", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(blocked["ok"])

        _, fp1 = self.guard("fingerprint")
        (self.tmp / "tracked.txt").write_text("base\nchanged\nchanged-again\n", encoding="utf-8")
        _, fp2 = self.guard("fingerprint")
        self.assertNotEqual(fp1["fingerprint"], fp2["fingerprint"])

        _, aborted = self.guard(
            "abort",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
        )
        self.assertTrue(aborted["lock_released"])
        self.assertTrue(snapshot.exists())

        # Restore only inside the disposable test repository.
        run(["git", "restore", "--worktree", "--staged", "."], self.tmp)
        (self.tmp / "untracked.txt").unlink()

        _, clean_start = self.guard("begin", "--session", "session-c")
        clean_snapshot = Path(clean_start["snapshot"])
        _, finished = self.guard(
            "finish",
            "--session", clean_start["session"],
            "--token", clean_start["token"],
            "--snapshot", clean_start["snapshot"],
        )
        self.assertTrue(finished["lock_released"])
        self.assertTrue(finished["snapshot_removed"])
        self.assertFalse(clean_snapshot.exists())

    def test_git_operation_blocks_begin_without_lock(self) -> None:
        git_dir = Path(run(["git", "rev-parse", "--git-dir"], self.tmp).stdout.strip())
        if not git_dir.is_absolute():
            git_dir = self.tmp / git_dir
        (git_dir / "MERGE_HEAD").write_text("deadbeef\n", encoding="ascii")

        proc, payload = self.guard("begin", "--session", "blocked", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(payload["ok"])

        _, status = self.guard("status")
        self.assertIsNone(status["claude_atomic_lock"])

    def test_linked_worktrees_use_independent_locks(self) -> None:
        linked = self.tmp.parent / f"{self.tmp.name}-linked"
        run(["git", "worktree", "add", "-b", "linked-test", str(linked)], self.tmp)

        def guard_at(cwd: Path, *args: str) -> dict:
            proc = run([sys.executable, str(GUARD), *args], cwd)
            return json.loads(proc.stdout)

        main_started = guard_at(self.tmp, "begin", "--session", "main-session")
        linked_started = guard_at(linked, "begin", "--session", "linked-session")
        self.assertTrue(main_started["ok"])
        self.assertTrue(linked_started["ok"])
        self.assertNotEqual(
            Path(main_started["snapshot"]).parent,
            Path(linked_started["snapshot"]).parent,
        )

        guard_at(
            self.tmp,
            "abort",
            "--session", main_started["session"],
            "--token", main_started["token"],
            "--snapshot", main_started["snapshot"],
        )
        guard_at(
            linked,
            "abort",
            "--session", linked_started["session"],
            "--token", linked_started["token"],
            "--snapshot", linked_started["snapshot"],
        )
        run(["git", "worktree", "remove", str(linked)], self.tmp)


if __name__ == "__main__":
    unittest.main()
