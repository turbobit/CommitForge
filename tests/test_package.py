from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTest(unittest.TestCase):
    def test_branding_and_version_are_consistent(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual("CommitForge", manifest["name"])
        self.assertEqual(version, manifest["version"])
        self.assertTrue(readme.startswith("# CommitForge"))

    def test_extended_modes_are_connected(self) -> None:
        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        modes = (
            ROOT / ".claude/skills/_git-atomic-core/extended-modes.md"
        ).read_text(encoding="utf-8")

        self.assertIn("extended-modes.md", cca)
        for mode in ("today", "release", "emergency", "learn"):
            self.assertIn(f"`{mode}`", cca)
            self.assertIn(f"`{mode}`", modes)
        self.assertIn("호스트의 로컬 시간대", modes)
        self.assertIn("git merge-base --is-ancestor", modes)
        self.assertIn("working tree가 깨끗해도", modes)
        self.assertIn("Guard `finish --allow-dirty`", modes)
        self.assertIn("learn-status-before.z", modes)
        self.assertIn("cmp -s", modes)
        self.assertIn("이 시점에 `finish`하지 않고", cca)

    def test_all_commands_load_learned_profile(self) -> None:
        for command in ("ccr", "cc", "cca"):
            skill = (
                ROOT / f".claude/skills/{command}/SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn(".commitforge/profile.md", skill)


if __name__ == "__main__":
    unittest.main()
