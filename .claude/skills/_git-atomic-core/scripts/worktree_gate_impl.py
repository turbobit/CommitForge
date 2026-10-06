"""Decision logic for worktree_gate.py; see that file for the policy."""

from __future__ import annotations

import fnmatch
import glob
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, Iterator, List, Optional, Tuple


# Mirrors guard.py; tests assert they stay equal.
LOCK_DIR_NAME = "claude-atomic.lock"
SNAPSHOT_DIR_NAME = "claude-atomic-snapshots"
MARKER_NAMES = {LOCK_DIR_NAME, SNAPSHOT_DIR_NAME}
EVIDENCE_TEXT = re.compile(r"claude-atomic|refs/commitforge|commitforge/recovery")
# Looser text match for values the gate cannot resolve (variables, inline
# interpreter code, xargs input): any mention of the recovery copies' home.
RECOVERY_TEXT = re.compile(r"commitforge|\.claude\b", re.IGNORECASE)
# macOS and Windows default filesystems ignore case: `~/.CLAUDE` is `~/.claude`.
CASE_INSENSITIVE = sys.platform in ("darwin", "win32")
LEDGER_LOCK = re.compile(r"/" + SNAPSHOT_DIR_NAME + r"/[^/]+/ledger/\.lock$")
COMMITFORGE_COMMANDS = {"cc", "ccr", "cf", "cfr", "ccf", "cr", "cca", "cp", "cpr"}
GUARD_SCRIPTS = {"guard.sh", "guard.py"}
SESSION_BOUND_GUARD = {
    "begin", "snapshot", "conserve", "finish", "abort", "verify-review",
    "audit-snapshot", "release-snapshot", "session-end",
}
MAX_DEPTH = 6
MAX_SCRIPT_BYTES = 512 * 1024

OPERATORS = sorted(
    [
        "&&", "||", ";;&", ";;", ";&", "|&", "&>>", "&>", ">>", ">&", ">|",
        "<<<", "<<-", "<<", "<&", "<>", ";", "&", "|", "(", ")", "<", ">", "\n",
    ],
    key=len,
    reverse=True,
)
REDIRECT_OPS = {"&>>", "&>", ">>", ">&", ">|", "<<<", "<<-", "<<", "<&", "<>", "<", ">"}
WRITE_REDIRECTS = {"&>>", "&>", ">>", ">&", ">|", "<>", ">"}
WORD_BREAK = set(" \t\r\n;&|()<>")
SPECIAL_VARS = set("@*#?$!-0123456789")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\+?=")

RESERVED_PREFIX = {"!", "{", "then", "do", "else", "elif", "if", "while", "until", "time", "}"}
RESERVED_SKIP = {"for", "select", "case", "function", "[[", "[", "test", "fi", "done", "esac", "]]"}
WRAPPERS = {
    "sudo", "doas", "nice", "timeout", "gtimeout", "nohup", "time", "command", "builtin",
    "exec", "env", "stdbuf", "ionice", "caffeinate", "chronic", "unbuffer", "watch",
    "flock", "setsid", "xargs", "parallel",
}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
INTERPRETER_CODE_FLAGS = {
    "python": {"-c"},
    "node": {"-e", "--eval", "-p", "--print"},
    "perl": {"-e", "-E"},
    "ruby": {"-e"},
    "php": {"-r"},
    "osascript": {"-e"},
    "deno": {"eval"},
    "bun": {"-e", "--eval"},
}
# Short options whose value is attached to them, ending a cluster (`-W...`).
CLUSTER_VALUE_LETTERS = {"python": "WX", "perl": "0CdDiIlmMx", "ruby": "0CEFIKlrTx"}
REMOVERS = {"rm", "rmdir", "unlink", "mv", "shred", "trash", "srm", "truncate"}
# Programs that overwrite their destination; checked like a `>` redirection.
OVERWRITERS = {"cp", "install", "ln", "rsync", "tee", "dd"}
# Options taking the wrapped command's working directory.
CHDIR_OPTIONS = {"env": {"-C", "--chdir"}, "sudo": {"-D", "--chdir"}}
REMOVE_HINT = re.compile(r"rmtree|unlink|remove|rmdir|\brm\b|delete|update-ref")
GIT_WORD = re.compile(r"\bgit\b")
GIT_DESTRUCTIVE_WORD = re.compile(
    r"\b(reset|stash|clean|rebase|cherry-pick|checkout|restore|switch|revert|merge|pull"
    r"|update-ref|read-tree|checkout-index|worktree|filter-branch|filter-repo|am|mv|rm"
    r"|apply|amend|branch|symbolic-ref|gc|prune|reflog)\b"
)

GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
READ_ONLY = {
    "status", "diff", "log", "show", "ls-files", "ls-tree", "cat-file", "rev-parse",
    "rev-list", "merge-base", "describe", "blame", "annotate", "grep", "shortlog",
    "for-each-ref", "show-ref", "check-attr", "check-ignore", "check-mailmap",
    "check-ref-format", "diff-tree", "diff-index", "diff-files", "name-rev", "var",
    "version", "help", "count-objects", "ls-remote", "whatchanged", "show-branch",
    "verify-commit", "verify-tag", "cherry", "range-diff", "fsck", "column",
    "interpret-trailers", "get-tar-commit-id",
}
ALWAYS_DENIED = {
    "reset", "rebase", "cherry-pick", "revert", "merge", "pull", "am", "mv", "read-tree",
    "checkout-index", "filter-branch", "filter-repo", "update-ref", "update-index",
    "notes", "replace", "bisect", "rerere", "sparse-checkout", "gc", "prune", "repack",
    "maintenance", "init", "clone", "archive", "format-patch", "pack-refs", "prune-packed",
    "write-tree", "commit-tree", "hash-object", "mktree", "mktag", "restore-index",
    "difftool", "mergetool", "citool", "gui", "send-email", "request-pull", "bundle",
}
FLAG_CHECKED = {
    "add", "stage", "commit", "restore", "apply", "rm", "checkout", "switch", "branch",
    "tag", "stash", "clean", "worktree", "submodule", "reflog", "symbolic-ref", "push",
    "fetch", "config", "remote",
}
KNOWN_SUBCOMMANDS = READ_ONLY | ALWAYS_DENIED | FLAG_CHECKED
SHARED_REF_SUBCOMMANDS = {
    "update-ref", "branch", "worktree", "gc", "prune", "repack", "maintenance",
    "reflog", "filter-branch", "filter-repo", "symbolic-ref", "replace", "pack-refs",
}
# Allowed whatever their arguments, so values xargs/find append are harmless.
ARGUMENT_FREE = READ_ONLY | {"add", "stage", "config", "remote"}


class Deny(Exception):
    pass


# --------------------------------------------------------------------------
# Lexer: the subset of bash that decides which simple commands run.


class Word:
    __slots__ = ("parts", "substs")

    def __init__(self) -> None:
        # (kind, text): lit (unquoted), qlit (quoted), var, home, subst
        self.parts: List[Tuple[str, str]] = []
        self.substs: List[str] = []

    @classmethod
    def literal(cls, text: str) -> "Word":
        word = cls()
        word.add("qlit", text)
        return word

    def add(self, kind: str, text: str) -> None:
        if kind in {"lit", "qlit"} and self.parts and self.parts[-1][0] == kind:
            self.parts[-1] = (kind, self.parts[-1][1] + text)
        else:
            self.parts.append((kind, text))

    def unquoted(self) -> Optional[str]:
        """The text when the word is a single unquoted literal (reserved words)."""
        if len(self.parts) == 1 and self.parts[0][0] == "lit":
            return self.parts[0][1]
        return None

    def raw(self) -> str:
        out = []
        for kind, text in self.parts:
            if kind == "var":
                out.append("${" + text + "}")
            elif kind == "subst":
                out.append("$(" + text + ")")
            elif kind == "home":
                out.append("~")
            else:
                out.append(text)
        return "".join(out)

    def has_pattern(self) -> bool:
        return any(
            kind == "lit" and (re.search(r"[*?\[]", text) or ("{" in text and "}" in text))
            for kind, text in self.parts
        )


