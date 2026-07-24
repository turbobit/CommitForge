#!/usr/bin/env python3
"""Static package verifier."""

from __future__ import annotations

from pathlib import Path
import json
import re
import runpy
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REQUIRED = [
    ".gitattributes",
    ".claude/skills/cc/SKILL.md",
    ".claude/skills/ccr/SKILL.md",
    ".claude/skills/cca/SKILL.md",
    ".claude/skills/cr/SKILL.md",
    ".claude/skills/_git-atomic-core/extended-modes.md",
    ".claude/skills/_git-atomic-core/deep-review-protocol.md",
    ".claude/skills/_git-atomic-core/language-api-pitfalls.md",
    ".claude/skills/_git-atomic-core/conditional-reviewers.md",
    ".claude/skills/_git-atomic-core/review-execution.md",
    ".claude/skills/_git-atomic-core/period-review-modes.md",
    ".claude/skills/_git-atomic-core/review-policy.md",
    ".claude/skills/_git-atomic-core/reporting-formats.md",
    ".claude/skills/_git-atomic-core/baseline-and-suppressions.md",
    ".claude/skills/_git-atomic-core/large-diff-review.md",
    ".claude/skills/_git-atomic-core/scripts/guard.py",
    ".claude/skills/_git-atomic-core/scripts/guard.sh",
    ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py",
    ".claude/skills/_git-atomic-core/scripts/report_validator.py",
    ".claude/skills/_git-atomic-core/scripts/baseline.py",
    ".claude/skills/_git-atomic-core/scripts/period_range.py",
    ".claude/agents/cca-git-reviewer.md",
    ".claude/agents/cca-correctness-reviewer.md",
    ".claude/agents/cca-security-reviewer.md",
    ".claude/agents/cca-performance-reviewer.md",
    ".claude/agents/cca-testing-reviewer.md",
    ".claude/agents/cca-line-reviewer.md",
    ".claude/agents/cca-architecture-reviewer.md",
    ".claude/agents/cca-language-api-reviewer.md",
    ".claude/agents/cca-ux-accessibility-reviewer.md",
    ".claude/agents/cca-observability-reviewer.md",
    ".claude/agents/cca-quality-reviewer.md",
    ".claude/agents/cca-data-migration-reviewer.md",
    ".claude/agents/cca-dependency-supply-chain-reviewer.md",
    ".claude/agents/cca-reliability-recovery-reviewer.md",
    ".claude/agents/cca-privacy-governance-reviewer.md",
    ".claude/agents/cca-requirements-product-reviewer.md",
    ".github/workflows/verify.yml",
    ".github/dependabot.yml",
    "evals/conditional-reviewer-triggers.json",
    "evals/live-review-scenarios.json",
    "evals/run_evals.py",
    "examples/review.yml",
    "examples/review-baseline.json",
    "release.py",
]


def frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise ValueError("YAML frontmatter 시작 누락")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("YAML frontmatter 종료 누락")
    return text[4:end]


