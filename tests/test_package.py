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
        period = (
            ROOT / ".claude/skills/_git-atomic-core/period-review-modes.md"
        ).read_text(encoding="utf-8")

        self.assertIn("extended-modes.md", cca)
        for mode in ("today", "weekly", "release", "emergency", "learn"):
            self.assertIn(f"`{mode}`", cca)
            self.assertIn(f"`{mode}`", modes)
        self.assertIn("호스트 로컬 달력", period)
        self.assertIn("git merge-base --is-ancestor", modes)
        self.assertIn("working tree가 깨끗해도", modes)
        self.assertIn("Guard `finish --allow-dirty`", modes)
        self.assertIn("learn-status-before.z", modes)
        self.assertIn("cmp -s", modes)
        self.assertIn("이 시점에 `finish`하지 않고", cca)

    def test_period_modes_are_shared_by_cr_and_cca(self) -> None:
        period = (
            ROOT / ".claude/skills/_git-atomic-core/period-review-modes.md"
        ).read_text(encoding="utf-8")
        for command in ("cr", "cca"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("period-review-modes.md", skill)
            self.assertIn("today", skill)
            self.assertIn("weekly", skill)
        self.assertIn("최근 24시간이 아니다", period)
        self.assertIn("최근 7일이 아니다", period)
        self.assertIn("period-interaction", period)
        self.assertIn(
            "Atomic Commit 계획·메시지·staging·commit·push는 항상 금지",
            period,
        )
        self.assertIn(
            "`--fix`를 명시한 경우에만 현재 working hunk",
            period,
        )
        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "기간 commit이 있으면 Step 3~5의 심층 리뷰·검증까지 계속",
            cca,
        )

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
        self.assertIn("기본 10개 관점과 조건부 심층 리뷰", cr)
        self.assertIn("Atomic Commit 계획, staging, commit, push를 하지 않았음", cr)
        self.assertNotIn("## 6. Atomic Commit 계획", cr)
        self.assertNotIn("`cca-git-reviewer`", cr)
        self.assertIn("Atomic Commit 계획이나 메시지 후보를 만들지 않는다", cr)
        self.assertNotIn("Bash(git add ", frontmatter)
        self.assertNotIn("Bash(git commit ", frontmatter)
        self.assertIn("[--fix]", frontmatter)
        self.assertNotIn("[--no-fix]", frontmatter)
        self.assertIn("기본은 모든 소스 수정을 금지하는 읽기 전용 리뷰", cr)
        self.assertIn("`--fix`를 명시한 경우에만", cr)
        self.assertIn("SOURCE_EDIT_ALLOWED=false", cr)
        self.assertIn("--source-read-only", cr)
        self.assertIn("cr_edit_gate.py", cr)
        self.assertIn("\n  - Edit\n", frontmatter)
        self.assertIn("\n  - Write\n", frontmatter)

        gates = (
            ROOT / ".claude/skills/_git-atomic-core/review-gates.md"
        ).read_text(encoding="utf-8")
        cr_gate = gates.split("## 5. `/cr` 완료 Gate", 1)[1].split(
            "## 6. `/cca` Commit Gate", 1
        )[0]
        self.assertNotIn("staging plan 완성", cr_gate)
        self.assertIn("HEAD와 staged diff가 시작 상태와 동일", cr_gate)

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

    def test_conditional_reviewers_have_triggers_and_connections(self) -> None:
        conditional = (
            ROOT / ".claude/skills/_git-atomic-core/conditional-reviewers.md"
        ).read_text(encoding="utf-8")
        cr = (ROOT / ".claude/skills/cr/SKILL.md").read_text(encoding="utf-8")
        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        reviewers = (
            "cca-data-migration-reviewer",
            "cca-dependency-supply-chain-reviewer",
            "cca-reliability-recovery-reviewer",
            "cca-privacy-governance-reviewer",
            "cca-requirements-product-reviewer",
        )
        for reviewer in reviewers:
            self.assertIn(reviewer, conditional)
            self.assertIn(reviewer, cr)
            self.assertIn(reviewer, cca)
            self.assertTrue((ROOT / f".claude/agents/{reviewer}.md").is_file())
        self.assertIn("명시적 기준이 없으면", conditional)
        self.assertIn("비활성화 근거", conditional)


if __name__ == "__main__":
    unittest.main()