class Lexer:
    def __init__(self, source: str) -> None:
        self.s = source
        self.i = 0
        self.n = len(source)
        self.tokens: List[Tuple[str, Any]] = []
        self.pending: List[Tuple[str, Dict[str, Any]]] = []

    def run(self) -> List[Tuple[str, Any]]:
        s = self.s
        while self.i < self.n:
            c = s[self.i]
            if c in " \t\r":
                self.i += 1
            elif s.startswith("\\\n", self.i):
                self.i += 2
            elif c == "#":
                end = s.find("\n", self.i)
                self.i = self.n if end < 0 else end
            elif c == "\n":
                self.tokens.append(("op", "\n"))
                self.i += 1
                self.read_heredocs()
            elif s.startswith("<(", self.i) or s.startswith(">(", self.i):
                body, self.i = self.paren_body(self.i + 2)
                word = Word()
                word.add("subst", body)
                word.substs.append(body)
                self.tokens.append(("word", word))
            else:
                op = next((o for o in OPERATORS if s.startswith(o, self.i)), None)
                if op is not None:
                    self.i += len(op)
                    self.tokens.append(("op", op))
                    if op in {"<<", "<<-"}:
                        self.read_heredoc_delimiter(strip_tabs=op == "<<-")
                    continue
                word, _ = self.read_word()
                if self.i < self.n and s[self.i] in "<>" and word.unquoted() is not None and word.unquoted().isdigit():
                    continue  # file descriptor prefix such as 2>&1
                self.tokens.append(("word", word))
        return self.tokens

    def read_heredoc_delimiter(self, *, strip_tabs: bool) -> None:
        while self.i < self.n and self.s[self.i] in " \t":
            self.i += 1
        if self.i >= self.n or self.s[self.i] in WORD_BREAK:
            return
        word, quoted = self.read_word()
        holder: Dict[str, Any] = {"body": "", "quoted": quoted, "strip": strip_tabs}
        self.tokens.append(("word", word))
        self.tokens.append(("heredoc", holder))
        self.pending.append(("".join(text for _, text in word.parts), holder))

    def read_heredocs(self) -> None:
        for delimiter, holder in self.pending:
            lines = []
            while self.i < self.n:
                end = self.s.find("\n", self.i)
                end = self.n if end < 0 else end
                line = self.s[self.i:end]
                self.i = min(end + 1, self.n)
                check = line.lstrip("\t") if holder["strip"] else line
                if check == delimiter:
                    break
                lines.append(line)
            holder["body"] = "\n".join(lines)
        self.pending = []

    def read_word(self) -> Tuple[Word, bool]:
        s = self.s
        word = Word()
        quoted = False
        start = self.i
        while self.i < self.n:
            c = s[self.i]
            if c in WORD_BREAK:
                break
            if c == "\\":
                if self.i + 1 < self.n:
                    if s[self.i + 1] != "\n":
                        word.add("qlit", s[self.i + 1])
                        quoted = True
                    self.i += 2
                else:
                    self.i += 1
            elif c == "'":
                end = s.find("'", self.i + 1)
                end = self.n if end < 0 else end
                word.add("qlit", s[self.i + 1:end])
                quoted = True
                self.i = end + 1
            elif c == "$" and s.startswith("$'", self.i):
                j = self.i + 2
                while j < self.n and s[j] != "'":
                    j += 2 if s[j] == "\\" else 1
                word.add("qlit", s[self.i + 2:j])
                quoted = True
                self.i = j + 1
            elif c == "$" and s.startswith('$"', self.i):
                self.i += 1
            elif c == '"':
                self.i += 1
                self.read_dquote(word)
                quoted = True
            elif c in "$`" and self.read_dollar(word):
                pass
            elif c == "~" and self.i == start and (
                self.i + 1 >= self.n or s[self.i + 1] == "/" or s[self.i + 1] in WORD_BREAK
            ):
                word.add("home", "")
                self.i += 1
            else:
                word.add("lit", c)
                self.i += 1
        return word, quoted

    def read_dquote(self, word: Word) -> None:
        s = self.s
        while self.i < self.n:
            c = s[self.i]
            if c == '"':
                self.i += 1
                return
            if c == "\\" and self.i + 1 < self.n and s[self.i + 1] in '"\\$`\n':
                if s[self.i + 1] != "\n":
                    word.add("qlit", s[self.i + 1])
                self.i += 2
            elif c in "$`" and not s.startswith("$'", self.i) and not s.startswith('$"', self.i) and self.read_dollar(word):
                pass
            else:
                word.add("qlit", c)
                self.i += 1

    def read_dollar(self, word: Word) -> bool:
        s = self.s
        if s[self.i] == "`":
            j = self.i + 1
            while j < self.n and s[j] != "`":
                j += 2 if s[j] == "\\" else 1
            body = s[self.i + 1:j].replace("\\`", "`")
            word.add("subst", body)
            word.substs.append(body)
            self.i = j + 1
            return True
        if s.startswith("$(", self.i):
            body, self.i = self.paren_body(self.i + 2)
            word.add("subst", body)
            word.substs.append(body)
            return True
        if s.startswith("${", self.i):
            depth, j = 1, self.i + 2
            while j < self.n and depth:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                j += 1
            inner = s[self.i + 2:j - 1]
            word.add("var", inner)
            word.substs.extend(substitutions(inner))
            self.i = j
            return True
        match = NAME.match(s, self.i + 1)
        if match:
            word.add("var", match.group(0))
            self.i = match.end()
            return True
        if self.i + 1 < self.n and s[self.i + 1] in SPECIAL_VARS:
            word.add("var", s[self.i + 1])
            self.i += 2
            return True
        return False

    def paren_body(self, start: int) -> Tuple[str, int]:
        s, depth, j = self.s, 1, start
        while j < self.n:
            c = s[j]
            if c == "\\":
                j += 2
                continue
            if c == "'":
                end = s.find("'", j + 1)
                j = self.n if end < 0 else end + 1
                continue
            if c == '"':
                j += 1
                while j < self.n and s[j] != '"':
                    j += 2 if s[j] == "\\" else 1
                j += 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return s[start:j], j + 1
            j += 1
        return s[start:], self.n


def substitutions(text: str) -> List[str]:
    """Command substitutions bash runs inside an unquoted heredoc or ${...}."""
    lexer = Lexer(text)
    word = Word()
    while lexer.i < lexer.n:
        c = text[lexer.i]
        if c == "\\":
            lexer.i += 2
        elif c in "$`" and lexer.read_dollar(word):
            pass
        else:
            lexer.i += 1
    return word.substs


class Command:
    __slots__ = ("words", "redirects")

    def __init__(self) -> None:
        self.words: List[Word] = []
        self.redirects: List[Tuple[str, Optional[Word], Optional[Dict[str, Any]]]] = []


def parse(tokens: List[Tuple[str, Any]]) -> List[Tuple[str, Any]]:
    items: List[Tuple[str, Any]] = []
    current: Optional[Command] = None
    i = 0
    while i < len(tokens):
        kind, value = tokens[i]
        if kind == "op" and value in REDIRECT_OPS:
            current = current or Command()
            target = tokens[i + 1][1] if i + 1 < len(tokens) and tokens[i + 1][0] == "word" else None
            step = 2 if target is not None else 1
            heredoc = None
            if i + step < len(tokens) and tokens[i + step][0] == "heredoc":
                heredoc = tokens[i + step][1]
                step += 1
            current.redirects.append((value, target, heredoc))
            i += step
        elif kind == "op":
            if current is not None:
                items.append(("cmd", current))
                current = None
            items.append(("op", value))
            i += 1
        elif kind == "word":
            current = current or Command()
            current.words.append(value)
            i += 1
        else:
            i += 1
    if current is not None:
        items.append(("cmd", current))
    return items


# --------------------------------------------------------------------------
# Repository and evidence lookups (no subprocess on the common path).


def repo_info(path: Path) -> Optional[Tuple[Path, Path, Path]]:
    """(git_dir, common_dir, worktree_root) for the repository containing path."""
    for ancestor in (path, *path.parents):
        dotgit = ancestor / ".git"
        git_dir: Optional[Path] = None
        root = ancestor
        if dotgit.is_dir():
            git_dir = dotgit
        elif dotgit.is_file():
            try:
                line = dotgit.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                return None
            if line.startswith("gitdir:"):
                git_dir = Path(os.path.normpath(ancestor / line[7:].strip()))
        elif (ancestor / "HEAD").is_file() and (
            (ancestor / "objects").is_dir() or (ancestor / "commondir").is_file()
        ):
            git_dir = ancestor
            root = ancestor.parent
        if git_dir is None:
            continue
        common = git_dir
        commondir = git_dir / "commondir"
        if commondir.is_file():
            try:
                common = Path(os.path.normpath(git_dir / commondir.read_text(encoding="utf-8").strip()))
            except (OSError, UnicodeError):
                pass
        return git_dir, common, root
    return None


def git_dir_info(git_dir: Path) -> Tuple[Path, Path, Path]:
    common = git_dir
    commondir = git_dir / "commondir"
    if commondir.is_file():
        try:
            common = Path(os.path.normpath(git_dir / commondir.read_text(encoding="utf-8").strip()))
        except (OSError, UnicodeError):
            pass
    return git_dir, common, git_dir.parent


