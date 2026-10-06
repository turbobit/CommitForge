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
LOCK_STALE_AFTER_SECONDS = 60.0

STAGES = ("init", "inventory", "review", "fix", "verify", "done")
TERMINAL_VERDICTS = ("PASS", "FINDING", "N_A")
VERDICTS = TERMINAL_VERDICTS + ("UNKNOWN",)

# Reviewer status shares the verdict spelling trap: "N/A" is not "N_A". An
# unvalidated status would read as "not UNKNOWN" and satisfy the coverage gate,
# so the gate can only be sound if `record` rejects anything outside this set.
REVIEWER_STATUSES = ("ACTIVE", "N_A", "UNKNOWN")

# review-execution.md §2 makes Line, Correctness and Security mandatory on
# every change, and Architecture (which owns contract and compatibility) and
# Performance are mandatory for `/cr`. The set is keyed by the skill that
# created the ledger because each carries a different one: `/cca` adds Git
# (atomicity), and `/cpr`/`/cp` add Release because a PR is where deployment
# order and rollback become real.
#
# Matching is by role keyword rather than by exact agent filename: Agent Team
# mode packs these perspectives into named core teammates
# (`core-correctness-line-state`), and a filename match would make the rule
# unsatisfiable in the structure the skill selects by default. That is also why
# review-execution.md §3.5 forbids abbreviating a role keyword in a teammate
# name -- `core-arch-...` would silently fail to satisfy `architecture` and
# would block a review that actually covered it.
# `/ccr` is absent on purpose. It never calls Guard `begin`, so it has no
# snapshot, and the ledger lives inside one. Giving it a snapshot would also
# give it the exclusive worktree lock, which would stop a lightweight planning
# command from running alongside a review -- a worse trade than the coverage it
# would buy, since `/cc` and `/cca` re-derive the plan anyway.
REQUIRED_REVIEWER_ROLES: dict[str, tuple[str, ...]] = {
    "cr": ("line", "correctness", "security", "architecture", "performance"),
    "cca": ("line", "correctness", "security", "architecture", "performance", "git"),
    "cpr": ("line", "correctness", "security", "architecture", "performance", "release"),
    "cp": ("line", "correctness", "security", "architecture", "performance", "release"),
}

# A ledger with no `skill` field predates the mapping, and an unmapped name is a
# skill that has not declared its set yet. Both fall back to the original three
# rather than to `/cr`'s five: widening the requirement under a review that is
# already in flight would block it for a perspective its own skill never asked
# for.
DEFAULT_REVIEWER_ROLES = ("line", "correctness", "security")


def required_roles_for(skill: Any) -> tuple[str, ...]:
    """Return the mandatory role keywords for the skill that owns a ledger."""
    if not isinstance(skill, str):
        return DEFAULT_REVIEWER_ROLES
    return REQUIRED_REVIEWER_ROLES.get(skill, DEFAULT_REVIEWER_ROLES)

# review-execution.md §3's finding schema. Every field here is optional so a
# reviewer that omits them still records, but a supplied value must be valid:
# §3.6 lets `confidence` flip a finding to REJECTED and `blocking_severity`
# gates on `severity`, so an unvalidated typo would read as "field absent" and
# silently skip the very gate the field exists to feed. That is the same
# failure the verdict and reviewer-status spellings are validated against.
#
# Each of these must stay equal to its `report_validator` counterpart: the
# ledger is where a finding is written and the validator is where the exported
# JSON/SARIF is checked, so a value accepted by one and refused by the other
# would make a recorded review unexportable. `tests/test_ledger.py` asserts
# they agree.
FINDING_SEVERITIES = ("CRITICAL", "MAJOR", "MINOR", "NOTE")
FINDING_STATUSES = (
    "OPEN",
    "FIXED",
    "REJECTED",
    "N_A",
    "UNKNOWN",
    "BASELINED",
    "STALE",
)
VERIFICATIONS = ("ISOLATED", "SELF", "UNVERIFIED")
CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 10

GENERATION_PREFIX = "gen"
FINGERPRINT_PREFIX_LEN = 8
INVENTORY_NAME = "inventory.jsonl"
HUNKS_NAME = "hunks.jsonl"
FINDINGS_NAME = "findings.jsonl"
REVIEWERS_NAME = "reviewers.json"


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
            except FileNotFoundError as exc:
                # The ledger directory does not exist yet. Only `init` creates
                # it, so this is "the ledger was never initialized" -- it must
                # surface as the documented `ledger_missing` rather than as a
                # raw FileNotFoundError that `main()`'s generic handler turns
                # into exit 3 with no `reason` for a caller to branch on.
                raise guard.GuardError(
                    "원장이 초기화되지 않았습니다.", reason="ledger_missing"
                ) from exc
            except FileExistsError:
                if time.monotonic() >= deadline:
                    # An orphaned lock (SIGKILL between mkdir and rmdir) would
                    # otherwise wedge every later command with no way to tell
                    # a live holder from a dead one, so report its age the way
                    # `guard.lock_owner_profile` does and name the recovery.
                    age = guard.lock_dir_age_seconds(self.path)
                    raise guard.GuardError(
                        "원장 잠금을 얻지 못했습니다. 다른 ledger 명령이 실행 중이 아니라면 "
                        f"남겨진 잠금 디렉터리를 제거하십시오: {self.path}",
                        reason="ledger_lock_timeout",
                        lock_path=str(self.path),
                        lock_age_seconds=age,
                        stale_candidate=age is not None and age >= LOCK_STALE_AFTER_SECONDS,
                    )
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, *exc_info: object) -> None:
        try:
            self.path.rmdir()
        except OSError as exc:
            # Losing the lock directory wedges every later ledger command, so
            # it must not vanish silently the way a bare `pass` did. The
            # in-flight exception (if any) still wins; this only annotates.
            print(
                f"warning: 원장 잠금을 해제하지 못했습니다: {self.path} ({exc})",
                file=sys.stderr,
            )


