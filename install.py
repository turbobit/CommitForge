#!/usr/bin/env python3
"""Install CommitForge skills at project or personal scope with backups."""

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
CORE_REFERENCE = ".claude/skills/_git-atomic-core"
POWERSHELL_ENCODED_PREFIX = (
    "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand "
)


def python_hook_command(
    executable: Path,
    script: Path,
) -> str:
    """Render a Python hook command without depending on the caller's shell."""
    executable = executable.resolve()
    script = script.resolve()
    if sys.platform != "win32":
        return shlex.join([str(executable), str(script)])

    def powershell_literal(value: Path) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    powershell = (
        f"& {powershell_literal(executable)} {powershell_literal(script)}\n"
        "exit $LASTEXITCODE\n"
    )
    encoded = base64.b64encode(powershell.encode("utf-16-le")).decode("ascii")
    # The outer shell only sees a fixed executable, switches, and Base64. Paths
    # therefore survive Git Bash, PowerShell, and cmd.exe without re-parsing.
    return POWERSHELL_ENCODED_PREFIX + encoded


def yaml_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def configure_skill_core_paths(claude_dir: Path, dry_run: bool) -> None:
    """Replace project-relative template paths with this installation's path."""
    core_path = (claude_dir / "skills" / "_git-atomic-core").resolve()
    if dry_run:
        print(f"[dry-run] configure skill core paths -> {core_path}")
        return

    for name in SKILLS:
        if name == "_git-atomic-core":
            continue
        skill_path = claude_dir / "skills" / name / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        if CORE_REFERENCE not in text:
            raise RuntimeError(
                f"Skill core 경로 template을 찾을 수 없습니다: {skill_path}"
            )
        frontmatter, separator, body = text.partition("\n---\n")
        if not separator:
            raise RuntimeError(f"Skill frontmatter 종료가 없습니다: {skill_path}")
        # Frontmatter uses YAML single-quoted permission patterns.
        configured_frontmatter = frontmatter.replace(
            CORE_REFERENCE, str(core_path).replace("'", "''")
        )
        configured_body = body.replace(CORE_REFERENCE, str(core_path))
        skill_path.write_text(
            configured_frontmatter + separator + configured_body,
            encoding="utf-8",
        )


def configure_cr_edit_gate(claude_dir: Path, dry_run: bool) -> None:
    """Pin the /cr edit hook to this installation without runtime env vars."""
    skill_path = claude_dir / "skills" / "cr" / "SKILL.md"
    gate_path = (
        claude_dir
        / "skills"
        / "_git-atomic-core"
        / "scripts"
        / "cr_edit_gate.py"
    )
    command = python_hook_command(
        Path(sys.executable),
        gate_path,
    )
    if dry_run:
        print(f"[dry-run] configure /cr edit hook -> {command}")
        return

    text = skill_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    matching = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("command:") and "cr_edit_gate.py" in line
    ]
    if len(matching) != 1:
        raise RuntimeError(
            "/cr Write hook 설정을 하나로 확정할 수 없습니다: "
            f"{skill_path} (matches={len(matching)})"
        )
    index = matching[0]
    newline = "\n" if lines[index].endswith("\n") else ""
    indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
    lines[index] = (
        f"{indent}command: {yaml_single_quoted(command)}{newline}"
    )
    skill_path.write_text("".join(lines), encoding="utf-8")


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


def remove_lifecycle_handlers(settings: dict, lifecycle_path: Path) -> None:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    # Remove current hooks and legacy turn-end cleanup registrations.
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
                if not is_commitforge_lifecycle_handler(handler, lifecycle_path)
            ]
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


def configure_lifecycle_hooks(
    claude_dir: Path,
    backup_root: Path,
    *,
    global_scope: bool,
    dry_run: bool,
) -> None:
    """Merge CommitForge session hooks without replacing user settings."""
    settings_name = "settings.json" if global_scope else "settings.local.json"
    settings_path = claude_dir / settings_name
    lifecycle_path = (
        claude_dir
        / "skills"
        / "_git-atomic-core"
        / "scripts"
        / "session_lifecycle.py"
    )
    command = python_hook_command(
        Path(sys.executable),
        lifecycle_path,
    )
    if dry_run:
        print(f"[dry-run] merge CommitForge lifecycle hooks -> {settings_path}")
        return
    if settings_path.is_symlink():
        raise RuntimeError(f"Claude 설정 심볼릭 링크는 자동 수정하지 않습니다: {settings_path}")

    if settings_path.exists():
        backup = backup_root / settings_name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(settings_path, backup)
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Claude 설정 JSON이 손상되었습니다: {settings_path}") from exc
        if not isinstance(settings, dict):
            raise RuntimeError(f"Claude 설정은 JSON object여야 합니다: {settings_path}")
    else:
        settings = {}

    remove_lifecycle_handlers(settings, lifecycle_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise RuntimeError(f"Claude hooks 설정은 JSON object여야 합니다: {settings_path}")
    handler = {
        "type": "command",
        "command": command,
        "timeout": 5,
    }
    # A completed or failed turn is not a session boundary. Register cleanup
    # only for actual session lifecycle events.
    for event in ("SessionStart", "SessionEnd"):
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise RuntimeError(
                f"Claude {event} hook 설정은 JSON array여야 합니다: {settings_path}"
            )
        groups.append({"hooks": [handler]})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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

    configure_skill_core_paths(claude_dir, args.dry_run)
    configure_cr_edit_gate(claude_dir, args.dry_run)
    configure_lifecycle_hooks(
        claude_dir,
        backup_root,
        global_scope=args.scope == "global",
        dry_run=args.dry_run,
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
    print("세션 잠금 정리: /clear, /exit, /resume, 로그아웃 등 SessionEnd에서만 자동 해제")
    print("새 .claude/agents 디렉터리를 처음 만든 실행 중 세션에서는 Claude Code 재시작을 권장합니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"설치 실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
