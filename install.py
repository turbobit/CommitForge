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
SKILLS = (
    "cc",
    "ccr",
    "cf",
    "cfr",
    "ccf",
    "cr",
    "cca",
    "cp",
    "cpr",
    "_git-atomic-core",
)
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
    "cca-release-deployment-reviewer.md",
    "cca-requirements-product-reviewer.md",
)
CORE_REFERENCE = ".claude/skills/_git-atomic-core"
MARKER_NAME = ".commitforge-install.json"
MARKER_SCHEMA = "commitforge-install/v1"
POWERSHELL_ENCODED_SWITCHES = (
    " -NoLogo -NoProfile -NonInteractive -EncodedCommand "
)
# Accept both the absolute path written now and the bare `powershell.exe`
# written by older installers, so upgrades and uninstalls still find them.
POWERSHELL_ENCODED_COMMAND = re.compile(
    r"(?:[^\s'\"]*[\\/])?powershell\.exe"
    + re.escape(POWERSHELL_ENCODED_SWITCHES)
    + r"(\S+)",
    re.IGNORECASE,
)
# Runs a hook script only when it exists. A bare `python <missing file>` exits 2,
# which Claude Code treats as a block: a moved project or a downgrade would then
# deny every Bash call. The code avoids quotes so every shell passes it intact.
# `-c` puts the hook's cwd (the project) first on sys.path, so a project
# `json.py` would shadow the stdlib; sys.path[0] is reset to the script's
# directory exactly as `python <script>` would set it.
HOOK_LAUNCHER = (
    "import io,os,sys;p=sys.argv[1];sys.argv=[p];sys.path[0]=os.path.dirname(p);"
    "os.path.isfile(p) and "
    "exec(io.FileIO(p).read(),dict(__name__=__name__,__file__=p))"
)
# Launchers written by earlier releases, still recognised for removal.
HOOK_LAUNCHERS = (
    HOOK_LAUNCHER,
    "import io,os,sys;p=sys.argv[1];sys.argv=[p];os.path.isfile(p) and "
    "exec(io.FileIO(p).read(),dict(__name__=__name__,__file__=p))",
)
GATE_SUFFIX = "_git-atomic-core/scripts/worktree_gate.py"