def all_git_dirs(common: Path) -> List[Path]:
    dirs = [common]
    worktrees = common / "worktrees"
    if worktrees.is_dir():
        dirs.extend(path for path in worktrees.iterdir() if path.is_dir())
    return dirs


def holds_evidence(directory: str) -> bool:
    if os.path.basename(os.path.normpath(directory)) == "refs" and os.path.exists(
        os.path.join(directory, "commitforge")
    ):
        return True
    for rel in (
        SNAPSHOT_DIR_NAME, LOCK_DIR_NAME, "refs/commitforge",
        ".git/" + SNAPSHOT_DIR_NAME, ".git/" + LOCK_DIR_NAME, ".git/refs/commitforge",
    ):
        if os.path.exists(os.path.join(directory, rel)):
            return True
    for pattern in ("worktrees/*/claude-atomic*", ".git/worktrees/*/claude-atomic*"):
        if glob.glob(os.path.join(glob.escape(directory), pattern)):
            return True
    for packed in ("packed-refs", ".git/packed-refs"):
        if packed_refs_mention(os.path.join(directory, packed)):
            return True
    return False


def packed_refs_mention(path: str) -> bool:
    try:
        with open(path, "rb") as stream:
            return b"refs/commitforge" in stream.read()
    except OSError:
        return False


def in_recovery_refs(parts: List[str]) -> bool:
    """Whether the split path lies inside a `refs/commitforge` tree."""
    return any(parts[i] == "refs" and parts[i + 1] == "commitforge" for i in range(len(parts) - 1))


def recovery_copy_root() -> str:
    """Mirrors guard.recovery_copy_root: Guard's copies outside the repository."""
    override = os.environ.get("COMMITFORGE_RECOVERY_DIR")
    root = os.path.expanduser(override) if override else os.path.join(
        os.path.expanduser("~"), ".claude", "commitforge", "recovery"
    )
    return os.path.normpath(os.path.abspath(root)).replace("\\", "/")


def canonical(path: str) -> str:
    """Path with symlinks resolved, case-folded where the filesystem folds case."""
    real = os.path.realpath(path).replace("\\", "/")
    return real.casefold() if CASE_INSENSITIVE else real


def mentions_evidence(text: str) -> bool:
    if EVIDENCE_TEXT.search(text) or RECOVERY_TEXT.search(text):
        return True
    override = os.environ.get("COMMITFORGE_RECOVERY_DIR")
    return bool(override) and override in text


def in_recovery_copies(path: str) -> bool:
    candidate, root = canonical(path), canonical(recovery_copy_root())
    return candidate == root or candidate.startswith(root + "/")


def covers_recovery_copies(path: str) -> bool:
    candidate, root = canonical(path), canonical(recovery_copy_root())
    return root.startswith(candidate.rstrip("/") + "/") and os.path.isdir(recovery_copy_root())


def is_protected(path: str, *, allow_ledger_lock: bool = False) -> bool:
    """True when removing or overwriting path destroys recovery evidence."""
    normal = os.path.normpath(path).replace("\\", "/")
    if allow_ledger_lock and LEDGER_LOCK.search(normal):
        return False
    if in_recovery_copies(normal) or covers_recovery_copies(normal):
        return True
    # A symlink or a case variant (`.GIT`, `Refs`) reaches the same evidence.
    for candidate in {normal, canonical(normal)}:
        parts = candidate.split("/")
        folded = [part.casefold() for part in parts] if CASE_INSENSITIVE else parts
        if MARKER_NAMES & set(folded):
            return True
        if in_recovery_refs(folded):
            return True
        if folded[-1] == "packed-refs" and packed_refs_mention(candidate):
            return True
    return os.path.isdir(normal) and holds_evidence(normal)


def evidence_entries(directory: str) -> Iterator[str]:
    """Every path inside the evidence directories that find could reach.

    Lazy, so a matching name test stops the walk of large snapshot trees.
    """
    bases = [directory, os.path.join(directory, ".git")]
    for base in list(bases):
        bases.extend(glob.glob(os.path.join(glob.escape(base), "worktrees", "*")))
    roots = [
        os.path.join(base, rel)
        for base in bases
        for rel in (SNAPSHOT_DIR_NAME, LOCK_DIR_NAME, os.path.join("refs", "commitforge"))
    ]
    if os.path.basename(os.path.normpath(directory)) == "refs":
        roots.append(os.path.join(directory, "commitforge"))
    normal = os.path.normpath(os.path.abspath(directory)).replace("\\", "/")
    if covers_recovery_copies(normal):
        roots.append(recovery_copy_root())
    for root in roots:
        if not os.path.isdir(root):
            continue
        yield root
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames + filenames:
                yield os.path.join(dirpath, name)


def overwrite_target(text: str) -> Optional[str]:
    """What writing to path would destroy, or None when the write is harmless."""
    normal = os.path.normpath(text).replace("\\", "/")
    parts = normal.split("/")
    if LOCK_DIR_NAME in parts or in_recovery_refs(parts) or parts[-1] == "packed-refs":
        return "잠금·recovery ref"
    if in_recovery_copies(normal):
        return "저장소 밖 복구 사본"
    if SNAPSHOT_DIR_NAME in parts:
        index = parts.index(SNAPSHOT_DIR_NAME)
        # Top-level snapshot files form the audited inventory; new files
        # and subdirectories (ledger/, learn/, patches/) are fine.
        if len(parts) == index + 3 and os.path.exists(text):
            return "snapshot 파일"
    return None


def brace_expand(pattern: str) -> List[str]:
    match = re.search(r"\{([^{}]*,[^{}]*)\}", pattern)
    if not match:
        return [pattern]
    head, tail = pattern[:match.start()], pattern[match.end():]
    out: List[str] = []
    for option in match.group(1).split(","):
        out.extend(brace_expand(head + option + tail))
    return out


# --------------------------------------------------------------------------
# Option parsing for allowlisted git subcommands.


def canon_long(option: str, known: List[str]) -> Optional[str]:
    name = option.split("=", 1)[0]
    if name in known:
        return name
    matches = [full for full in known if full.startswith(name)]
    return matches[0] if len(matches) == 1 else None


def abbreviates(option: str, full: str) -> bool:
    name = option.split("=", 1)[0]
    return len(name) >= 3 and full.startswith(name)


def parse_options(
    values: List[Optional[str]],
    long_known: List[str],
    long_value: set,
    short_flags: str,
    short_value: str,
) -> Optional[Tuple[set, set, List[Optional[str]]]]:
    """Strictly parse options; None means unknown or unresolvable (deny)."""
    longs: set = set()
    shorts: set = set()
    positionals: List[Optional[str]] = []
    after = False
    i = 0
    while i < len(values):
        value = values[i]
        i += 1
        if after:
            positionals.append(value)
            continue
        if value is None:
            return None
        if value == "--":
            after = True
        elif value == "-" or not value.startswith("-"):
            positionals.append(value)
        elif value.startswith("--"):
            name = canon_long(value, long_known)
            if name is None:
                return None
            longs.add(name)
            if name in long_value and "=" not in value:
                if i < len(values) and values[i] is None:
                    return None
                i += 1
        else:
            for j, char in enumerate(value[1:], start=1):
                if char in short_value:
                    shorts.add(char)
                    if j == len(value) - 1:
                        if i < len(values) and values[i] is None:
                            return None
                        i += 1
                    break
                if char not in short_flags:
                    return None
                shorts.add(char)
    return longs, shorts, positionals


RESTORE_LONG = [
    "--source", "--staged", "--worktree", "--ours", "--theirs", "--merge", "--conflict",
    "--ignore-unmerged", "--overlay", "--no-overlay", "--quiet", "--progress",
    "--no-progress", "--pathspec-from-file", "--pathspec-file-nul", "--patch",
    "--ignore-skip-worktree-bits", "--recurse-submodules", "--no-recurse-submodules",
]
APPLY_LONG = [
    "--stat", "--numstat", "--summary", "--check", "--index", "--intent-to-add",
    "--cached", "--3way", "--ours", "--theirs", "--union", "--build-fake-ancestor",
    "--reverse", "--reject", "--no-add", "--allow-binary-replacement", "--binary",
    "--exclude", "--include", "--ignore-space-change", "--ignore-whitespace",
    "--whitespace", "--directory", "--unsafe-paths", "--allow-empty", "--apply",
    "--verbose", "--quiet", "--recount", "--inaccurate-eof", "--unidiff-zero",
    "--allow-overlap",
]
RM_LONG = [
    "--cached", "--dry-run", "--force", "--ignore-unmatch", "--quiet", "--sparse",
    "--pathspec-from-file", "--pathspec-file-nul",
]
BRANCH_LONG = [
    "--delete", "--force", "--move", "--copy", "--create-reflog", "--track",
    "--no-track", "--set-upstream-to", "--unset-upstream", "--edit-description",
    "--list", "--show-current", "--verbose", "--quiet", "--abbrev", "--no-abbrev",
    "--column", "--no-column", "--sort", "--merged", "--no-merged", "--contains",
    "--no-contains", "--points-at", "--format", "--remotes", "--all", "--ignore-case",
    "--omit-empty", "--color", "--no-color", "--recurse-submodules",
]
BRANCH_VALUE = {
    "--set-upstream-to", "--sort", "--merged", "--no-merged", "--contains",
    "--no-contains", "--points-at", "--format",
}
TAG_LONG = [
    "--annotate", "--sign", "--no-sign", "--local-user", "--force", "--delete",
    "--verify", "--list", "--sort", "--format", "--color", "--contains",
    "--no-contains", "--merged", "--no-merged", "--points-at", "--message", "--file",
    "--trailer", "--edit", "--no-edit", "--cleanup", "--create-reflog", "--ignore-case",
    "--omit-empty", "--column", "--no-column",
]
TAG_VALUE = {
    "--local-user", "--sort", "--format", "--contains", "--no-contains", "--merged",
    "--no-merged", "--points-at", "--message", "--file", "--trailer", "--cleanup",
}
COMMIT_LONG_VALUE = (
    "--message", "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash",
    "--author", "--date", "--template", "--trailer", "--cleanup", "--pathspec-from-file",
)
CLEAN_LONG = ["--dry-run", "--force", "--interactive", "--quiet", "--exclude"]


