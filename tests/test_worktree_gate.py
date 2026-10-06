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
SCRIPTS = ROOT / ".claude/skills/_git-atomic-core/scripts"
GATE = SCRIPTS / "worktree_gate.py"
GUARD = SCRIPTS / "guard.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))
import guard  # noqa: E402
import install  # noqa: E402
import worktree_gate_impl  # noqa: E402

NL = "\n"

# Commands a /ccf run executed on 2026-10-06 while holding the Guard lock,
# followed by forms a review found to slip past a deny-list version.
LOCKED_DENIED = [
    "git reset --soft HEAD~1 2>&1",
    "git reset HEAD -- . 2>&1",
    "git checkout 0feeb2d4 -- . 2>&1",
    "git rebase -i f94206a8 2>&1",
    "GIT_SEQUENCE_EDITOR=\"sed -i '' 's/^pick a/pick b/'\" git rebase -i f94206a8 2>&1",
    "git reset --hard f94206a8 2>&1",
    "git cherry-pick ad48748a 2>&1",
    "git status --short" + NL + NL + "git checkout -- .",
    "git log --oneline -5  # check" + NL + "git reset --hard",
    "git add -A &&" + NL + "git reset --hard",
    "x=$(git rev-parse HEAD);git reset --hard $x",
    "[ $# -eq 0 ] && git reset --hard",
    "git commit \\" + NL + "  --amend --no-edit",
    "git -C . \\" + NL + "  checkout -- .",
    'for f in a.txt b.txt; do git checkout f027d351 -- "$f"; done',
    "git diff --name-only | xargs git checkout --",
    "if ! git diff --quiet; then git stash; fi",
    "{ git reset --hard; }",
    "bash -lc 'git reset --hard'",
    "sh -ec 'git reset --hard'",
    "bash <<'EOF'" + NL + "git reset --hard" + NL + "EOF",
    "echo 'git reset --hard' | bash",
    "nice -n 10 git reset --hard",
    "sudo -u u git reset --hard",
    "env -u X git reset --hard",
    "timeout 5 git reset --hard",
    "exec git reset --hard",
    "\\git reset --hard",
    "/usr/bin/git reset --hard",
    "git commit -F - <<EOF" + NL + "docs: `git checkout -- .` 대신 restore" + NL + "EOF",
    'grep -q x <<<"t"' + NL + "git reset --hard",
    "cat <(git stash)",
    "eval eval eval eval git reset --hard",
    'cd "$(git rev-parse --show-toplevel)" && git checkout -- .',
    'git -C "$PWD" reset --hard',
    "(cd /tmp && git status) && git reset --hard",
    "cd sub && git reset --hard",
    "cd /nonexistent-commitforge-dir; git reset --hard",
    "git -C sub reset --hard",
    "git --git-dir=.git --work-tree=. reset --hard",
    "GIT_DIR=.git git reset --hard",
    "GIT_DIR=$X git reset --hard",
    "git co -- .",
    "git -c alias.r='reset --hard' r",
    "git rest --hard",
    'f(){ git "$@"; }; f reset --hard',
    "G=git; $G reset --hard",
    "git $(echo reset) --hard",
    "git {reset,status}",
    "git restore --staged --work -- a.txt",
    "git restore -sSTABLE -- a",
    "git restore .",
    "git commit --amen --no-edit",
    "git apply --check --apply p.diff",
    "git apply p.diff",
    "git show HEAD:t.txt > t.txt",
    "git diff --output=t.txt",
    "find . -name '*.txt' -exec git checkout -- {} +",
    "python3 -c 'import subprocess;subprocess.run([\"git\",\"reset\",\"--hard\"])'",
    "git checkout",
    "git checkout -b x HEAD~3",
    "git switch -C main",
    "git stash push -- a",
    "git branch -f main HEAD~1",
    "git clean -fd",
    "git update-index --assume-unchanged a",
    "git worktree remove --force ../wt",
]
LOCKED_ALLOWED = [
    "git status --short --branch --untracked-files=all",
    "git add -- src/a.ts src/b.ts",
    "git restore --staged -- src/a.ts",
    "git restore -S -- src/a.ts",
    'git restore --staged -- "$f"',
    "git apply --cached --recount patch.diff",
    "git apply --check patch.diff",
    "git apply --stat p.diff",
    "git rm --cached -- old.txt",
    "git switch -c feature/x",
    "git checkout -b feature/x",
    "git diff --cached && git show --stat HEAD",
    "git branch --show-current",
    "git branch --sort -committerdate",
    "git stash list",
    "git clean -n",
    "git st",
    "git diff refs/commitforge/snapshots/x -- src/remove_user.ts",
    'bash "/x/guard.sh" conserve --session s1',
    'bash "/x/guard.sh" abort --session "$COMMITFORGE_SESSION_ID"',
    "git commit -m \"$(cat <<'EOF'" + NL + "fix: git reset --hard 대신 restore 사용" + NL + NL
    + "- git checkout -- . 금지" + NL + "EOF" + NL + ")\"",
    "git commit -F - <<'EOF'" + NL + "git reset --hard 규칙 문서화" + NL + "EOF",
    "git commit -F - <<'END-MSG'" + NL + "fix: don't use git reset" + NL + "END-MSG",
    "git commit -m 'docs: `git checkout` 금지'",
    'git commit -am "msg"',
    "ls .git/claude-atomic-snapshots",
    "git diff > /tmp/x.diff",
    "git diff --cached > .git/claude-atomic-snapshots/20261006-x/patches/a.patch",
    "git log -1 2>&1",
    "git show HEAD:a.txt | head",
    "pnpm lint && pnpm test",
    "git push -u origin feature/x",
    "git fetch origin",
    "cd /tmp && git reset --hard",
    "rmdir .git/claude-atomic-snapshots/20261006-x/ledger/.lock",
    "python3 /x/scripts/ledger.py record --session s1",
    "git log --format='reset %h'",
    'echo "git reset --hard is dangerous"',
    'grep -rn "git reset" .',
    "git tag -a v1.0.0 -m 'release'",
    "git add .claude/skills/_git-atomic-core/scripts/guard.py",
    "git diff -- guard.py worktree_gate.py",
]
EVIDENCE_DENIED = [
    'rm -rf "/r/.git/claude-atomic-snapshots/20261006-x" 2>&1 && echo removed',
    "rm -rf .git/claude-atomic*",
    "rm -rf .git/claude-*",
    "cd .git/claude-atomic-snapshots && rm -rf ./*",
    "ls -d .git/claude-atomic-snapshots/* | xargs rm -rf",
    'S=.git/claude-atomic-snapshots; rm -rf "$S"',
    "find .git -name 'claude-atomic*' -exec rm -rf {} +",
    "find .git/claude-atomic-snapshots -mindepth 1 -delete",
    "git for-each-ref --format='delete %(refname)' refs/commitforge | git update-ref --stdin",
    'git update-ref -d "refs/commitforge/snapshots/x" 2>&1',
    "rm -rf .git",
    "rm -rf guard.py .git/claude-atomic-snapshots",
    "python3 -Ic \"import shutil; shutil.rmtree('.git/claude-atomic-snapshots')\"",
    "perl -ne 'unlink q(.git/claude-atomic-snapshots/x)' f",
    "rm -rf .git/*",
    "rmdir .git/claude-atomic.lock",
    "mv .git/claude-atomic-snapshots /tmp/x",
    "echo x > .git/claude-atomic.lock/owner.json",
    "python3 -c 'import shutil; shutil.rmtree(\".git/claude-atomic-snapshots/x\")'",
    "rm .git/claude-atomic-snapshots/20261006-x/ledger/../.cca-snapshot.json",
]
UNLOCKED_ALLOWED = [
    "git reset --hard",
    "git checkout -- .",
    "git stash",
    "rm -rf node_modules",
    "find . -name '*.pyc' -delete",
    "rmdir .git/claude-atomic-snapshots/20261006-x/ledger/.lock",
    'bash "/x/guard.sh" clean',
]


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class WorktreeGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="commitforge-gate-"))
        git("init", "-q", cwd=self.tmp)
        git("config", "alias.co", "checkout", cwd=self.tmp)
        git("config", "alias.st", "status", cwd=self.tmp)
        (self.tmp / "sub").mkdir()
        snapshot = self.tmp / ".git/claude-atomic-snapshots/20261006-x"
        (snapshot / "ledger/.lock").mkdir(parents=True)
        (self.tmp / ".git/refs/commitforge/snapshots").mkdir(parents=True)
        self.transcript = self.tmp / "transcript.jsonl"
        self.transcript.write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hold_lock(self, git_dir: Path | None = None) -> None:
        lock = (git_dir or self.tmp / ".git") / "claude-atomic.lock"
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps({"session": "s1"}), encoding="utf-8")

    def gate(self, command: str, cwd: Path | None = None, session: str = "s1") -> subprocess.CompletedProcess[str]:
        payload = {
            "session_id": session,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(cwd or self.tmp),
            "transcript_path": str(self.transcript),
        }
        proc = subprocess.run(
            [sys.executable, str(GATE)],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return subprocess.CompletedProcess(
            proc.args, proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")
        )

    def assert_denied(self, command: str, cwd: Path | None = None) -> None:
        proc = self.gate(command, cwd)
        self.assertEqual(proc.returncode, 2, command.replace(NL, "⏎"))
        self.assertIn("CommitForge", proc.stderr)

    def assert_allowed(self, command: str, cwd: Path | None = None) -> None:
        proc = self.gate(command, cwd)
        self.assertEqual(proc.returncode, 0, f"{command.replace(NL, '⏎')}\n{proc.stderr}")

    def user_typed(self, text: str, *, meta: bool = False) -> None:
        event = {"type": "user", "message": {"role": "user", "content": text}}
        if meta:
            event["isMeta"] = True
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def test_locked_worktree_denies_everything_outside_the_allowlist(self) -> None:
        self.hold_lock()
        for command in LOCKED_DENIED:
            with self.subTest(command=command):
                self.assert_denied(command)
        self.assertNotIn("s1", self.gate("git reset --hard").stderr)

    def test_locked_worktree_allows_the_commit_skills_commands(self) -> None:
        self.hold_lock()
        for command in LOCKED_ALLOWED:
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_evidence_deletion_is_denied_without_a_lock(self) -> None:
        for command in EVIDENCE_DENIED:
            with self.subTest(command=command):
                proc = self.gate(command)
                self.assertEqual(proc.returncode, 2, command)
                self.assertIn("복구 근거", proc.stderr)

    def test_unlocked_worktree_is_not_restricted(self) -> None:
        for command in UNLOCKED_ALLOWED:
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_lock_in_another_repository_does_not_gate_this_one(self) -> None:
        self.hold_lock()
        other = Path(tempfile.mkdtemp(prefix="commitforge-gate-other-"))
        try:
            git("init", "-q", cwd=other)
            self.assert_allowed("git reset --hard", cwd=other)
            self.assert_allowed(f"cd {other} && git reset --hard")
            self.assert_denied(f"cd {other} && git -C {self.tmp} reset --hard")
            self.assert_denied(f"GIT_DIR={self.tmp}/.git git reset --hard", cwd=other)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_linked_worktree_lock_protects_shared_refs_only(self) -> None:
        git("commit", "-q", "--allow-empty", "-m", "init", cwd=self.tmp)
        linked = self.tmp.parent / (self.tmp.name + "-linked")
        try:
            git("worktree", "add", "-q", str(linked), "-b", "wtb", cwd=self.tmp)
            self.hold_lock(self.tmp / ".git/worktrees" / linked.name)
            self.assert_denied("git reset --hard", cwd=linked)
            self.assert_denied(f"git worktree remove --force {linked}")
            self.assert_denied("git update-ref refs/heads/wtb HEAD")
            self.assert_denied("git branch -f wtb HEAD")
            self.assert_denied(f"git --git-dir={linked}/.git reset --hard")
            self.assert_allowed("git reset --hard")
            self.assert_allowed("git status", cwd=linked)
        finally:
            shutil.rmtree(linked, ignore_errors=True)

    def test_guard_calls_must_name_the_hook_session(self) -> None:
        self.hold_lock()
        for command in (
            'bash "/x/guard.sh" abort --session sessA',
            'bash "/x/guard.sh" finish --session=sessA',
            'COMMITFORGE_SESSION_ID=sessA bash "/x/guard.sh" abort --session "$COMMITFORGE_SESSION_ID"',
            'bash "/x/guard.sh" abort --session "$OTHER"',
        ):
            with self.subTest(command=command):
                proc = self.gate(command)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("--session", proc.stderr)
        self.assert_allowed('python3 "/x/guard.py" abort --session s1')
        self.assert_allowed('bash "/x/guard.sh" status')

    def test_guard_clean_requires_the_latest_prompt_to_request_it(self) -> None:
        self.hold_lock()
        clean = 'bash "/x/guard.sh" clean --request-session "$COMMITFORGE_SESSION_ID"'
        self.assert_denied(clean)

        self.user_typed("<command-name>/ccf</command-name>\n<command-args>clean</command-args>")
        self.user_typed("Base directory for this skill: ...", meta=True)
        self.assert_allowed(clean)

        self.user_typed("네, 정리해 주세요")
        self.assert_denied(clean)

        self.user_typed("<command-name>/simplify</command-name>\n<command-args>clean up</command-args>")
        self.assert_denied(clean)

        self.user_typed("<command-name>/commitforge:cc</command-name>\n<command-args>clean</command-args>")
        self.assert_allowed(clean)

    def test_real_guard_lock_and_session_only_abort(self) -> None:
        (self.tmp / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(GUARD), "begin", "--session", "s1"],
            cwd=self.tmp, stdout=subprocess.PIPE, check=True,
        )
        self.assert_denied("git stash -u")
        self.assert_allowed(f'python3 "{GUARD}" abort --session "$COMMITFORGE_SESSION_ID"')
        subprocess.run(
            [sys.executable, str(GUARD), "abort", "--session", "s1"],
            cwd=self.tmp, stdout=subprocess.PIPE, check=True,
        )
        self.assert_allowed("git stash -u")

    def test_non_ascii_paths_are_decoded_as_utf8(self) -> None:
        korean = self.tmp / "한글 폴더"
        korean.mkdir()
        git("init", "-q", cwd=korean)
        self.hold_lock(korean / ".git")
        self.assert_denied("git reset --hard", cwd=korean)

    def test_malformed_input_fails_open(self) -> None:
        for raw in (b"not json", b"[]", json.dumps({"tool_input": "x"}).encode(), b"\xff\xfe"):
            proc = subprocess.run([sys.executable, str(GATE)], input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(proc.returncode, 0, raw)

    def test_internal_error_denies_only_under_a_lock(self) -> None:
        original = worktree_gate_impl.Gate.run

        def broken(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("parser bug")

        worktree_gate_impl.Gate.run = broken  # type: ignore[assignment]
        try:
            event = {"cwd": str(self.tmp), "session_id": "s1"}
            self.assertIsNone(worktree_gate_impl.evaluate(event, "git status"))
            self.hold_lock()
            self.assertIn("RuntimeError", worktree_gate_impl.evaluate(event, "git status") or "")
        finally:
            worktree_gate_impl.Gate.run = original  # type: ignore[assignment]

    def test_constants_match_guard(self) -> None:
        self.assertEqual(worktree_gate_impl.LOCK_DIR_NAME, guard.LOCK_DIR_NAME)
        self.assertEqual(worktree_gate_impl.SNAPSHOT_DIR_NAME, guard.SNAPSHOT_DIR_NAME)
        skills = {name for name in install.SKILLS if not name.startswith("_")}
        self.assertEqual(worktree_gate_impl.COMMITFORGE_COMMANDS, skills)


class HookLauncherTest(unittest.TestCase):
    def test_missing_script_passes_and_present_script_still_denies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="commitforge-launcher-") as temp:
            repo = Path(temp)
            git("init", "-q", cwd=repo)
            (repo / ".git/claude-atomic.lock").mkdir()
            payload = json.dumps({"tool_input": {"command": "git reset --hard"}, "cwd": str(repo)})
            argv = [sys.executable, "-c", install.HOOK_LAUNCHER]
            denied = subprocess.run([*argv, str(GATE)], input=payload.encode(), capture_output=True, check=False)
            self.assertEqual(denied.returncode, 2, denied.stderr)
            missing = subprocess.run([*argv, str(repo / "gone.py")], input=payload.encode(), capture_output=True, check=False)
            self.assertEqual(missing.returncode, 0)

    def test_uninstall_matches_launcher_form_and_moved_gate_paths(self) -> None:
        import uninstall

        moved = "/old/place/.claude/skills/_git-atomic-core/scripts/worktree_gate.py"
        gate_path = Path("/new/.claude/skills/_git-atomic-core/scripts/worktree_gate.py")
        for module in (install, uninstall):
            launcher = {
                "type": "command",
                "command": subprocess.list2cmdline([sys.executable, "-c", module.HOOK_LAUNCHER, moved])
                if sys.platform == "win32"
                else " ".join([sys.executable, "-c", repr(module.HOOK_LAUNCHER), moved]),
            }
            self.assertTrue(module.is_commitforge_lifecycle_handler(launcher, gate_path), module.__name__)
            unrelated = {"type": "command", "command": f"{sys.executable} /opt/other/worktree_gate.py"}
            self.assertFalse(module.is_commitforge_lifecycle_handler(unrelated, gate_path))


if __name__ == "__main__":
    unittest.main()