def resolve_ledger(
    session: str, token: str | None
) -> tuple[dict[str, Path], Path, Path, str]:
    """Bind to the snapshot owned by this session, token and project root.

    Reuses guard's resolution so a lock-free snapshot (`/ccf` up to 1.20.0),
    which carries a different token, is never selected. The resolved token is returned so
    callers never resolve it a second time.
    """
    ctx = guard.repo_context(Path.cwd().resolve())
    safe = guard.safe_session(session)
    resolved_token, snapshot, _ = guard.resolve_owned_review_context(ctx, safe, token, None)
    guard.validate_snapshot(ctx, snapshot, safe, resolved_token)
    return ctx, snapshot, snapshot / LEDGER_DIR_NAME, resolved_token


def read_run_optional(ledger_dir: Path) -> dict[str, Any] | None:
    """Load `run.json`, or None when it does not exist.

    `guard.read_json` swallows `JSONDecodeError` and returns None, which makes
    "the file is not there" and "the file is there but unreadable" look
    identical. Both fail closed, but the second is a corrupted ledger and must
    be diagnosed as `ledger_corrupt` so a caller is not told to run `init` on a
    ledger that already exists and holds verdicts.
    """
    path = ledger_dir / RUN_NAME
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise guard.GuardError(
            "원장 run.json을 읽을 수 없습니다.", reason="ledger_corrupt", path=str(path)
        ) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise guard.GuardError(
            "원장 run.json을 해석할 수 없습니다.", reason="ledger_corrupt", path=str(path)
        ) from exc
    if not isinstance(data, dict) or not data:
        raise guard.GuardError(
            "원장 run.json의 형식이 올바르지 않습니다.",
            reason="ledger_corrupt",
            path=str(path),
        )
    # Callers read these four unguarded -- `int(data["iteration"])`,
    # `data["stage"]`, `data["active_generation"]`, `data["scopes"]` -- so a
    # run.json that parses but carries a wrong type or a missing key would
    # raise TypeError/KeyError from deep inside a command and exit 3 with no
    # `reason`, which is exactly the misdiagnosis this function exists to
    # prevent. Validate the shape once, here, where it can still be named.
    for field, kinds in (
        ("stage", str),
        ("iteration", int),
        ("active_generation", str),
        ("scopes", list),
    ):
        value = data.get(field)
        # `bool` is an `int` subclass; an iteration of `true` is corruption.
        if not isinstance(value, kinds) or isinstance(value, bool):
            raise guard.GuardError(
                f"원장 run.json의 {field} 항목이 올바르지 않습니다.",
                reason="ledger_corrupt",
                path=str(path),
                field=field,
            )
    if data["iteration"] < 1 or not all(
        isinstance(scope, str) for scope in data["scopes"]
    ):
        raise guard.GuardError(
            "원장 run.json의 iteration 또는 scopes 값이 올바르지 않습니다.",
            reason="ledger_corrupt",
            path=str(path),
        )
    return data


def read_run(ledger_dir: Path) -> dict[str, Any]:
    data = read_run_optional(ledger_dir)
    if data is None:
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
    """Validate declared scopes, preserving order and dropping duplicates.

    A scope is enumerated once per occurrence by `cmd_inventory`, so a repeated
    `--scope working` would emit the same ids twice and double `total`,
    `by_verdict` and every per-scope count the final report is required to
    quote -- while `inventory_ids` (a set) stays consistent, so nothing else
    would ever flag the inflation. Deduplicate here, at the only entry point.
    """
    scopes: list[str] = []
    for value in raw:
        if value in scopes:
            continue
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
                # Prefixes are forced on for every diff this module reads, so
                # a non-rename header is exactly `a/<P> b/<P>`. That is
                # solvable without guessing where the a-token ends, which is
                # what makes a path containing the literal " b/" resolve
                # correctly instead of colliding with a shorter one.
                if remainder.startswith("a/"):
                    half = (len(remainder) - 5) // 2
                    candidate = remainder[2 : 2 + half]
                    if half > 0 and remainder == f"a/{candidate} b/{candidate}":
                        return candidate
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


def unified_header_path(token: str, prefix: str) -> str | None:
    """Decode a `--- <token>` / `+++ <token>` path, or None for `/dev/null`.

    Unlike the `diff --git` header, which packs both sides onto one line with
    no unambiguous separator, these lines carry exactly one token terminated
    by end-of-line. A path containing the literal `" b/"` therefore reads back
    exactly, where the two-sided header can only guess.

    git appends a single TAB terminator to an unquoted name that contains a
    space, so `patch(1)` can find the end of the field. That TAB is not part
    of the path. A name that really ended in a TAB would have been C-quoted
    instead (a TAB is a control character), so stripping one trailing TAB from
    an unquoted token is unambiguous.
    """
    if token.startswith('"'):
        end = _quoted_token_end(token, 0)
        path = decode_git_quoted(token[1:end] if end != -1 else token[1:])
    else:
        path = token[:-1] if token.endswith("\t") else token
    if path == "/dev/null":
        return None
    return path[len(prefix) :] if path.startswith(prefix) else path


