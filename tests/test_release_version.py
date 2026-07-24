from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".claude/skills/_git-atomic-core/scripts/release_version.py"
)


class ReleaseVersionTest(unittest.TestCase):
    def run_script(self, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return json.loads(result.stdout)

    def test_stable_bumps_preserve_v_prefix(self) -> None:
        payload = self.run_script(
            "--bump",
            "minor",
            "--existing-tag",
            "v1.8.0",
            "--existing-tag",
            "v1.7.1",
        )
        self.assertEqual("v1.9.0", payload["next_tag"])
        self.assertEqual("1.9.0", payload["target_version"])

    def test_prerelease_ordinal_increments(self) -> None:
        payload = self.run_script(
            "--target",
            "2.0.0",
            "--channel",
            "rc",
            "--existing-tag",
            "v1.9.0",
            "--existing-tag",
            "v2.0.0-rc.1",
            "--existing-tag",
            "v2.0.0-rc.2",
        )
        self.assertEqual("v2.0.0-rc.3", payload["next_tag"])
        self.assertEqual(3, payload["prerelease_number"])

    def test_package_prefix_isolated_from_other_tags(self) -> None:
        payload = self.run_script(
            "--package",
            "mobile",
            "--bump",
            "patch",
            "--existing-tag",
            "mobile-v1.4.2",
            "--existing-tag",
            "web-v9.0.0",
        )
        self.assertEqual("mobile-v1.4.3", payload["next_tag"])

    def test_explicit_prerelease_target_is_preserved(self) -> None:
        payload = self.run_script(
            "--target",
            "2.0.0-beta.4",
            "--existing-tag",
            "v1.9.0",
        )
        self.assertEqual("v2.0.0-beta.4", payload["next_tag"])

    def test_existing_target_is_rejected(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--target",
                "1.8.0",
                "--existing-tag",
                "v1.8.0",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("이미 존재하는 tag", result.stderr)

    def test_unsafe_package_or_prefix_is_rejected(self) -> None:
        for args in (
            ("--package", "../mobile"),
            ("--tag-prefix", "release branch/"),
        ):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *args],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)

    def test_target_cannot_regress_or_add_prerelease_after_stable(self) -> None:
        for target in ("1.9.0", "2.0.0-rc.1"):
            with self.subTest(target=target):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--target",
                        target,
                        "--existing-tag",
                        "v2.0.0",
                    ],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("현재 stable version", result.stderr)


if __name__ == "__main__":
    unittest.main()
