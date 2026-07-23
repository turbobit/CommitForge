from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release.py"


class ReleaseTest(unittest.TestCase):
    def run_release(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(RELEASE), *args],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_metadata_is_current(self) -> None:
        self.run_release("--check")

    def test_archives_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="commitforge-release-a-") as first:
            with tempfile.TemporaryDirectory(prefix="commitforge-release-b-") as second:
                self.run_release("--check", "--archives-dir", first)
                self.run_release("--check", "--archives-dir", second)

                first_files = sorted(Path(first).iterdir())
                second_files = sorted(Path(second).iterdir())
                self.assertEqual(
                    [path.name for path in first_files],
                    [path.name for path in second_files],
                )
                for left, right in zip(first_files, second_files):
                    self.assertEqual(left.read_bytes(), right.read_bytes())

                tar_path = next(path for path in first_files if path.name.endswith(".tar.gz"))
                with tempfile.TemporaryDirectory(prefix="commitforge-extract-") as extracted:
                    with tarfile.open(tar_path, "r:gz") as archive:
                        archive.extractall(extracted)
                    package_root = next(Path(extracted).iterdir())
                    subprocess.run(
                        [sys.executable, "release.py", "--check"],
                        cwd=package_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )
                    subprocess.run(
                        [sys.executable, "verify.py"],
                        cwd=package_root,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )


if __name__ == "__main__":
    unittest.main()