def main() -> None:
    errors = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"필수 파일 누락: {rel}")

    for command in ("cc", "ccr", "cr", "cca"):
        path = ROOT / f".claude/skills/{command}/SKILL.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            fm = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        for field in ("description:", "disable-model-invocation: true", "argument-hint:"):
            if field not in fm:
                errors.append(f"{path}: frontmatter 필드 누락 {field}")
        if len(text.splitlines()) > 500:
            errors.append(f"{path}: SKILL.md 500줄 초과")

    valid_colors = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
    for path in sorted((ROOT / ".claude/agents").glob("cca-*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            fm = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        for field in ("name:", "description:", "tools:", "disallowedTools:", "model:"):
            if field not in fm:
                errors.append(f"{path}: frontmatter 필드 누락 {field}")
        color_match = re.search(r"^color:\s*([a-z]+)\s*$", fm, re.MULTILINE)
        if not color_match:
            errors.append(f"{path}: color 누락 또는 형식 오류")
        elif color_match.group(1) not in valid_colors:
            errors.append(f"{path}: 지원하지 않는 color {color_match.group(1)}")
        if re.search(r"^\s*-\s*Bash(?:\(|\s|$)", fm, re.MULTILINE):
            errors.append(f"{path}: reviewer에 Bash 도구가 허용됨")

    readme = ROOT / "README.md"
    if readme.exists() and not readme.read_text(encoding="utf-8").startswith("# CommitForge"):
        errors.append("README.md: CommitForge 제목 누락")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest_path = ROOT / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("name") != "CommitForge":
            errors.append("MANIFEST.json: name이 CommitForge가 아님")
        if manifest.get("version") != version:
            errors.append("MANIFEST.json: VERSION과 version 불일치")
        if manifest.get("reproducible") is not True:
            errors.append("MANIFEST.json: reproducible 표시 누락")

    cca_path = ROOT / ".claude/skills/cca/SKILL.md"
    modes_path = ROOT / ".claude/skills/_git-atomic-core/extended-modes.md"
    if cca_path.exists() and modes_path.exists():
        cca_text = cca_path.read_text(encoding="utf-8")
        modes_text = modes_path.read_text(encoding="utf-8")
        for mode in ("today", "3days", "weekly", "release", "emergency", "learn"):
            if f"`{mode}`" not in cca_text:
                errors.append(f"cca/SKILL.md: {mode} 모드 분기 누락")
            if f"## " not in modes_text or f"`{mode}`" not in modes_text:
                errors.append(f"extended-modes.md: {mode} 모드 설명 누락")

    period_modes = ROOT / ".claude/skills/_git-atomic-core/period-review-modes.md"
    if period_modes.exists():
        period_text = period_modes.read_text(encoding="utf-8")
        for skill_path in (ROOT / ".claude/skills/cr/SKILL.md", cca_path):
            if skill_path.exists() and "period-review-modes.md" not in skill_path.read_text(
                encoding="utf-8"
            ):
                errors.append(f"{skill_path}: today·3days·weekly 공통 규칙 연결 누락")
        for contract in (
            "최근 24시간이 아니다",
            "정확한 72시간 rolling window가 아니다",
            "최근 7일이 아니다",
            "period-interaction",
            "Atomic Commit 계획·메시지·staging·commit·push는 항상 금지",
        ):
            if contract not in period_text:
                errors.append(f"period-review-modes.md: 계약 누락 {contract}")

    if cca_path.exists():
        cca_text = cca_path.read_text(encoding="utf-8")
        deep_reviewers = (
            "cca-line-reviewer",
            "cca-architecture-reviewer",
            "cca-language-api-reviewer",
            "cca-ux-accessibility-reviewer",
            "cca-observability-reviewer",
            "cca-quality-reviewer",
        )
        for reviewer in deep_reviewers:
            if reviewer not in cca_text:
                errors.append(f"cca/SKILL.md: {reviewer} 연결 누락")
        for reference in ("deep-review-protocol.md", "language-api-pitfalls.md"):
            if reference not in cca_text:
                errors.append(f"cca/SKILL.md: {reference} 연결 누락")

    cr_path = ROOT / ".claude/skills/cr/SKILL.md"
    if cr_path.exists():
        cr_text = cr_path.read_text(encoding="utf-8")
        cr_frontmatter = frontmatter(cr_text)
        for reviewer in (
            "cca-line-reviewer",
            "cca-architecture-reviewer",
            "cca-language-api-reviewer",
            "cca-ux-accessibility-reviewer",
            "cca-observability-reviewer",
            "cca-quality-reviewer",
        ):
            if reviewer not in cr_text:
                errors.append(f"cr/SKILL.md: {reviewer} 연결 누락")
        for forbidden in ("Bash(git add ", "Bash(git commit "):
            if forbidden in cr_frontmatter:
                errors.append(f"cr/SKILL.md: 금지 도구 허용 {forbidden.strip()}")
        if "cca-git-reviewer" in cr_text:
            errors.append("cr/SKILL.md: Atomic Commit 전용 git reviewer 연결")
        if "Atomic Commit 계획이나 메시지 후보를 만들지 않는다" not in cr_text:
            errors.append("cr/SKILL.md: review-only 출력 경계 누락")
        if "--review-only" not in cr_text or "verify-review" not in cr_text:
            errors.append("cr/SKILL.md: deterministic review invariant 연결 누락")
        if "[--fix]" not in cr_frontmatter or "[--no-fix]" in cr_frontmatter:
            errors.append("cr/SKILL.md: 기본 read-only/--fix opt-in 인자 계약 오류")
        if "기본은 모든 소스 수정을 금지하는 읽기 전용 리뷰" not in cr_text:
            errors.append("cr/SKILL.md: 기본 read-only 정책 누락")
        for contract in (
            "SOURCE_EDIT_ALLOWED=false",
            "--source-read-only",
            "cr_edit_gate.py",
        ):
            if contract not in cr_text:
                errors.append(f"cr/SKILL.md: source read-only 강제 계약 누락 {contract}")
        for required in ("\n  - Edit\n", "\n  - Write\n"):
            if required not in cr_frontmatter:
                errors.append(
                    f"cr/SKILL.md: --fix 편집 도구 사전 승인 누락 {required.strip()}"
                )

    conditional_path = ROOT / ".claude/skills/_git-atomic-core/conditional-reviewers.md"
    conditional_reviewers = (
        "cca-data-migration-reviewer",
        "cca-dependency-supply-chain-reviewer",
        "cca-reliability-recovery-reviewer",
        "cca-privacy-governance-reviewer",
        "cca-requirements-product-reviewer",
    )
    if conditional_path.exists():
        conditional_text = conditional_path.read_text(encoding="utf-8")
        for reviewer in conditional_reviewers:
            if reviewer not in conditional_text:
                errors.append(f"conditional-reviewers.md: {reviewer} trigger 누락")
            if cca_path.exists() and reviewer not in cca_text:
                errors.append(f"cca/SKILL.md: {reviewer} 조건부 연결 누락")
            if cr_path.exists() and reviewer not in cr_text:
                errors.append(f"cr/SKILL.md: {reviewer} 조건부 연결 누락")

    execution_path = ROOT / ".claude/skills/_git-atomic-core/review-execution.md"
    if execution_path.exists():
        execution_text = execution_path.read_text(encoding="utf-8")
        for field in (
            '"id"',
            '"reviewer"',
            '"fingerprint"',
            '"severity"',
            '"status"',
            '"evidence"',
            '"blocking"',
        ):
            if field not in execution_text:
                errors.append(f"review-execution.md: finding schema {field} 누락")
        for policy in (
            "기본 동시 실행 목표는 6개",
            "최대 8개",
            "3~4개로 축소",
            "UNKNOWN",
            "fallback",
        ):
            if policy not in execution_text:
                errors.append(f"review-execution.md: 실행 정책 {policy} 누락")

    actual_agents = tuple(
        path.name for path in sorted((ROOT / ".claude/agents").glob("cca-*.md"))
    )
    for registry_file in ("install.py", "uninstall.py"):
        registry = tuple(runpy.run_path(str(ROOT / registry_file))["AGENTS"])
        if tuple(sorted(registry)) != actual_agents:
            errors.append(f"{registry_file}: AGENTS 목록이 실제 agent 파일과 불일치")

    guard = ROOT / ".claude/skills/_git-atomic-core/scripts/guard.py"
    if guard.exists():
        proc = subprocess.run(
            [sys.executable, str(guard), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"guard.py --help 실패: {proc.stderr}")
        if "verify-review" not in proc.stdout:
            errors.append("guard.py: verify-review command 누락")
        if "audit-snapshot" not in proc.stdout:
            errors.append("guard.py: audit-snapshot command 누락")

    for skill_path in (cr_path, cca_path):
        if not skill_path.exists():
            continue
        skill_text = skill_path.read_text(encoding="utf-8")
        for reference in (
            "review-policy.md",
            "reporting-formats.md",
            "baseline-and-suppressions.md",
            "large-diff-review.md",
        ):
            if reference not in skill_text:
                errors.append(f"{skill_path}: {reference} 연결 누락")

    workflow = ROOT / ".github/workflows/verify.yml"
    if workflow.exists():
        workflow_text = workflow.read_text(encoding="utf-8")
        if re.search(r"uses:\s*actions/(checkout|setup-python)@v\d+", workflow_text):
            errors.append("verify.yml: GitHub Action이 full SHA로 고정되지 않음")
        for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
            if runner not in workflow_text:
                errors.append(f"verify.yml: {runner} matrix 누락")
        if 'PYTHONUTF8: "1"' not in workflow_text:
            errors.append("verify.yml: Windows UTF-8 출력 설정 누락")

    attributes = ROOT / ".gitattributes"
    if attributes.exists() and "* text=auto eol=lf" not in attributes.read_text(
        encoding="utf-8"
    ):
        errors.append(".gitattributes: LF checkout 정책 누락")

    eval_runner = ROOT / "evals/run_evals.py"
    if eval_runner.exists():
        proc = subprocess.run(
            [sys.executable, str(eval_runner), "--check"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"live eval contract 실패: {proc.stderr or proc.stdout}")

    release = ROOT / "release.py"
    if release.exists() and manifest_path.exists():
        proc = subprocess.run(
            [sys.executable, str(release), "--check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"release.py --check 실패: {proc.stderr or proc.stdout}")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "required_files": len(REQUIRED)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
