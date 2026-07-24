#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/_git-atomic-core/scripts/pr_context.py"


def run(
    args: list[str],
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


class PullRequestContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="commitforge-pr-context-"))
        self.remote = self.tmp / "remote.git"
        self.repo = self.tmp / "repo"
        run(["git", "init", "--bare", str(self.remote)], self.tmp)
        run(["git", "init", "-b", "main", str(self.repo)], self.tmp)
        run(["git", "config", "user.name", "CommitForge Test"], self.repo)
        run(["git", "config", "user.email", "test@example.invalid"], self.repo)
        run(["git", "remote", "add", "origin", str(self.remote)], self.repo)
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "base.txt"], self.repo)
        run(["git", "commit", "-m", "test: base"], self.repo)
        run(["git", "push", "-u", "origin", "main"], self.repo)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def context(self, *args: str, check: bool = True) -> tuple[
        subprocess.CompletedProcess[str], dict[str, object]
    ]:
        proc = run([sys.executable, str(SCRIPT), *args], self.repo, check=check)
        payload = json.loads(proc.stdout) if proc.returncode == 0 else {}
        return proc, payload

    def test_feature_branch_context_and_dirty_state(self) -> None:
        run(["git", "switch", "-c", "feat/example"], self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        run(["git", "add", "feature.txt"], self.repo)
        run(["git", "commit", "-m", "feat: example"], self.repo)

        _, payload = self.context("--base", "main")
        self.assertTrue(payload["clean"])
        self.assertFalse(payload["branch_needs_creation"])
        self.assertEqual(payload["commit_count"], 1)
        self.assertEqual(payload["files"], 1)

        (self.repo / "feature.txt").write_text("dirty\n", encoding="utf-8")
        _, dirty = self.context("--base", "main")
        self.assertFalse(dirty["clean"])
        self.assertTrue(dirty["status"])

    def test_main_ahead_can_be_previewed_for_automatic_branch(self) -> None:
        (self.repo / "ahead.txt").write_text("ahead\n", encoding="utf-8")
        run(["git", "add", "ahead.txt"], self.repo)
        run(["git", "commit", "-m", "feat: ahead"], self.repo)

        blocked, _ = self.context("--base", "main", check=False)
        self.assertNotEqual(blocked.returncode, 0)

        _, payload = self.context(
            "--base", "main", "--allow-base-head"
        )
        self.assertTrue(payload["branch_needs_creation"])
        self.assertEqual(payload["branch"], "main")
        self.assertEqual(payload["commit_count"], 1)

    def test_main_without_ahead_commit_returns_zero_for_skill_gate(self) -> None:
        _, payload = self.context(
            "--base", "main", "--allow-base-head"
        )
        self.assertTrue(payload["branch_needs_creation"])
        self.assertEqual(payload["commit_count"], 0)
