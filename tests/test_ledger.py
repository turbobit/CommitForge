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
SCRIPTS = PACKAGE_ROOT / ".claude/skills/_git-atomic-core/scripts"
GUARD = SCRIPTS / "guard.py"
LEDGER = SCRIPTS / "ledger.py"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


class LedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cca-ledger-test-"))
        run(["git", "init"], self.tmp)
        run(["git", "config", "user.name", "CCA Test"], self.tmp)
        run(["git", "config", "user.email", "cca@example.invalid"], self.tmp)
        (self.tmp / "tracked.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: initial"], self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def script(
        self, path: Path, *args: str, check: bool = True
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        proc = run([sys.executable, str(path), *args], self.tmp, check=check)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid JSON: {proc.stdout}\n{proc.stderr}") from exc
        return proc, payload

    def guard(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.script(GUARD, *args, check=check)

    def ledger(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.script(LEDGER, *args, check=check)

    def record(self, session: str, payload: dict, check: bool = True):
        proc = subprocess.run(
            [sys.executable, str(LEDGER), "record", "--session", session],
            cwd=self.tmp, text=True, input=json.dumps(payload),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if check and proc.returncode != 0:
            raise AssertionError(f"record failed: {proc.stdout}\n{proc.stderr}")
        return proc, json.loads(proc.stdout)

    def begin(self, session: str = "session-a") -> dict:
        _, started = self.guard("begin", "--session", session)
        return started


class LedgerFoundationTest(LedgerTestCase):
    def test_status_reports_absent_ledger_before_init(self) -> None:
        started = self.begin()
        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["ok"])
        self.assertFalse(status["exists"])

    def test_init_creates_run_metadata(self) -> None:
        started = self.begin()
        _, created = self.ledger(
            "init", "--session", started["session"], "--scope", "working"
        )
        self.assertTrue(created["ok"])
        self.assertEqual(created["stage"], "init")
        self.assertEqual(created["scopes"], ["working"])

        ledger_dir = Path(started["snapshot"]) / "ledger"
        self.assertTrue((ledger_dir / "run.json").is_file())
        run_data = json.loads((ledger_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run_data["session"], started["session"])
        self.assertEqual(run_data["token"], started["token"])
        self.assertEqual(run_data["iteration"], 1)
        self.assertEqual(run_data["active_generation"], "")

        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["exists"])
        self.assertEqual(status["stage"], "init")

    def test_init_rejects_foreign_session(self) -> None:
        self.begin("session-owner")
        proc, refused = self.ledger(
            "init", "--session", "session-other", "--scope", "working", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(refused["ok"])

    def test_init_requires_active_lock(self) -> None:
        proc, refused = self.ledger(
            "init", "--session", "session-a", "--scope", "working", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(refused["ok"])

    def test_init_rejects_unknown_scope(self) -> None:
        started = self.begin()
        proc, refused = self.ledger(
            "init", "--session", started["session"], "--scope", "bogus", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_scope_invalid")


class InventoryWorkingScopeTest(LedgerTestCase):
    def init_ledger(self) -> dict:
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        return started

    def ids_by_kind(self, payload: dict) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for entry in payload["entries"]:
            grouped.setdefault(entry["kind"], []).append(entry["id"])
        return grouped

    def test_text_change_produces_hunk_entries(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertTrue(built["ok"])
        grouped = self.ids_by_kind(built)
        self.assertIn("hunk", grouped)
        self.assertTrue(
            any(entry.startswith("working:tracked.txt#") for entry in grouped["hunk"])
        )

    def test_untracked_file_produces_untracked_entry(self) -> None:
        (self.tmp / "new.txt").write_text("fresh\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["untracked"], ["untracked:new.txt#0"])

    def test_binary_change_produces_binary_entry(self) -> None:
        target = self.tmp / "blob.bin"
        target.write_bytes(bytes(range(256)))
        run(["git", "add", "blob.bin"], self.tmp)
        run(["git", "commit", "-m", "test: binary"], self.tmp)
        target.write_bytes(bytes(range(255, -1, -1)))
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["binary"], ["working:blob.bin#0"])

    def test_mode_only_change_produces_meta_entry(self) -> None:
        if sys.platform.startswith("win"):
            self.skipTest("Windows는 실행 비트를 추적하지 않는다")
        run(["git", "update-index", "--chmod=+x", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: chmod"], self.tmp)
        run(["git", "update-index", "--chmod=-x", "tracked.txt"], self.tmp)
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["meta"], ["staged:tracked.txt#0"])

    def test_quoted_filename_produces_entry_with_decoded_path(self) -> None:
        if sys.platform.startswith("win"):
            self.skipTest("Windows는 파일명에 큰따옴표를 허용하지 않는다")
        quoted_name = 'quote"d.txt'
        (self.tmp / quoted_name).write_text("base\n", encoding="utf-8")
        run(["git", "add", "--", quoted_name], self.tmp)
        run(["git", "commit", "-m", "test: quoted name"], self.tmp)
        (self.tmp / quoted_name).write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertTrue(
            any(
                entry == f"working:{quoted_name}#1"
                for entry in grouped["hunk"]
            )
        )

    def test_rename_to_quoted_name_produces_entry_with_new_path(self) -> None:
        if sys.platform.startswith("win"):
            self.skipTest("Windows는 파일명에 큰따옴표를 허용하지 않는다")
        renamed = 'renamed"q.txt'
        run(["git", "mv", "tracked.txt", renamed], self.tmp)
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["meta"], [f"staged:{renamed}#0"])

    def test_multiple_files_each_start_hunk_numbering_at_one(self) -> None:
        (self.tmp / "second.txt").write_text("second\n", encoding="utf-8")
        run(["git", "add", "second.txt"], self.tmp)
        run(["git", "commit", "-m", "test: second file"], self.tmp)
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        (self.tmp / "second.txt").write_text("second\nmore\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertIn("working:tracked.txt#1", grouped["hunk"])
        self.assertIn("working:second.txt#1", grouped["hunk"])

    def test_single_file_multiple_hunks_numbered_in_order(self) -> None:
        lines = [f"line{i}\n" for i in range(1, 21)]
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: many lines"], self.tmp)
        lines[0] = "line1-changed\n"
        lines[-1] = "line20-changed\n"
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        tracked_hunks = sorted(
            entry for entry in grouped["hunk"] if entry.startswith("working:tracked.txt#")
        )
        self.assertEqual(tracked_hunks, ["working:tracked.txt#1", "working:tracked.txt#2"])

    def test_inventory_is_written_to_active_generation(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        generation = built["generation"]
        self.assertTrue(generation.startswith("gen-01-"))
        path = Path(started["snapshot"]) / "ledger" / generation / "inventory.jsonl"
        self.assertTrue(path.is_file())
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(len(lines), built["total"])

    def test_inventory_is_idempotent(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, first = self.ledger("inventory", "--session", started["session"])
        _, second = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(first["total"], second["total"])
        self.assertEqual(first["generation"], second["generation"])


class InventoryRangeScopeTest(LedgerTestCase):
    def make_range(self) -> str:
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "ranged.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "ranged.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ranged"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        return f"{base}..{head}"

    def test_range_scope_covers_committed_hunks(self) -> None:
        spec = self.make_range()
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", "working", "--scope", f"range:{spec}",
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        ranged = [
            entry for entry in built["entries"]
            if entry["source"].startswith("range@")
        ]
        self.assertTrue(any(entry["path"] == "ranged.txt" for entry in ranged))

    def test_invalid_range_fails_closed(self) -> None:
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"], "--scope", "range:deadbeef..cafebabe"
        )
        proc, refused = self.ledger("inventory", "--session", started["session"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_range_unresolved")

    def test_range_scope_rejects_option_injection_via_output_flag(self) -> None:
        started = self.begin()
        target = self.tmp / "pwned.txt"
        proc, refused = self.ledger(
            "init", "--session", started["session"],
            "--scope", f"range:--output={target}..HEAD",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_scope_invalid")
        self.assertFalse(target.exists())

    def test_range_scope_rejects_leading_dash_option(self) -> None:
        started = self.begin()
        proc, refused = self.ledger(
            "init", "--session", started["session"],
            "--scope", "range:-p..HEAD",
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_scope_invalid")

    def test_two_range_scopes_produce_disjoint_ids(self) -> None:
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "shared.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "shared.txt"], self.tmp)
        run(["git", "commit", "-m", "test: shared v1"], self.tmp)
        mid = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "shared.txt").write_text("two\n", encoding="utf-8")
        run(["git", "add", "shared.txt"], self.tmp)
        run(["git", "commit", "-m", "test: shared v2"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()

        first_spec = f"{base}..{mid}"
        second_spec = f"{mid}..{head}"

        started = self.begin()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", f"range:{first_spec}", "--scope", f"range:{second_spec}",
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        ranged = [entry for entry in built["entries"] if entry["path"] == "shared.txt"]
        self.assertEqual(len(ranged), 2)
        ids = [entry["id"] for entry in ranged]
        self.assertEqual(len(ids), len(set(ids)))


class RecordTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, [entry["id"] for entry in built["entries"]]

    def test_record_accepts_known_ids(self) -> None:
        started, ids = self.prepared()
        _, saved = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "PASS", "reviewer": "cca-line-reviewer"}]},
        )
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["recorded_verdicts"], 1)

    def test_record_rejects_fabricated_id(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": "working:does-not-exist.py#9", "verdict": "PASS"}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_unknown_id")

    def test_record_rejects_invalid_verdict(self) -> None:
        started, ids = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "LOOKS_FINE"}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_invalid_verdict")

    def test_record_rejects_non_dict_verdict_element(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.record(
            started["session"], {"verdicts": ["not-a-dict"]}, check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_bad_input")

    def test_record_rejects_non_string_verdict_id(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": 123, "verdict": "PASS"}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_bad_input")

    def test_record_rejects_reviewer_missing_name(self) -> None:
        started, ids = self.prepared()
        proc, refused = self.record(
            started["session"],
            {
                "verdicts": [{"id": ids[0], "verdict": "PASS"}],
                "reviewers": [{"status": "ACTIVE"}],
            },
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_bad_input")

    def test_record_rejects_verdicts_not_a_list(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.record(
            started["session"], {"verdicts": "PASS"}, check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_bad_input")

    def test_rejected_batch_leaves_hunks_file_unchanged(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "PASS", "reviewer": "r0"}]},
        )
        _, status = self.ledger("status", "--session", started["session"])
        hunks = (
            Path(started["snapshot"]) / "ledger" / status["active_generation"] / "hunks.jsonl"
        )
        before = hunks.read_bytes()

        self.record(
            started["session"],
            {"verdicts": [{"id": "working:does-not-exist.py#9", "verdict": "PASS"}]},
            check=False,
        )
        self.record(
            started["session"], {"verdicts": ["not-a-dict"]}, check=False
        )

        self.assertEqual(hunks.read_bytes(), before)

    def test_finding_verdict_requires_finding_record(self) -> None:
        started, ids = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_finding_missing")

    def test_finding_verdict_accepted_with_finding(self) -> None:
        started, ids = self.prepared()
        _, saved = self.record(
            started["session"],
            {
                "verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}],
                "findings": [{"id": "f-1", "severity": "MAJOR", "file": "tracked.txt"}],
            },
        )
        self.assertEqual(saved["recorded_findings"], 1)

    def test_reader_tolerates_one_truncated_trailing_line(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        hunks = (
            Path(started["snapshot"]) / "ledger" / status["active_generation"] / "hunks.jsonl"
        )
        with hunks.open("a", encoding="utf-8") as stream:
            stream.write('{"id": "truncated"')
        _, again = self.ledger("status", "--session", started["session"])
        self.assertTrue(again["ok"])

    def test_concurrent_records_do_not_lose_entries(self) -> None:
        started, ids = self.prepared()
        processes = [
            subprocess.Popen(
                [sys.executable, str(LEDGER), "record", "--session", started["session"]],
                cwd=self.tmp, text=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            for _ in range(4)
        ]
        for index, proc in enumerate(processes):
            proc.communicate(
                json.dumps(
                    {"verdicts": [{"id": ids[0], "verdict": "PASS", "reviewer": f"r{index}"}]}
                )
            )
        for proc in processes:
            self.assertEqual(proc.returncode, 0)

        _, status = self.ledger("status", "--session", started["session"])
        hunks = (
            Path(started["snapshot"]) / "ledger" / status["active_generation"] / "hunks.jsonl"
        )
        lines = [line for line in hunks.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 4)


if __name__ == "__main__":
    unittest.main()
