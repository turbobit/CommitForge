#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
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

        _, audited = self.guard(
            "audit-snapshot",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
        )
        self.assertTrue(audited["ok"])

        working_diff = snapshot / "working.diff"
        original_working_diff = working_diff.read_bytes()
        working_diff.write_bytes(original_working_diff + b"tampered")
        audit_proc, audit_failed = self.guard(
            "audit-snapshot",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            check=False,
        )
        self.assertNotEqual(audit_proc.returncode, 0)
        self.assertFalse(audit_failed["ok"])
        self.assertIn("corrupt", audit_failed["error"])
        working_diff.write_bytes(original_working_diff)

        proc, blocked = self.guard("begin", "--session", "session-b", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["reason"], "guard_lock_conflict")
        self.assertEqual(blocked["lock_scope"], "worktree_git_dir")
        self.assertEqual(Path(blocked["project_root"]), self.tmp.resolve())
        self.assertEqual(Path(blocked["git_dir"]), (self.tmp / ".git").resolve())
        self.assertEqual(blocked["lock_owner"]["session"], "session-a")
        self.assertEqual(blocked["lock_owner_snapshots"], [started["snapshot"]])
        self.assertGreaterEqual(blocked["lock_age_seconds"], 0)
        self.assertTrue(blocked["recovery"]["auto_snapshot_lookup"])
        self.assertEqual(blocked["recovery"]["snapshot"], started["snapshot"])
        self.assertEqual(blocked["recovery"]["cwd"], str(self.tmp.resolve()))
        self.assertEqual(
            blocked["recovery"]["abort_argv"][-4:],
            ["--session", "session-a", "--token", started["token"]],
        )

        _, fp1 = self.guard("fingerprint")
        (self.tmp / "tracked.txt").write_text("base\nchanged\nchanged-again\n", encoding="utf-8")
        _, fp2 = self.guard("fingerprint")
        self.assertNotEqual(fp1["fingerprint"], fp2["fingerprint"])

        _, aborted = self.guard(
            "abort",
            "--session", started["session"],
            "--token", started["token"],
        )
        self.assertTrue(aborted["lock_released"])
        self.assertEqual(aborted["snapshot"], started["snapshot"])
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

    def test_clean_releases_only_current_lock_and_preserves_snapshot(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")
        _, started = self.guard("begin", "--session", "stale-owner")
        snapshot = Path(started["snapshot"])

        _, cleaned = self.guard(
            "clean",
            "--request-session",
            "cleanup-requester",
        )
        self.assertTrue(cleaned["lock_found"])
        self.assertTrue(cleaned["lock_released"])
        self.assertEqual(cleaned["lock_owner"]["session"], "stale-owner")
        self.assertEqual(cleaned["lock_owner_snapshots"], [started["snapshot"]])
        self.assertEqual(cleaned["snapshots_removed"], 0)
        self.assertTrue(snapshot.exists())

        _, status = self.guard("status")
        self.assertIsNone(status["claude_atomic_lock"])

        _, repeated = self.guard("clean")
        self.assertFalse(repeated["lock_found"])
        self.assertFalse(repeated["lock_released"])
        self.assertTrue(snapshot.exists())

    def test_clean_refuses_unexpected_lock_contents(self) -> None:
        _, started = self.guard("begin", "--session", "guarded-owner")
        lock_path = self.tmp / ".git" / "claude-atomic.lock"
        (lock_path / "unexpected").write_text("do not remove\n", encoding="utf-8")

        proc, payload = self.guard("clean", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "clean_lock_contents_unexpected")
        self.assertTrue(lock_path.exists())

        (lock_path / "unexpected").unlink()
        self.guard(
            "abort",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
        )

    def owner_path(self) -> Path:
        return self.tmp / ".git" / "claude-atomic.lock" / "owner.json"

    def rewrite_owner(self, **changes: object) -> dict:
        owner_file = self.owner_path()
        owner = json.loads(owner_file.read_text(encoding="utf-8"))
        owner.update(changes)
        owner_file.write_text(json.dumps(owner, ensure_ascii=False, indent=2), encoding="utf-8")
        return owner

    def age_owner(self, seconds: int) -> None:
        created = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)
        self.rewrite_owner(created_at=created.isoformat())

    def test_begin_records_owner_host_identity(self) -> None:
        self.guard("begin", "--session", "identity-owner")
        owner = json.loads(self.owner_path().read_text(encoding="utf-8"))
        self.assertEqual(owner["hostname"], socket.gethostname())
        self.assertIsInstance(owner["guard_pid"], int)

    def test_begin_conflict_reports_stale_candidate_and_clean_hint(self) -> None:
        self.guard("begin", "--session", "first-owner")

        proc, payload = self.guard("begin", "--session", "second-owner", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "guard_lock_conflict")
        self.assertFalse(payload["stale_candidate"])
        self.assertEqual(payload["lock_owner_hostname"], socket.gethostname())
        self.assertTrue(payload["lock_owner_same_host"])
        self.assertFalse(payload["lock_owner_same_session"])
        self.assertIn("clean_hint", payload["recovery"])

    def test_reclaim_stale_refuses_recent_lock(self) -> None:
        _, started = self.guard("begin", "--session", "busy-owner")

        proc, payload = self.guard(
            "begin", "--session", "impatient", "--reclaim-stale", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "guard_lock_conflict")
        self.assertEqual(payload["reclaim_refused_reason"], "lock_not_stale")
        self.assertEqual(
            json.loads(self.owner_path().read_text(encoding="utf-8"))["token"],
            started["token"],
        )

    def test_reclaim_stale_recovers_aged_lock_and_preserves_snapshot(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")
        _, started = self.guard("begin", "--session", "crashed-owner")
        old_snapshot = Path(started["snapshot"])
        self.age_owner(7200)

        _, reclaimed = self.guard("begin", "--session", "next-owner", "--reclaim-stale")
        self.assertTrue(reclaimed["ok"])
        self.assertTrue(reclaimed["reclaimed_lock"])
        self.assertEqual(reclaimed["previous_owner"]["session"], "crashed-owner")
        self.assertEqual(reclaimed["reclaim_reason"], "stale_lock_age")
        self.assertNotEqual(reclaimed["token"], started["token"])
        self.assertTrue(old_snapshot.exists())

        _, status = self.guard("status")
        self.assertEqual(status["claude_atomic_lock"]["session"], "next-owner")

    def test_reclaim_stale_allows_same_session_reentry(self) -> None:
        _, started = self.guard("begin", "--session", "same-session")

        _, reclaimed = self.guard("begin", "--session", "same-session", "--reclaim-stale")
        self.assertTrue(reclaimed["reclaimed_lock"])
        self.assertEqual(reclaimed["reclaim_reason"], "same_session_reentry")
        self.assertNotEqual(reclaimed["token"], started["token"])

    def test_reclaim_stale_refuses_other_host(self) -> None:
        self.guard("begin", "--session", "remote-owner")
        self.rewrite_owner(hostname="some-other-host")
        self.age_owner(7200)

        proc, payload = self.guard(
            "begin", "--session", "local", "--reclaim-stale", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reclaim_refused_reason"], "different_host")
        self.assertFalse(payload["lock_owner_same_host"])
        self.assertTrue(self.owner_path().exists())

    def test_reclaim_stale_refuses_owner_with_unknown_host(self) -> None:
        self.guard("begin", "--session", "legacy-owner")
        owner = json.loads(self.owner_path().read_text(encoding="utf-8"))
        owner.pop("hostname")
        self.owner_path().write_text(
            json.dumps(owner, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.age_owner(7200)

        proc, payload = self.guard(
            "begin", "--session", "local", "--reclaim-stale", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reclaim_refused_reason"], "owner_host_unknown")
        self.assertIsNone(payload["lock_owner_same_host"])
        self.assertTrue(self.owner_path().exists())

    def test_reclaim_stale_respects_custom_threshold(self) -> None:
        self.guard("begin", "--session", "short-lived")
        self.age_owner(120)

        _, reclaimed = self.guard(
            "begin", "--session", "taker", "--reclaim-stale", "--stale-after", "60"
        )
        self.assertTrue(reclaimed["reclaimed_lock"])

    def test_reclaim_stale_refuses_unexpected_lock_contents(self) -> None:
        _, started = self.guard("begin", "--session", "guarded")
        lock_path = self.tmp / ".git" / "claude-atomic.lock"
        (lock_path / "unexpected").write_text("keep\n", encoding="utf-8")
        self.age_owner(7200)

        proc, payload = self.guard(
            "begin", "--session", "taker", "--reclaim-stale", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reclaim_refused_reason"], "lock_contents_unexpected")
        self.assertTrue((lock_path / "unexpected").exists())
        self.assertEqual(
            json.loads(self.owner_path().read_text(encoding="utf-8"))["token"],
            started["token"],
        )

    def write_index_lock(self, *, age_seconds: int = 0, size: int = 0) -> Path:
        lock = self.tmp / ".git" / "index.lock"
        lock.write_bytes(b"x" * size)
        if age_seconds:
            past = dt.datetime.now(dt.timezone.utc).timestamp() - age_seconds
            os.utime(lock, (past, past))
        return lock

    def test_begin_diagnoses_stale_git_index_lock(self) -> None:
        self.write_index_lock(age_seconds=1800)

        proc, payload = self.guard("begin", "--session", "blocked", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "git_external_lock")
        entry = payload["git_locks"][0]
        self.assertTrue(entry["path"].endswith("index.lock"))
        self.assertGreaterEqual(entry["age_seconds"], 1800)
        self.assertEqual(entry["size"], 0)
        self.assertTrue(entry["stale_candidate"])
        self.assertIn("remove_hint", payload["recovery"])

    def test_begin_treats_fresh_git_index_lock_as_active(self) -> None:
        self.write_index_lock()

        proc, payload = self.guard("begin", "--session", "blocked", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "git_external_lock")
        self.assertFalse(payload["git_locks"][0]["stale_candidate"])

    def test_begin_treats_non_empty_git_index_lock_as_active(self) -> None:
        self.write_index_lock(age_seconds=1800, size=64)

        _, payload = self.guard("begin", "--session", "blocked", check=False)
        self.assertFalse(payload["git_locks"][0]["stale_candidate"])

    def test_git_index_lock_stale_threshold_is_configurable(self) -> None:
        self.write_index_lock(age_seconds=120)

        _, payload = self.guard(
            "begin", "--session", "blocked", "--git-lock-stale-after", "60", check=False
        )
        self.assertTrue(payload["git_locks"][0]["stale_candidate"])

    def test_clean_removes_verified_stale_git_lock(self) -> None:
        lock = self.write_index_lock(age_seconds=1800)

        _, cleaned = self.guard("clean", "--request-session", "requester")
        self.assertTrue(cleaned["ok"])
        self.assertFalse(cleaned["lock_found"])
        self.assertEqual(cleaned["git_locks"], [])
        self.assertEqual(
            [Path(path).resolve() for path in cleaned["git_locks_removed"]],
            [lock.resolve()],
        )
        self.assertIn("stale Git lock을 제거", cleaned["message"])
        self.assertFalse(lock.exists())

    def test_clean_preserves_fresh_git_lock(self) -> None:
        lock = self.write_index_lock()

        _, cleaned = self.guard("clean", "--request-session", "requester")
        self.assertEqual(cleaned["git_locks_removed"], [])
        self.assertEqual(len(cleaned["git_locks"]), 1)
        self.assertFalse(cleaned["git_locks"][0]["stale_candidate"])
        self.assertTrue(lock.exists())

    def test_read_only_handle_is_not_mistaken_for_writer(self) -> None:
        lock = self.write_index_lock(age_seconds=1800)
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys,time;"
                    "fd=os.open(sys.argv[1],os.O_RDONLY);"
                    "print('ready',flush=True);time.sleep(30)"
                ),
                str(lock),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "ready")
            _, status = self.guard("status")
            self.assertEqual(status["git_locks"][0]["writer_pids"], [])
            self.assertTrue(status["git_locks"][0]["stale_candidate"])
        finally:
            holder.terminate()
            holder.wait(timeout=10)
            if holder.stdout:
                holder.stdout.close()
            if holder.stderr:
                holder.stderr.close()

    def test_clean_preserves_lock_held_open_for_writing(self) -> None:
        lock = self.write_index_lock(age_seconds=1800)
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys,time;"
                    "fd=os.open(sys.argv[1],os.O_RDWR);"
                    "print('ready',flush=True);time.sleep(30)"
                ),
                str(lock),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "ready")
            _, cleaned = self.guard("clean")
            self.assertEqual(cleaned["git_locks_removed"], [])
            self.assertFalse(cleaned["git_locks"][0]["stale_candidate"])
            self.assertTrue(lock.exists())
        finally:
            holder.terminate()
            holder.wait(timeout=10)
            if holder.stdout:
                holder.stdout.close()
            if holder.stderr:
                holder.stderr.close()

    def test_stale_thresholds_must_be_positive(self) -> None:
        for command in (
            ["begin", "--session", "invalid", "--stale-after", "0"],
            ["clean", "--git-lock-stale-after", "-1"],
            ["status", "--git-lock-stale-after", "0"],
        ):
            proc = run([sys.executable, str(GUARD), *command], self.tmp, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("1 이상", proc.stderr)

    def test_clean_message_stays_quiet_without_git_locks(self) -> None:
        _, cleaned = self.guard("clean", "--request-session", "requester")
        self.assertEqual(cleaned["git_locks"], [])
        self.assertNotIn("Git 자체 lock", cleaned["message"])

    def test_status_reports_git_lock_details(self) -> None:
        self.write_index_lock(age_seconds=1800)

        _, status = self.guard("status")
        self.assertTrue(status["git_locks"][0]["stale_candidate"])
        self.assertEqual(
            [entry["path"] for entry in status["git_locks"]],
            status["git_lock_files"],
        )

    def test_status_reports_stale_candidate(self) -> None:
        self.guard("begin", "--session", "aging-owner")
        self.age_owner(7200)

        _, status = self.guard("status")
        self.assertTrue(status["stale_candidate"])
        self.assertEqual(status["lock_owner_hostname"], socket.gethostname())

    def test_clean_refuses_symbolic_link_lock_path(self) -> None:
        lock_path = self.tmp / ".git" / "claude-atomic.lock"
        outside = self.tmp / "outside-lock"
        outside.mkdir()
        owner_file = outside / "owner.json"
        owner_file.write_text('{"session":"do-not-touch"}\n', encoding="utf-8")
        lock_path.symlink_to(outside, target_is_directory=True)

        proc, payload = self.guard("clean", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(payload["reason"], "clean_lock_path_unsafe")
        self.assertTrue(owner_file.exists())
        self.assertTrue(lock_path.is_symlink())

    def test_review_only_preserves_head_branch_and_index(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nstaged\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)

        _, started = self.guard("begin", "--session", "review-pass")
        (self.tmp / "tracked.txt").write_text(
            "base\nstaged\nreview-fix\n",
            encoding="utf-8",
        )

        _, verified = self.guard(
            "verify-review",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["checks"]["staged_diff_unchanged"])

        _, finished = self.guard(
            "finish",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--review-only",
        )
        self.assertTrue(finished["review_invariants"]["ok"])
        self.assertFalse(finished["worktree_clean"])

        _, changed = self.guard("begin", "--session", "review-block")
        run(["git", "add", "tracked.txt"], self.tmp)
        proc, payload = self.guard(
            "verify-review",
            "--session", changed["session"],
            "--token", changed["token"],
            "--snapshot", changed["snapshot"],
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertIn("staged_diff_unchanged", payload["error"])

        finish_proc, finish_payload = self.guard(
            "finish",
            "--session", changed["session"],
            "--token", changed["token"],
            "--snapshot", changed["snapshot"],
            "--review-only",
            check=False,
        )
        self.assertNotEqual(finish_proc.returncode, 0)
        self.assertFalse(finish_payload["ok"])

        _, aborted = self.guard(
            "abort",
            "--session", changed["session"],
            "--token", changed["token"],
            "--snapshot", changed["snapshot"],
        )
        self.assertTrue(aborted["lock_released"])

        run(["git", "commit", "-m", "test: staged baseline"], self.tmp)
        _, head_changed = self.guard("begin", "--session", "review-head")
        (self.tmp / "tracked.txt").write_text(
            "base\nstaged\nreview-fix\ncommitted\n",
            encoding="utf-8",
        )
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: forbidden review commit"], self.tmp)
        head_proc, head_payload = self.guard(
            "verify-review",
            "--session", head_changed["session"],
            "--token", head_changed["token"],
            "--snapshot", head_changed["snapshot"],
            check=False,
        )
        self.assertNotEqual(head_proc.returncode, 0)
        self.assertIn("head_unchanged", head_payload["error"])
        self.guard(
            "abort",
            "--session", head_changed["session"],
            "--token", head_changed["token"],
            "--snapshot", head_changed["snapshot"],
        )

        _, branch_changed = self.guard("begin", "--session", "review-branch")
        run(["git", "switch", "-c", "unexpected-review-branch"], self.tmp)
        branch_proc, branch_payload = self.guard(
            "verify-review",
            "--session", branch_changed["session"],
            "--token", branch_changed["token"],
            "--snapshot", branch_changed["snapshot"],
            check=False,
        )
        self.assertNotEqual(branch_proc.returncode, 0)
        self.assertIn("branch_unchanged", branch_payload["error"])
        self.guard(
            "abort",
            "--session", branch_changed["session"],
            "--token", branch_changed["token"],
            "--snapshot", branch_changed["snapshot"],
        )

    def test_review_commands_auto_resolve_current_owner_context(self) -> None:
        (self.tmp / "tracked.txt").write_text(
            "base\nreview target\n",
            encoding="utf-8",
        )
        _, started = self.guard("begin", "--session", "auto-review-context")
        snapshot = Path(started["snapshot"])

        _, verified = self.guard(
            "verify-review",
            "--session", started["session"],
            "--source-read-only",
        )
        self.assertTrue(verified["ok"])

        _, finished = self.guard(
            "finish",
            "--session", started["session"],
            "--review-only",
            "--source-read-only",
        )
        self.assertTrue(finished["lock_released"])
        self.assertTrue(finished["snapshot_removed"])
        self.assertFalse(snapshot.exists())

        _, status = self.guard("status")
        self.assertIsNone(status["claude_atomic_lock"])

    def test_review_context_does_not_replace_explicit_wrong_snapshot(self) -> None:
        _, started = self.guard("begin", "--session", "wrong-review-context")

        proc, payload = self.guard(
            "verify-review",
            "--session", started["session"],
            "--snapshot", Path(started["snapshot"]).name,
            "--source-read-only",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("작업 트리 밖", payload["error"])

        self.guard(
            "abort",
            "--session", started["session"],
            "--token", started["token"],
        )

    def test_source_read_only_preserves_working_tree(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nreview target\n", encoding="utf-8")
        _, started = self.guard("begin", "--session", "source-read-only")

        _, verified = self.guard(
            "verify-review",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--source-read-only",
        )
        self.assertTrue(verified["checks"]["working_diff_unchanged"])
        self.assertTrue(verified["checks"]["untracked_content_unchanged"])

        (self.tmp / "tracked.txt").write_text(
            "base\nreview target\nforbidden fix\n",
            encoding="utf-8",
        )
        proc, payload = self.guard(
            "verify-review",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--source-read-only",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("working_diff_unchanged", payload["error"])

        (self.tmp / "tracked.txt").write_text("base\nreview target\n", encoding="utf-8")
        (self.tmp / "unexpected.txt").write_text("new\n", encoding="utf-8")
        proc, payload = self.guard(
            "verify-review",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--source-read-only",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("status_unchanged", payload["error"])
        (self.tmp / "unexpected.txt").unlink()

        _, finished = self.guard(
            "finish",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--review-only",
            "--source-read-only",
        )
        self.assertTrue(finished["review_invariants"]["ok"])

    def test_expected_branch_allows_only_main_or_master_branch_creation(self) -> None:
        start_branch = run(["git", "branch", "--show-current"], self.tmp).stdout.strip()
        self.assertIn(start_branch, {"main", "master"})
        _, started = self.guard("begin", "--session", "pr-auto-branch")
        run(["git", "switch", "-c", "feat/pr-preview"], self.tmp)

        _, verified = self.guard(
            "verify-review",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--source-read-only",
            "--expected-branch", "feat/pr-preview",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["checks"]["branch_unchanged_or_expected"])

        proc, payload = self.guard(
            "finish",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--review-only",
            "--source-read-only",
            "--expected-branch", "fix/wrong-branch",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("branch_unchanged_or_expected", payload["error"])

        _, finished = self.guard(
            "finish",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--review-only",
            "--source-read-only",
            "--expected-branch", "feat/pr-preview",
        )
        self.assertTrue(finished["review_invariants"]["ok"])

        _, invalid_start = self.guard("begin", "--session", "pr-wrong-start")
        run(["git", "switch", "-c", "feat/nested-branch"], self.tmp)
        invalid_proc, invalid_payload = self.guard(
            "verify-review",
            "--session", invalid_start["session"],
            "--token", invalid_start["token"],
            "--snapshot", invalid_start["snapshot"],
            "--source-read-only",
            "--expected-branch", "feat/nested-branch",
            check=False,
        )
        self.assertNotEqual(invalid_proc.returncode, 0)
        self.assertIn("branch_unchanged_or_expected", invalid_payload["error"])
        self.guard(
            "abort",
            "--session", invalid_start["session"],
            "--token", invalid_start["token"],
            "--snapshot", invalid_start["snapshot"],
        )

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

        cleaned_main = guard_at(self.tmp, "clean", "--request-session", "clean-main")
        self.assertTrue(cleaned_main["lock_released"])
        linked_status = guard_at(linked, "status")
        self.assertEqual(
            linked_status["claude_atomic_lock"]["session"],
            linked_started["session"],
        )
        self.assertTrue(Path(main_started["snapshot"]).exists())
        guard_at(
            linked,
            "abort",
            "--session", linked_started["session"],
            "--token", linked_started["token"],
            "--snapshot", linked_started["snapshot"],
        )
        run(["git", "worktree", "remove", str(linked)], self.tmp)

    def test_independent_repositories_under_same_parent_do_not_share_lock(self) -> None:
        sibling = self.tmp.parent / f"{self.tmp.name}-independent"
        sibling.mkdir()
        run(["git", "init"], sibling)

        def guard_at(cwd: Path, *args: str, check: bool = True) -> tuple[
            subprocess.CompletedProcess[str], dict
        ]:
            proc = run([sys.executable, str(GUARD), *args], cwd, check=check)
            return proc, json.loads(proc.stdout)

        _, first = guard_at(self.tmp, "begin", "--session", "repo-a")
        _, second = guard_at(sibling, "begin", "--session", "repo-b")
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertNotEqual(first["project_root"], second["project_root"])
        self.assertNotEqual(Path(first["snapshot"]).parent, Path(second["snapshot"]).parent)

        nested = self.tmp / "nested" / "directory"
        nested.mkdir(parents=True)
        blocked_proc, blocked = guard_at(
            nested,
            "begin",
            "--session",
            "repo-a-nested",
            check=False,
        )
        self.assertNotEqual(blocked_proc.returncode, 0)
        self.assertEqual(blocked["reason"], "guard_lock_conflict")
        self.assertEqual(Path(blocked["project_root"]), self.tmp.resolve())

        guard_at(
            self.tmp,
            "abort",
            "--session", first["session"],
            "--token", first["token"],
            "--snapshot", first["snapshot"],
        )
        guard_at(
            sibling,
            "abort",
            "--session", second["session"],
            "--token", second["token"],
            "--snapshot", second["snapshot"],
        )
        shutil.rmtree(sibling, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
