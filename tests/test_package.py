from __future__ import annotations

import json
from pathlib import Path
import os
import re
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

    def test_ci_matrix_has_no_duplicate_primary_environment(self) -> None:
        workflow = (ROOT / ".github/workflows/verify.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(workflow.count("jobs:\n  verify:"), 1)
        self.assertEqual(workflow.count("\n  portability:"), 1)
        self.assertIn("needs: verify", workflow)
        self.assertIn("cancel-in-progress: true", workflow)
        self.assertEqual(workflow.count('python-version: "3.13"'), 1)
        self.assertEqual(workflow.count("Check live eval contracts"), 0)
        self.assertEqual(workflow.count("persist-credentials: false"), 2)
        self.assertIn("python -m compileall", workflow)

        dependabot = (ROOT / ".github/dependabot.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("open-pull-requests-limit: 5", dependabot)
        self.assertIn("github-actions:", dependabot)

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
        for command in ("cr", "ccr", "cpr", "cca"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            frontmatter = skill.split("\n---\n", 1)[0]
            self.assertIn("--team|--no-team", frontmatter)
            self.assertIn("agent_team_mode.py", skill)
            self.assertIn("Agent", frontmatter)
        for command in ("cc", "cf", "cfr", "cp"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("--team|--no-team", skill.split("\n---\n", 1)[0])
        for contract in (
            "source-read-only 실행, `/ccr`, `/cpr`와 `/cca`",
            "`/cr --fix`, `/cc`, `/cp`",
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
            "Team 리뷰 → 집계·종료 → lead 수정",
        ):
            self.assertIn(contract, execution)

        cca = (ROOT / ".claude/skills/cca/SKILL.md").read_text(encoding="utf-8")
        for contract in (
            "종료한 뒤에만 Step 4의 lead 수정으로 넘어간다",
            "이전 reviewer 상태를 모두 무효화한다",
            "새 fingerprint의 전체 diff",
            "재리뷰한다",
            "새 read-only Team",
            "lead 수정",
            "graceful-stop.md",
        ):
            self.assertIn(contract, cca)

        graceful = (
            ROOT / ".claude/skills/_git-atomic-core/graceful-stop.md"
        ).read_text(encoding="utf-8")
        for contract in (
            "GRACEFUL_STOP_REQUESTED=true",
            "리뷰 반복 <현재>/<--iterations 상한> 시작",
            "모든 재리뷰를 시작할 때",
            "새 수정·Team·검증·commit을 시작하지 않는다",
            "Guard `abort`",
            "snapshot을 보존",
            "`UNKNOWN`",
        ):
            self.assertIn(contract, graceful)

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
        for command in ("ccr", "cc", "ccf", "cf", "cfr", "cr", "cca", "cpr", "cp"):
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
        for command in ("ccr", "cc", "cf", "cfr", "cr", "cca", "cpr", "cp"):
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

    def test_guard_uses_claude_lifecycle_session_identity(self) -> None:
        for command in ("ccr", "cc", "cf", "cfr", "cr", "cca", "cpr", "cp"):
            skill = (ROOT / f".claude/skills/{command}/SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("COMMITFORGE_SESSION_ID", skill)
            self.assertNotIn("<current-session-id>", skill)
        safety = (
            ROOT / ".claude/skills/_git-atomic-core/safety-and-concurrency.md"
        ).read_text(encoding="utf-8")
        for contract in (
            "SessionStart",
            "`Stop`·`StopFailure`에서는 잠금을 유지",
            "`SessionEnd`에서만",
            "수동·자동 `/compact`",
            "Diff snapshot",
        ):
            self.assertIn(contract, safety)

    def test_guard_launch_failures_are_fail_closed(self) -> None:
        for command in ("cc", "cf", "cfr", "cr", "cca", "cpr", "cp"):
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
        for command in ("ccr", "cc", "cf", "cfr", "cr", "cca", "cpr", "cp"):
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
        for command in ("cc", "ccr", "cf", "cfr", "cr", "cca", "cpr", "cp"):
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

    def test_fast_commit_commands_enforce_execution_boundary(self) -> None:
        cf = (ROOT / ".claude/skills/cf/SKILL.md").read_text(encoding="utf-8")
        cfr = (ROOT / ".claude/skills/cfr/SKILL.md").read_text(encoding="utf-8")
        rules = (
            ROOT / ".claude/skills/_git-atomic-core/fast-commit-rules.md"
        ).read_text(encoding="utf-8")
        cf_frontmatter = cf.split("\n---\n", 1)[0]
        cfr_frontmatter = cfr.split("\n---\n", 1)[0]

        for skill in (cf, cfr):
            self.assertIn("fast-commit-rules.md", skill)
            self.assertIn("disable-model-invocation: true", skill)

        self.assertIn("Bash(git add *)", cf_frontmatter)
        self.assertIn("Bash(git commit *)", cf_frontmatter)
        for forbidden in (
            "\n  - Edit\n",
            "\n  - Write\n",
            "Bash(git push ",
            "Bash(git commit --amend",
        ):
            self.assertNotIn(forbidden, cf_frontmatter)

        for forbidden in (
            "\n  - Edit\n",
            "\n  - Write\n",
            "Bash(git add ",
            "Bash(git commit ",
            "Bash(git apply ",
            "Bash(git restore ",
            "Bash(git push ",
        ):
            self.assertNotIn(forbidden, cfr_frontmatter)
        self.assertIn("실제 staging과 commit은 수행하지 않는다", cfr)

    def test_fast_commit_is_documented_as_non_atomic(self) -> None:
        rules = (
            ROOT / ".claude/skills/_git-atomic-core/fast-commit-rules.md"
        ).read_text(encoding="utf-8")
        reporting = (
            ROOT / ".claude/skills/_git-atomic-core/reporting.md"
        ).read_text(encoding="utf-8")
        cf = (ROOT / ".claude/skills/cf/SKILL.md").read_text(encoding="utf-8")
        cfr = (ROOT / ".claude/skills/cfr/SKILL.md").read_text(encoding="utf-8")

        for contract in (
            "Atomic Commit이 아니다",
            "대표 type",
            "feat > fix > perf > refactor > test > docs > build/ci > style > chore",
            "차단 스캔",
            "merge conflict marker",
        ):
            self.assertIn(contract, rules)
        for text in (cf, cfr):
            self.assertIn("이 커밋은 Atomic Commit이 아니다", text)
            self.assertIn("`/cc`", text)
        self.assertIn("## `/cf`", reporting)
        self.assertIn("## `/cfr`", reporting)

    def test_ccf_is_cc_without_hunk_splitting(self) -> None:
        cc = (ROOT / ".claude/skills/cc/SKILL.md").read_text(encoding="utf-8")
        ccf = (ROOT / ".claude/skills/ccf/SKILL.md").read_text(encoding="utf-8")
        cc_frontmatter = cc.split("\n---\n", 1)[0]
        ccf_frontmatter = ccf.split("\n---\n", 1)[0]

        self.assertIn("disable-model-invocation: true", ccf)
        self.assertIn("Bash(git add *)", ccf_frontmatter)
        self.assertIn("Bash(git commit *)", ccf_frontmatter)
        for forbidden in (
            "\n  - Edit\n",
            "\n  - Write\n",
            "Bash(git push ",
            "Bash(git rebase ",
            "Bash(git reset ",
            # Selective patches are the hunk path `/ccf` deliberately drops.
            "Bash(git apply ",
        ):
            self.assertNotIn(forbidden, ccf_frontmatter)

        # Apart from patch application, `/ccf` is pre-approved for exactly
        # what `/cc` is, so it cannot silently lose a `/cc` safety step.
        def tools(frontmatter: str) -> set[str]:
            block = frontmatter.split("allowed-tools:\n", 1)[1]
            return {
                line.strip()[2:]
                for line in block.splitlines()
                if line.startswith("  - ")
            }

        self.assertEqual(
            tools(cc_frontmatter) - {"Bash(git apply --cached *)", "Bash(git apply --check *)"},
            tools(ccf_frontmatter),
        )

        # The full `/cc` Guard contract is kept.
        for contract in (
            'guard.sh" begin',
            'guard.sh" fingerprint',
            'guard.sh" finish',
            'guard.sh" abort',
            "lock-cleanup.md",
            "atomic-commit-rules.md",
            "staging-strategy.md",
            "safety-and-concurrency.md",
            "선행 커밋 의존성",
            "`--no-verify`가 없으면",
        ):
            self.assertIn(contract, ccf, contract)
        self.assertNotIn('guard.sh" snapshot', ccf)
        self.assertNotIn("release-snapshot", ccf)
        self.assertNotIn("fast-commit-rules.md", ccf)

        # The only difference: no hunk-level splitting.
        for contract in (
            "의미별로 분리",
            "여러 개의 commit",
            "hunk 단위로 분리하지 않는다",
            "파일 단위로만 분리한다",
            "가장 지배적인 의도",
            "완전한 Atomic Commit이 아닐 수 있다",
        ):
            self.assertIn(contract, ccf, contract)

        for contract in ("secret", "merge conflict marker", "중단"):
            self.assertIn(contract, ccf, contract)

    def test_ccf_contract_is_documented_in_core(self) -> None:
        rules = (
            ROOT / ".claude/skills/_git-atomic-core/fast-commit-rules.md"
        ).read_text(encoding="utf-8")
        core_readme = (
            ROOT / ".claude/skills/_git-atomic-core/README.md"
        ).read_text(encoding="utf-8")
        reporting = (
            ROOT / ".claude/skills/_git-atomic-core/reporting.md"
        ).read_text(encoding="utf-8")
        recovery = (
            ROOT / ".claude/skills/_git-atomic-core/recovery.md"
        ).read_text(encoding="utf-8")
        staging = (
            ROOT / ".claude/skills/_git-atomic-core/staging-strategy.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## `/ccf`", reporting)
        self.assertIn("`/cc` 형식을 그대로 따르고", reporting)
        self.assertIn("`/ccf`", core_readme)
        self.assertIn("`/ccf`는 이 절", staging)
        # Fast Commit rules no longer govern `/ccf`.
        self.assertIn("`/ccf`는 이 문서를 따르지 않는다", rules)
        self.assertNotIn("## 8. `/ccf`", rules)
        # Lock-free snapshots left by older `/ccf` stay recoverable.
        self.assertIn("1.20.0 이하 `/ccf`", recovery)
        self.assertIn("release-snapshot", recovery)

    def test_fast_commit_verification_policy_is_explicit(self) -> None:
        cf = (ROOT / ".claude/skills/cf/SKILL.md").read_text(encoding="utf-8")
        cf_frontmatter = cf.split("\n---\n", 1)[0]
        rules = (
            ROOT / ".claude/skills/_git-atomic-core/fast-commit-rules.md"
        ).read_text(encoding="utf-8")

        self.assertIn("--verify", cf_frontmatter)
        self.assertIn("--no-verify", cf_frontmatter)
        for contract in (
            "기본적으로 프로젝트 검증을 실행하지 않는다",
            "commit hook은 기본적으로 존중한다",
            "`--verify`",
            "`--no-verify`",
        ):
            self.assertIn(contract, cf)
        self.assertIn("어떤 인자로도 생략할 수 없다", rules)

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
            "cca-release-deployment-reviewer",
            "cca-requirements-product-reviewer",
        )
        for reviewer in reviewers:
            self.assertIn(reviewer, conditional)
            self.assertIn(reviewer, cr)
            self.assertIn(reviewer, cca)
            self.assertTrue((ROOT / f".claude/agents/{reviewer}.md").is_file())
        self.assertIn("명시적 기준이 없으면", conditional)
        self.assertIn("비활성화 근거", conditional)

    def test_every_rule_in_the_trigger_script_has_an_agent_and_a_table_row(self) -> None:
        # The script, the activation table and the agent directory are three
        # copies of one list. A rule with no agent activates a reviewer that
        # cannot run; an agent with no rule never activates from a path.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "reviewer_triggers",
            ROOT / ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        conditional = (
            ROOT / ".claude/skills/_git-atomic-core/conditional-reviewers.md"
        ).read_text(encoding="utf-8")
        for reviewer in module.RULES:
            self.assertTrue(
                (ROOT / f".claude/agents/{reviewer}.md").is_file(),
                f"{reviewer} has a trigger rule but no agent definition",
            )
            self.assertIn(reviewer, conditional)

    def test_performance_reviewer_covers_exhaustion_and_responsiveness(self) -> None:
        # A leak, a pegged core and a frozen main thread are not "slow code":
        # they are unbounded growth and lost responsiveness, and a checklist
        # built from complexity and I/O alone never asks about them.
        performance = (
            ROOT / ".claude/agents/cca-performance-reviewer.md"
        ).read_text(encoding="utf-8")
        for topic in (
            "메모리 누수",
            "cleanup",
            "unbounded",
            "busy",
            "timeout",
            "main thread",
            "long task",
            "hydration",
        ):
            self.assertIn(topic, performance)

    def test_every_reviewer_separates_theoretical_risk_from_real_risk(self) -> None:
        # `confidence` only measures whether a claim holds in the code, so a
        # theoretical path traced end to end still scores 10 and sails past the
        # threshold. Reachability is the second axis that catches it, and it
        # only works if every reviewer carries it -- one agent without the
        # section is the hole the noise comes back through.
        agents = sorted((ROOT / ".claude/agents").glob("cca-*.md"))
        self.assertTrue(agents)
        for path in agents:
            body = path.read_text(encoding="utf-8")
            for section in ("도달성", "보고 제외", "판정 precedent"):
                # Some reviewers number their sections ("## 5. 도달성"), so the
                # heading is matched by name rather than by exact string.
                self.assertRegex(
                    body,
                    rf"(?m)^## (?:\d+\. )?{re.escape(section)}$",
                    f"{path.name} is missing the {section} section",
                )
            for grade in ("`실재`", "`조건부`", "`이론`"):
                self.assertIn(
                    grade,
                    body,
                    f"{path.name} does not use the {grade} reachability grade",
                )
            # Pointing at the shared definition is what keeps seventeen
            # reviewers on one ruler instead of seventeen private ones.
            self.assertIn("§3.2", body, f"{path.name} does not cite the shared axis")

    def test_reachability_axis_is_defined_and_enforced_in_the_core(self) -> None:
        core = ROOT / ".claude/skills/_git-atomic-core"
        execution = (core / "review-execution.md").read_text(encoding="utf-8")
        gates = (core / "review-gates.md").read_text(encoding="utf-8")
        policy = (core / "review-policy.md").read_text(encoding="utf-8")

        self.assertIn("## 3.2 도달성 등급 기준", execution)
        # The two questions must stay split: merged, confidence in whether a
        # claim holds leaks into whether it actually happens.
        for marker in ("### 두 질문", "성립불가", "확인불가"):
            self.assertIn(marker, execution)
        # A downgrade that also lowers severity would erase the finding from
        # the report, which is the opposite of what the axis is for.
        self.assertIn("`blocking`을 `false`로 바꾼다", execution)
        self.assertIn("심각도를 낮추지 않는다", execution)
        # Irreversible damage keeps its teeth. The list lives in review-policy
        # and must not be forked into a second copy here.
        self.assertIn("되돌릴 수 없는 피해는 이 강등에서 제외한다", execution)
        self.assertIn("되돌릴 수", policy)

        self.assertIn("도달성", gates)
        self.assertIn("차단은 심각도 × 도달성이다", gates)


if __name__ == "__main__":
    unittest.main()