def parse_diff_entries(diff: bytes, source: str) -> list[dict[str, Any]]:
    """Split a git diff into hunk, binary and meta entries.

    Every changed file yields at least one entry. A file whose diff carries no
    `@@` hunk is a mode or rename change and becomes a `meta` entry, so it can
    never disappear from the denominator.

    The path comes from the file's `+++` line when it has one, falling back to
    its `---` line for a deletion and to the `diff --git` header for the
    rename-, mode- and binary-only changes that carry neither. Both fallbacks
    are exact for every path the `+++` line would have resolved; only the
    header is a heuristic, and reaching it requires a path that git could not
    quote and a change with no content at all.
    """
    entries: list[dict[str, Any]] = []
    state: dict[str, Any] = {
        "path": None,
        "index": 0,
        "saw_hunk": False,
        "binary": False,
        "minus_path": None,
    }

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
        state.update(
            {
                "path": None,
                "index": 0,
                "saw_hunk": False,
                "binary": False,
                "minus_path": None,
            }
        )

    for raw_line in diff.split(b"\n"):
        line = raw_line.decode("utf-8", "replace")
        if line.startswith("diff --git "):
            flush()
            remainder = line[len("diff --git ") :]
            state["path"] = extract_b_path(remainder)
            continue
        # An unmerged path (a conflicted stash pop, merge or cherry-pick that
        # left `UU` entries) is emitted as a combined diff, whose header is
        # `diff --cc <path>` / `diff --combined <path>` -- a single
        # EOL-terminated token with no `a/`/`b/` prefixes -- and whose hunks
        # start with `@@@` rather than `@@`. Without this branch the header is
        # unrecognized, `state["path"]` stays None, the `continue` below
        # swallows the whole file section, and the conflicted file silently
        # disappears from the denominator.
        if line.startswith("diff --cc ") or line.startswith("diff --combined "):
            flush()
            token = line.split(" ", 2)[2]
            state["path"] = unified_header_path(token, "") or token
            continue
        # `git diff --cached` reports a conflicted path as this one line and
        # emits no diff body for it at all, so it must become a meta entry or
        # it is invisible to the inventory.
        if line.startswith("* Unmerged path "):
            flush()
            token = line[len("* Unmerged path ") :]
            resolved = unified_header_path(token, "") or token
            entries.append(
                {
                    "id": f"{source}:{resolved}#0",
                    "kind": "unmerged",
                    "source": source,
                    "path": resolved,
                    "header": "",
                }
            )
            continue
        if state["path"] is None:
            continue
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            state["binary"] = True
            continue
        # Only before the first `@@`: inside a hunk, an added line whose
        # content begins with `++ ` renders as `+++ ` and must not be mistaken
        # for a file header.
        # A rename carries no content and therefore no `+++` line, but its
        # `rename to` line is a single EOL-terminated token, which is exact
        # where the two-sided `diff --git` header is a heuristic.
        if not state["saw_hunk"] and line.startswith("rename to "):
            resolved = unified_header_path(line[len("rename to ") :], "")
            if resolved is not None:
                state["path"] = resolved
            continue
        if not state["saw_hunk"] and line.startswith("--- "):
            state["minus_path"] = unified_header_path(line[4:], "a/")
            continue
        if not state["saw_hunk"] and line.startswith("+++ "):
            resolved = unified_header_path(line[4:], "b/")
            if resolved is None:
                resolved = state["minus_path"]
            if resolved is not None:
                state["path"] = resolved
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
    """Read untracked paths back out of the snapshot.

    `capture_snapshot` writes `untracked.z` with `surrogateescape`, and
    `guard.list_untracked` -- which `live_scope_entries` uses for every
    generation after the first -- decodes with the same handler. Decoding with
    `replace` here instead would be lossy in both directions: the same file
    would get a different id before and after an `advance`, and two distinct
    non-UTF-8 names would collapse onto one id, so a single PASS would mark
    both covered. Use guard's own inverse decoder.
    """
    raw = (snapshot / "untracked.z").read_bytes()
    return [
        untracked_record(guard.decode(chunk)) for chunk in raw.split(b"\0") if chunk
    ]


def working_scope_entries(snapshot: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    entries.extend(parse_diff_entries((snapshot / "staged.diff").read_bytes(), "staged"))
    entries.extend(parse_diff_entries((snapshot / "working.diff").read_bytes(), "working"))
    entries.extend(untracked_entries(snapshot))
    return entries


def range_source(expression: str) -> str:
    """The inventory `source` for a committed range.

    A distinct source per range expression (rather than the shared literal
    "range") keeps ids from two declared range scopes disjoint even when they
    touch the same path at the same hunk index; the digest is a pure function
    of the expression -- `hashlib`, never the process-salted builtin `hash` --
    so a re-run of `inventory` is idempotent across processes.
    """
    return f"range@{hashlib.sha256(expression.encode('utf-8')).hexdigest()[:8]}"


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
            guard.diff_argv("--binary", "--full-index", "--no-ext-diff", expression),
            cwd=ctx["root"],
        )
    except guard.GuardError as exc:
        raise guard.GuardError(
            f"커밋 범위를 해석하지 못했습니다: {expression}",
            reason="ledger_range_unresolved",
            range=expression,
        ) from exc
    return parse_diff_entries(diff, range_source(expression))


def live_scope_entries(ctx: dict[str, Path], scopes: list[str]) -> list[dict[str, Any]]:
    """Build the denominator from the live worktree, not the snapshot.

    The snapshot holds the pre-fix diff, so a post-fix generation must read
    current state instead.
    """
    entries: list[dict[str, Any]] = []
    for scope in scopes:
        if scope != "working":
            entries.extend(range_scope_entries(ctx, scope))
            continue
        entries.extend(
            parse_diff_entries(
                guard.run_git(
                    guard.diff_argv(
                        "--cached", "--binary", "--full-index", "--no-ext-diff"
                    ),
                    cwd=ctx["root"],
                ),
                "staged",
            )
        )
        entries.extend(
            parse_diff_entries(
                guard.run_git(
                    guard.diff_argv("--binary", "--full-index", "--no-ext-diff"),
                    cwd=ctx["root"],
                ),
                "working",
            )
        )
        entries.extend(untracked_record(path) for path in guard.list_untracked(ctx["root"]))
    return entries


def generation_name(iteration: int, fingerprint: str) -> str:
    """`gen-<NN>-<fingerprint prefix>`, the generation directory name.

    `coverage` recovers the prefix with `rsplit("-", 1)` and checks it against
    the live fingerprint, so the truncation length lives here only -- callers
    pass the full fingerprint rather than each slicing their own prefix.
    """
    return f"{GENERATION_PREFIX}-{iteration:02d}-{fingerprint[:FINGERPRINT_PREFIX_LEN]}"


