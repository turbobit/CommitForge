#!/usr/bin/env python3
"""Machine-owned review ledger for /cr.

The ledger lives inside the Guard snapshot directory so it inherits that
directory's ownership, integrity audit and cleanup lifecycle. Only the lead
agent writes to it; reviewer subagents have no Bash tool and cannot.
"""

from __future__ import annotations

import argparse
import hashlib
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

GENERATION_PREFIX = "gen"
INVENTORY_NAME = "inventory.jsonl"


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


def split_range_expression(expression: str) -> tuple[str, str, str]:
    """Split a range expression into (left, separator, right).

    The triple-dot symmetric-difference form (`A...B`) is checked before the
    plain two-dot form (`A..B`) since `..` is a substring of `...` and would
    otherwise split in the wrong place. Returns `("", "", "")` when neither
    separator is present.
    """
    triple_at = expression.find("...")
    if triple_at != -1:
        return expression[:triple_at], "...", expression[triple_at + 3 :]
    double_at = expression.find("..")
    if double_at != -1:
        return expression[:double_at], "..", expression[double_at + 2 :]
    return expression, "", ""


def validate_scopes(raw: list[str]) -> list[str]:
    scopes = []
    for value in raw:
        if value == "working":
            scopes.append(value)
            continue
        if value.startswith("range:"):
            expression = value[len("range:") :]
            left, sep, right = split_range_expression(expression)
            # Both sides must be present and neither may start with `-`: an
            # empty side (`..HEAD`, `A..`) is legal git shorthand for HEAD but
            # is rejected here rather than resolved, and a leading `-` would
            # let the expression be parsed as a git option (e.g.
            # `--output=<path>`) instead of a revision, letting `git diff`
            # exit 0 having diffed nothing and, in the `--output` case,
            # written outside the ledger directory. Both must fail closed at
            # validation time, before any git subprocess ever sees the value.
            if sep and left and right and not left.startswith("-") and not right.startswith("-"):
                scopes.append(value)
                continue
        raise guard.GuardError(
            f"알 수 없는 scope입니다: {value}", reason="ledger_scope_invalid"
        )
    if not scopes:
        raise guard.GuardError("scope가 비어 있습니다.", reason="ledger_scope_invalid")
    return scopes


_SIMPLE_QUOTE_ESCAPES = {
    "\\": 0x5C, '"': 0x22, "n": 0x0A, "t": 0x09, "r": 0x0D,
    "a": 0x07, "b": 0x08, "f": 0x0C, "v": 0x0B,
}


def decode_git_quoted(content: str) -> str:
    """Decode the inner content of a git C-quoted token (no surrounding quotes).

    Handles the escapes git emits when a path needs quoting: `\\\\`, `\\"`,
    the usual single-letter C escapes, and `\\NNN` three-digit octal byte
    escapes (used for bytes >= 0x80, e.g. under `core.quotePath`). Bytes are
    accumulated and decoded as UTF-8 with `replace` so a non-UTF-8 byte
    sequence degrades gracefully instead of raising. An escape this function
    does not recognize is kept literally rather than raising, so a malformed
    header degrades to a best-effort path instead of crashing the inventory.
    """
    out = bytearray()
    i = 0
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == "\\" and i + 1 < n:
            nxt = content[i + 1]
            if nxt in _SIMPLE_QUOTE_ESCAPES:
                out.append(_SIMPLE_QUOTE_ESCAPES[nxt])
                i += 2
                continue
            octal = content[i + 1 : i + 4]
            if len(octal) == 3 and all(d in "01234567" for d in octal):
                out.append(int(octal, 8) & 0xFF)
                i += 4
                continue
            out.extend(b"\\")
            i += 1
            continue
        out.extend(ch.encode("utf-8", "replace"))
        i += 1
    return bytes(out).decode("utf-8", "replace")


def _quoted_token_end(text: str, start: int) -> int:
    """Return the index of the unescaped closing quote for the quoted token
    whose opening `"` sits at `start`, or -1 if it is never closed."""
    i = start + 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i
        i += 1
    return -1


def extract_b_path(remainder: str) -> str:
    """Extract and decode the b-side path from a `diff --git` header remainder.

    Git quotes the a-token and b-token independently, so a rename where only
    one side needs quoting is common. An unquoted token can never itself
    contain a literal `"` (that character always forces quoting), so once the
    a-token is known to be unquoted, the first `"` remaining in the string can
    only be the start of a quoted b-token. When neither token is quoted, a
    path may legitimately contain spaces, so there is no exact boundary; this
    falls back to the last ` b/` occurrence, which is the best available
    heuristic for that ambiguous case. Never raises: a header this cannot
    make sense of comes back unparsed rather than crashing the inventory.
    """
    try:
        if remainder.startswith('"'):
            end = _quoted_token_end(remainder, 0)
            if end == -1:
                return remainder
            b_token = remainder[end + 1 :].lstrip(" ")
        else:
            quote_at = remainder.find('"')
            if quote_at != -1:
                b_token = remainder[quote_at:]
            else:
                idx = remainder.rfind(" b/")
                if idx == -1:
                    return remainder
                b_token = remainder[idx + 1 :]

        if b_token.startswith('"'):
            end = _quoted_token_end(b_token, 0)
            content = b_token[1:end] if end != -1 else b_token[1:]
            path = decode_git_quoted(content)
        else:
            path = b_token

        return path[2:] if path.startswith("b/") else path
    except Exception:
        return remainder


