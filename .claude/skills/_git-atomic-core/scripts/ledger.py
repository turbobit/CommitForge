#!/usr/bin/env python3
"""Machine-owned review ledger for /cr.

The ledger lives inside the Guard snapshot directory so it inherits that
directory's ownership, integrity audit and cleanup lifecycle. Only the lead
agent writes to it; reviewer subagents have no Bash tool and cannot.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import guard  # noqa: E402


LEDGER_DIR_NAME = "ledger"
RUN_NAME = "run.json"
LOCK_NAME = ".lock"
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05

STAGES = ("init", "inventory", "review", "fix", "verify", "done")
TERMINAL_VERDICTS = ("PASS", "FINDING", "N_A")
VERDICTS = TERMINAL_VERDICTS + ("UNKNOWN",)


class LedgerLock:
    """Directory-based exclusive lock.

    `fcntl.flock` is POSIX-only and this package is tested on windows-latest,
    so the lock uses `mkdir` atomicity exactly as `guard.acquire_lock` does.
    """

    def __init__(self, ledger_dir: Path) -> None:
        self.path = ledger_dir / LOCK_NAME

    def __enter__(self) -> "LedgerLock":
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self.path.mkdir(mode=0o700)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise guard.GuardError(
                        "원장 잠금을 얻지 못했습니다.",
                        reason="ledger_lock_timeout",
                        lock_path=str(self.path),
                    )
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, *exc_info: object) -> None:
        try:
            self.path.rmdir()
        except OSError:
            pass


def resolve_ledger(
    session: str, token: str | None
) -> tuple[dict[str, Path], Path, Path, str]:
    """Bind to the snapshot owned by this session, token and project root.

    Reuses guard's resolution so a lock-free `/ccf` snapshot, which carries a
    different token, is never selected. The resolved token is returned so
    callers never resolve it a second time.
    """
    ctx = guard.repo_context(Path.cwd().resolve())
    safe = guard.safe_session(session)
    resolved_token, snapshot = guard.resolve_owned_review_context(ctx, safe, token, None)
    guard.validate_snapshot(ctx, snapshot, safe, resolved_token)
    return ctx, snapshot, snapshot / LEDGER_DIR_NAME, resolved_token


def read_run(ledger_dir: Path) -> dict[str, Any]:
    data = guard.read_json(ledger_dir / RUN_NAME)
    if not data:
        raise guard.GuardError("원장이 초기화되지 않았습니다.", reason="ledger_missing")
    return data


def write_run(ledger_dir: Path, data: dict[str, Any]) -> None:
    """Replace run.json atomically; it is the only non-append-only file."""
    tmp = ledger_dir / f"{RUN_NAME}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(tmp, ledger_dir / RUN_NAME)


def validate_scopes(raw: list[str]) -> list[str]:
    scopes = []
    for value in raw:
        if value == "working":
            scopes.append(value)
            continue
        if value.startswith("range:") and ".." in value[len("range:") :]:
            scopes.append(value)
            continue
        raise guard.GuardError(
            f"알 수 없는 scope입니다: {value}", reason="ledger_scope_invalid"
        )
    if not scopes:
        raise guard.GuardError("scope가 비어 있습니다.", reason="ledger_scope_invalid")
    return scopes


def cmd_init(args: argparse.Namespace) -> None:
    scopes = validate_scopes(args.scope)
    _, _, ledger_dir, resolved_token = resolve_ledger(args.session, args.token)
    ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with LedgerLock(ledger_dir):
        data = {
            "session": guard.safe_session(args.session),
            "token": resolved_token,
            "stage": "init",
            "iteration": 1,
            "active_generation": "",
            "scopes": scopes,
        }
        write_run(ledger_dir, data)
    guard.emit({"ok": True, **data})


def cmd_status(args: argparse.Namespace) -> None:
    _, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    if not (ledger_dir / RUN_NAME).is_file():
        guard.emit({"ok": True, "exists": False})
    data = read_run(ledger_dir)
    guard.emit(
        {
            "ok": True,
            "exists": True,
            "stage": data["stage"],
            "iteration": data["iteration"],
            "active_generation": data["active_generation"],
            "scopes": data["scopes"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the ledger for an owned snapshot")
    init.add_argument("--session", required=True)
    init.add_argument("--token")
    init.add_argument("--scope", action="append", default=[])

    status = sub.add_parser("status", help="Report ledger progress and coverage")
    status.add_argument("--session", required=True)
    status.add_argument("--token")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {"init": cmd_init, "status": cmd_status}
    try:
        handlers[args.command](args)
    except guard.GuardError as exc:
        guard.emit({"ok": False, "error": str(exc), **exc.details}, exit_code=2)
    except KeyboardInterrupt:
        guard.emit({"ok": False, "error": "사용자 중단"}, exit_code=130)
    except Exception as exc:
        guard.emit(
            {"ok": False, "error": f"예기치 않은 ledger 오류: {type(exc).__name__}: {exc}"},
            exit_code=3,
        )


if __name__ == "__main__":
    main()
