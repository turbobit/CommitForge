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


class AdvanceTest(LedgerTestCase):
    def started_with_inventory(self) -> tuple[dict, dict]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, built

    def test_advance_creates_new_generation_from_live_diff(self) -> None:
        started, first = self.started_with_inventory()
        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        _, advanced = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.assertTrue(advanced["ok"])
        self.assertEqual(advanced["iteration"], 2)
        self.assertNotEqual(advanced["generation"], first["generation"])
        self.assertTrue(advanced["generation"].startswith("gen-02-"))
        self.assertGreaterEqual(advanced["total"], 1)
        inventory_path = (
            Path(started["snapshot"]) / "ledger" / advanced["generation"] / "inventory.jsonl"
        )
        lines = [
            json.loads(line)
            for line in inventory_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(any(entry["path"] == "tracked.txt" for entry in lines))

    def test_previous_generation_stays_immutable(self) -> None:
        started, first = self.started_with_inventory()
        ledger_dir = Path(started["snapshot"]) / "ledger"
        original = (ledger_dir / first["generation"] / "inventory.jsonl").read_bytes()

        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.assertEqual(
            (ledger_dir / first["generation"] / "inventory.jsonl").read_bytes(), original
        )

    def test_advance_rejects_stale_fingerprint(self) -> None:
        started, _ = self.started_with_inventory()
        proc, refused = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", "0" * 64, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_fingerprint_mismatch")


class CoverageTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        # Two independent entries (a tracked hunk plus an untracked file) so
        # that recording a verdict for only one of them leaves the other
        # genuinely pending; a single-entry fixture would make "record the
        # only id" and "cover everything" indistinguishable.
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("fresh\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        ids = [entry["id"] for entry in built["entries"]]
        # Guard the fixture's own premise: several tests below record a
        # verdict for ids[0] only and assert the rest stays pending. A
        # one-entry inventory would make them vacuously pass.
        self.assertGreater(len(ids), 1, f"fixture must yield >1 inventory entry: {ids}")
        return started, ids

    def test_status_reports_incomplete_coverage(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertFalse(status["complete"])
        self.assertGreater(status["pending_count"], 0)

    def test_status_reports_complete_coverage(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["complete"])
        self.assertEqual(status["pending"], [])

    def test_unknown_verdict_blocks_completion(self) -> None:
        started, ids = self.prepared()
        verdicts = [{"id": identifier, "verdict": "PASS"} for identifier in ids[1:]]
        verdicts.append({"id": ids[0], "verdict": "UNKNOWN"})
        self.record(started["session"], {"verdicts": verdicts})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertFalse(status["complete"])
        self.assertEqual(status["unknown"], [ids[0]])

    def test_latest_verdict_wins_for_same_id(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "UNKNOWN"}]})
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertEqual(status["unknown"], [])

    def test_report_emits_findings_and_counts(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {
                "verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}],
                "findings": [{"id": "f-1", "severity": "MAJOR", "file": "tracked.txt"}],
            },
        )
        _, report = self.ledger("report", "--session", started["session"])
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["findings"][0]["id"], "f-1")
        self.assertEqual(report["coverage"]["by_verdict"]["FINDING"], 1)

    def test_corrupted_verdict_value_blocks_completion(self) -> None:
        # cmd_record validates against VERDICTS at write time, so the only
        # way an out-of-vocabulary value reaches hunks.jsonl is a
        # hand-edited or corrupted file. Simulate that directly.
        started, ids = self.prepared()
        _, status = self.ledger("status", "--session", started["session"])
        generation = status["generation"]
        hunks = Path(started["snapshot"]) / "ledger" / generation / "hunks.jsonl"
        with hunks.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"id": ids[0], "verdict": "REVIEWED"}) + "\n")
        _, status = self.ledger("status", "--session", started["session"])
        self.assertFalse(status["complete"])
        self.assertIn(ids[0], status["unknown"])

    def test_status_before_inventory_has_full_key_set(self) -> None:
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, status = self.ledger("status", "--session", started["session"])
        self.assertIsInstance(status["complete"], bool)
        self.assertIsInstance(status["fingerprint_matches_current"], bool)
        self.assertIsInstance(status["generation"], str)
        self.assertIsInstance(status["pending"], list)
        self.assertIsInstance(status["pending_count"], int)
        self.assertIsInstance(status["unknown"], list)
        self.assertIsInstance(status["unknown_count"], int)


class GateTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        # Two independent entries (as in CoverageTest.prepared) so that
        # recording a verdict for only ids[0] leaves a genuine pending
        # entry; a single-entry fixture would make "record the only id"
        # and "cover everything" indistinguishable.
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("fresh\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        ids = [entry["id"] for entry in built["entries"]]
        # Guard the fixture's own premise: the blocking tests below record a
        # verdict for ids[0] only and expect the gate to refuse on what is
        # left. A one-entry inventory would make them vacuously pass.
        self.assertGreater(len(ids), 1, f"fixture must yield >1 inventory entry: {ids}")
        return started, ids

    def test_incomplete_ledger_blocks_verify_review(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")
        self.assertGreater(refused["pending_count"], 0)

    def test_complete_ledger_passes_verify_review(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger"]["complete"])

    def test_unknown_verdict_blocks_verify_review(self) -> None:
        started, ids = self.prepared()
        verdicts = [{"id": identifier, "verdict": "PASS"} for identifier in ids[1:]]
        verdicts.append({"id": ids[0], "verdict": "UNKNOWN"})
        self.record(started["session"], {"verdicts": verdicts})
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_unknown")

    def test_missing_ledger_blocks_verify_review(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_missing")

    def test_allow_unledgered_passes_with_bypass_marker(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", "--allow-unledgered",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger_bypassed"])
        self.assertGreater(verified["ledger"]["pending_count"], 0)

    def test_finish_enforces_the_same_gate(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        proc, refused = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")
        self.assertTrue(Path(started["snapshot"]).exists())

    def test_stale_ledger_blocks_verify_review(self) -> None:
        # A fully-verdicted ledger whose fingerprint has moved (simulating
        # --fix without a following advance) must still be refused: the
        # gate exists specifically to catch this "complete but stale" case.
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_stale")

    def test_allow_unledgered_reports_stale_bypass_reason(self) -> None:
        # complete=True for a stale-but-fully-verdicted ledger, so
        # ledger_bypassed must be derived from the reason the gate would
        # have raised, not from `complete` alone -- otherwise this exact
        # bypass would silently report ledger_bypassed: false.
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--require-ledger", "--allow-unledgered",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger"]["complete"])
        self.assertTrue(verified["ledger_bypassed"])
        self.assertEqual(verified["ledger"]["bypassed_reason"], "ledger_stale")

    def test_no_generation_blocks_verify_review_with_accurate_reason(self) -> None:
        # Before `inventory` ever runs, coverage()'s no-generation
        # early-return hard-codes fingerprint_matches_current: False; the
        # gate must not misreport this as ledger_stale (implying a missed
        # advance) when the truth is inventory was simply never run.
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_no_generation")

    def test_truncated_inventory_blocks_verify_review(self) -> None:
        # write_inventory persists the per-generation entry count into
        # run.json; if inventory.jsonl is later truncated (crash mid-write,
        # or tampering) the mismatch must fail closed rather than let a
        # zero-entry denominator report complete: True.
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, status = self.ledger("status", "--session", started["session"])
        generation = status["generation"]
        inventory_path = Path(started["snapshot"]) / "ledger" / generation / "inventory.jsonl"
        inventory_path.write_text("", encoding="utf-8")
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_inventory_mismatch")


class AutoArmedGateTest(LedgerTestCase):
    """The gate must arm on the ledger's presence, not on a remembered flag.

    `--require-ledger` lived in the same SKILL.md a compaction eats, so a run
    that forgot it reached a successful `finish` with an untouched ledger --
    the exact inversion the ledger exists to remove.
    """

    def prepared(self) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("fresh\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        ids = [entry["id"] for entry in built["entries"]]
        self.assertGreater(len(ids), 1, f"fixture must yield >1 inventory entry: {ids}")
        return started, ids

    def test_finish_without_require_ledger_blocks_on_incomplete_ledger(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")
        self.assertTrue(Path(started["snapshot"]).exists())
        self.assertTrue((Path(started["snapshot"]) / "ledger" / "run.json").is_file())

    def test_verify_review_without_require_ledger_blocks_on_incomplete_ledger(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")

    def test_complete_ledger_passes_without_require_ledger(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, verified = self.guard(
            "verify-review", "--session", started["session"], "--source-read-only"
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger"]["complete"])
        self.assertFalse(verified["ledger_bypassed"])

    def test_allow_unledgered_still_works_on_the_auto_armed_path(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, finished = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", "--allow-unledgered",
        )
        self.assertTrue(finished["ok"])
        self.assertTrue(finished["ledger_bypassed"])
        self.assertEqual(finished["ledger"]["bypassed_reason"], "ledger_incomplete")

    def test_run_without_a_ledger_is_untouched(self) -> None:
        # `/cpr` and `/cca` never create a ledger. Presence detection must
        # leave those paths exactly as they were: no gate, no ledger keys.
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        _, finished = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only",
        )
        self.assertTrue(finished["ok"])
        self.assertTrue(finished["snapshot_removed"])
        self.assertIsNone(finished["ledger"])
        self.assertFalse(finished["ledger_bypassed"])

    def test_require_ledger_still_fails_when_no_ledger_exists(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        proc, refused = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_missing")


class EmptyInventoryGateTest(LedgerTestCase):
    """A zero-entry denominator is vacuously complete.

    It must be refused when the snapshot captured content -- that means a
    scope covering those changes was never declared, or the denominator was
    lost -- and must pass when the snapshot is genuinely empty, which is the
    documented "검토 대상 없음" exit of SKILL.md §2.
    """

    def undeclared_working_scope(self) -> dict:
        # The reviewed changes are in the working tree, but only an empty
        # range scope was declared: the denominator misses everything.
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("fresh\n", encoding="utf-8")
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"], "--scope", f"range:{head}..{head}"
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(built["total"], 0)
        return started

    def clean_tree(self) -> dict:
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(built["total"], 0)
        return started

    def test_empty_inventory_over_a_non_empty_snapshot_blocks_verify_review(self) -> None:
        started = self.undeclared_working_scope()
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_empty_inventory")

    def test_empty_inventory_over_a_non_empty_snapshot_blocks_finish(self) -> None:
        started = self.undeclared_working_scope()
        proc, refused = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_empty_inventory")
        self.assertTrue(Path(started["snapshot"]).exists())

    def test_clean_tree_review_passes_the_gate_and_finishes(self) -> None:
        # SKILL.md §2: "working change와 선택한 기간·commit range가 모두 비어
        # 있을 때만 Guard finish 후 '검토 대상 없음'으로 종료한다." The
        # zero-total rule must not turn that documented exit into a dead end.
        started = self.clean_tree()
        _, verified = self.guard(
            "verify-review", "--session", started["session"], "--source-read-only"
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger"]["complete"])
        self.assertFalse(verified["ledger_bypassed"])

        _, finished = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only",
        )
        self.assertTrue(finished["ok"])
        self.assertTrue(finished["snapshot_removed"])
        self.assertFalse(finished["ledger_bypassed"])
        self.assertFalse(Path(started["snapshot"]).exists())

    def test_declared_range_with_no_commits_is_an_empty_review(self) -> None:
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", "working", "--scope", f"range:{head}..{head}",
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(built["total"], 0)
        _, verified = self.guard(
            "verify-review", "--session", started["session"], "--source-read-only"
        )
        self.assertTrue(verified["ok"])

    def test_declaring_the_range_scope_fills_the_denominator(self) -> None:
        # The supported fix: declare the range once §2 has computed it. The
        # second `init` merges instead of resetting.
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "ranged.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "ranged.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ranged"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()

        started = self.clean_tree()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", "working", "--scope", f"range:{base}..{head}",
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertGreater(built["total"], 0)
        self.record(
            started["session"],
            {"verdicts": [{"id": e["id"], "verdict": "PASS"} for e in built["entries"]]},
        )
        _, verified = self.guard(
            "verify-review", "--session", started["session"], "--source-read-only"
        )
        self.assertTrue(verified["ledger"]["complete"])

    def test_allow_unledgered_reports_empty_inventory_bypass(self) -> None:
        started = self.undeclared_working_scope()
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--allow-unledgered",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger_bypassed"])
        self.assertEqual(verified["ledger"]["bypassed_reason"], "ledger_empty_inventory")


class InventoryRerunTest(LedgerTestCase):
    def multi_line_base(self) -> list[str]:
        lines = [f"line{i}\n" for i in range(1, 21)]
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: many lines"], self.tmp)
        return lines

    def test_rerun_after_advance_keeps_the_hunk_the_fix_created(self) -> None:
        # `cmd_inventory` used to always read the snapshot, which froze the
        # pre-fix state. Re-running it after `advance` collapsed the gen-02
        # denominator back to the pre-fix set -- and rewrote inventory_totals
        # to match, so the mismatch check never fired and the fix's own new
        # hunk was never reviewed.
        lines = self.multi_line_base()
        lines[0] = "line1-changed\n"
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")

        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, first = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(first["total"], 1)

        lines[-1] = "line20-changed\n"
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        _, advanced = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.assertEqual(advanced["total"], 2)

        _, rebuilt = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(rebuilt["generation"], advanced["generation"])
        self.assertEqual(rebuilt["total"], 2)
        self.assertIn("working:tracked.txt#2", [e["id"] for e in rebuilt["entries"]])

        self.record(
            started["session"],
            {"verdicts": [{"id": "working:tracked.txt#1", "verdict": "PASS"}]},
        )
        proc, refused = self.guard(
            "verify-review", "--session", started["session"], check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")

    def test_rerun_with_a_moved_denominator_conflicts(self) -> None:
        lines = self.multi_line_base()
        lines[0] = "line1-changed\n"
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")

        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        self.ledger("inventory", "--session", started["session"])
        _, fingerprint = self.guard("fingerprint")
        self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )

        lines[-1] = "line20-changed\n"
        (self.tmp / "tracked.txt").write_text("".join(lines), encoding="utf-8")
        proc, refused = self.ledger(
            "inventory", "--session", started["session"], check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_inventory_conflict")
        self.assertGreater(refused["added_count"], 0)


class InitMergeTest(LedgerTestCase):
    def test_rerun_preserves_generation_and_unions_scopes(self) -> None:
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "ranged.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "ranged.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ranged"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()

        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        self.record(
            started["session"],
            {"verdicts": [{"id": built["entries"][0]["id"], "verdict": "PASS"}]},
        )

        _, merged = self.ledger(
            "init", "--session", started["session"], "--scope", f"range:{base}..{head}"
        )
        self.assertEqual(merged["scopes"], ["working", f"range:{base}..{head}"])
        self.assertEqual(merged["scopes_added"], [f"range:{base}..{head}"])
        # A widened denominator invalidates the active inventory.
        self.assertEqual(merged["active_generation"], "")

        _, rebuilt = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(rebuilt["generation"], built["generation"])
        self.assertGreater(rebuilt["total"], built["total"])
        # The verdict recorded before the merge survives the rebuild.
        _, status = self.ledger("status", "--session", started["session"])
        self.assertEqual(status["by_verdict"]["PASS"], 1)

    def test_rerun_with_the_same_scope_is_a_no_op(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        _, again = self.ledger(
            "init", "--session", started["session"], "--scope", "working"
        )
        self.assertEqual(again["scopes_added"], [])
        self.assertEqual(again["active_generation"], built["generation"])

    def test_rerun_after_advance_does_not_orphan_the_generation(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        self.ledger("inventory", "--session", started["session"])
        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        _, advanced = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.record(
            started["session"],
            {"verdicts": [{"id": "working:tracked.txt#1", "verdict": "PASS"}]},
        )

        _, again = self.ledger(
            "init", "--session", started["session"], "--scope", "working"
        )
        self.assertEqual(again["iteration"], 2)
        self.assertEqual(again["active_generation"], advanced["generation"])
        _, status = self.ledger("status", "--session", started["session"])
        self.assertEqual(status["generation"], advanced["generation"])
        self.assertEqual(status["by_verdict"]["PASS"], 1)

    def test_corrupt_run_json_is_diagnosed_as_corrupt(self) -> None:
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        run_path = Path(started["snapshot"]) / "ledger" / "run.json"
        run_path.write_text("{not json", encoding="utf-8")
        proc, refused = self.ledger(
            "status", "--session", started["session"], check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_corrupt")


class DiffPrefixConfigTest(LedgerTestCase):
    def hostile_prefix_config(self) -> None:
        # Every knob git offers for rewriting diff path prefixes. srcPrefix
        # and dstPrefix (git >= 2.41) survive `diff.noprefix=false`, so they
        # have to be pinned separately or the denominator's paths come back
        # as `dst/<path>`.
        run(["git", "config", "diff.noprefix", "true"], self.tmp)
        run(["git", "config", "diff.mnemonicPrefix", "true"], self.tmp)
        run(["git", "config", "diff.srcPrefix", "src/"], self.tmp)
        run(["git", "config", "diff.dstPrefix", "dst/"], self.tmp)

    def test_guard_and_ledger_agree_on_the_ledger_path_literals(self) -> None:
        # `guard.ledger_present` duplicates these two segments on purpose so
        # that a `finish` for /cc, /cca or /cpr never has to import ledger.py.
        # Duplication is only safe while the two definitions agree.
        sys.path.insert(0, str(SCRIPTS))
        import guard as guard_module
        import ledger as ledger_module

        source = (SCRIPTS / "guard.py").read_text(encoding="utf-8")
        self.assertIn(
            f'snapshot / "{ledger_module.LEDGER_DIR_NAME}" / "{ledger_module.RUN_NAME}"',
            source,
        )
        self.assertTrue(hasattr(guard_module, "ledger_present"))

    def test_noprefix_config_still_yields_the_real_path(self) -> None:
        # `diff.noprefix=true` is a common global setting. It drops the
        # `a/`/`b/` prefixes, and the `diff --git` header then reads as
        # `diff --git tracked.txt tracked.txt`, which used to produce the id
        # `working:tracked.txt tracked.txt#1`.
        self.hostile_prefix_config()
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        ids = [entry["id"] for entry in built["entries"]]
        self.assertIn("working:tracked.txt#1", ids)

    def test_noprefix_config_still_yields_the_real_path_in_a_range_scope(self) -> None:
        self.hostile_prefix_config()
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "ranged.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "ranged.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ranged"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"], "--scope", f"range:{base}..{head}"
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertEqual([entry["path"] for entry in built["entries"]], ["ranged.txt"])

    def test_path_containing_b_slash_keeps_a_distinct_id(self) -> None:
        # `diff --git a/x b/y.txt b/x b/y.txt` has no unambiguous separator,
        # so the header heuristic resolved it to `y.txt` -- colliding with a
        # real `y.txt` so one verdict covered both entries.
        self.hostile_prefix_config()
        nested = self.tmp / "x b"
        nested.mkdir()
        (nested / "y.txt").write_text("one\n", encoding="utf-8")
        (self.tmp / "y.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "--", "x b/y.txt", "y.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ambiguous paths"], self.tmp)
        (nested / "y.txt").write_text("one\ntwo\n", encoding="utf-8")
        (self.tmp / "y.txt").write_text("one\ntwo\n", encoding="utf-8")

        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        ids = [entry["id"] for entry in built["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("working:x b/y.txt#1", ids)
        self.assertIn("working:y.txt#1", ids)

    def test_rename_into_a_path_containing_b_slash_keeps_the_real_path(self) -> None:
        # A rename has no content and therefore no `+++` line; its path comes
        # from the `rename to` line rather than the ambiguous two-sided header.
        self.hostile_prefix_config()
        nested = self.tmp / "x b"
        nested.mkdir()
        run(["git", "mv", "tracked.txt", "x b/renamed.txt"], self.tmp)
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(
            [entry["id"] for entry in built["entries"]], ["staged:x b/renamed.txt#0"]
        )


if __name__ == "__main__":
    unittest.main()
