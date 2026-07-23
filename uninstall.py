#!/usr/bin/env python3
"""Remove only files installed by this package, preserving a backup."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import shutil
import sys


SKILLS = ("cc", "ccr", "cca", "_git-atomic-core")
AGENTS = (
    "cca-git-reviewer.md",
    "cca-correctness-reviewer.md",
    "cca-security-reviewer.md",
    "cca-performance-reviewer.md",
    "cca-testing-reviewer.md",
)


def backup_and_remove(path: Path, backup: Path, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise RuntimeError(f"심볼릭 링크는 자동 제거하지 않습니다: {path}")
    if dry_run:
        print(f"[dry-run] backup/remove {path} -> {backup}")
        return
    backup.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        shutil.copytree(path, backup)
        shutil.rmtree(path)
    else:
        shutil.copy2(path, backup)
        path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("project", "global"), default="project")
    parser.add_argument("--target")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.scope == "global":
        claude_dir = Path.home() / ".claude"
    else:
        claude_dir = Path(args.target or Path.cwd()).expanduser().resolve() / ".claude"

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = claude_dir / ".cca-uninstall-backups" / timestamp

    for name in SKILLS:
        backup_and_remove(
            claude_dir / "skills" / name,
            backup_root / "skills" / name,
            args.dry_run,
        )
    for name in AGENTS:
        backup_and_remove(
            claude_dir / "agents" / name,
            backup_root / "agents" / name,
            args.dry_run,
        )

    print(f"제거 범위: {args.scope}")
    print(f"대상: {claude_dir}")
    print(f"제거 전 백업: {backup_root}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"제거 실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
