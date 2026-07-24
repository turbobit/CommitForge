#!/usr/bin/env python3
"""Deny /cr editing unless exact --fix is valid for the selected mode."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import sys
from typing import Any


COMMAND_PATTERN = re.compile(r"<command-name>\s*/cr\s*</command-name>")
ARGS_PATTERN = re.compile(
    r"<command-args>(.*?)</command-args>",
    flags=re.DOTALL,
)


def text_content(message: Any) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, list):
        return ""
    chunks = []
    for item in message:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text", "")))
    return "\n".join(chunks)


def latest_cr_args(transcript_path: Path) -> str | None:
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "user":
            continue
        payload = event.get("message", {})
        content = text_content(
            payload.get("content", "") if isinstance(payload, dict) else ""
        )
        if not COMMAND_PATTERN.search(content):
            continue
        match = ARGS_PATTERN.search(content)
        return match.group(1).strip() if match else ""
    return None


def exact_fix_requested(arguments: str | None) -> bool:
    if arguments is None:
        return False
    try:
        return "--fix" in shlex.split(arguments)
    except ValueError:
        return False


def strict_read_only_mode(arguments: str | None) -> str | None:
    if arguments is None:
        return None
    try:
        tokens = shlex.split(arguments)
    except ValueError:
        return None
    return next(
        (token for token in tokens if token in {"release", "emergency", "learn"}),
        None,
    )


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError):
        print(
            "CommitForge: /cr 편집 권한을 확인할 수 없어 파일 수정을 차단합니다.",
            file=sys.stderr,
        )
        return 2

    transcript = event.get("transcript_path")
    arguments = (
        latest_cr_args(Path(transcript)) if isinstance(transcript, str) else None
    )
    mode = strict_read_only_mode(arguments)
    if mode:
        print(
            f"CommitForge: /cr {mode} 모드는 --fix와 관계없이 항상 read-only입니다.",
            file=sys.stderr,
        )
        return 2
    if not exact_fix_requested(arguments):
        print(
            "CommitForge: 기본 /cr은 read-only입니다. 파일을 수정하려면 "
            "명령 호출에 독립된 --fix 옵션을 명시하세요.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
