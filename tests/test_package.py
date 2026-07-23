from __future__ import annotations

import json
from pathlib import Path
import runpy
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
        for command in ("ccr", "cc", "cr", "cca"):
            skill = (
                ROOT / f".claude/skills/{command}/SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn(".commitforge/profile.md", skill)

    def test_cr_stops_before_staging_and_commit(self) -> None:
        cr_path = ROOT / ".claude/skills/cr/SKILL.md"
        cr = cr_path.read_text(encoding="utf-8")
        frontmatter = cr.split("\n---\n", 1)[0]

        self.assertTrue(cr_path.is_file())
        self.assertIn("11개 관점 심층 리뷰", cr)
        self.assertIn("Atomic Commit 계획, staging, commit, push를 하지 않았음", cr)
        self.assertNotIn("## 6. Atomic Commit 계획", cr)
        self.assertNotIn("Bash(git add ", frontmatter)
        self.assertNotIn("Bash(git commit ", frontmatter)

    def test_installer_agent_registries_match_package(self) -> None:
        actual = tuple(
            path.name for path in sorted((ROOT / ".claude/agents").glob("cca-*.md"))
        )
        for registry_file in ("install.py", "uninstall.py"):
            registered = tuple(
                sorted(runpy.run_path(str(ROOT / registry_file))["AGENTS"])
            )
            self.assertEqual(actual, registered)

    def test_review_agents_are_read_only(self) -> None:
        for path in (ROOT / ".claude/agents").glob("cca-*.md"):
            frontmatter = path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
            self.assertNotRegex(frontmatter, r"(?m)^\s*-\s*Bash(?:\(|\s|$)")

    def test_deep_reviewers_are_installed_and_connected(self) -> None:
        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        reviewers = (
            "cca-line-reviewer",
            "cca-architecture-reviewer",
            "cca-language-api-reviewer",
            "cca-ux-accessibility-reviewer",
            "cca-observability-reviewer",
            "cca-quality-reviewer",
        )
        for reviewer in reviewers:
            self.assertIn(reviewer, cca)
            self.assertTrue((ROOT / f".claude/agents/{reviewer}.md").is_file())

    def test_deep_review_coverage_is_explicit(self) -> None:
        protocol = (
            ROOT / ".claude/skills/_git-atomic-core/deep-review-protocol.md"
        ).read_text(encoding="utf-8")
        catalog = (
            ROOT / ".claude/skills/_git-atomic-core/language-api-pitfalls.md"
        ).read_text(encoding="utf-8")
        for topic in (
            "변경 라인 원장",
            "제거된 동작",
            "Cross-file",
            "Wrapper와 Proxy",
            "Architecture",
            "Accessibility",
            "Observability",
        ):
            self.assertIn(topic, protocol)
        for language in (
            "JavaScript·TypeScript",
            "Dart·Flutter",
            "Python",
            "Go",
            "Rust",
            "Java·Kotlin",
            "Swift·Objective-C",
            "C·C++",
            "SQL·Database",
        ):
            self.assertIn(language, catalog)


if __name__ == "__main__":
    unittest.main()