def parse_diff_entries(diff: bytes, source: str) -> list[dict[str, Any]]:
    """Split a git diff into hunk, binary and meta entries.

    Every changed file yields at least one entry. A file whose diff carries no
    `@@` hunk is a mode or rename change and becomes a `meta` entry, so it can
    never disappear from the denominator.
    """
    entries: list[dict[str, Any]] = []
    state: dict[str, Any] = {"path": None, "index": 0, "saw_hunk": False, "binary": False}

    def flush() -> None:
        path = state["path"]
        if path is None:
            return
        if state["binary"]:
            kind = "binary"
        elif not state["saw_hunk"]:
            kind = "meta"
        else:
            kind = None
        if kind is not None:
            entries.append(
                {
                    "id": f"{source}:{path}#0",
                    "kind": kind,
                    "source": source,
                    "path": path,
                    "header": "",
                }
            )
        state.update({"path": None, "index": 0, "saw_hunk": False, "binary": False})

    for raw_line in diff.split(b"\n"):
        line = raw_line.decode("utf-8", "replace")
        if line.startswith("diff --git "):
            flush()
            remainder = line[len("diff --git ") :]
            state["path"] = extract_b_path(remainder)
            continue
        if state["path"] is None:
            continue
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            state["binary"] = True
            continue
        if line.startswith("@@"):
            state["saw_hunk"] = True
            state["index"] += 1
            entries.append(
                {
                    "id": f"{source}:{state['path']}#{state['index']}",
                    "kind": "hunk",
                    "source": source,
                    "path": state["path"],
                    "header": line.strip(),
                }
            )
    flush()
    return entries


def untracked_record(path: str) -> dict[str, Any]:
    return {
        "id": f"untracked:{path}#0",
        "kind": "untracked",
        "source": "untracked",
        "path": path,
        "header": "",
    }


def untracked_entries(snapshot: Path) -> list[dict[str, Any]]:
    raw = (snapshot / "untracked.z").read_bytes()
    return [
        untracked_record(chunk.decode("utf-8", "replace"))
        for chunk in raw.split(b"\0")
        if chunk
    ]


def working_scope_entries(snapshot: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    entries.extend(parse_diff_entries((snapshot / "staged.diff").read_bytes(), "staged"))
    entries.extend(parse_diff_entries((snapshot / "working.diff").read_bytes(), "working"))
    entries.extend(untracked_entries(snapshot))
    return entries


def range_scope_entries(ctx: dict[str, Path], spec: str) -> list[dict[str, Any]]:
    """Enumerate hunks in a committed range.

    The snapshot only captures working state, so `--base`, `--range`, `pr` and
    the period modes need their denominator computed here instead.

    `validate_scopes` already rejects a leading `-` on either side, but that
    check runs at `init` time against the raw string. This still resolves
    both sides with `git rev-parse --verify <side>^{commit}` before ever
    calling `git diff`, so a side that cannot be resolved to a commit fails
    closed here too, and the range only ever reaches `git diff` once both
    ends are known-good commit ids.
    """
    expression = spec[len("range:") :]
    left, _sep, right = split_range_expression(expression)
    for side in (left, right):
        try:
            guard.run_git(["rev-parse", "--verify", f"{side}^{{commit}}"], cwd=ctx["root"])
        except guard.GuardError as exc:
            raise guard.GuardError(
                f"커밋 범위를 해석하지 못했습니다: {expression}",
                reason="ledger_range_unresolved",
                range=expression,
            ) from exc
    try:
        diff = guard.run_git(
            ["diff", "--binary", "--full-index", "--no-ext-diff", expression],
            cwd=ctx["root"],
        )
    except guard.GuardError as exc:
        raise guard.GuardError(
            f"커밋 범위를 해석하지 못했습니다: {expression}",
            reason="ledger_range_unresolved",
            range=expression,
        ) from exc
    # A distinct source per range expression (rather than the shared literal
    # "range") keeps ids from two declared range scopes disjoint even when
    # they touch the same path at the same hunk index; the digest is a pure
    # function of the expression so a re-run of `inventory` is idempotent.
    source = f"range@{hashlib.sha256(expression.encode('utf-8')).hexdigest()[:8]}"
    return parse_diff_entries(diff, source)


def fingerprint_short(ctx: dict[str, Path]) -> str:
    return guard.repository_fingerprint(ctx["root"])["fingerprint"][:8]


def generation_name(iteration: int, short: str) -> str:
    return f"{GENERATION_PREFIX}-{iteration:02d}-{short}"


def write_inventory(gen_dir: Path, entries: list[dict[str, Any]]) -> None:
    with (gen_dir / INVENTORY_NAME).open("w", encoding="utf-8", newline="\n") as stream:
        for entry in entries:
            stream.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


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


def cmd_inventory(args: argparse.Namespace) -> None:
    ctx, snapshot, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        name = data["active_generation"] or generation_name(
            data["iteration"], fingerprint_short(ctx)
        )
        gen_dir = ledger_dir / name
        gen_dir.mkdir(mode=0o700, exist_ok=True)

        entries: list[dict[str, Any]] = []
        for scope in data["scopes"]:
            if scope == "working":
                entries.extend(working_scope_entries(snapshot))
            else:
                entries.extend(range_scope_entries(ctx, scope))
        write_inventory(gen_dir, entries)

        data["active_generation"] = name
        data["stage"] = "inventory"
        write_run(ledger_dir, data)

    guard.emit({"ok": True, "generation": name, "total": len(entries), "entries": entries})


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

    inventory = sub.add_parser("inventory", help="Build the machine-owned denominator")
    inventory.add_argument("--session", required=True)
    inventory.add_argument("--token")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {"init": cmd_init, "status": cmd_status, "inventory": cmd_inventory}
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
