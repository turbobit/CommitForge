from __future__ import annotations

import json
from pathlib import Path
import os
import runpy
import subprocess
import sys
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
        cr = (ROOT / ".claude/skills/cr/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("extended-modes.md", cr)
        for mode in ("today", "3days", "weekly", "release", "emergency", "learn"):
            self.assertIn(f"`{mode}`", cca)
            self.assertIn(f"`{mode}`", cr)
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
            self.assertIn("3days", skill)
            self.assertIn("weekly", skill)
        self.assertIn("최근 24시간이 아니다", period)
        self.assertIn("정확한 72시간 rolling window가 아니다", period)
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

    def test_reviewer_concurrency_is_adaptive(self) -> None:
        execution = (
            ROOT / ".claude/skills/_git-atomic-core/review-execution.md"
        ).read_text(encoding="utf-8")
        for contract in (
            "기본 동시 실행 목표는 6개",
            "최대 8개",
            "3~4개로 축소",
            "환경 상한",
        ):
            self.assertIn(contract, execution)
        self.assertNotIn("최대 4개 agent", execution)

    def test_read_only_commands_have_adaptive_agent_team_contract(self) -> None:
        execution = (
            ROOT / ".claude/skills/_git-atomic-core/review-execution.md"
        ).read_text(encoding="utf-8")
        for command in ("cr", "ccr", "cpr"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            frontmatter = skill.split("\n---\n", 1)[0]
            self.assertIn("--team|--no-team", frontmatter)
            self.assertIn("agent_team_mode.py", skill)
            self.assertIn("Agent", frontmatter)
        for command in ("cc", "cca", "cp"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("--team|--no-team", skill.split("\n---\n", 1)[0])
        for contract in (
            "source-read-only 실행, `/ccr`, `/cpr`",
            "`/cr --fix`, `/cc`, `/cca`, `/cp`",
            "implicit team",
            "core 3명을 기본",
            "Agent Team을 기본으로 선택",
            "변경 파일 2개 이하, 추가+삭제 80줄 이하",
            "파일 수로 균등 분할하지 않는다",
            "`ACTIVE`, 근거 있는 `N/A`, `UNKNOWN`",
            "Testing/Independent Verification",
            "Performance/Reliability/Observability/Operability",
            "UX/Accessibility",
            "Data/Migration",
            "Requirements/Product",
            "Release/Deployment/Rollback",
            "Domain/Framework",
            "shard mode와 Team 인원은 별개",
            "계산하지 않은 값",
            "SendMessage",
            "WCAG 2.2",
            "artifact provenance",
            "traces/metrics/logs",
        ):
            self.assertIn(contract, execution)

    def test_agent_team_environment_probe_is_exact_and_read_only(self) -> None:
        script = (
            ROOT
            / ".claude/skills/_git-atomic-core/scripts/agent_team_mode.py"
        )
        for raw, expected in ((None, False), ("0", False), ("true", False), ("1", True)):
            env = os.environ.copy()
            if raw is None:
                env.pop("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", None)
            else:
                env["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = raw
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertEqual(
                json.loads(proc.stdout)["enabled"],
                expected,
            )
            payload = json.loads(proc.stdout)
            self.assertEqual(
                payload["default_mode"],
                "team_first" if expected else "subagent_fallback",
            )
            self.assertEqual(
                payload["eligible_commands"],
                ["cr_read_only", "ccr", "cpr"],
            )
            self.assertEqual(
                payload["default_team_size"],
                {"cr_read_only": 3, "cpr": 3, "ccr": 3},
            )
            self.assertEqual(payload["trivial_downgrade"]["max_files"], 2)
            self.assertTrue(
                payload["trivial_downgrade"]["disabled_by_force_team"]
            )
            self.assertEqual(
                payload["conditional_specialists"],
                [
                    "testing_independent_verification",
                    "performance_reliability_observability",
                    "ux_accessibility",
                    "data_migration",
                    "requirements_product",
                    "release_deployment_rollback",
                    "domain_framework",
                ],
            )
            self.assertEqual(
                payload["testing_policy"],
                "required_for_any_non_documentation_behavior_change",
            )

    def test_every_command_supports_current_project_lock_clean(self) -> None:
        for command in ("ccr", "cc", "cr", "cca", "cpr", "cp"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            frontmatter = skill.split("\n---\n", 1)[0]
            self.assertIn("[clean", frontmatter)
            self.assertIn("lock-cleanup.md", skill)
        cleanup = (
            ROOT / ".claude/skills/_git-atomic-core/lock-cleanup.md"
        ).read_text(encoding="utf-8")
        self.assertIn("현재 worktree 잠금만", cleanup)
        self.assertIn("Diff snapshot은 삭제하지 않는다", cleanup)

    def test_every_command_resolves_core_path_before_running_anything(self) -> None:
        for command in ("ccr", "cc", "cr", "cca", "cpr", "cp"):
            skill_path = ROOT / f".claude/skills/{command}/SKILL.md"
            skill = skill_path.read_text(encoding="utf-8")
            body = skill.split("\n---\n", 1)[1]
            headings = [
                line for line in body.splitlines() if line.startswith("## ")
            ]
            self.assertEqual(
                headings[0],
                "## Skill 경로 확정 (필수 Preflight)",
                f"{command}: 경로 확정 Preflight가 본문 첫 섹션이 아니다",
            )
            self.assertIn("이 SKILL.md가 들어 있는 디렉터리의 절대경로", skill)
            self.assertIn("_git-atomic-core/scripts/guard.py", skill)
            self.assertIn("fail-closed", skill)

    def test_guard_launch_failures_are_fail_closed(self) -> None:
        for command in ("cc", "cr", "cca", "cpr", "cp"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("exit code 126", skill, command)
            self.assertIn("command not found", skill, command)
            self.assertIn("stale_candidate", skill, command)
            self.assertIn("--reclaim-stale", skill, command)
            self.assertIn("git_external_lock", skill, command)
            self.assertIn("recovery.remove_hint", skill, command)

    def test_stale_lock_contract_is_documented(self) -> None:
        safety = (
            ROOT / ".claude/skills/_git-atomic-core/safety-and-concurrency.md"
        ).read_text(encoding="utf-8")
        recovery = (
            ROOT / ".claude/skills/_git-atomic-core/recovery.md"
        ).read_text(encoding="utf-8")
        for text in (safety, recovery):
            self.assertIn("--reclaim-stale", text)
            self.assertIn("stale_candidate", text)
        self.assertIn("different_host", safety)
        self.assertIn("lock_not_stale", safety)
        self.assertIn("snapshot은 보존", recovery)

    def test_all_commands_load_learned_profile(self) -> None:
        for command in ("ccr", "cc", "cr", "cca", "cpr", "cp"):
            skill = (
                ROOT / f".claude/skills/{command}/SKILL.md"
            ).read_text(encoding="utf-8")
            self.assertIn(".commitforge/profile.md", skill)
            self.assertIn(".commitforge/profile.json", skill)

    def test_release_emergency_and_learn_execution_boundaries(self) -> None:
        cr = (ROOT / ".claude/skills/cr/SKILL.md").read_text(encoding="utf-8")
        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        modes = (
            ROOT / ".claude/skills/_git-atomic-core/extended-modes.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`release`, `emergency`, `learn`이면 `SOURCE_EDIT_ALLOWED=false`", cr)
        self.assertIn("Atomic Commit 계획이나 메시지 초안을 만들지 않는다", cr)
        self.assertIn("`--dry-run`인 경우", cca)
        self.assertIn("`emergency --diagnose`", cca)
        self.assertIn("`--preview`면 history 분석 결과만", cca)
        self.assertIn("release_version.py", cca)
        self.assertIn("release_version.py", cr)
        self.assertIn("로컬 annotated tag", modes)
        self.assertIn("remote push, GitHub Release, publish, deploy", modes)
        self.assertIn("`.commitforge/profile.json`", modes)

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
        self.assertIn("fail-closed로 중단한다", cr)
        self.assertIn("변경 스캔, reviewer, 테스트, fingerprint, `abort`", cr)
        self.assertIn("reason=guard_lock_conflict", cr)
        self.assertIn("현재 세션은 lock을 획득하지", cr)
        self.assertIn("lock_owner_snapshots", cr)
        self.assertIn("`abort` 성공 결과를", cr)
        self.assertIn("Guard의 `lock_age_seconds`만", cr)
        self.assertIn("`recovery.abort_argv`를 인자 단위 그대로", cr)
        self.assertIn("\n  - Edit\n", frontmatter)
        self.assertIn("\n  - Write\n", frontmatter)

    def test_skill_frontmatter_has_no_runtime_path_variables(self) -> None:
        for command in ("cc", "ccr", "cr", "cca", "cpr", "cp"):
            skill = (
                ROOT / f".claude/skills/{command}/SKILL.md"
            ).read_text(encoding="utf-8")
            frontmatter = skill.split("\n---\n", 1)[0]
            self.assertNotIn("${", frontmatter)
            self.assertIn(".claude/skills/_git-atomic-core", skill)
        for path in (ROOT / ".claude/skills").rglob("*.md"):
            self.assertNotIn("${", path.read_text(encoding="utf-8"))

    def test_validation_permissions_avoid_speculative_failure_messages(self) -> None:
        strategy = (
            ROOT / ".claude/skills/_git-atomic-core/validation-strategy.md"
        ).read_text(encoding="utf-8")
        for contract in (
            "package manager 전체를 wildcard 허용하지 않는다",
            "추측성 진행 문구를 출력하지 않는다",
            "내장 permission UI",
            "실제 거절·도구 부재·환경 실패가 발생한 뒤에만",
            "시도하지 않은 검증을 “시도함”으로 보고하지 않는다",
        ):
            self.assertIn(contract, strategy)

    def test_all_result_reports_include_elapsed_minutes(self) -> None:
        reporting = (
            ROOT / ".claude/skills/_git-atomic-core/reporting.md"
        ).read_text(encoding="utf-8")
        formats = (
            ROOT / ".claude/skills/_git-atomic-core/reporting-formats.md"
        ).read_text(encoding="utf-8")
        pr_workflow = (
            ROOT / ".claude/skills/_git-atomic-core/pull-request-workflow.md"
        ).read_text(encoding="utf-8")
        for contract in (
            "성공·실패·중단·부분 완료",
            "소요 시간: N.N분",
            "소요 시간: 0.1분 미만",
            "소요 시간: 측정 불가 (사유)",
            "lock_age_seconds",
        ):
            self.assertIn(contract, reporting)
        self.assertIn('"elapsed_minutes": 1.2', formats)
        self.assertIn("소요 시간(분)", pr_workflow)

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

    def test_installer_skill_registries_match_package(self) -> None:
        actual = tuple(
            path.name
            for path in sorted((ROOT / ".claude/skills").iterdir())
            if path.is_dir()
        )
        for registry_file in ("install.py", "uninstall.py"):
            registered = tuple(
                sorted(runpy.run_path(str(ROOT / registry_file))["SKILLS"])
            )
            self.assertEqual(actual, registered)

    def test_pull_request_commands_enforce_execution_boundary(self) -> None:
        cp = (ROOT / ".claude/skills/cp/SKILL.md").read_text(encoding="utf-8")
        cpr = (ROOT / ".claude/skills/cpr/SKILL.md").read_text(encoding="utf-8")
        workflow = (
            ROOT / ".claude/skills/_git-atomic-core/pull-request-workflow.md"
        ).read_text(encoding="utf-8")
        cp_frontmatter = cp.split("\n---\n", 1)[0]
        cpr_frontmatter = cpr.split("\n---\n", 1)[0]

        for skill in (cp, cpr):
            self.assertIn("pull-request-workflow.md", skill)
            self.assertIn("disable-model-invocation: true", skill)
        for forbidden in ("Bash(git add ", "Bash(git commit ", "\n  - Edit\n"):
            self.assertNotIn(forbidden, cp_frontmatter)
        self.assertIn("Bash(git push *)", cp_frontmatter)
        self.assertIn("Bash(gh pr create *)", cp_frontmatter)
        for forbidden in (
            "\n  - Write\n",
            "\n  - Edit\n",
            "Bash(git push ",
            "Bash(gh pr create ",
        ):
            self.assertNotIn(forbidden, cpr_frontmatter)
        for contract in (
            "이미 열린 PR",
            "tracking ref",
            "force",
            "source/index/HEAD",
        ):
            self.assertIn(contract, workflow)

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