def write_inventory(gen_dir: Path, entries: list[dict[str, Any]]) -> None:
    """Replace a generation's inventory atomically.

    Written to a temp file in the same directory and then `os.replace`d onto
    the target, matching `write_run`'s existing pattern. Writing in place
    (the prior approach) truncates the file first, so a crash mid-write left
    an empty `inventory.jsonl` that `read_jsonl` reports as `[]` rather than
    as an error -- an empty denominator that the gate would otherwise wrongly
    treat as fully covered.
    """
    tmp = gen_dir / f"{INVENTORY_NAME}.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        for entry in entries:
            stream.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    os.replace(tmp, gen_dir / INVENTORY_NAME)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read append-only records, tolerating one torn trailing line.

    A crash during append can leave a partial last line. That must not
    invalidate every record written before it.

    Every surviving record must also be an object. `json.loads` happily
    returns a scalar or a list, and callers then do `record.get(...)` or
    `entry["id"]`, which raises `AttributeError`/`TypeError`/`KeyError` --
    exception types that `guard.ledger_gate`'s `except ledger.guard.GuardError`
    wrapper does not catch, so the carefully built `ledger_corrupt` diagnosis
    is lost and guard exits 3 with no `reason` at all. Reject the shape here,
    where it can still be named.

    `line=` is the real 1-based file line number, not the index among
    non-blank lines, so the number can be used to find the record.
    """
    if not path.is_file():
        return []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    numbered = [
        (number, line) for number, line in enumerate(raw_lines, 1) if line.strip()
    ]
    records: list[dict[str, Any]] = []
    for position, (number, line) in enumerate(numbered):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if position == len(numbered) - 1:
                break
            raise guard.GuardError(
                "원장 레코드가 손상되었습니다.",
                reason="ledger_corrupt",
                path=str(path),
                line=number,
            )
        if not isinstance(record, dict):
            raise guard.GuardError(
                "원장 레코드가 object가 아닙니다.",
                reason="ledger_corrupt",
                path=str(path),
                line=number,
            )
        records.append(record)
    return records


def drop_torn_tail(path: Path) -> bool:
    """Truncate an unterminated trailing line. Returns True if one was dropped.

    Every record is written with its newline in a single `write`, so a file
    that does not end in one was cut short by a crash and its last line is a
    partial record. `read_jsonl` already treats that line as absent; this
    makes the file agree, which is what keeps the tolerance true across the
    next append.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return False
    if not raw or raw.endswith(b"\n"):
        return False
    os.truncate(path, raw.rfind(b"\n") + 1)
    return True


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Append records, dropping a torn trailing line first.

    `read_jsonl` tolerates one unparsable last line, but that tolerance only
    held until the next write: appending straight onto a line with no
    terminating newline concatenated the new record onto the torn fragment.
    The batch then reported success while being invisible to `coverage`, and
    the batch after that made the mangled line non-last, turning the whole
    file into a permanent `ledger_corrupt` with no recovery command.
    """
    if not records:
        return
    drop_torn_tail(path)
    payload = "".join(
        json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n" for record in records
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def active_generation_dir(ledger_dir: Path, data: dict[str, Any]) -> Path:
    name = data.get("active_generation") or ""
    if not name:
        raise guard.GuardError(
            "활성 세대가 없습니다. inventory를 먼저 실행하십시오.",
            reason="ledger_no_generation",
        )
    return ledger_dir / name


def inventory_entry_id(record: dict[str, Any], path: Path) -> str:
    """Return an inventory record's id, or fail closed as `ledger_corrupt`.

    `read_jsonl` guarantees a dict; it cannot guarantee the fields. Indexing
    `record["id"]` directly raised a bare `KeyError` that `guard.ledger_gate`'s
    `except ledger.guard.GuardError` wrapper does not catch, so guard exited 3
    with no `reason` instead of naming the corruption.
    """
    identifier = record.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise guard.GuardError(
            "원장 inventory 레코드에 id가 없습니다.",
            reason="ledger_corrupt",
            path=str(path),
        )
    return identifier


def inventory_ids(gen_dir: Path) -> set[str]:
    path = gen_dir / INVENTORY_NAME
    return {inventory_entry_id(record, path) for record in read_jsonl(path)}


PENDING_SAMPLE_LIMIT = 20


def scope_sources(scope: str) -> set[str]:
    """The `source` values a declared scope can contribute to the inventory."""
    if scope == "working":
        return {"staged", "working", "untracked"}
    return {range_source(scope[len("range:") :])} if scope.startswith("range:") else set()


def scopes_without_entries(
    data: dict[str, Any], per_scope: dict[str, dict[str, int]]
) -> list[str]:
    """Declared scopes that contributed nothing to the denominator.

    `coverage`'s `scopes` list is built from the entries themselves, so a
    scope that produced none simply never appears -- a `/cr pr|--base|--range`
    whose range resolved to zero commits (stale base, already-merged branch,
    wrong period window) reported 100% coverage with no trace of the scope
    anywhere. An empty range is legitimately an empty review and must not
    block, but it must be visible, so name it instead of dropping it.
    """
    return [
        scope
        for scope in (data.get("scopes") or [])
        if isinstance(scope, str) and not (scope_sources(scope) & set(per_scope))
    ]


def latest_verdicts(gen_dir: Path) -> dict[str, str]:
    """Collapse the append-only log so the last write for an id wins."""
    resolved: dict[str, str] = {}
    for record in read_jsonl(gen_dir / HUNKS_NAME):
        identifier = record.get("id")
        if isinstance(identifier, str):
            resolved[identifier] = record.get("verdict", "UNKNOWN")
    return resolved


def coverage(ctx: dict[str, Path], ledger_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Summarize the active generation's denominator against its verdicts.

    The no-generation case takes the same tail return with empty inputs rather
    than a hand-written second dict, so the two shapes cannot drift: a key
    added to one but not the other used to be a KeyError waiting for the first
    consumer that read it, and `by_verdict` had in fact already drifted to a
    bare `{}` where the populated path returns a zero-filled histogram.
    """
    generation = data.get("active_generation") or ""
    gen_dir = ledger_dir / generation if generation else None
    inventory_path = gen_dir / INVENTORY_NAME if gen_dir else None
    entries = read_jsonl(inventory_path) if inventory_path else []
    resolved = latest_verdicts(gen_dir) if gen_dir else {}

    by_verdict = {name: 0 for name in VERDICTS}
    pending: list[str] = []
    unknown: list[str] = []
    per_scope: dict[str, dict[str, int]] = {}

    for entry in entries:
        identifier = inventory_entry_id(entry, inventory_path)
        source = entry.get("source")
        if not isinstance(source, str) or not source:
            raise guard.GuardError(
                "원장 inventory 레코드에 source가 없습니다.",
                reason="ledger_corrupt",
                path=str(inventory_path),
                id=identifier,
            )
        bucket = per_scope.setdefault(source, {"total": 0, "covered": 0})
        bucket["total"] += 1
        verdict = resolved.get(identifier)
        if verdict is None:
            pending.append(identifier)
            continue
        # A value outside VERDICTS can only reach here through a hand-edited
        # or corrupted hunks.jsonl (cmd_record validates against VERDICTS at
        # write time). It must still fail closed: fold it into UNKNOWN rather
        # than let an unrecognized value slip through as "covered", since
        # coverage() feeds the gate directly and this design must never fail
        # open.
        if verdict not in VERDICTS:
            verdict = "UNKNOWN"
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        if verdict == "UNKNOWN":
            unknown.append(identifier)
            continue
        bucket["covered"] += 1

    if generation:
        current = guard.repository_fingerprint(ctx["root"])["fingerprint"]
        matches = current.startswith(generation.rsplit("-", 1)[-1])
    else:
        # No generation means "inventory has not run yet", not "the repository
        # moved". Reporting False here would be a sentinel that reads as a
        # mismatch, which is why the gate has to test `generation` first and
        # why SKILL.md's resume rule mistook the pre-inventory state for
        # ledger/repository divergence. None says "unknown".
        matches = None

    reviewers = (guard.read_json(gen_dir / REVIEWERS_NAME) or {}) if gen_dir else {}
    roles = reviewer_roles(reviewers, required_roles_for(data.get("skill")))

    return {
        # `complete` stays a statement about the hunk denominator. Reviewer
        # coverage is a second, independent axis the gate checks separately, so
        # that resume-after-compaction keeps reading `complete` as "which hunks
        # are left" rather than silently changing meaning.
        "complete": bool(generation) and not pending and not unknown,
        "fingerprint_matches_current": matches,
        "generation": generation,
        "total": len(entries),
        "pending": pending[:PENDING_SAMPLE_LIMIT],
        "pending_count": len(pending),
        "unknown": unknown[:PENDING_SAMPLE_LIMIT],
        "unknown_count": len(unknown),
        "by_verdict": by_verdict,
        "scopes": [
            {"source": source, **counts} for source, counts in sorted(per_scope.items())
        ],
        "scopes_declared": list(data.get("scopes") or []),
        "scopes_without_entries": scopes_without_entries(data, per_scope),
        "reviewers": reviewers,
        "reviewer_roles": roles,
        "reviewer_roles_missing": [
            role for role, status in roles.items() if status is None
        ],
        "reviewer_roles_unknown": [
            role for role, status in roles.items() if status == "UNKNOWN"
        ],
    }


