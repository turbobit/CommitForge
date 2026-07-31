#!/usr/bin/env python3
"""Remove only files installed by CommitForge, preserving a backup."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
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
POWERSHELL_ENCODED_PREFIX = (
    "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand "
)


def lifecycle_script_from_command(command: str) -> Path | None:
    """Return the script target only for a generated two-argument hook."""
    if command.startswith(POWERSHELL_ENCODED_PREFIX):
        try:
            encoded = command.removeprefix(POWERSHELL_ENCODED_PREFIX)
            command = base64.b64decode(encoded, validate=True).decode("utf-16-le")
        except (UnicodeError, ValueError):
            return None
        match = re.fullmatch(
            r"& '((?:[^']|'')*)' '((?:[^']|'')*)'\r?\n"
            r"exit \$LASTEXITCODE\r?\n?",
            command,
        )
        if match is None:
            return None
        return Path(match.group(2).replace("''", "'")).expanduser().resolve()

    try:
        argv = shlex.split(command, posix=sys.platform != "win32")
    except ValueError:
        return None
    if len(argv) != 2:
        return None
    script = argv[1]
    if len(script) >= 2 and script[0] == script[-1] and script[0] in "'\"":
        script = script[1:-1]
    return Path(script).expanduser().resolve()


def is_commitforge_lifecycle_handler(
    handler: object,
    lifecycle_path: Path,
) -> bool:
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    command = handler.get("command")
    if not isinstance(command, str):
        return False
    target = lifecycle_script_from_command(command)
    return target is not None and os.path.normcase(str(target)) == os.path.normcase(
        str(lifecycle_path.resolve())
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
    lifecycle_path = (
        claude_dir
        / "skills"
        / "_git-atomic-core"
        / "scripts"
        / "session_lifecycle.py"
    )
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
                    if not is_commitforge_lifecycle_handler(
                        handler,
                        lifecycle_path,
                    )
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
