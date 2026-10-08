#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest
import os
import tempfile


# Guard begin writes a recovery copy under the home directory; keep tests out of it.
os.environ.setdefault(
    "COMMITFORGE_RECOVERY_DIR", tempfile.mkdtemp(prefix="commitforge-recovery-test-")
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE_ROOT / ".claude/skills/_git-atomic-core/scripts"
TRIGGERS = SCRIPTS / "reviewer_triggers.py"


def classify(*paths: str, context: str = "") -> dict:
    argv = [sys.executable, str(TRIGGERS), *paths]
    if context:
        argv += ["--context", context]
    proc = subprocess.run(argv, text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f"triggers failed: {proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout)


class DataMigrationTriggerTest(unittest.TestCase):
    """실측으로 확인한 미탐지 경로가 활성화되어야 한다."""

    def test_plural_schema_directory_activates_data_migration(self) -> None:
        # 기존 패턴은 `schema`만 있어 복수형 디렉터리를 놓쳤다.
        result = classify("src/schemas/user.py")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_singular_schema_directory_still_activates(self) -> None:
        result = classify("src/schema/user.py")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_schema_definition_files_activate_data_migration(self) -> None:
        for path in ("api/user.proto", "events/click.avsc"):
            with self.subTest(path=path):
                result = classify(path)
                self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_storage_format_paths_activate_data_migration(self) -> None:
        result = classify("config/storage-format.yaml")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_unrelated_source_does_not_activate_data_migration(self) -> None:
        # 패턴은 하한선이다. 넓히더라도 평범한 소스를 끌어들이면 안 된다.
        result = classify("src/ui/button.tsx", "docs/readme.md")
        self.assertNotIn("cca-data-migration-reviewer", result["active"])


class ReliabilityTriggerTest(unittest.TestCase):
    def test_lock_and_recovery_paths_activate_reliability_reviewer(self) -> None:
        result = classify(
            ".claude/skills/_git-atomic-core/recovery.md",
            "editor-extension/test/lockWarning.test.ts",
        )
        self.assertIn("cca-reliability-recovery-reviewer", result["active"])

    def test_stale_and_concurrency_paths_activate_reliability_reviewer(self) -> None:
        result = classify("src/session/stale_reclaim.py", "tests/test_concurrency.py")
        self.assertIn("cca-reliability-recovery-reviewer", result["active"])

    def test_dependency_lockfiles_do_not_activate_reliability_reviewer(self) -> None:
        """A lockfile is a supply-chain artifact, not a locking primitive."""
        result = classify(
            "editor-extension/package-lock.json",
            "poetry.lock",
            "Cargo.lock",
        )
        self.assertIn("cca-dependency-supply-chain-reviewer", result["active"])
        self.assertNotIn("cca-reliability-recovery-reviewer", result["active"])


class ReleaseTriggerTest(unittest.TestCase):
    def test_release_artifacts_activate_release_reviewer(self) -> None:
        result = classify("VERSION", "MANIFEST.json", "checksums.sha256", "install.py")
        self.assertIn("cca-release-deployment-reviewer", result["active"])

    def test_deploy_and_rollback_paths_activate_release_reviewer(self) -> None:
        result = classify("deploy/rollback.sh", "src/flags/feature_flag.ts")
        self.assertIn("cca-release-deployment-reviewer", result["active"])

    def test_plain_source_change_does_not_activate_release_reviewer(self) -> None:
        result = classify("src/core/parser.ts")
        self.assertNotIn("cca-release-deployment-reviewer", result["active"])


class RequirementsTriggerTest(unittest.TestCase):
    def test_spec_source_file_does_not_activate_requirements_reviewer(self) -> None:
        """`spec.ts` is code. Requirements needs a comparable written criterion."""
        result = classify("src/spec.ts", "app/specs.ts")
        self.assertNotIn("cca-requirements-product-reviewer", result["active"])

    def test_spec_document_activates_requirements_reviewer(self) -> None:
        result = classify("docs/superpowers/specs/2026-09-12-cr-review-ledger-design.md")
        self.assertIn("cca-requirements-product-reviewer", result["active"])


class EvidenceShapeTest(unittest.TestCase):
    def test_context_evidence_records_pattern_not_raw_text(self) -> None:
        secretish = "retry 로직 수정 요청, 토큰은 ghp_exampleexampleexample 이다"
        result = classify("src/a.ts", context=secretish)
        blob = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("ghp_exampleexampleexample", blob)
        self.assertIn("cca-reliability-recovery-reviewer", result["active"])

    def test_path_evidence_reports_source_and_matched_pattern(self) -> None:
        result = classify("db/migrations/001_init.sql")
        entries = result["evidence"]["cca-data-migration-reviewer"]
        self.assertTrue(all("source" in item and "matched" in item for item in entries))
        self.assertTrue(any(item["source"] == "db/migrations/001_init.sql" for item in entries))


class InactiveReportingTest(unittest.TestCase):
    def test_inactive_reviewers_are_listed_with_reason(self) -> None:
        result = classify("src/core/parser.ts")
        inactive = {item["reviewer"]: item["reason"] for item in result["inactive"]}
        self.assertIn("cca-data-migration-reviewer", inactive)
        self.assertTrue(inactive["cca-data-migration-reviewer"])

    def test_active_and_inactive_partition_every_known_reviewer(self) -> None:
        result = classify("db/migrations/001_init.sql")
        names = set(result["active"]) | {item["reviewer"] for item in result["inactive"]}
        self.assertEqual(names, set(result["known_reviewers"]))
        self.assertFalse(set(result["active"]) & {item["reviewer"] for item in result["inactive"]})


if __name__ == "__main__":
    unittest.main()