def reviewer_roles(
    reviewers: dict[str, Any],
    required: tuple[str, ...] = DEFAULT_REVIEWER_ROLES,
) -> dict[str, str | None]:
    """Resolve recorded reviewer names onto the mandatory role keywords.

    A name satisfies a role when it contains that role's keyword, so both
    `cca-security-reviewer` and an Agent Team teammate called
    `core-security-privacy-supply-chain` count for `security`, and one
    teammate covering two perspectives satisfies both.

    Where several names map to the same role the worst status wins: a run that
    recorded Security twice, once ACTIVE and once UNKNOWN, has an unresolved
    Security perspective and must not be able to hide it behind the other
    record.
    """
    severity = {"ACTIVE": 0, "N_A": 1, "UNKNOWN": 2}
    resolved: dict[str, str | None] = {role: None for role in required}
    for name, status in reviewers.items():
        if not isinstance(name, str):
            continue
        # An unrecognized status can only come from a hand-edited
        # reviewers.json; fold it into UNKNOWN so it fails closed exactly like
        # an out-of-range verdict does in the loop above.
        if status not in REVIEWER_STATUSES:
            status = "UNKNOWN"
        lowered = name.lower()
        for role in required:
            if role not in lowered:
                continue
            current = resolved[role]
            if current is None or severity[status] > severity[current]:
                resolved[role] = status
    return resolved


def cmd_init(args: argparse.Namespace) -> None:
    """Create the ledger, or merge newly declared scopes into an existing one.

    `init` is not destructive. The range scope of a `/cr pr|today|--base|
    --range` run is only known after the range has been computed, which
    happens after the ledger must already exist for resume-after-compaction to
    work, so declaring a scope late is the normal path rather than an error. A
    re-run that reset `iteration` and `active_generation` would orphan gen-02
    and every verdict recorded in it -- it fails closed, but it throws away
    completed work, and a post-compaction model re-reading SKILL.md is exactly
    who would do it.

    Scopes are therefore unioned, never replaced, and progress is preserved.
    Declaring a scope that is already present is a no-op. Adding a genuinely
    new scope widens the denominator, so the active generation's inventory is
    no longer the whole truth: `active_generation` is cleared so the next
    `inventory` rebuilds it. The gate reads that as `ledger_no_generation`
    until it does, and the rebuilt inventory is a superset of the old one, so
    verdicts already recorded in that generation stay valid.
    """
    scopes = validate_scopes(args.scope)
    _, _, ledger_dir, resolved_token = resolve_ledger(args.session, args.token)
    ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with LedgerLock(ledger_dir):
        existing = read_run_optional(ledger_dir)
        if existing is None:
            data: dict[str, Any] = {
                "session": guard.safe_session(args.session),
                "token": resolved_token,
                "stage": "init",
                "iteration": 1,
                "active_generation": "",
                "scopes": scopes,
                "skill": args.skill or "",
            }
            added = list(scopes)
        else:
            data = dict(existing)
            declared = list(data.get("scopes") or [])
            added = [scope for scope in scopes if scope not in declared]
            data["session"] = guard.safe_session(args.session)
            data["token"] = resolved_token
            data["scopes"] = declared + added
            # `/cr` calls `init` twice: once for `working` right after Guard
            # `begin`, then again for `range:<A>..<B>` once §2 has computed the
            # range. The second call need not repeat `--skill`, so an absent
            # value must not erase what the first call stored.
            if args.skill:
                data["skill"] = args.skill
            if added and data.get("active_generation"):
                data["active_generation"] = ""
                data["stage"] = "init"
        write_run(ledger_dir, data)
    guard.emit({"ok": True, **data, "scopes_added": added})


