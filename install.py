#!/usr/bin/env python3
"""Install CommitForge skills at project or personal scope with backups."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import shutil
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_CLAUDE = PACKAGE_ROOT / ".claude"
SKILLS = ("cc", "ccr", "cr", "cca", "cp", "cpr", "_git-atomic-core")
AGENTS = (
    "cca-git-reviewer.md",
    "cca-correctness-reviewer.md",
    "cca-security-reviewer.md",
    "cca-performance-reviewer.md",
    "cca-testing-reviewer.md",
    "cca-line-reviewer.md",
    "cca-architecture-reviewer.md",
    "cca-language-api-reviewer.md",
    "cca-ux-accessibility-reviewer.md",
    "cca-observability-reviewer.md",
    "cca-quality-reviewer.md",
    "cca-data-migration-reviewer.md",
    "cca-dependency-supply-chain-reviewer.md",
    "cca-reliability-recovery-reviewer.md",
    "cca-privacy-governance-reviewer.md",
    "cca-requirements-product-reviewer.md",
)


def copy_with_backup(src: Path, dst: Path, backup: Path, dry_run: bool) -> None:
    if dst.is_symlink():
        raise RuntimeError(f"심볼릭 링크 대상은 자동 교체하지 않습니다: {dst}")
    if dst.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            print(f"[dry-run] backup {dst} -> {backup}")
        else:
            if dst.is_dir():
                shutil.copytree(dst, backup)
                shutil.rmtree(dst)
            else:
                shutil.copy2(dst, backup)
                dst.unlink()
    if dry_run:
        print(f"[dry-run] install {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("project", "global"), default="project")
    parser.add_argument(
        "--target",
        help="project root for project scope; ignored for global scope",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.scope == "global":
        claude_dir = Path.home() / ".claude"
    else:
        project = Path(args.target or Path.cwd()).expanduser().resolve()
        claude_dir = project / ".claude"

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = claude_dir / ".commitforge-backups" / timestamp

    for name in SKILLS:
        copy_with_backup(
            SOURCE_CLAUDE / "skills" / name,
            claude_dir / "skills" / name,
            backup_root / "skills" / name,
            args.dry_run,
        )

    for name in AGENTS:
        copy_with_backup(
            SOURCE_CLAUDE / "agents" / name,
            claude_dir / "agents" / name,
            backup_root / "agents" / name,
            args.dry_run,
        )

    print()
    print(f"설치 범위: {args.scope}")
    print(f"설치 위치: {claude_dir}")
    if backup_root.exists() or args.dry_run:
        print(f"기존 파일 백업: {backup_root}")
    print("CommitForge 설치 완료")
    print("사용 명령: /ccr, /cc, /cr, /cca, /cpr, /cp")
    print("Pull Request: /cpr 미리보기, /cp 실제 생성")
    print("기간 리뷰: /cr today, /cr 3days, /cr weekly")
    print(
        "확장 모드: /cca today, /cca 3days, /cca weekly, /cca release, "
        "/cca emergency, /cca learn"
    )
    print("새 .claude/agents 디렉터리를 처음 만든 실행 중 세션에서는 Claude Code 재시작을 권장합니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"설치 실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
