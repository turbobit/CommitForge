#!/usr/bin/env python3
"""Bind CommitForge locks to Claude Code sessions and clean them on SessionEnd."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SESSION_ENV_NAME = "COMMITFORGE_SESSION_ID"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
REASON_PATTERN = re.compile(r"^[a-z0-9_]{1,80}$")


def read_event() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("Claude hook 입력 JSON을 읽을 수 없습니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Claude hook 입력은 JSON object여야 합니다.")
    return payload


def validated_session(payload: dict[str, Any]) -> str:
    session = payload.get("session_id")
    if not isinstance(session, str) or not SESSION_PATTERN.fullmatch(session):
        raise ValueError("유효한 Claude session_id가 없습니다.")
    return session


def persist_session(session: str) -> None:
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        raise ValueError("SessionStart hook에 CLAUDE_ENV_FILE이 없습니다.")
    path = Path(env_file)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"export {SESSION_ENV_NAME}={session}\n")


def end_session(payload: dict[str, Any], session: str) -> None:
    reason = payload.get("reason")
    if not isinstance(reason, str) or not REASON_PATTERN.fullmatch(reason):
        raise ValueError(f"안전하지 않은 lifecycle reason입니다: {reason!r}")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("SessionEnd hook에 cwd가 없습니다.")

    guard = Path(__file__).resolve().with_name("guard.py")
    subprocess.run(
        [
            sys.executable,
            str(guard),
            "session-end",
            "--session",
            session,
            "--reason",
            reason,
        ],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=4,
    )


def main() -> int:
    try:
        payload = read_event()
        session = validated_session(payload)
        event = payload.get("hook_event_name")
        if event == "SessionStart":
            persist_session(session)
        elif event == "SessionEnd":
            end_session(payload, session)
        elif event == "Stop":
            end_session({**payload, "reason": "stop"}, session)
        elif event == "StopFailure":
            end_session({**payload, "reason": "stop_failure"}, session)
        else:
            raise ValueError(f"지원하지 않는 hook event입니다: {event!r}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"CommitForge lifecycle hook: {exc}", file=sys.stderr)
        # Lifecycle hooks are best-effort. Guard remains fail-closed and stale
        # recovery is available when Claude cannot deliver SessionEnd.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