def git_rule(sub: str, values: List[Optional[str]], unknown_args: bool) -> Optional[str]:
    """Why this git command may discard work under a lock, or None when allowed."""
    if sub in ARGUMENT_FREE:
        for value in values:
            if value is not None and value.startswith("--") and abbreviates(value, "--output"):
                return f"git {sub} --output (파일 덮어쓰기)"
        return None
    if sub in ALWAYS_DENIED:
        return f"git {sub}"
    if unknown_args:
        return f"git {sub} (인자를 정적으로 확인할 수 없음)"
    if sub == "commit":
        skip = False
        for value in values:
            if skip:
                skip = False
                continue
            if value == "--":
                break
            if value is None:
                return "git commit (해석할 수 없는 옵션)"
            if value.startswith("--"):
                if abbreviates(value, "--amend"):
                    return "git commit --amend"
                skip = "=" not in value and any(abbreviates(value, full) for full in COMMIT_LONG_VALUE)
            elif value.startswith("-") and len(value) > 1:
                for j, char in enumerate(value[1:], start=1):
                    if char in "mFCct":
                        skip = j == len(value) - 1
                        break
        return None
    if sub == "restore":
        parsed = parse_options(values, RESTORE_LONG, {"--source", "--conflict", "--pathspec-from-file"}, "SWpqm23", "s")
        if parsed is None:
            return "git restore (확인할 수 없는 옵션)"
        longs, shorts, _ = parsed
        staged = "--staged" in longs or "S" in shorts
        worktree = "--worktree" in longs or "W" in shorts
        return None if staged and not worktree else "git restore (working tree)"
    if sub == "apply":
        parsed = parse_options(values, APPLY_LONG, {"--exclude", "--include", "--whitespace", "--directory"}, "RvqN3z", "pC")
        if parsed is None:
            return "git apply (확인할 수 없는 옵션)"
        longs = parsed[0]
        if "--index" in longs:
            return "git apply --index"
        if "--cached" in longs:
            return None
        if "--apply" not in longs and longs & {"--check", "--stat", "--numstat", "--summary"}:
            return None
        return "git apply (working tree)"
    if sub == "rm":
        parsed = parse_options(values, RM_LONG, {"--pathspec-from-file"}, "rfnq", "")
        if parsed is None:
            return "git rm (확인할 수 없는 옵션)"
        longs, shorts, _ = parsed
        return None if longs & {"--cached", "--dry-run"} or "n" in shorts else "git rm (--cached 없음)"
    if sub == "checkout":
        if len(values) == 2 and values[0] == "-b" and values[1] and not values[1].startswith("-"):
            return None
        return "git checkout"
    if sub == "switch":
        if len(values) == 2 and values[0] in {"-c", "--create"} and values[1] and not values[1].startswith("-"):
            return None
        return "git switch"
    if sub == "branch":
        parsed = parse_options(values, BRANCH_LONG, BRANCH_VALUE, "dDfmMcCrailqvt", "u")
        if parsed is None:
            return "git branch (확인할 수 없는 옵션)"
        longs, shorts, _ = parsed
        if longs & {"--delete", "--force", "--move", "--copy"} or shorts & set("dDfmMcC"):
            return "git branch (삭제·강제 이동)"
        return None
    if sub == "tag":
        parsed = parse_options(values, TAG_LONG, TAG_VALUE, "asvlne", "umF")
        if parsed is None:
            return "git tag (확인할 수 없는 옵션)"
        longs, shorts, _ = parsed
        if longs & {"--delete", "--force"} or shorts & set("df"):
            return "git tag (삭제·강제 이동)"
        return None
    if sub == "stash":
        return None if values[:1] in (["list"], ["show"]) else "git stash"
    if sub == "clean":
        parsed = parse_options(values, CLEAN_LONG, {"--exclude"}, "dfnqxX", "e")
        if parsed is None:
            return "git clean (확인할 수 없는 옵션)"
        longs, shorts, _ = parsed
        return None if "--dry-run" in longs or "n" in shorts else "git clean"
    if sub == "worktree":
        return None if values[:1] == ["list"] else "git worktree"
    if sub == "submodule":
        first = next((v for v in values if v is None or not v.startswith("-")), "status")
        return None if first in {"status", "summary"} else "git submodule"
    if sub == "reflog":
        first = values[0] if values else "show"
        if first is None:
            return "git reflog (해석할 수 없는 인자)"
        return None if first in {"show", "exists"} or first.startswith("-") else f"git reflog {first}"
    if sub == "symbolic-ref":
        if any(v is None for v in values):
            return "git symbolic-ref (해석할 수 없는 인자)"
        if any(v in {"-d", "--delete"} for v in values):
            return "git symbolic-ref --delete"
        positionals = [v for v in values if not v.startswith("-")]
        return "git symbolic-ref (HEAD 변경)" if len(positionals) >= 2 else None
    if sub == "push":
        for value in values:
            if value is None:
                return "git push (해석할 수 없는 인자)"
            if value.startswith("--"):
                if any(abbreviates(value, full) for full in ("--force", "--force-with-lease", "--delete", "--mirror", "--prune")):
                    return "git push (강제·삭제)"
            elif value.startswith("-"):
                if set(value[1:]) & {"f", "d"}:
                    return "git push (강제·삭제)"
            elif value.startswith("+") or value.startswith(":"):
                return "git push (강제·삭제 refspec)"
        return None
    if sub == "fetch":
        for value in values:
            if value is None:
                return "git fetch (해석할 수 없는 인자)"
            if (value.startswith("--") and abbreviates(value, "--update-head-ok")) or (
                value.startswith("-") and not value.startswith("--") and "u" in value
            ):
                return "git fetch --update-head-ok"
        return None
    return f"git {sub}"


# --------------------------------------------------------------------------
# Evaluation.