def cmd_status(args: argparse.Namespace) -> None:
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
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
            "scopes_declared": data["scopes"],
            **coverage(ctx, ledger_dir, data),
        }
    )


def all_findings(ledger_dir: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Every finding recorded in this run, oldest generation first.

    Reading only the active generation lost the entire report of any review
    that actually found something: a finding is recorded, `--fix` applies it,
    and §4's mandatory `advance` opens a generation whose `findings.jsonl` is
    empty. `report` then returned `findings: []` -- for exactly the runs that
    had findings -- while the records sat unreachable in the previous
    generation's directory. Only reviews that found nothing reported
    correctly. Each finding carries its generation so a fixed one can still be
    told apart from one found in the final pass.
    """
    findings: list[dict[str, Any]] = []
    active = data.get("active_generation") or ""
    for name in sorted(totals_by_generation(data) | ({active} if active else set())):
        for record in read_jsonl(ledger_dir / name / FINDINGS_NAME):
            findings.append({**record, "generation": name})
    return findings


def totals_by_generation(data: dict[str, Any]) -> set[str]:
    totals = data.get("inventory_totals")
    return set(totals) if isinstance(totals, dict) else set()


def cmd_report(args: argparse.Namespace) -> None:
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    data = read_run(ledger_dir)
    summary = coverage(ctx, ledger_dir, data)
    generation = data.get("active_generation") or ""
    findings = all_findings(ledger_dir, data)
    guard.emit(
        {
            "ok": True,
            "generation": generation,
            "iteration": data["iteration"],
            "coverage": summary,
            "verification": verification_summary(findings),
            "findings": findings,
        }
    )


def cmd_inventory(args: argparse.Namespace) -> None:
    """Build (or idempotently rebuild) the active generation's denominator.

    The `working` scope is derived from the snapshot only while the snapshot
    is still the truth, i.e. while the repository fingerprint is unchanged
    since `begin`. Otherwise it must come from the live worktree -- the same
    rule `cmd_advance` follows -- because a stale snapshot cannot contain the
    hunks an edit created. Re-reading the snapshot then would shrink the
    denominator back to the pre-edit set and rewrite `inventory_totals` to
    match, so the mismatch check would not fire and those hunks would never be
    reviewed.

    Keying that choice on `iteration > 1` was not enough: `cmd_init` clears
    `active_generation` to widen a scope but deliberately leaves `iteration`
    alone, so a re-`inventory` after an edit still took the snapshot branch
    while `generation_name` stamped the generation with the *current*
    fingerprint. The names then agreed, `ledger_stale` could not fire, and the
    gate passed with the edit's hunks absent from the denominator. Comparing
    fingerprints instead makes the content and the name always agree.

    An inventory that already exists for the active generation is never
    silently replaced by a different one. An identical id set is idempotent,
    as before; a different one means the reviewed surface moved under a
    generation whose verdicts were recorded against the old denominator, and
    is refused as `ledger_inventory_conflict`. `advance` is the supported way
    to move to a new denominator, and `init` clears `active_generation` when a
    new scope widens it.
    """
    ctx, snapshot, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        iteration = int(data["iteration"])
        active = data["active_generation"] or ""
        fingerprint = guard.repository_fingerprint(ctx["root"])["fingerprint"]
        name = active or generation_name(iteration, fingerprint)
        gen_dir = ledger_dir / name

        snapshot_fingerprint = (
            (guard.read_json(snapshot / guard.MARKER_NAME) or {}).get("fingerprint") or {}
        ).get("fingerprint")
        snapshot_is_current = snapshot_fingerprint == fingerprint

        entries: list[dict[str, Any]] = []
        if iteration > 1 or not snapshot_is_current:
            entries.extend(live_scope_entries(ctx, data["scopes"]))
        else:
            for scope in data["scopes"]:
                if scope == "working":
                    entries.extend(working_scope_entries(snapshot))
                else:
                    entries.extend(range_scope_entries(ctx, scope))

        if active and (gen_dir / INVENTORY_NAME).is_file():
            previous = inventory_ids(gen_dir)
            current = {entry["id"] for entry in entries}
            if previous != current:
                raise guard.GuardError(
                    "활성 세대의 inventory가 이미 다른 내용으로 존재합니다. "
                    "수정 후에는 advance로 새 세대를 여십시오.",
                    reason="ledger_inventory_conflict",
                    generation=name,
                    added=sorted(current - previous)[:PENDING_SAMPLE_LIMIT],
                    removed=sorted(previous - current)[:PENDING_SAMPLE_LIMIT],
                    added_count=len(current - previous),
                    removed_count=len(previous - current),
                )

        gen_dir.mkdir(mode=0o700, exist_ok=True)
        write_inventory(gen_dir, entries)

        data["active_generation"] = name
        data["stage"] = "inventory"
        totals = dict(data.get("inventory_totals") or {})
        totals[name] = len(entries)
        data["inventory_totals"] = totals
        write_run(ledger_dir, data)

    guard.emit({"ok": True, "generation": name, "total": len(entries), "entries": entries})


def cmd_seal(args: argparse.Namespace) -> None:
    """Record that the review gate passed, before the command mutates the repo.

    `/cca` closes its review and then deliberately stages and commits. Those
    writes move HEAD and empty the working tree, so the generation fingerprint
    stops matching and every later gate reports `ledger_stale` -- a true
    statement about a ledger that is not actually unfinished. Sealing lets the
    gate tell the command's own commits apart from unreviewed drift.

    The seal runs the gate's own checks, so it cannot be used to skip them: an
    incomplete denominator or a missing required perspective refuses here
    exactly as it would at `finish`. Only a run that would have passed can
    seal.
    """
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        summary = coverage(ctx, ledger_dir, data)
        failure = guard.ledger_gate_failure(
            data,
            summary,
            empty_denominator_is_wrong=guard.denominator_should_be_nonempty(
                data, summary, ledger_dir.parent
            ),
        )
        if failure:
            raise guard.GuardError(
                "원장이 완결되지 않아 봉인할 수 없습니다.",
                reason=failure,
                pending_count=summary["pending_count"],
                pending=summary["pending"],
                reviewer_roles_missing=summary["reviewer_roles_missing"],
                reviewer_roles_unknown=summary["reviewer_roles_unknown"],
            )
        sealed = {
            "generation": summary["generation"],
            "fingerprint": guard.repository_fingerprint(ctx["root"])["fingerprint"],
            "total": summary["total"],
        }
        data["sealed"] = sealed
        write_run(ledger_dir, data)
    guard.emit({"ok": True, "sealed": sealed, "coverage": summary})


def cmd_advance(args: argparse.Namespace) -> None:
    """Open a new generation for a repository state the active one predates.

    `advance` is destructive by design: the new generation starts with an
    empty `hunks.jsonl`, so every verdict has to be re-recorded against the
    new denominator. That is correct after a fix, and catastrophic when the
    command is repeated -- `active_generation` only ever moves forward, so a
    second `advance` on an unchanged repository silently strands a fully
    verdicted generation with no way back. `--fingerprint` alone does not
    prevent it: it only proves the caller re-read the *current* fingerprint,
    never that anything changed. Refuse the no-op explicitly.
    """
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    current = guard.repository_fingerprint(ctx["root"])["fingerprint"]
    if args.fingerprint != current:
        raise guard.GuardError(
            "전달된 fingerprint가 현재 저장소 상태와 다릅니다.",
            reason="ledger_fingerprint_mismatch",
            expected=current,
            received=args.fingerprint,
        )
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        active = data["active_generation"] or ""
        if active and active.rsplit("-", 1)[-1] == current[:FINGERPRINT_PREFIX_LEN]:
            raise guard.GuardError(
                "활성 세대가 이미 현재 저장소 상태로 만들어져 있어 전이할 것이 없습니다. "
                "수정을 적용한 뒤 다시 실행하십시오.",
                reason="ledger_advance_noop",
                generation=active,
                fingerprint=current,
            )
        data["iteration"] = int(data["iteration"]) + 1
        name = generation_name(data["iteration"], current)
        gen_dir = ledger_dir / name
        gen_dir.mkdir(mode=0o700, exist_ok=True)

        entries = live_scope_entries(ctx, data["scopes"])
        write_inventory(gen_dir, entries)

        data["active_generation"] = name
        data["stage"] = "review"
        # A new generation is new review work, so any earlier seal no longer
        # describes it. Leaving the seal would let a post-fix run skip the gate
        # on the strength of a pass that covered the pre-fix denominator.
        data.pop("sealed", None)
        totals = dict(data.get("inventory_totals") or {})
        totals[name] = len(entries)
        data["inventory_totals"] = totals
        write_run(ledger_dir, data)

    guard.emit(
        {"ok": True, "generation": name, "iteration": data["iteration"], "total": len(entries)}
    )


def _require_list_of_dicts(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Validate `payload[key]` is absent, or a list whose elements are all objects.

    record's stdin is model-authored input reaching the ledger directly, so a
    malformed shape here must fail closed as `ledger_bad_input` rather than
    raise `AttributeError`/`KeyError` deeper in `cmd_record` when a caller
    later does `.get(...)` on an element that turned out not to be a dict.
    """
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise guard.GuardError(
            f"{key}는 object의 list여야 합니다.", reason="ledger_bad_input", field=key
        )
    return value


def _require_str_field(record: dict[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise guard.GuardError(
            f"{label} 항목의 {field}는 비어 있지 않은 문자열이어야 합니다.",
            reason="ledger_bad_input",
            field=field,
        )
    return value


def _require_str_list_field(record: dict[str, Any], field: str, label: str) -> None:
    value = record.get(field)
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise guard.GuardError(
            f"{label} 항목의 {field}는 문자열 list여야 합니다.",
            reason="ledger_bad_input",
            field=field,
        )


def _require_enum_field(
    record: dict[str, Any],
    field: str,
    allowed: tuple[str, ...],
    label: str,
    reason: str,
) -> None:
    value = record.get(field)
    if value is None:
        return
    if value not in allowed:
        raise guard.GuardError(
            f"{label} 항목의 {field} 값이 허용되지 않습니다: {value}",
            reason=reason,
            field=field,
            id=record.get("id"),
            allowed=list(allowed),
        )


def _require_confidence_field(record: dict[str, Any], label: str) -> None:
    value = record.get("confidence")
    if value is None:
        return
    # `bool` subclasses `int`, so `True` would pass an isinstance check and sit
    # inside the range as 1 -- the lowest confidence there is. Accepting it
    # would turn a type error into a silent "reject this finding".
    if isinstance(value, bool) or not isinstance(value, int):
        raise guard.GuardError(
            f"{label} 항목의 confidence는 정수여야 합니다: {value!r}",
            reason="ledger_invalid_confidence",
            field="confidence",
            id=record.get("id"),
        )
    if not CONFIDENCE_MIN <= value <= CONFIDENCE_MAX:
        raise guard.GuardError(
            f"{label} 항목의 confidence는 "
            f"{CONFIDENCE_MIN}~{CONFIDENCE_MAX} 범위여야 합니다: {value}",
            reason="ledger_invalid_confidence",
            field="confidence",
            id=record.get("id"),
            min=CONFIDENCE_MIN,
            max=CONFIDENCE_MAX,
        )


def verification_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    """Count how each reported finding was verified, per review-execution.md §3.6.

    The skill must report ISOLATED/SELF/UNVERIFIED counts, and `cr/SKILL.md` §7
    forbids tallying coverage numbers from memory -- so the numbers have to come
    from here. Counts mirror the `findings` list exactly (one entry per recorded
    finding per generation), which is why a finding re-recorded in a later
    generation is counted in each: the summary and the list it summarizes must
    never disagree.

    A finding with no `verification` counts as UNVERIFIED. Absent and explicitly
    unverified mean the same thing to the gate, and collapsing them keeps the
    count honest for reviewers that never reached §3.6.
    """
    counts = {"isolated": 0, "self": 0, "unverified": 0, "rejected": 0, "total": 0}
    for finding in findings:
        counts["total"] += 1
        value = finding.get("verification") or "UNVERIFIED"
        if value == "ISOLATED":
            counts["isolated"] += 1
        elif value == "SELF":
            counts["self"] += 1
        else:
            counts["unverified"] += 1
        if finding.get("status") == "REJECTED":
            counts["rejected"] += 1
    return counts


def cmd_record(args: argparse.Namespace) -> None:
    # Read the raw bytes and decode as UTF-8 explicitly. `json.load(sys.stdin)`
    # decodes with the locale codec, so the Korean finding text this package
    # pipes in raises UnicodeDecodeError on a Windows console codepage (cp949,
    # cp1252) or silently stores mojibake (cp437) -- and UnicodeDecodeError is
    # not a JSONDecodeError, so it escaped as exit 3 with no `reason` instead
    # of `ledger_bad_input`.
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise guard.GuardError(
            "record 입력 JSON을 읽을 수 없습니다. UTF-8 JSON이어야 합니다.",
            reason="ledger_bad_input",
        ) from exc
    if not isinstance(payload, dict):
        raise guard.GuardError(
            "record 입력은 JSON object여야 합니다.", reason="ledger_bad_input"
        )

    verdicts = _require_list_of_dicts(payload, "verdicts")
    findings = _require_list_of_dicts(payload, "findings")
    reviewers = _require_list_of_dicts(payload, "reviewers")

    # Shape-validate every element before any semantic check (unknown id,
    # invalid verdict, missing finding) and before any write, so a batch
    # rejected for a malformed shape leaves the ledger untouched exactly like
    # one rejected for a semantic reason.
    for verdict in verdicts:
        _require_str_field(verdict, "id", "verdicts")
        _require_str_list_field(verdict, "finding_ids", "verdicts")
    for finding in findings:
        _require_str_field(finding, "id", "findings")
        _require_enum_field(
            finding, "severity", FINDING_SEVERITIES, "findings", "ledger_invalid_severity"
        )
        _require_enum_field(
            finding, "status", FINDING_STATUSES, "findings", "ledger_invalid_finding_status"
        )
        _require_enum_field(
            finding, "verification", VERIFICATIONS, "findings", "ledger_invalid_verification"
        )
        _require_confidence_field(finding, "findings")
    for reviewer in reviewers:
        _require_str_field(reviewer, "name", "reviewers")
        status = reviewer.get("status", "UNKNOWN")
        if status not in REVIEWER_STATUSES:
            raise guard.GuardError(
                f"허용되지 않는 reviewer 상태입니다: {status}",
                reason="ledger_invalid_reviewer_status",
                name=reviewer.get("name"),
                allowed=list(REVIEWER_STATUSES),
            )

    _, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        gen_dir = active_generation_dir(ledger_dir, data)
        known = inventory_ids(gen_dir)
        finding_ids = {record.get("id") for record in read_jsonl(gen_dir / FINDINGS_NAME)}
        finding_ids.update(record.get("id") for record in findings)

        for verdict in verdicts:
            identifier = verdict.get("id")
            if identifier not in known:
                raise guard.GuardError(
                    f"inventory에 없는 id입니다: {identifier}",
                    reason="ledger_unknown_id",
                    id=identifier,
                )
            if verdict.get("verdict") not in VERDICTS:
                raise guard.GuardError(
                    f"허용되지 않는 판정입니다: {verdict.get('verdict')}",
                    reason="ledger_invalid_verdict",
                    id=identifier,
                )
            if verdict.get("verdict") == "FINDING":
                linked = verdict.get("finding_ids") or []
                missing = [value for value in linked if value not in finding_ids]
                if not linked or missing:
                    raise guard.GuardError(
                        "FINDING 판정에는 대응하는 finding 레코드가 필요합니다.",
                        reason="ledger_finding_missing",
                        id=identifier,
                        missing=missing,
                    )

        append_jsonl(gen_dir / FINDINGS_NAME, findings)
        append_jsonl(gen_dir / HUNKS_NAME, verdicts)
        if reviewers:
            existing = guard.read_json(gen_dir / REVIEWERS_NAME) or {}
            for reviewer in reviewers:
                existing[reviewer["name"]] = reviewer.get("status", "UNKNOWN")
            tmp = gen_dir / f"{REVIEWERS_NAME}.tmp"
            tmp.write_text(json.dumps(existing, ensure_ascii=True, indent=2), encoding="utf-8")
            os.replace(tmp, gen_dir / REVIEWERS_NAME)

        data["stage"] = "review"
        write_run(ledger_dir, data)

    guard.emit(
        {
            "ok": True,
            "recorded_verdicts": len(verdicts),
            "recorded_findings": len(findings),
            "recorded_reviewers": len(reviewers),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the ledger for an owned snapshot")
    init.add_argument("--session", required=True)
    init.add_argument("--token")
    init.add_argument("--scope", action="append", default=[])
    init.add_argument(
        "--skill",
        help="이 원장을 만든 skill 이름(예: cr). 필수 reviewer 관점 집합을 결정한다",
    )

    status = sub.add_parser("status", help="Report ledger progress and coverage")
    status.add_argument("--session", required=True)
    status.add_argument("--token")

    inventory = sub.add_parser("inventory", help="Build the machine-owned denominator")
    inventory.add_argument("--session", required=True)
    inventory.add_argument("--token")

    record = sub.add_parser("record", help="Append verdicts, findings and reviewer status")
    record.add_argument("--session", required=True)
    record.add_argument("--token")

    seal = sub.add_parser("seal", help="Record that the review gate passed before staging")
    seal.add_argument("--session", required=True)
    seal.add_argument("--token")

    advance = sub.add_parser("advance", help="Open a new generation after a fix")
    advance.add_argument("--session", required=True)
    advance.add_argument("--token")
    advance.add_argument("--fingerprint", required=True)

    report = sub.add_parser("report", help="Emit findings and coverage for the final report")
    report.add_argument("--session", required=True)
    report.add_argument("--token")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {
        "init": cmd_init,
        "seal": cmd_seal,
        "status": cmd_status,
        "inventory": cmd_inventory,
        "record": cmd_record,
        "advance": cmd_advance,
        "report": cmd_report,
    }
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
