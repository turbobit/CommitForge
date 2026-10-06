#!/usr/bin/env python3
"""PreToolUse gate that keeps Bash commands from discarding uncommitted work.

Guard's conservation check reports a loss only after the fact, and only when
the model calls it correctly. One /ccf run mistyped its token so every Guard
call failed, then reordered commits with `checkout <commit> -- .`,
`reset --hard` and cherry-pick, ran `clean` unasked, and finally deleted its own
snapshot and recovery ref. This hook stops those steps before they run.

It is registered for every session because another session can discard the
work of a run that holds the worktree lock. What it enforces:

- While the CommitForge lock of the worktree a git command acts on exists,
  git runs only from an allowlist: read-only commands, `add`, `commit` without
  `--amend`, `restore --staged`, `apply --cached`, `rm --cached`, `/cp`'s
  `switch -c <branch>` and a few read forms. Anything it cannot resolve
  statically (variables, substitutions, aliases, unknown wrappers, code fed to
  shells) is denied rather than guessed. Commands that move shared refs or
  remove worktrees honour a lock held in any worktree of the repository.
- Guard calls must name the hook's own session, and `clean` needs the user's
  latest prompt to be `/<CommitForge command> clean`.
- Deleting snapshots, the lock or `refs/commitforge` is denied with or without
  a lock. This part is best effort: it resolves globs, `cd`, tracked shell
  variables and xargs/find pipelines, but a script file run by an interpreter
  is not inspected.

The bash subset parser below is deliberately conservative: when it cannot tell
what bash would run, a held lock turns that into a denial.

Malformed hook input fails open, and so does a missing script (the installer
wraps the hook in a launcher), since this hook gates every Bash call.
"""

from __future__ import annotations

import json
import re
import sys


NEEDS_CHECK = re.compile(
    r"git|guard|claude-|commitforge|[$`\\]"
    r"|\b(?:eval|source|exec|xargs|find|parallel|sudo|doas|env|nice|timeout|nohup"
    r"|bash|sh|zsh|dash|ksh|fish|python[0-9.]*|node|perl|ruby|php|osascript|deno|bun"
    r"|rm|rmdir|unlink|mv|shred|trash|srm|truncate)\b"
    r"|(?:^|[\s;&|(])\.\s|>"
)


def main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not NEEDS_CHECK.search(command):
        return 0
    # Deferred so the common case pays only for json and re. The installer's
    # launcher runs this file with exec, so its directory is not on sys.path.
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from worktree_gate_impl import evaluate

    denial = evaluate(event, command)
    if denial is None:
        return 0
    sys.stderr.buffer.write((denial + "\n").encode("utf-8"))
    sys.stderr.flush()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
