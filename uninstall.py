#!/usr/bin/env python3
"""Remove only files installed by CommitForge, preserving a backup."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import sys


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


def is_commitforge_lifecycle_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = handler.get("command")
    return (
        handler.get("type") == "command"
        and isinstance(command, str)
        and "_git-atomic-core" in command
        and "session_lifecycle.py" in command
    )


def remove_lifecycle_hooks(
    claude_dir: Path,
    backup_root: Path,
    *,
    global_scope: bool,
    dry_run: bool,
) -> None:
    settings_name = "settings.json" if global_scope else "settings.local.json"
    settings_path = claude_dir / settings_name
    if not settings_path.exists():
        return
    if settings_path.is_symlink():
        raise RuntimeError(f"Claude 설정 심볼릭 링크는 자동 수정하지 않습니다: {settings_path}")
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise RuntimeError(f"Claude 설정은 JSON object여야 합니다: {settings_path}")
    hooks = settings.get("hooks")
    changed = False
    if isinstance(hooks, dict):
        for event in ("SessionStart", "SessionEnd", "Stop", "StopFailure"):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            kept_groups = []
            for group in groups:
                if not isinstance(group, dict):
                    kept_groups.append(group)
                    continue
                handlers = group.get("hooks")
                if not isinstance(handlers, list):
                    kept_groups.append(group)
                    continue
                kept_handlers = [
                    handler
                    for handler in handlers
                    if not is_commitforge_lifecycle_handler(handler)
                ]
                changed = changed or len(kept_handlers) != len(handlers)
                if kept_handlers:
                    updated = dict(group)
                    updated["hooks"] = kept_handlers
                    kept_groups.append(updated)
            if kept_groups:
                hooks[event] = kept_groups
            else:
                hooks.pop(event, None)
        if not hooks:
            settings.pop("hooks", None)
    if not changed:
        return
    backup = backup_root / settings_name
    if dry_run:
        print(f"[dry-run] backup/remove CommitForge hooks {settings_path} -> {backup}")
        return
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings_path, backup)
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
    backup_root = claude_dir / ".commitforge-uninstall-backups" / timestamp

    remove_lifecycle_hooks(
        claude_dir,
        backup_root,
        global_scope=args.scope == "global",
        dry_run=args.dry_run,
    )

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