def read_text(path: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > MAX_SCRIPT_BYTES:
            return None
        with open(path, "rb") as stream:
            return stream.read().decode("utf-8")
    except (OSError, UnicodeError):
        return None


class Gate:
    def __init__(self, cwd: Path, session: Optional[str], transcript: Optional[Path], root_text: str) -> None:
        self.base_cwd = cwd
        self.session = session
        self.transcript = transcript
        self.root_text = root_text
        self._alias_cache: Dict[Tuple[str, str], Optional[str]] = {}

    # ---- values

    def value(self, word: Optional[Word], env: Dict[str, Optional[str]], cwd: Optional[Path]) -> Optional[str]:
        if word is None:
            return None
        out = []
        for kind, text in word.parts:
            if kind in {"lit", "qlit"}:
                out.append(text)
            elif kind == "home":
                out.append(os.path.expanduser("~"))
            elif kind == "var":
                if text in env:
                    resolved = env[text]
                elif text == "COMMITFORGE_SESSION_ID":
                    resolved = self.session
                elif text == "HOME":
                    resolved = os.path.expanduser("~")
                elif text == "PWD":
                    resolved = str(cwd) if cwd is not None else None
                else:
                    resolved = None
                if resolved is None:
                    return None
                out.append(resolved)
            else:
                return None
        return "".join(out)

    @staticmethod
    def resolve_path(base: Optional[Path], value: str) -> Optional[Path]:
        path = Path(os.path.expanduser(value))
        if path.is_absolute():
            return Path(os.path.normpath(path))
        if base is None:
            return None
        return Path(os.path.normpath(base / path))

    # ---- locks

    def lock_for(self, path: Optional[Path], git_dir: Optional[Path] = None) -> Optional[Path]:
        info = git_dir_info(git_dir) if git_dir is not None else (repo_info(path) if path is not None else None)
        if info is None:
            return None
        lock = info[0] / LOCK_DIR_NAME
        return lock if lock.is_dir() else None

    def any_lock_for(self, path: Optional[Path], git_dir: Optional[Path] = None) -> Optional[Path]:
        info = git_dir_info(git_dir) if git_dir is not None else (repo_info(path) if path is not None else None)
        if info is None:
            return None
        for candidate in all_git_dirs(info[1]):
            lock = candidate / LOCK_DIR_NAME
            if lock.is_dir():
                return lock
        return None

    def lock_near(self, cwd: Optional[Path]) -> Optional[Path]:
        """Lock for a command whose target is only partly known."""
        return self.lock_for(cwd) or self.lock_for(self.base_cwd)

    def unknown(self, cwd: Optional[Path], what: str) -> None:
        lock = self.lock_near(cwd)
        if lock is not None:
            raise Deny(lock_message(f"정적으로 확인할 수 없는 {what}"))
        if EVIDENCE_TEXT.search(self.root_text):
            raise Deny(evidence_message(f"정적으로 확인할 수 없는 {what}"))

    # ---- script walking

    def run(self, source: str, cwd: Optional[Path], env: Dict[str, Optional[str]], depth: int) -> Optional[Path]:
        if depth > MAX_DEPTH:
            self.unknown(cwd, "깊게 중첩된 명령")
            return cwd
        items = parse(Lexer(source).run())
        stack: List[Optional[Path]] = []
        for index, (kind, item) in enumerate(items):
            if kind == "op":
                if item == "(":
                    stack.append(cwd)
                elif item == ")" and stack:
                    cwd = stack.pop()
                continue
            before = items[index - 1][1] if index > 0 and items[index - 1][0] == "op" else None
            after = items[index + 1][1] if index + 1 < len(items) and items[index + 1][0] == "op" else None
            isolated = before in {"|", "|&"} or after in {"|", "|&", "&"}
            cwd = self.command(item, cwd, env, depth, isolated, before)
        return cwd

    def command(self, cmd: Command, cwd: Optional[Path], env: Dict[str, Optional[str]], depth: int, isolated: bool, before: Optional[str]) -> Optional[Path]:
        for word in cmd.words + [target for _, target, _ in cmd.redirects if target is not None]:
            for body in word.substs:
                self.run(body, cwd, dict(env), depth + 1)
        stdin: List[Optional[str]] = []
        for op, target, heredoc in cmd.redirects:
            if heredoc is not None:
                if not heredoc["quoted"]:
                    for body in substitutions(heredoc["body"]):
                        self.run(body, cwd, dict(env), depth + 1)
                stdin.append(heredoc["body"])
            elif op == "<<<":
                stdin.append(self.value(target, env, cwd))

        words = list(cmd.words)
        assignments: List[Tuple[str, Word]] = []
        while words:
            split = split_assignment(words[0])
            if split is None:
                break
            assignments.append(split)
            words.pop(0)
        if not words:
            for name, word in assignments:
                env[name] = self.value(word, env, cwd)
            self.check_redirects(cmd.redirects, env, cwd)
            return cwd
        local = dict(env)
        for name, word in assignments:
            local[name] = self.value(word, env, cwd)
        return self.argv(words, cwd, local, env, depth, isolated, before, cmd.redirects, stdin, False)

    def argv(
        self,
        words: List[Word],
        cwd: Optional[Path],
        local: Dict[str, Optional[str]],
        env: Dict[str, Optional[str]],
        depth: int,
        isolated: bool,
        before: Optional[str],
        redirects: list,
        stdin: List[Optional[str]],
        unknown_args: bool,
    ) -> Optional[Path]:
        while words and words[0].unquoted() in RESERVED_PREFIX:
            words = words[1:]
        if not words:
            return cwd
        reserved = words[0].unquoted()
        if reserved in RESERVED_SKIP:
            if reserved in {"for", "select"} and len(words) > 1 and words[1].unquoted():
                env[words[1].unquoted()] = None
            return cwd
        head = self.value(words[0], local, cwd)
        self.check_redirects(redirects, local, cwd)
        if head is None:
            self.unknown(cwd, "명령 이름")
            return cwd
        program = os.path.basename(head)

        if program in {"cd", "pushd"}:
            if isolated:
                return cwd
            args = [w for w in words[1:] if self.value(w, local, cwd) not in {"--", "-P", "-L", "-e", "-@"}]
            if not args:
                return Path(os.path.expanduser("~"))
            target = self.value(args[0], local, cwd)
            if target is None or target == "-":
                return None
            resolved = self.resolve_path(cwd, target)
            # A failed cd leaves bash where it was (`cd /missing; git reset`),
            # so a target that is not a directory now leaves the cwd unknown.
            return resolved if resolved is not None and resolved.is_dir() else None
        if program == "popd":
            return cwd if isolated else None
        if program in {"export", "declare", "typeset", "local", "readonly"}:
            for word in words[1:]:
                split = split_assignment(word)
                if split is not None:
                    env[split[0]] = self.value(split[1], env, cwd)
            return cwd
        if self.guard_index(words, local, cwd) is not None:
            self.guard(words, local, cwd)
            return cwd
        if program == "eval":
            parts = [self.value(word, local, cwd) for word in words[1:]]
            if any(part is None for part in parts):
                self.unknown(cwd, "eval 인자")
            else:
                self.run(" ".join(parts), cwd, env, depth + 1)
            return cwd
        if program in {"source", "."}:
            path = self.value(words[1], local, cwd) if len(words) > 1 else None
            resolved = self.resolve_path(cwd, path) if path else None
            text = read_text(str(resolved)) if resolved else None
            if text is None:
                self.unknown(cwd, "source 파일")
            else:
                self.run(text, cwd, env, depth + 1)
            return cwd
        if program in WRAPPERS:
            inner, inner_cwd = self.unwrap(program, words[1:], local, cwd)
            if inner:
                # The wrapper's own directory change never reaches the caller.
                self.argv(
                    inner, inner_cwd, local, env, depth, True, before, [], stdin,
                    unknown_args or program in {"xargs", "parallel"},
                )
            return cwd
        if program == "find":
            self.find(words, local, cwd, depth)
            return cwd
        if program in SHELLS:
            self.shell(words, local, env, cwd, depth, stdin, before)
            return cwd
        family = interpreter_family(program)
        if family is not None:
            self.interpreter(family, words, local, cwd, stdin, before)
            return cwd
        if program == "git":
            self.git(words, local, cwd, depth, redirects, unknown_args)
            return cwd
        if program in REMOVERS:
            self.remover(program, words, local, cwd, unknown_args)
        elif program in OVERWRITERS:
            self.overwriter(program, words, local, cwd, unknown_args)
        return cwd

    def unwrap(self, program: str, args: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path]) -> Tuple[List[Word], Optional[Path]]:
        """The wrapped command and the directory it runs in (`env -C`)."""
        interesting = WRAPPERS | SHELLS | REMOVERS | OVERWRITERS | {"git", "eval", "source", "find"}
        chdir = CHDIR_OPTIONS.get(program, set())
        inner_cwd = cwd
        index = 0
        while index < len(args):
            word = args[index]
            index += 1
            value = self.value(word, local, cwd)
            if value is None:
                self.unknown(cwd, f"{program}로 감싼 명령")
                continue
            if program == "env":
                split = split_assignment(word)
                if split is not None:
                    local[split[0]] = self.value(split[1], local, cwd)
                    continue
            target: Optional[str] = ""
            if value in chdir:
                target = self.value(args[index], local, cwd) if index < len(args) else None
                index += 1
            elif any(value.startswith(option + "=") for option in chdir if option.startswith("--")):
                target = value.split("=", 1)[1]
            elif any(value.startswith(option) for option in chdir if len(option) == 2) and len(value) > 2:
                # Attached short form: `env -C.git/refs`, `sudo -D/tmp`.
                target = value[2:]
            if target != "":
                resolved = self.resolve_path(inner_cwd, target) if target is not None else None
                if resolved is None:
                    self.unknown(cwd, f"{program}의 작업 디렉터리")
                inner_cwd = resolved
                continue
            name = os.path.basename(value)
            if name in interesting or interpreter_family(name) or name in GUARD_SCRIPTS:
                return args[index - 1:], inner_cwd
        return [], inner_cwd

    # ---- program handlers

    def guard_index(self, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path]) -> Optional[int]:
        """Index of the Guard script when this command runs it, else None.

        Only `guard.sh ...` or `<shell|python> [-opts] guard.py ...` count: a
        Guard path given as an argument (`git add .../guard.py`, `rm guard.py`)
        must still reach that program's own checks.
        """
        for index, word in enumerate(words[:3]):
            value = self.value(word, local, cwd)
            if value is None:
                return None
            name = os.path.basename(value)
            if name in GUARD_SCRIPTS:
                return index
            if index == 0 and (name in SHELLS or interpreter_family(name) == "python"):
                continue
            if index > 0 and value.startswith("-"):
                continue
            return None
        return None

    def guard(self, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path]) -> None:
        index = self.guard_index(words, local, cwd)
        assert index is not None
        rest = [self.value(word, local, cwd) for word in words[index + 1:]]
        sub = rest[0] if rest else None
        if sub is None:
            self.unknown(cwd, "Guard 하위 명령")
            return
        if self.session and sub in SESSION_BOUND_GUARD:
            for i, value in enumerate(rest):
                if value is None:
                    continue
                if value == "--session" or value.startswith("--session="):
                    named = value.split("=", 1)[1] if "=" in value else (rest[i + 1] if i + 1 < len(rest) else None)
                    if named != self.session:
                        raise Deny(SESSION_MESSAGE)
        if sub == "clean" and self.lock_near(cwd) is not None and not self.user_requested_clean():
            raise Deny(CLEAN_MESSAGE)

    def find(self, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path], depth: int) -> None:
        values = [self.value(word, local, cwd) for word in words]
        starts: List[Optional[str]] = []
        i = 1
        while i < len(values) and (values[i] is None or not values[i].startswith(("-", "(", "!"))):
            starts.append(values[i])
            i += 1
        tests = [
            (values[j], values[j + 1]) for j in range(len(values) - 1)
            if values[j] in {"-name", "-iname", "-path", "-ipath", "-wholename", "-regex", "-iregex"}
        ]
        destructive = "-delete" in values
        j = i
        while j < len(values):
            if values[j] in {"-exec", "-execdir", "-ok", "-okdir"}:
                k = j + 1
                while k < len(values) and values[k] not in {";", "+"}:
                    k += 1
                inner = words[j + 1:k]
                if inner:
                    program = self.value(inner[0], local, cwd)
                    if program is not None and os.path.basename(program) in REMOVERS | OVERWRITERS:
                        destructive = True
                    self.argv(inner, cwd, local, dict(local), depth + 1, True, None, [], [], True)
                j = k + 1
            else:
                j += 1
        if not destructive:
            return
        base = cwd or self.base_cwd
        for start in starts or ["."]:
            if start is None:
                self.unknown(cwd, "find 시작 경로")
                continue
            path = self.resolve_path(base, start)
            if path is None:
                continue
            text = str(path)
            parts = text.replace("\\", "/").split("/")
            if is_protected(text) and (
                MARKER_NAMES & set(parts)
                or in_recovery_refs(parts)
                or in_recovery_copies(os.path.normpath(text).replace("\\", "/"))
                or not tests
                or any(self.find_test_hits_evidence(flag, pattern, text, start) for flag, pattern in tests)
            ):
                raise Deny(evidence_message("find로 snapshot·잠금·recovery ref 삭제"))

    @staticmethod
    def pattern_hits_evidence(pattern: str) -> bool:
        targets = list(MARKER_NAMES) + ["commitforge", "refs", ".git", "packed-refs"]
        return any(fnmatch.fnmatch(target, pattern) for target in targets) or EVIDENCE_TEXT.search(pattern) is not None

    @classmethod
    def find_test_hits_evidence(cls, flag: str, pattern: Optional[str], start: str, shown: str) -> bool:
        """Whether a find name test can select a file inside the evidence.

        Matching only the evidence directory names would let
        `find .git -name '.cca-snapshot.json' -delete` through, so the test is
        run against every path inside them, printed as find would print it.
        """
        if pattern is None or cls.pattern_hits_evidence(pattern):
            return True
        fold = flag in {"-iname", "-ipath", "-iregex"}
        if fold:
            pattern = pattern.lower()
        for entry in evidence_entries(start):
            if flag in {"-name", "-iname"}:
                subject = os.path.basename(entry)
            else:
                subject = os.path.join(shown, os.path.relpath(entry, start))
            if fold:
                subject = subject.lower()
            if flag in {"-regex", "-iregex"}:
                try:
                    if re.fullmatch(pattern, subject):
                        return True
                except re.error:
                    return True
            elif fnmatch.fnmatchcase(subject, pattern):
                return True
        return False

    def shell(self, words: List[Word], local: Dict[str, Optional[str]], env: Dict[str, Optional[str]], cwd: Optional[Path], depth: int, stdin: List[Optional[str]], before: Optional[str]) -> None:
        i = 1
        has_c = False
        while i < len(words):
            value = self.value(words[i], local, cwd)
            if value is None or value == "--":
                i += value == "--"
                break
            if value.startswith(("-", "+")):
                if value.startswith("-") and not value.startswith("--") and "c" in value[1:]:
                    has_c = True
                i += 2 if value in {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"} else 1
                continue
            break
        if has_c:
            code = self.value(words[i], local, cwd) if i < len(words) else None
            if code is None:
                self.unknown(cwd, "셸 -c 코드")
            else:
                self.run(code, cwd, dict(env), depth + 1)
            return
        if i < len(words):
            path = self.value(words[i], local, cwd)
            resolved = self.resolve_path(cwd or self.base_cwd, path) if path else None
            text = read_text(str(resolved)) if resolved else None
            if text is None:
                self.unknown(cwd, "셸 스크립트")
            else:
                self.run(text, cwd, dict(env), depth + 1)
            return
        for text in stdin:
            if text is None:
                self.unknown(cwd, "셸 입력")
            else:
                self.run(text, cwd, dict(env), depth + 1)
        if not stdin and before in {"|", "|&"}:
            self.unknown(cwd, "파이프로 받은 셸 코드")

    def interpreter(self, family: str, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path], stdin: List[Optional[str]], before: Optional[str]) -> None:
        flags = INTERPRETER_CODE_FLAGS[family]
        codes: List[Optional[str]] = []
        script: Optional[str] = None
        i = 1
        while i < len(words):
            value = self.value(words[i], local, cwd)
            if value in flags:
                codes.append(self.value(words[i + 1], local, cwd) if i + 1 < len(words) else None)
                i += 2
                continue
            if family == "python" and value == "-m":
                return
            if value is None:
                codes.append(None)
                break
            if value.startswith("-") and not value.startswith("--") and len(value) > 2:
                # Clustered short options: `python3 -Ic CODE`, `perl -ne CODE`,
                # `python3 -cCODE`. The code letter ends the cluster.
                letters = value[1:]
                found: Optional[str] = None
                for k, char in enumerate(letters):
                    if family == "python" and char == "m":
                        return
                    if "-" + char in flags:
                        found = letters[k + 1:]
                        break
                    if char in CLUSTER_VALUE_LETTERS.get(family, ""):
                        break
                if found is not None:
                    if found:
                        codes.append(found)
                        i += 1
                    else:
                        codes.append(self.value(words[i + 1], local, cwd) if i + 1 < len(words) else None)
                        i += 2
                    if family == "python":
                        break
                    continue
            if value.startswith("-"):
                i += 1
                continue
            script = value
            break
        if not codes and script is None:
            codes.extend(stdin)
            if not stdin and before in {"|", "|&"}:
                codes.append(None)
        for code in codes:
            if code is None:
                self.unknown(cwd, "인터프리터 코드")
            else:
                self.check_code(code, cwd)
        # Script files are not inspected: project scripts mention git freely
        # and regex matching them would block verification runs.

    def check_code(self, code: str, cwd: Optional[Path]) -> None:
        if mentions_evidence(code) and REMOVE_HINT.search(code):
            raise Deny(evidence_message("인터프리터 코드로 snapshot·잠금·recovery ref 삭제"))
        if GIT_WORD.search(code) and GIT_DESTRUCTIVE_WORD.search(code):
            lock = self.lock_near(cwd)
            if lock is not None:
                raise Deny(lock_message("인터프리터 코드 안의 git 명령"))

    def remover(self, program: str, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path], unknown_args: bool) -> None:
        if unknown_args and mentions_evidence(self.root_text):
            raise Deny(evidence_message(f"{program}로 snapshot·잠금·recovery ref 삭제"))
        after = False
        for word in words[1:]:
            value = self.value(word, local, cwd)
            if value is None:
                # `S=$(...)/claude-atomic-snapshots; rm -rf "$S"` hides the path
                # in a variable whose value is unknown, so look at the whole command.
                if mentions_evidence(word.raw()) or mentions_evidence(self.root_text):
                    raise Deny(evidence_message(f"{program}로 snapshot·잠금·recovery ref 삭제"))
                continue
            if not after and value == "--":
                after = True
                continue
            if not after and value.startswith("-") and value != "-":
                continue
            for path in self.expand(word, value, local, cwd):
                if is_protected(path, allow_ledger_lock=program in {"rm", "rmdir", "unlink"}):
                    raise Deny(evidence_message(f"{program}로 snapshot·잠금·recovery ref 삭제"))

    def overwriter(self, program: str, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path], unknown_args: bool) -> None:
        """Deny cp/tee/dd/... whose destination is a lock, recovery ref or snapshot file."""
        reason = f"{program}로 snapshot·잠금·recovery ref 덮어쓰기"
        if unknown_args and mentions_evidence(self.root_text):
            raise Deny(evidence_message(reason))
        base = cwd or self.base_cwd
        pairs = [(word, self.value(word, local, cwd)) for word in words[1:]]
        if any(value is None for _, value in pairs):
            if mentions_evidence(self.root_text):
                raise Deny(evidence_message(reason))
        known = [(word, value) for word, value in pairs if value is not None]
        values = [value for _, value in known]
        sources: List[str] = []
        # (word, value); a None word marks a value that is not a shell word.
        targets: List[Tuple[Optional[Word], str]] = []
        if program == "dd":
            targets = [(None, value[3:]) for value in values if value.startswith("of=")]
        else:
            positionals: List[Tuple[Optional[Word], str]] = []
            directory: Optional[Tuple[Optional[Word], str]] = None
            after = False
            i = 0
            while i < len(known):
                word, value = known[i]
                i += 1
                if not after and value == "--":
                    after = True
                elif not after and value in {"-t", "--target-directory"}:
                    directory = known[i] if i < len(known) else None
                    i += 1
                elif not after and value.startswith("--target-directory="):
                    directory = (None, value.split("=", 1)[1])
                elif after or not value.startswith("-") or value == "-":
                    positionals.append((word, value))
            if program == "tee":
                targets = positionals
            elif directory is not None:
                targets, sources = [directory], [value for _, value in positionals]
            elif positionals:
                targets, sources = positionals[-1:], [value for _, value in positionals[:-1]]
        deleting = program == "rsync" and any(value.startswith("--delete") for value in values)
        for word, target in targets:
            if word is not None:
                # Globs reach existing snapshot files the literal path does not name.
                texts = self.expand(word, target, local, cwd)
            else:
                path = self.resolve_path(base, target)
                texts = [str(path)] if path is not None else []
            for text in texts:
                candidates = [text]
                if os.path.isdir(text):
                    candidates.extend(os.path.join(text, os.path.basename(src.rstrip("/"))) for src in sources)
                if any(overwrite_target(candidate) for candidate in candidates) or (deleting and is_protected(text)):
                    raise Deny(evidence_message(reason))

    def expand(self, word: Word, value: str, local: Dict[str, Optional[str]], cwd: Optional[Path]) -> List[str]:
        base = cwd or self.base_cwd
        if not word.has_pattern():
            path = self.resolve_path(base, value)
            return [str(path)] if path is not None else []
        pattern_parts = []
        for kind, text in word.parts:
            if kind == "lit":
                pattern_parts.append(text)
            elif kind == "home":
                pattern_parts.append(glob.escape(os.path.expanduser("~")))
            elif kind == "var":
                pattern_parts.append(glob.escape(self.value(_var_word(text), local, cwd) or ""))
            else:
                pattern_parts.append(glob.escape(text))
        pattern = "".join(pattern_parts)
        if not os.path.isabs(os.path.expanduser(pattern)):
            pattern = os.path.join(glob.escape(str(base)), pattern)
        found: List[str] = []
        for candidate in brace_expand(pattern):
            found.extend(glob.glob(candidate))
        return found

    # ---- git

    def git(self, words: List[Word], local: Dict[str, Optional[str]], cwd: Optional[Path], depth: int, redirects: list, unknown_args: bool) -> None:
        args = [self.value(word, local, cwd) for word in words[1:]]
        repo = cwd
        known = cwd is not None
        git_dir: Optional[Path] = None
        aliases: Dict[str, str] = {}
        work_tree_values: List[str] = []
        i = 0
        while i < len(args):
            value = args[i]
            if value is None or not value.startswith("-"):
                break
            name, eq, inline = value.partition("=")
            if name in GIT_VALUE_OPTIONS and not eq:
                option_value = args[i + 1] if i + 1 < len(args) else None
                i += 2
            else:
                option_value = inline if eq else None
                i += 1
            if name == "-C":
                resolved = self.resolve_path(repo, option_value) if option_value is not None and known else None
                known = resolved is not None
                repo = resolved
            elif name == "-c" and option_value is not None and option_value.startswith("alias."):
                key, _, body = option_value[6:].partition("=")
                aliases[key] = body
            elif name == "-c" and option_value is None:
                known = False
            elif name == "--git-dir":
                resolved = self.resolve_path(repo, option_value) if option_value is not None and known else None
                if resolved is None:
                    known = False
                else:
                    git_dir = resolved if resolved.is_dir() else self.git_dir_from_file(resolved)
                    known = git_dir is not None
            elif name == "--work-tree":
                if option_value is None:
                    known = False
                else:
                    work_tree_values.append(option_value)
        for env_name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            if env_name in local:
                if local[env_name] is None:
                    known = False
                elif env_name == "GIT_DIR":
                    resolved = self.resolve_path(repo, local[env_name])
                    git_dir = resolved if resolved is not None and resolved.is_dir() else None
                    known = known and git_dir is not None
                elif env_name == "GIT_WORK_TREE":
                    work_tree_values.append(local[env_name])  # type: ignore[arg-type]
        sub = args[i] if i < len(args) else None
        rest = args[i + 1:]

        if known:
            local_lock = self.lock_for(repo, git_dir)
            shared_lock = self.any_lock_for(repo, git_dir)
        else:
            local_lock = self.lock_near(cwd)
            shared_lock = local_lock or self.any_lock_for(self.base_cwd)
        # `--work-tree`/GIT_WORK_TREE write into that tree whatever the git dir,
        # so a lock held by the targeted worktree applies too.
        for work_tree in work_tree_values:
            target = self.resolve_path(repo if known else cwd, work_tree)
            if target is None:
                local_lock = local_lock or self.lock_near(cwd)
                continue
            tree_lock = self.lock_for(target)
            local_lock = local_lock or tree_lock
            shared_lock = shared_lock or tree_lock

        if sub == "update-ref" or (sub is None and i < len(args)):
            # xargs/parallel append refs the command line never shows.
            self.check_ref_evidence(rest, repo if known else self.base_cwd, unknown_args)
        elif sub in {"push", "fetch", "notes", "symbolic-ref"}:
            self.check_ref_targets(sub, rest)
        if i >= len(args):
            return
        if sub is None:
            if local_lock or shared_lock:
                raise Deny(lock_message("해석할 수 없는 git 하위 명령"))
            return
        if sub == "stage":
            sub = "add"
        if not local_lock and not shared_lock:
            return

        if sub not in KNOWN_SUBCOMMANDS:
            alias = aliases.get(sub)
            if alias is None and known and repo is not None:
                alias = self.git_alias(repo, sub)
            if alias is None:
                raise Deny(lock_message(f"git {sub} (알 수 없는 하위 명령이나 alias)"))
            if any(value is None for value in rest):
                raise Deny(lock_message(f"git {sub} (해석할 수 없는 alias 인자)"))
            if alias.startswith("!"):
                self.run(alias[1:] + " " + " ".join(shlex.quote(v) for v in rest), repo, {}, depth + 1)
                return
            try:
                expanded = shlex.split(alias)
            except ValueError:
                raise Deny(lock_message(f"git {sub} (해석할 수 없는 alias)"))
            prefix = [words[0]] + words[1:1 + i]
            new_words = prefix + [Word.literal(v) for v in expanded] + [Word.literal(v) for v in rest]  # type: ignore[arg-type]
            if depth >= MAX_DEPTH:
                raise Deny(lock_message("깊게 중첩된 git alias"))
            self.git(new_words, local, cwd, depth + 1, redirects, unknown_args)
            return

        lock = shared_lock if sub in SHARED_REF_SUBCOMMANDS else local_lock
        if lock is None:
            return
        reason = git_rule(sub, rest, unknown_args)
        if reason:
            raise Deny(lock_message(reason))
        if local_lock is not None:
            self.check_git_output(redirects, local, cwd, repo if known else None)

    @staticmethod
    def git_dir_from_file(path: Path) -> Optional[Path]:
        try:
            line = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return None
        if not line.startswith("gitdir:"):
            return None
        return Path(os.path.normpath(path.parent / line[7:].strip()))

    def git_alias(self, repo: Path, sub: str) -> Optional[str]:
        key = (str(repo), sub)
        if key not in self._alias_cache:
            try:
                proc = subprocess.run(
                    ["git", "config", "--get", f"alias.{sub}"],
                    cwd=str(repo),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=3,
                )
                found = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                found = ""
            self._alias_cache[key] = found or None
        return self._alias_cache[key]

    def check_ref_evidence(self, values: List[Optional[str]], repo: Optional[Path], unknown_args: bool = False) -> None:
        if any(v is not None and "refs/commitforge" in v for v in values):
            raise Deny(evidence_message("git update-ref로 recovery ref 변경"))
        uncertain = unknown_args or any(v is None for v in values) or "--stdin" in values
        if uncertain and (EVIDENCE_TEXT.search(self.root_text) or self.repo_has_recovery_refs(repo)):
            raise Deny(evidence_message("확인할 수 없는 git update-ref"))

    @staticmethod
    def check_ref_targets(sub: str, values: List[Optional[str]]) -> None:
        """Deny push/fetch/notes/symbolic-ref that write or delete refs/commitforge.

        Reading a recovery ref (`git push origin refs/commitforge/x:refs/heads/b`)
        stays allowed; only a recovery ref on the destination side is denied.
        """
        deleting = sub == "push" and any(
            v is not None and (
                (v.startswith("--") and abbreviates(v, "--delete"))
                or (v.startswith("-") and not v.startswith("--") and "d" in v[1:])
            )
            for v in values
        )
        for value in values:
            if value is None:
                continue
            if sub in {"push", "fetch"} and ":" in value:
                # `+refs/*:refs/*` (with --prune) rewrites or deletes recovery
                # refs without ever naming them.
                destination = value.split(":", 1)[1]
                if "*" in destination and fnmatch.fnmatchcase("refs/commitforge/snapshots/x", destination):
                    raise Deny(evidence_message(f"git {sub}로 recovery ref 변경"))
            if "refs/commitforge" not in value:
                continue
            if sub in {"notes", "symbolic-ref"} or deleting:
                raise Deny(evidence_message(f"git {sub}로 recovery ref 변경"))
            if ":" in value and "refs/commitforge" in value.split(":", 1)[1]:
                raise Deny(evidence_message(f"git {sub}로 recovery ref 변경"))

    @staticmethod
    def repo_has_recovery_refs(repo: Optional[Path]) -> bool:
        info = repo_info(repo) if repo is not None else None
        if info is None:
            return False
        common = info[1]
        return (common / "refs" / "commitforge").exists() or packed_refs_mention(str(common / "packed-refs"))

    def check_git_output(self, redirects: list, local: Dict[str, Optional[str]], cwd: Optional[Path], repo: Optional[Path]) -> None:
        info = repo_info(repo or cwd or self.base_cwd)
        for op, target, _ in redirects:
            if op not in WRITE_REDIRECTS:
                continue
            value = self.value(target, local, cwd)
            if value is None:
                raise Deny(lock_message("git 출력의 리다이렉션 대상을 확인할 수 없음"))
            if op == ">&" and (value.isdigit() or value == "-"):
                continue
            if value.startswith("/dev/"):
                continue
            path = self.resolve_path(cwd or self.base_cwd, value)
            if path is None or info is None:
                continue
            git_dir, _, root = info
            inside_root = path == root or root in path.parents
            inside_git = path == git_dir or git_dir in path.parents
            if inside_root and not inside_git:
                raise Deny(lock_message("git 출력으로 작업 트리 파일 덮어쓰기"))

    def check_redirects(self, redirects: list, local: Dict[str, Optional[str]], cwd: Optional[Path]) -> None:
        for op, target, _ in redirects:
            if op not in WRITE_REDIRECTS:
                continue
            value = self.value(target, local, cwd)
            if value is None:
                if target is not None and mentions_evidence(target.raw()):
                    raise Deny(evidence_message("리다이렉션으로 snapshot·잠금 덮어쓰기"))
                continue
            if op == ">&" and (value.isdigit() or value == "-"):
                continue
            path = self.resolve_path(cwd or self.base_cwd, value)
            if path is None:
                continue
            target = overwrite_target(str(path))
            if target is not None:
                raise Deny(evidence_message(f"리다이렉션으로 {target} 덮어쓰기"))

    # ---- clean authorisation

    def user_requested_clean(self) -> bool:
        """True only when the latest user prompt is `/<CommitForge cmd> clean`."""
        if self.transcript is None:
            return False
        try:
            lines = self.transcript.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return False
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") != "user" or event.get("isMeta"):
                continue
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                if any(isinstance(item, dict) and item.get("type") == "tool_result" for item in content):
                    continue
                content = "\n".join(
                    str(item.get("text", "")) for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            if not isinstance(content, str):
                continue
            name = re.search(r"<command-name>\s*/([\w:.-]+)\s*</command-name>", content)
            if name is None or name.group(1).split(":")[-1] not in COMMITFORGE_COMMANDS:
                return False
            args = re.search(r"<command-args>(.*?)</command-args>", content, flags=re.DOTALL)
            try:
                first = shlex.split(args.group(1))[:1] if args else []
            except ValueError:
                return False
            return first == ["clean"]
        return False


def _var_word(name: str) -> Word:
    word = Word()
    word.add("var", name)
    return word


def split_assignment(word: Word) -> Optional[Tuple[str, Word]]:
    if not word.parts or word.parts[0][0] != "lit":
        return None
    match = ASSIGNMENT.match(word.parts[0][1])
    if match is None:
        return None
    value = Word()
    remainder = word.parts[0][1][match.end():]
    if remainder:
        value.add("lit", remainder)
    for part in word.parts[1:]:
        value.parts.append(part)
    value.substs = list(word.substs)
    return match.group(1), value


def interpreter_family(program: str) -> Optional[str]:
    if re.fullmatch(r"python[0-9.]*", program):
        return "python"
    return program if program in INTERPRETER_CODE_FLAGS else None


def lock_message(reason: str) -> str:
    return (
        "CommitForge: 이 worktree에 Guard 잠금이 걸려 있어, 커밋되지 않은 변경을 잃을 수 "
        f"있거나 정적으로 확인할 수 없는 명령을 차단했습니다: {reason}.\n"
        "- index만 되돌릴 때는 `git restore --staged -- <경로>`를 쓰십시오.\n"
        "- 이 잠금이 당신 실행의 것이면, 커밋 순서·구성이 틀렸어도 history를 고치지 말고 "
        '더 이상 커밋하지 마십시오. Guard `abort --session "$COMMITFORGE_SESSION_ID"`로 '
        "멈춘 뒤 사용자에게 보고하십시오.\n"
        "- 다른 실행의 잠금이면 그 실행이 끝날 때까지 이 worktree의 git 변경을 멈추고 "
        "사용자에게 알리십시오. 다른 세션의 잠금을 풀지 마십시오."
    )


def evidence_message(reason: str) -> str:
    return (
        f"CommitForge: 복구 근거를 지우거나 덮어쓰는 명령은 차단됩니다: {reason}.\n"
        "snapshot, Guard 잠금, refs/commitforge recovery ref는 Guard `finish`만 "
        "정리합니다. Guard 명령이 실패했다면 원인을 사용자에게 그대로 보고하십시오. "
        "사용자가 복구를 마친 뒤 직접 지우려면 `!` 접두어로 실행합니다."
    )


SESSION_MESSAGE = (
    "CommitForge: Guard 명령의 --session은 현재 세션이어야 합니다. "
    '`--session "$COMMITFORGE_SESSION_ID"`만 쓰고, 다른 세션의 잠금·snapshot은 '
    "건드리지 마십시오."
)
CLEAN_MESSAGE = (
    "CommitForge: Guard `clean`은 사용자가 직전 입력으로 `/<명령> clean`을 직접 "
    "실행했을 때만 허용됩니다. 실행 중인 작업의 잠금을 스스로 풀지 말고, 정리가 "
    "필요하면 사용자에게 `/<명령> clean` 입력을 안내하십시오."
)


def evaluate(event: Dict[str, Any], command: str) -> Optional[str]:
    cwd_value = event.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value else Path.cwd()
    session = event.get("session_id") if isinstance(event.get("session_id"), str) else None
    transcript = event.get("transcript_path")
    gate = Gate(
        Path(os.path.normpath(cwd)),
        session or None,
        Path(transcript) if isinstance(transcript, str) and transcript else None,
        command,
    )
    try:
        gate.run(command, gate.base_cwd, {}, 0)
    except Deny as denial:
        return str(denial)
    except Exception as exc:  # noqa: BLE001 - a parser bug must not open the gate
        if gate.lock_near(gate.base_cwd) is not None:
            return lock_message(f"명령을 검사하지 못함 ({type(exc).__name__})")
        return None
    return None
