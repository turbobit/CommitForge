#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import os


# Guard begin writes a recovery copy under the home directory; keep tests out of it.
os.environ.setdefault(
    "COMMITFORGE_RECOVERY_DIR", tempfile.mkdtemp(prefix="commitforge-recovery-test-")
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INSTALL = PACKAGE_ROOT / "install.py"
UNINSTALL = PACKAGE_ROOT / "uninstall.py"
MARKER_NAME = ".commitforge-install.json"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(f"failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


class InstallMarkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cf-marker-test-"))
        self.marker = self.tmp / ".claude" / MARKER_NAME

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_writes_marker_with_package_version(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))

        self.assertTrue(self.marker.is_file(), "설치 마커가 기록되지 않았습니다")
        payload = json.loads(self.marker.read_text(encoding="utf-8"))
        version = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(payload["schema"], "commitforge-install/v1")
        self.assertEqual(payload["version"], version)
        self.assertEqual(payload["scope"], "project")
        self.assertEqual(
            payload["core_path"],
            str((self.tmp / ".claude" / "skills" / "_git-atomic-core").resolve()),
        )
        self.assertTrue(payload["installed_at"].endswith("Z"))
        self.assertTrue(Path(payload["python"]).name.startswith("python"))

    def test_dry_run_does_not_write_marker(self) -> None:
        proc = run(INSTALL, "--scope", "project", "--target", str(self.tmp), "--dry-run")

        self.assertFalse(self.marker.exists(), "dry-run이 마커를 기록했습니다")
        self.assertIn(MARKER_NAME, proc.stdout)

    def test_uninstall_removes_marker(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))
        self.assertTrue(self.marker.is_file())

        run(UNINSTALL, "--scope", "project", "--target", str(self.tmp))

        self.assertFalse(self.marker.exists(), "제거 후에도 마커가 남았습니다")

    def test_marker_write_failure_does_not_fail_install(self) -> None:
        """마커 기록이 실패해도 설치 자체는 성공해야 한다.

        마커는 표시용 메타데이터일 뿐이고, 이 시점에는 이미 skills·agents
        복사와 hook 설정이 전부 끝난 상태다. 마커 경로에 디렉터리를 미리
        만들어 write_text가 실패하도록 강제한다.
        """
        claude_dir = self.tmp / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / MARKER_NAME).mkdir()

        proc = run(INSTALL, "--scope", "project", "--target", str(self.tmp))

        self.assertEqual(proc.returncode, 0)
        self.assertTrue(
            (claude_dir / "skills" / "cr" / "SKILL.md").is_file(),
            "마커 기록 실패로 skills 설치까지 중단됐습니다",
        )
        self.assertIn("경고", proc.stderr)

    def test_reinstall_refreshes_marker_timestamp(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))
        first = json.loads(self.marker.read_text(encoding="utf-8"))
        self.marker.write_text(
            json.dumps({**first, "version": "0.0.1"}, ensure_ascii=False),
            encoding="utf-8",
        )

        run(INSTALL, "--scope", "project", "--target", str(self.tmp))

        second = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(second["version"], first["version"])


if __name__ == "__main__":
    unittest.main()