def python_hook_command(
    executable: Path,
    script: Path,
    *,
    launcher: bool = False,
) -> str:
    """Render a Python hook command without depending on the caller's shell.

    With launcher, a missing script exits 0 instead of Python's 2.
    """
    executable = executable.resolve()
    script = script.resolve()
    middle = ["-c", HOOK_LAUNCHER] if launcher else []
    if sys.platform != "win32":
        return shlex.join([str(executable), *middle, str(script)])

    def powershell_literal(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    words = [executable, *middle, script]
    powershell = (
        "& " + " ".join(powershell_literal(word) for word in words) + "\n"
        "exit $LASTEXITCODE\n"
    )
    encoded = base64.b64encode(powershell.encode("utf-16-le")).decode("ascii")
    # The outer shell only sees a fixed executable, switches, and Base64. Paths
    # therefore survive Git Bash, PowerShell, and cmd.exe without re-parsing.
    return windows_powershell_executable() + POWERSHELL_ENCODED_SWITCHES + encoded


def windows_powershell_executable() -> str:
    """Return Windows PowerShell by absolute path; hook shells may lack it on PATH."""
    system_root = os.environ.get("SystemRoot") or os.environ.get("windir")
    if system_root:
        candidate = (
            Path(system_root)
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        # Forward slashes stay literal in Git Bash, cmd.exe, and PowerShell.
        posix = candidate.as_posix()
        if candidate.is_file() and not re.search(r"[\s'\"]", posix):
            return posix
    return "powershell.exe"


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
    """Return the script target of a generated hook (plain or launcher form)."""
    powershell_match = POWERSHELL_ENCODED_COMMAND.fullmatch(command)
    if powershell_match is not None:
        try:
            encoded = powershell_match.group(1)
            command = base64.b64decode(encoded, validate=True).decode("utf-16-le")
        except (UnicodeError, ValueError):
            return None
        match = re.fullmatch(
            r"& '((?:[^']|'')*)'(?: '-c' '(?:[^']|'')*')? '((?:[^']|'')*)'\r?\n"
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
    if len(argv) == 4 and argv[1] == "-c" and argv[2] in HOOK_LAUNCHERS:
        argv = [argv[0], argv[3]]
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
    if target is None:
        return False
    if lifecycle_path.name == "worktree_gate.py" and target.as_posix().endswith(GATE_SUFFIX):
        # Stale entries from a moved project or older install still match.
        return True
    return os.path.normcase(str(target)) == os.path.normcase(
        str(lifecycle_path.resolve())
    )


def remove_lifecycle_handlers(
    settings: dict, lifecycle_path: Path, gate_path: Path
) -> None:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    # Remove current hooks and legacy turn-end cleanup registrations.
    for event in ("SessionStart", "SessionEnd", "Stop", "StopFailure", "PreToolUse"):
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
                if not any(
                    is_commitforge_lifecycle_handler(handler, path)
                    for path in (lifecycle_path, gate_path)
                )
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
    gate_path = lifecycle_path.with_name("worktree_gate.py")
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

    remove_lifecycle_handlers(settings, lifecycle_path, gate_path)
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
    # Every session, not only the one running a commit skill: another session
    # can discard work while a Guard run holds the worktree lock.
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        raise RuntimeError(
            f"Claude PreToolUse hook 설정은 JSON array여야 합니다: {settings_path}"
        )
    pre_tool_use.append(
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": python_hook_command(
                        Path(sys.executable), gate_path, launcher=True
                    ),
                    "timeout": 10,
                }
            ],
        }
    )
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def package_version() -> str:
    return (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def write_install_marker(claude_dir: Path, *, scope: str, dry_run: bool) -> None:
    """Record what this installation placed, for upgrade and tooling checks.

    마커는 표시용 메타데이터일 뿐이다 (확장은 "마커 없음 + 해시 일치"도 ok로
    본다). 이 함수가 호출되는 시점에는 이미 skills·agents 복사와 hook 설정이
    전부 끝난 상태이므로, 마커 기록이 실패해도 설치 전체를 실패로 만들지
    않는다 — 경고만 남기고 넘어간다.
    """
    marker_path = claude_dir / MARKER_NAME
    if dry_run:
        print(f"[dry-run] write install marker -> {marker_path}")
        return

    try:
        payload = {
            "schema": MARKER_SCHEMA,
            "version": package_version(),
            "scope": scope,
            "installed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "python": str(Path(sys.executable)),
            "core_path": str((claude_dir / "skills" / "_git-atomic-core").resolve()),
        }
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(
            f"경고: 설치 마커를 기록하지 못했습니다: {exc} (설치 자체는 계속 진행합니다)",
            file=sys.stderr,
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
    write_install_marker(claude_dir, scope=args.scope, dry_run=args.dry_run)

    print()
    print(f"설치 범위: {args.scope}")
    print(f"설치 위치: {claude_dir}")
    if backup_root.exists() or args.dry_run:
        print(f"기존 파일 백업: {backup_root}")
    print("CommitForge 설치 완료")
    print("사용 명령: /ccr, /cc, /cr, /cca, /cpr, /cp")
    print("Fast Commit: /cfr 미리보기, /cf 단일 커밋 · /ccf: hunk 분리 없는 파일 단위 커밋")
    print("Pull Request: /cpr 미리보기, /cp 실제 생성")
    print("기간 리뷰: /cr today, /cr 3days, /cr weekly")
    print(
        "확장 모드: /cca today, /cca 3days, /cca weekly, /cca release, "
        "/cca emergency, /cca learn"
    )
    print("세션 잠금 정리: /clear, /exit, /resume, 로그아웃 등 SessionEnd에서만 자동 해제")
    print("변경 보존 게이트: Guard 잠금 중 reset·checkout·rebase 등과 snapshot 삭제를 모든 세션에서 차단")
    print("새 .claude/agents 디렉터리를 처음 만든 실행 중 세션에서는 Claude Code 재시작을 권장합니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"설치 실패: {exc}", file=sys.stderr)
        raise SystemExit(1)
