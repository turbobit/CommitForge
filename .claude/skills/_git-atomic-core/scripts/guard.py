#!/usr/bin/env python3
"""Safety guard for the Claude Code atomic Git skills.

The guard provides:
- a per-worktree advisory lock;
- a session-unique snapshot of staged/unstaged diffs and untracked files;
- repository fingerprints for TOCTOU detection;
- an explicit current-worktree lock cleanup command that preserves snapshots;
- safe cleanup that only removes the snapshot owned by the invoking session.

It intentionally never modifies tracked working-tree content or the Git index.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
from typing import Any, Optional


SCHEMA_VERSION = 1
LOCK_DIR_NAME = "claude-atomic.lock"
SNAPSHOT_DIR_NAME = "claude-atomic-snapshots"
MARKER_NAME = ".cca-snapshot.json"
DEFAULT_STALE_AFTER_SECONDS = 3600
DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS = 300


class GuardError(RuntimeError):
    """Expected safety failure."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.details = details


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def run_git(args: list[str], *, cwd: Path, check: bool = True) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise GuardError(f"git {' '.join(args)} 실패: {stderr or 'unknown error'}")
    return proc.stdout


def decode(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


def resolve_git_path(raw: str, cwd: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def repo_context(cwd: Path) -> dict[str, Path]:
    try:
        root = resolve_git_path(decode(run_git(["rev-parse", "--show-toplevel"], cwd=cwd)).strip(), cwd)
        git_dir = resolve_git_path(decode(run_git(["rev-parse", "--git-dir"], cwd=cwd)).strip(), cwd)
        common_dir = resolve_git_path(decode(run_git(["rev-parse", "--git-common-dir"], cwd=cwd)).strip(), cwd)
    except GuardError as exc:
        raise GuardError("현재 디렉터리는 Git 작업 트리가 아닙니다.") from exc
    return {"root": root, "git_dir": git_dir, "common_dir": common_dir}


def operation_state(git_dir: Path) -> list[str]:
    checks = {
        "merge": git_dir / "MERGE_HEAD",
        "cherry-pick": git_dir / "CHERRY_PICK_HEAD",
        "revert": git_dir / "REVERT_HEAD",
        "bisect": git_dir / "BISECT_LOG",
        "rebase-merge": git_dir / "rebase-merge",
        "rebase-apply": git_dir / "rebase-apply",
        "sequencer": git_dir / "sequencer",
    }
    return [name for name, path in checks.items() if path.exists()]


def external_locks(git_dir: Path, common_dir: Path) -> list[str]:
    candidates = [
        git_dir / "index.lock",
        git_dir / "HEAD.lock",
        common_dir / "packed-refs.lock",
        common_dir / "config.lock",
    ]
    return [str(p) for p in candidates if p.exists()]


def lock_file_writers(path: Path) -> list[int] | None:
    """Best-effort PIDs holding the file open for writing.

    Linux uses procfs, macOS/Unix uses lsof, and Windows uses Win32 share-mode
    compatibility. Read-only handles such as Finder, Spotlight, Explorer, and
    indexers are not writers. An inconclusive check returns None and therefore
    never qualifies a lock for automatic cleanup.
    """
    if sys.platform.startswith("linux"):
        try:
            target = path.stat()
        except OSError:
            return []
        proc_root = Path("/proc")
        if not proc_root.is_dir():
            return None
        writers: list[int] = []
        try:
            processes = list(proc_root.iterdir())
        except OSError:
            return None
        for process in processes:
            if not process.name.isdigit():
                continue
            fd_root = process / "fd"
            try:
                descriptors = list(fd_root.iterdir())
            except OSError:
                continue
            for descriptor in descriptors:
                try:
                    opened = descriptor.stat()
                except OSError:
                    continue
                if opened.st_dev != target.st_dev or opened.st_ino != target.st_ino:
                    continue
                try:
                    fdinfo = (process / "fdinfo" / descriptor.name).read_text(
                        encoding="ascii"
                    )
                except OSError:
                    return None
                flags_line = next(
                    (line for line in fdinfo.splitlines() if line.startswith("flags:")),
                    None,
                )
                if flags_line is None:
                    return None
                try:
                    flags = int(flags_line.split(":", 1)[1].strip(), 8)
                except ValueError:
                    return None
                if (flags & 0o3) in {os.O_WRONLY, os.O_RDWR}:
                    pid = int(process.name)
                    if pid not in writers:
                        writers.append(pid)
        return writers

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = (
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            )
            create_file.restype = wintypes.HANDLE
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = (wintypes.HANDLE,)
            close_handle.restype = wintypes.BOOL
            handle = create_file(
                str(path),
                0x80000000,  # GENERIC_READ
                # Permit readers and delete-aware tools, but deliberately omit
                # FILE_SHARE_WRITE. A normal Explorer/indexer read handle stays
                # compatible; an existing writer makes this open fail.
                0x00000001 | 0x00000004,  # FILE_SHARE_READ | FILE_SHARE_DELETE
                None,
                3,  # OPEN_EXISTING
                0x80,  # FILE_ATTRIBUTE_NORMAL
                None,
            )
            invalid = wintypes.HANDLE(-1).value
            if handle == invalid:
                # This can also be a restrictive non-writer handle. Treat it as
                # unknown rather than falsely reporting a writer.
                return None
            close_handle(handle)
            return []
        except (AttributeError, OSError, ValueError):
            return None

    if shutil.which("lsof") is None:
        return None
    try:
        proc = subprocess.run(
            ["lsof", "-Fpfa", "--", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if proc.returncode not in {0, 1}:
        return None

    writers: list[int] = []
    pid: int | None = None
    file_seen = False
    for line in decode(proc.stdout).splitlines():
        if line.startswith("p"):
            try:
                pid = int(line[1:])
            except ValueError:
                pid = None
            file_seen = False
        elif line.startswith("f"):
            file_seen = True
        elif line.startswith("a") and pid is not None and file_seen:
            # With `-F pfa`, lsof emits access mode as a separate `a` field.
            if line[1:].strip() in {"w", "u"} and pid not in writers:
                writers.append(pid)
    return writers


def external_lock_details(
    git_dir: Path,
    common_dir: Path,
    *,
    stale_after: int = DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS,
) -> list[dict[str, Any]]:
    """Describe Git's own lock files so a blocked run is actionable.

    Only an explicit clean may delete a verified stale candidate. Begin/status
    remain read-only with respect to Git locks.
    """
    details: list[dict[str, Any]] = []
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    for path in (
        git_dir / "index.lock",
        git_dir / "HEAD.lock",
        common_dir / "packed-refs.lock",
        common_dir / "config.lock",
    ):
        try:
            stat = path.stat()
        except OSError:
            continue
        age = max(0, int(now - stat.st_mtime))
        writers = lock_file_writers(path)
        details.append(
            {
                "path": str(path),
                "size": stat.st_size,
                "age_seconds": age,
                "modified_at": dt.datetime.fromtimestamp(
                    stat.st_mtime, dt.timezone.utc
                ).isoformat(),
                "writer_pids": writers,
                "stale_after_seconds": stale_after,
                "stale_candidate": (
                    age >= stale_after
                    and stat.st_size == 0
                    and writers == []
                ),
            }
        )
    return details


def remove_stale_git_locks(
    ctx: dict[str, Path],
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    """Remove only verified stale Git lock files for an explicit clean request."""
    operations = operation_state(ctx["git_dir"])
    if operations:
        return {
            "removed": [],
            "skipped": [
                {"path": entry["path"], "reason": "git_operation_in_progress"}
                for entry in details
            ],
            "operations": operations,
        }

    removed: list[str] = []
    skipped: list[dict[str, str]] = []
    for entry in details:
        path = Path(entry["path"])
        if not entry["stale_candidate"]:
            skipped.append({"path": str(path), "reason": "not_stale_candidate"})
            continue
        if entry["writer_pids"] != []:
            skipped.append({"path": str(path), "reason": "writer_check_unavailable_or_busy"})
            continue
        if path.is_symlink():
            skipped.append({"path": str(path), "reason": "unsafe_symlink"})
            continue

        try:
            before = path.stat()
        except OSError:
            skipped.append({"path": str(path), "reason": "disappeared"})
            continue

        writers = lock_file_writers(path)
        if writers != []:
            skipped.append({"path": str(path), "reason": "writer_check_unavailable_or_busy"})
            continue
        try:
            current = path.stat()
        except OSError:
            skipped.append({"path": str(path), "reason": "disappeared"})
            continue
        if (
            current.st_dev != before.st_dev
            or current.st_ino != before.st_ino
            or current.st_size != before.st_size
            or current.st_mtime_ns != before.st_mtime_ns
        ):
            skipped.append({"path": str(path), "reason": "lock_changed_during_check"})
            continue

        try:
            path.unlink()
        except OSError:
            skipped.append({"path": str(path), "reason": "remove_failed"})
        else:
            removed.append(str(path))

    return {"removed": removed, "skipped": skipped, "operations": operations}


def git_lock_recovery(details: list[dict[str, Any]]) -> dict[str, Any]:
    stale = [entry["path"] for entry in details if entry["stale_candidate"]]
    return {
        "stale_lock_paths": stale,
        "remove_hint": (
            "`clean`은 안전 조건이 재확인된 stale Git lock만 제거합니다. "
            "남아 있다면 실행 중인 git 명령, IDE, Git GUI를 확인하십시오."
            if stale
            else "실행 중인 git 명령이나 IDE의 Git 작업이 끝나기를 기다린 뒤 다시 실행하십시오."
        ),
        "clean_argv": [
            sys.executable,
            str(Path(__file__).resolve()),
            "clean",
        ],
        "manual_remove_paths": stale,
        "requires_no_running_git_confirmation": True,
    }


def lock_paths(ctx: dict[str, Path]) -> tuple[Path, Path]:
    lock_dir = ctx["git_dir"] / LOCK_DIR_NAME
    owner_file = lock_dir / "owner.json"
    return lock_dir, owner_file


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def owned_snapshots(
    ctx: dict[str, Path],
    session: str,
    token: str,
) -> list[Path]:
    snapshot_root = ctx["git_dir"] / SNAPSHOT_DIR_NAME
    if not snapshot_root.exists():
        return []

    matches = []
    for candidate in snapshot_root.iterdir():
        if not candidate.is_dir():
            continue
        metadata = read_json(candidate / MARKER_NAME)
        if not metadata:
            continue
        if metadata.get("session") != session or metadata.get("token") != token:
            continue
        project_root = metadata.get("project_root")
        if not isinstance(project_root, str) or Path(project_root).resolve() != ctx["root"]:
            continue
        matches.append(candidate.resolve())
    return sorted(matches)


def safe_session(value: str) -> str:
    value = value.strip()
    if (
        not value
        or len(value) > 80
        or any(not (ch.isalnum() or ch in "-_.") for ch in value)
    ):
        raise GuardError(
            "session ID가 비어 있거나 안전한 형식이 아닙니다. "
            "설치된 SessionStart hook의 COMMITFORGE_SESSION_ID를 사용하십시오.",
            reason="invalid_session_id",
        )
    return value


def positive_seconds(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("초 단위 임계값은 1 이상이어야 합니다.")
    return parsed


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def lock_age_seconds(owner: dict[str, Any] | None) -> int | None:
    if not owner or not isinstance(owner.get("created_at"), str):
        return None
    try:
        created_at = dt.datetime.fromisoformat(owner["created_at"].replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return max(0, int((dt.datetime.now(dt.timezone.utc) - created_at).total_seconds()))


def lock_dir_age_seconds(lock_dir: Path) -> int | None:
    """Fallback age for locks whose owner metadata is missing or corrupt."""
    try:
        created = lock_dir.stat().st_mtime
    except OSError:
        return None
    return max(0, int(dt.datetime.now(dt.timezone.utc).timestamp() - created))


def lock_owner_profile(
    lock_dir: Path,
    owner: dict[str, Any] | None,
    *,
    session: str,
    stale_after: int,
) -> dict[str, Any]:
    """Classify an existing lock owner without ever mutating it.

    Age alone never proves the owner is gone, so the result only marks a stale
    *candidate*. Reclaiming still requires an explicit `--reclaim-stale`.
    """
    host = socket.gethostname()
    owner_host = owner.get("hostname") if isinstance(owner, dict) else None
    age = lock_age_seconds(owner)
    if age is None:
        age = lock_dir_age_seconds(lock_dir)
    return {
        "hostname": owner_host,
        "same_host": None if not isinstance(owner_host, str) else owner_host == host,
        "same_session": bool(owner) and owner.get("session") == session,
        "age_seconds": age,
        "stale_after_seconds": stale_after,
        "stale_candidate": age is not None and age >= stale_after,
        "owner_readable": owner is not None,
    }


def recovery_details(
    ctx: dict[str, Path],
    owner: dict[str, Any] | None,
    owner_snapshots: list[str],
) -> dict[str, Any] | None:
    if not owner:
        return None
    session = owner.get("session")
    token = owner.get("token")
    if not isinstance(session, str) or not isinstance(token, str):
        return None
    guard_path = str(Path(__file__).resolve())
    return {
        "cwd": str(ctx["root"]),
        "status_argv": [sys.executable, guard_path, "status"],
        "abort_argv": [
            sys.executable,
            guard_path,
            "abort",
            "--session",
            session,
            "--token",
            token,
        ],
        "clean_hint": "이 저장소에서 `/cr clean`(또는 같은 접두어의 다른 명령)으로 현재 worktree 잠금만 해제할 수 있습니다.",
        "clean_argv": [
            sys.executable,
            guard_path,
            "clean",
            "--request-session",
            "<현재-세션-ID>",
        ],
        "reclaim_hint": (
            "원래 실행이 끝났음을 확인했다면 `begin --reclaim-stale`로 "
            "같은 호스트의 오래된 잠금만 회수할 수 있습니다."
        ),
        "snapshot": owner_snapshots[0] if len(owner_snapshots) == 1 else None,
        "auto_snapshot_lookup": True,
        "requires_owner_inactive_confirmation": True,
    }


def current_head(root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return decode(proc.stdout).strip() if proc.returncode == 0 else "UNBORN"


def branch_name(root: Path) -> str:
    return decode(run_git(["branch", "--show-current"], cwd=root)).strip() or "(detached HEAD)"


def sha256_file(path: Path, *, full_hash_limit: int = 64 * 1024 * 1024) -> str:
    size = path.stat().st_size
    h = hashlib.sha256()
    if size <= full_hash_limit:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    # For very large files, hash stable samples plus size/mtime to avoid excessive latency.
    with path.open("rb") as f:
        h.update(f.read(1024 * 1024))
        if size > 2 * 1024 * 1024:
            f.seek(max(0, size - 1024 * 1024))
            h.update(f.read(1024 * 1024))
    st = path.stat()
    h.update(str(size).encode())
    h.update(str(st.st_mtime_ns).encode())
    return "sampled:" + h.hexdigest()


def list_untracked(root: Path) -> list[str]:
    raw = run_git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=root)
    return [decode(item) for item in raw.split(b"\0") if item]


def untracked_manifest(root: Path) -> tuple[list[dict[str, Any]], int]:
    manifest: list[dict[str, Any]] = []
    total = 0
    for rel in list_untracked(root):
        path = root / rel
        try:
            st = path.lstat()
        except FileNotFoundError:
            manifest.append({"path": rel, "state": "disappeared"})
            continue

        entry: dict[str, Any] = {
            "path": rel,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "mode": oct(st.st_mode),
        }
        if path.is_symlink():
            entry["kind"] = "symlink"
            entry["target"] = os.readlink(path)
        elif path.is_file():
            entry["kind"] = "file"
            entry["sha256"] = sha256_file(path)
            total += st.st_size
        else:
            entry["kind"] = "other"
        manifest.append(entry)
    return manifest, total


def repository_fingerprint(root: Path) -> dict[str, Any]:
    h = hashlib.sha256()
    components: dict[str, str] = {}

    blobs = {
        "head": current_head(root).encode(),
        "status": run_git(["status", "--porcelain=v2", "-z", "--untracked-files=all"], cwd=root),
        "staged_diff": run_git(["diff", "--cached", "--binary", "--full-index", "--no-ext-diff"], cwd=root),
        "working_diff": run_git(["diff", "--binary", "--full-index", "--no-ext-diff"], cwd=root),
    }
    manifest, _ = untracked_manifest(root)
    blobs["untracked"] = json.dumps(
        manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8", "surrogatepass")

    for name in sorted(blobs):
        digest = hashlib.sha256(blobs[name]).hexdigest()
        components[name] = digest
        h.update(name.encode())
        h.update(b"\0")
        h.update(blobs[name])
        h.update(b"\0")
    return {"fingerprint": h.hexdigest(), "components": components}


def reclaim_refusal(
    ctx: dict[str, Path],
    lock_dir: Path,
    owner: dict[str, Any] | None,
    profile: dict[str, Any],
) -> str | None:
    """Return the reason a stale reclaim must be refused, or None when allowed.

    Ordered from strongest safety signal to weakest so that a lock on another
    machine is never taken over just because it looks old.
    """
    if profile["same_host"] is False:
        return "different_host"
    if not profile["same_session"] and profile["same_host"] is not True:
        return "owner_host_unknown"
    if not profile["same_session"] and not profile["stale_candidate"]:
        return "lock_not_stale"
    if lock_dir.is_symlink() or not lock_dir.is_dir():
        return "lock_path_unsafe"

    owner_file = lock_dir / "owner.json"
    if owner_file.is_symlink():
        return "owner_path_unsafe"
    if owner:
        owner_worktree = owner.get("worktree")
        owner_git_dir = owner.get("git_dir")
        if not isinstance(owner_worktree, str) or Path(owner_worktree).resolve() != ctx["root"]:
            return "lock_owner_scope_mismatch"
        if isinstance(owner_git_dir, str) and Path(owner_git_dir).resolve() != ctx["git_dir"]:
            return "lock_owner_scope_mismatch"

    try:
        entries = sorted(path.name for path in lock_dir.iterdir())
    except OSError:
        return "lock_contents_unreadable"
    if [name for name in entries if name != owner_file.name]:
        return "lock_contents_unexpected"
    return None


def acquire_lock(
    ctx: dict[str, Path],
    session: str,
    *,
    reclaim_stale: bool = False,
    stale_after: int = DEFAULT_STALE_AFTER_SECONDS,
) -> tuple[str, Path, dict[str, Any] | None]:
    lock_dir, owner_file = lock_paths(ctx)
    token = secrets.token_hex(24)
    owner = {
        "schema": SCHEMA_VERSION,
        "session": session,
        "token": token,
        "created_at": utc_now(),
        "worktree": str(ctx["root"]),
        "git_dir": str(ctx["git_dir"]),
        "hostname": socket.gethostname(),
        "begin_pid": os.getpid(),
    }
    reclaimed: dict[str, Any] | None = None

    for attempt in (0, 1):
        try:
            lock_dir.mkdir(mode=0o700)
            break
        except FileExistsError:
            existing = read_json(owner_file)
            profile = lock_owner_profile(
                lock_dir, existing, session=session, stale_after=stale_after
            )
            refusal: str | None = "reclaim_not_requested"
            if reclaim_stale and attempt == 0:
                refusal = reclaim_refusal(ctx, lock_dir, existing, profile)
                if refusal is None:
                    owner_bytes: bytes | None = None
                    try:
                        owner_bytes = owner_file.read_bytes()
                    except FileNotFoundError:
                        pass
                    try:
                        current_owner_bytes = owner_file.read_bytes()
                    except FileNotFoundError:
                        current_owner_bytes = None
                    except OSError:
                        current_owner_bytes = b"__unreadable__"
                    if current_owner_bytes != owner_bytes:
                        refusal = "lock_owner_changed"
                    else:
                        try:
                            if owner_file.exists():
                                owner_file.unlink()
                            lock_dir.rmdir()
                        except OSError:
                            if (
                                owner_bytes is not None
                                and not owner_file.exists()
                                and lock_dir.exists()
                            ):
                                try:
                                    owner_file.write_bytes(owner_bytes)
                                except OSError:
                                    pass
                            refusal = "reclaim_release_failed"
                        else:
                            reclaimed = {
                                "previous_owner": existing,
                                "reason": (
                                    "same_session_reentry"
                                    if profile["same_session"]
                                    else "stale_lock_age"
                                    if existing
                                    else "stale_orphan_lock"
                                ),
                                "previous_lock_age_seconds": profile["age_seconds"],
                                "stale_after_seconds": stale_after,
                            }
                            continue

            owner_snapshots = []
            if existing:
                owner_session = existing.get("session")
                owner_token = existing.get("token")
                if isinstance(owner_session, str) and isinstance(owner_token, str):
                    owner_snapshots = [
                        str(path) for path in owned_snapshots(ctx, owner_session, owner_token)
                    ]
            raise GuardError(
                "동일 Git worktree에서 다른 /cc, /cr, /cca, /cpr 또는 /cp 실행이 "
                "진행 중입니다. 서로 다른 저장소의 잠금은 이 실행을 차단하지 않습니다. "
                f"project_root={ctx['root']}, git_dir={ctx['git_dir']}, "
                f"lock={lock_dir}, owner={existing or 'unreadable'}",
                reason="guard_lock_conflict",
                lock_scope="worktree_git_dir",
                project_root=str(ctx["root"]),
                git_dir=str(ctx["git_dir"]),
                lock_path=str(lock_dir),
                lock_owner=existing,
                lock_created_at=existing.get("created_at") if existing else None,
                lock_age_seconds=lock_age_seconds(existing),
                lock_owner_hostname=profile["hostname"],
                lock_owner_same_host=profile["same_host"],
                lock_owner_same_session=profile["same_session"],
                stale_after_seconds=stale_after,
                stale_candidate=profile["stale_candidate"],
                reclaim_requested=bool(reclaim_stale),
                reclaim_refused_reason=refusal,
                lock_owner_snapshots=owner_snapshots,
                recovery=recovery_details(ctx, existing, owner_snapshots),
            )

    try:
        owner_file.write_text(json.dumps(owner, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(lock_dir, ignore_errors=True)
        raise
    return token, lock_dir, reclaimed


def verify_owner(ctx: dict[str, Path], session: str, token: str) -> dict[str, Any]:
    lock_dir, owner_file = lock_paths(ctx)
    owner = read_json(owner_file)
    if not owner:
        raise GuardError(f"유효한 잠금 소유자 정보가 없습니다: {lock_dir}")
    if owner.get("session") != session or owner.get("token") != token:
        raise GuardError("현재 세션이 소유하지 않은 잠금은 해제할 수 없습니다.")
    if Path(owner.get("worktree", "")).resolve() != ctx["root"]:
        raise GuardError("잠금의 작업 트리가 현재 저장소와 일치하지 않습니다.")
    return owner


def resolve_owned_review_context(
    ctx: dict[str, Path],
    session: str,
    token: str | None,
    snapshot_arg: str | None,
) -> tuple[str, Path]:
    """Resolve review identity from the current worktree lock when omitted.

    Explicit values remain authoritative and are never silently replaced. This
    keeps wrong cross-worktree paths fail-closed while allowing /cr to avoid
    reconstructing long token and snapshot arguments after a lengthy review.
    """
    lock_dir, owner_file = lock_paths(ctx)
    owner = read_json(owner_file)
    if not owner:
        raise GuardError(
            f"유효한 잠금 소유자 정보가 없습니다: {lock_dir}",
            reason="owner_not_found",
        )
    if owner.get("session") != session:
        raise GuardError(
            "현재 session이 이 worktree 잠금의 owner와 일치하지 않습니다.",
            reason="owner_session_mismatch",
        )

    owner_token = owner.get("token")
    if not isinstance(owner_token, str) or not owner_token:
        raise GuardError(
            "현재 잠금의 owner token을 확인할 수 없습니다.",
            reason="owner_token_unreadable",
        )
    resolved_token = token if token is not None else owner_token
    verify_owner(ctx, session, resolved_token)

    if snapshot_arg is not None:
        return resolved_token, Path(snapshot_arg)

    matches = owned_snapshots(ctx, session, resolved_token)
    if not matches:
        raise GuardError(
            "현재 lock owner와 일치하는 스냅샷을 찾지 못했습니다.",
            reason="owner_snapshot_not_found",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
        )
    if len(matches) > 1:
        raise GuardError(
            "현재 lock owner와 일치하는 스냅샷이 여러 개여서 자동 선택할 수 없습니다.",
            reason="owner_snapshot_ambiguous",
            matching_snapshots=[str(path) for path in matches],
        )
    return resolved_token, matches[0]


def release_lock(ctx: dict[str, Path], session: str, token: str) -> None:
    verify_owner(ctx, session, token)
    lock_dir, _ = lock_paths(ctx)
    shutil.rmtree(lock_dir)


def capture_snapshot(
    ctx: dict[str, Path],
    session: str,
    token: str,
    *,
    max_untracked_bytes: int,
) -> tuple[Path, list[str], dict[str, Any]]:
    root = ctx["root"]
    snapshot_root = ctx["git_dir"] / SNAPSHOT_DIR_NAME
    snapshot_root.mkdir(parents=True, exist_ok=True)

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{timestamp}-{safe_session(session)[:24]}-{secrets.token_hex(4)}"
    snapshot = snapshot_root / name
    snapshot.mkdir(mode=0o700)

    warnings: list[str] = []
    manifest, untracked_total = untracked_manifest(root)
    fingerprint = repository_fingerprint(root)

    files: dict[str, bytes] = {
        "status.txt": run_git(["status", "--short", "--branch", "--untracked-files=all"], cwd=root),
        "status-porcelain-v2.z": run_git(
            ["status", "--porcelain=v2", "-z", "--untracked-files=all"], cwd=root
        ),
        "working.diff": run_git(
            ["diff", "--binary", "--full-index", "--no-ext-diff"], cwd=root
        ),
        "staged.diff": run_git(
            ["diff", "--cached", "--binary", "--full-index", "--no-ext-diff"], cwd=root
        ),
        "working.stat": run_git(["diff", "--stat"], cwd=root),
        "staged.stat": run_git(["diff", "--cached", "--stat"], cwd=root),
        "untracked.z": b"\0".join(p.encode("utf-8", "surrogateescape") for p in list_untracked(root)),
    }
    for filename, data in files.items():
        (snapshot / filename).write_bytes(data)

    archived_untracked = False
    if manifest and untracked_total <= max_untracked_bytes:
        archive_path = snapshot / "untracked.tar.gz"
        with tarfile.open(archive_path, mode="w:gz", dereference=False) as tar:
            for entry in manifest:
                if entry.get("kind") not in {"file", "symlink"}:
                    continue
                rel = entry["path"]
                path = root / rel
                if path.exists() or path.is_symlink():
                    tar.add(path, arcname=rel, recursive=False)
        archived_untracked = True
    elif manifest:
        warnings.append(
            "추적되지 않은 파일의 총 크기가 한도를 초과하여 파일 목록과 해시만 저장했습니다 "
            f"({untracked_total} bytes > {max_untracked_bytes} bytes)."
        )

    snapshot_files = {}
    for path in sorted(snapshot.iterdir()):
        if not path.is_file() or path.name == MARKER_NAME:
            continue
        data = path.read_bytes()
        snapshot_files[path.name] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    metadata = {
        "schema": SCHEMA_VERSION,
        "session": session,
        "token": token,
        "created_at": utc_now(),
        "project_root": str(root),
        "git_dir": str(ctx["git_dir"]),
        "common_dir": str(ctx["common_dir"]),
        "head": current_head(root),
        "branch": branch_name(root),
        "fingerprint": fingerprint,
        "untracked_total_bytes": untracked_total,
        "untracked_archived": archived_untracked,
        "untracked_manifest": manifest,
        "warnings": warnings,
        "snapshot_files": snapshot_files,
    }
    marker = snapshot / MARKER_NAME
    marker.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
    return snapshot, warnings, fingerprint


def validate_snapshot(ctx: dict[str, Path], snapshot: Path, session: str, token: str) -> dict[str, Any]:
    snapshot_root = (ctx["git_dir"] / SNAPSHOT_DIR_NAME).resolve()
    resolved = snapshot.resolve()
    try:
        resolved.relative_to(snapshot_root)
    except ValueError as exc:
        raise GuardError("현재 Git 작업 트리 밖의 스냅샷은 제거할 수 없습니다.") from exc

    marker = resolved / MARKER_NAME
    metadata = read_json(marker)
    if not metadata:
        raise GuardError("스냅샷 소유권 표시가 없거나 손상되었습니다.")
    if metadata.get("session") != session or metadata.get("token") != token:
        raise GuardError("현재 세션이 소유하지 않은 스냅샷은 제거할 수 없습니다.")
    if Path(metadata.get("project_root", "")).resolve() != ctx["root"]:
        raise GuardError("스냅샷의 프로젝트 루트가 현재 저장소와 일치하지 않습니다.")
    return metadata


def cmd_probe(args: argparse.Namespace) -> None:
    cwd = Path.cwd().resolve()
    ctx = repo_context(cwd)
    lock_dir, owner_file = lock_paths(ctx)
    payload = {
        "ok": True,
        "project_root": str(ctx["root"]),
        "git_dir": str(ctx["git_dir"]),
        "common_dir": str(ctx["common_dir"]),
        "head": current_head(ctx["root"]),
        "branch": branch_name(ctx["root"]),
        "operations": operation_state(ctx["git_dir"]),
        "git_lock_files": external_locks(ctx["git_dir"], ctx["common_dir"]),
        "claude_atomic_lock": read_json(owner_file) if lock_dir.exists() else None,
    }
    emit(payload)


def cmd_begin(args: argparse.Namespace) -> None:
    cwd = Path.cwd().resolve()
    ctx = repo_context(cwd)
    operations = operation_state(ctx["git_dir"])
    git_lock_stale_after = int(
        getattr(args, "git_lock_stale_after", DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS)
    )
    git_locks = external_lock_details(
        ctx["git_dir"], ctx["common_dir"], stale_after=git_lock_stale_after
    )
    if operations:
        raise GuardError(f"진행 중인 Git 작업이 있어 중단합니다: {', '.join(operations)}")
    if git_locks:
        stale = [entry for entry in git_locks if entry["stale_candidate"]]
        summary = (
            "오래되고 비어 있으며 사용 중이 아닌 lock으로 보입니다. "
            "명시적 `clean`으로 안전 조건을 재검사해 정리할 수 있습니다."
            if stale
            else "다른 git 프로세스가 사용 중일 수 있으니 끝나기를 기다리십시오."
        )
        raise GuardError(
            "Git 자체 lock 파일이 있어 Guard begin을 중단합니다. begin은 이 파일을 "
            "삭제하지 않습니다. "
            f"{summary} locks={[entry['path'] for entry in git_locks]}",
            reason="git_external_lock",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            git_locks=git_locks,
            git_lock_files=[entry["path"] for entry in git_locks],
            recovery=git_lock_recovery(git_locks),
        )

    session = safe_session(args.session)
    token, _, reclaimed = acquire_lock(
        ctx,
        session,
        reclaim_stale=bool(getattr(args, "reclaim_stale", False)),
        stale_after=int(getattr(args, "stale_after", DEFAULT_STALE_AFTER_SECONDS)),
    )
    try:
        snapshot, warnings, fingerprint = capture_snapshot(
            ctx,
            session,
            token,
            max_untracked_bytes=args.max_untracked_mib * 1024 * 1024,
        )
    except Exception:
        try:
            release_lock(ctx, session, token)
        except Exception:
            pass
        raise

    emit(
        {
            "ok": True,
            "session": session,
            "token": token,
            "snapshot": str(snapshot),
            "project_root": str(ctx["root"]),
            "head": current_head(ctx["root"]),
            "branch": branch_name(ctx["root"]),
            "fingerprint": fingerprint["fingerprint"],
            "warnings": warnings,
            "reclaimed_lock": reclaimed is not None,
            "reclaim_reason": reclaimed["reason"] if reclaimed else None,
            "previous_owner": reclaimed["previous_owner"] if reclaimed else None,
            "previous_lock_age_seconds": (
                reclaimed["previous_lock_age_seconds"] if reclaimed else None
            ),
            "cleanup_policy": "모든 의도된 커밋과 검증이 성공한 경우에만 finish를 실행하십시오.",
        }
    )


def cmd_fingerprint(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    payload = repository_fingerprint(ctx["root"])
    payload.update(
        {
            "ok": True,
            "head": current_head(ctx["root"]),
            "branch": branch_name(ctx["root"]),
            "project_root": str(ctx["root"]),
        }
    )
    emit(payload)


def review_invariants(
    ctx: dict[str, Path],
    snapshot: Path,
    metadata: dict[str, Any],
    *,
    source_read_only: bool = False,
    expected_branch: Optional[str] = None,
) -> dict[str, Any]:
    start_head = metadata.get("head", "")
    start_branch = metadata.get("branch", "")
    current_head_value = current_head(ctx["root"])
    current_branch_value = branch_name(ctx["root"])
    start_staged = (snapshot / "staged.diff").read_bytes()
    current_staged = run_git(
        ["diff", "--cached", "--binary", "--full-index", "--no-ext-diff"],
        cwd=ctx["root"],
    )
    branch_valid = current_branch_value == start_branch
    if expected_branch:
        valid_expected = subprocess.run(
            ["git", "check-ref-format", "--branch", expected_branch],
            cwd=ctx["root"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        branch_valid = (
            valid_expected
            and start_branch in {"main", "master"}
            and current_branch_value == expected_branch
            and current_branch_value != start_branch
        )
    checks = {
        "head_unchanged": current_head_value == start_head,
        "branch_unchanged_or_expected": branch_valid,
        "staged_diff_unchanged": current_staged == start_staged,
    }
    if source_read_only:
        start_working = (snapshot / "working.diff").read_bytes()
        current_working = run_git(
            ["diff", "--binary", "--full-index", "--no-ext-diff"],
            cwd=ctx["root"],
        )
        start_status = (snapshot / "status-porcelain-v2.z").read_bytes()
        current_status = run_git(
            ["status", "--porcelain=v2", "-z", "--untracked-files=all"],
            cwd=ctx["root"],
        )
        current_untracked, _ = untracked_manifest(ctx["root"])
        checks.update(
            {
                "working_diff_unchanged": current_working == start_working,
                "status_unchanged": current_status == start_status,
                "untracked_content_unchanged": (
                    current_untracked == metadata.get("untracked_manifest", [])
                ),
            }
        )
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "start_head": start_head,
        "current_head": current_head_value,
        "start_branch": start_branch,
        "current_branch": current_branch_value,
    }


def cmd_verify_review(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    token, snapshot = resolve_owned_review_context(
        ctx, session, args.token, args.snapshot
    )
    metadata = validate_snapshot(ctx, snapshot, session, token)
    result = review_invariants(
        ctx,
        snapshot,
        metadata,
        source_read_only=args.source_read_only,
        expected_branch=args.expected_branch,
    )
    if not result["ok"]:
        failed = [name for name, passed in result["checks"].items() if not passed]
        raise GuardError(
            "/cr 불변 조건을 충족하지 못했습니다: " + ", ".join(failed)
        )
    emit(result)


def audit_snapshot(snapshot: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    expected = metadata.get("snapshot_files")
    if not isinstance(expected, dict):
        raise GuardError("snapshot checksum inventory가 없습니다.")

    actual_names = {
        path.name
        for path in snapshot.iterdir()
        if path.is_file() and path.name != MARKER_NAME
    }
    expected_names = set(expected)
    missing = sorted(expected_names - actual_names)
    unexpected = sorted(actual_names - expected_names)
    corrupt = []
    for name in sorted(expected_names & actual_names):
        data = (snapshot / name).read_bytes()
        record = expected[name]
        if (
            len(data) != record.get("size")
            or hashlib.sha256(data).hexdigest() != record.get("sha256")
        ):
            corrupt.append(name)

    return {
        "ok": not missing and not unexpected and not corrupt,
        "missing": missing,
        "unexpected": unexpected,
        "corrupt": corrupt,
        "files": len(expected),
    }


def cmd_audit_snapshot(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    verify_owner(ctx, session, args.token)
    snapshot = Path(args.snapshot)
    metadata = validate_snapshot(ctx, snapshot, session, args.token)
    result = audit_snapshot(snapshot, metadata)
    if not result["ok"]:
        raise GuardError(
            "snapshot 무결성 검증 실패: "
            f"missing={result['missing']}, unexpected={result['unexpected']}, "
            f"corrupt={result['corrupt']}"
        )
    emit(result)


def cmd_finish(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    token, snapshot = resolve_owned_review_context(
        ctx, session, args.token, args.snapshot
    )
    metadata = validate_snapshot(ctx, snapshot, session, token)
    if args.source_read_only and not args.review_only:
        raise GuardError("--source-read-only는 --review-only와 함께 사용해야 합니다.")
    audit_result = None
    if isinstance(metadata.get("snapshot_files"), dict):
        audit_result = audit_snapshot(snapshot, metadata)
        if not audit_result["ok"]:
            raise GuardError(
                "snapshot 무결성 검증에 실패해 삭제하지 않습니다: "
                f"missing={audit_result['missing']}, "
                f"unexpected={audit_result['unexpected']}, "
                f"corrupt={audit_result['corrupt']}"
            )

    review_result = None
    if args.review_only:
        review_result = review_invariants(
            ctx,
            snapshot,
            metadata,
            source_read_only=args.source_read_only,
            expected_branch=args.expected_branch,
        )
        if not review_result["ok"]:
            failed = [
                name for name, passed in review_result["checks"].items() if not passed
            ]
            raise GuardError(
                "/cr 불변 조건을 충족하지 못해 스냅샷을 삭제하지 않습니다: "
                + ", ".join(failed)
            )

    dirty = decode(
        run_git(["status", "--porcelain", "--untracked-files=all"], cwd=ctx["root"])
    )
    if dirty and not (args.allow_dirty or args.review_only):
        raise GuardError(
            "작업 트리가 깨끗하지 않아 스냅샷을 삭제하지 않습니다. "
            "모든 의도된 변경이 커밋되었는지 확인하십시오."
        )

    if not args.keep_snapshot:
        shutil.rmtree(snapshot)
    release_lock(ctx, session, token)
    emit(
        {
            "ok": True,
            "snapshot_removed": not args.keep_snapshot,
            "snapshot": str(snapshot),
            "lock_released": True,
            "worktree_clean": not bool(dirty),
            "review_invariants": review_result,
            "snapshot_audit": audit_result,
        }
    )


def cmd_abort(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    verify_owner(ctx, session, args.token)
    if args.snapshot:
        snapshot = Path(args.snapshot)
    else:
        matches = owned_snapshots(ctx, session, args.token)
        if not matches:
            raise GuardError(
                "현재 lock owner와 일치하는 스냅샷을 찾지 못했습니다. "
                "`status`로 경로를 확인한 뒤 --snapshot을 명시하십시오.",
                reason="owner_snapshot_not_found",
                project_root=str(ctx["root"]),
                git_dir=str(ctx["git_dir"]),
            )
        if len(matches) > 1:
            raise GuardError(
                "현재 lock owner와 일치하는 스냅샷이 여러 개입니다. "
                "해제할 경로를 --snapshot으로 명시하십시오.",
                reason="owner_snapshot_ambiguous",
                matching_snapshots=[str(path) for path in matches],
            )
        snapshot = matches[0]
    validate_snapshot(ctx, snapshot, session, args.token)
    release_lock(ctx, session, args.token)
    emit(
        {
            "ok": True,
            "snapshot_removed": False,
            "snapshot": str(snapshot),
            "lock_released": True,
            "message": "작업 실패/중단으로 Diff 스냅샷은 보존했습니다.",
        }
    )


def cmd_session_end(args: argparse.Namespace) -> None:
    """Release only a lock owned by the ending Claude session."""
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    lock_dir, owner_file = lock_paths(ctx)
    if not lock_dir.exists():
        emit(
            {
                "ok": True,
                "reason": "lock_not_found",
                "session": session,
                "session_end_reason": args.reason,
                "project_root": str(ctx["root"]),
                "lock_found": False,
                "lock_released": False,
                "snapshot_removed": False,
            }
        )
    if lock_dir.is_symlink() or not lock_dir.is_dir() or owner_file.is_symlink():
        raise GuardError(
            "SessionEnd 정리 대상 잠금 경로가 안전하지 않습니다.",
            reason="session_end_lock_path_unsafe",
            lock_path=str(lock_dir),
        )

    owner_bytes = owner_file.read_bytes()
    owner = read_json(owner_file)
    if not owner:
        raise GuardError(
            "SessionEnd 정리 대상 owner 정보가 없거나 손상되었습니다.",
            reason="session_end_owner_unreadable",
            lock_path=str(lock_dir),
        )
    if owner.get("session") != session:
        emit(
            {
                "ok": True,
                "reason": "session_end_owner_mismatch",
                "session": session,
                "session_end_reason": args.reason,
                "project_root": str(ctx["root"]),
                "lock_found": True,
                "lock_released": False,
                "snapshot_removed": False,
                "lock_owner_session": owner.get("session"),
            }
        )
    if (
        Path(str(owner.get("worktree", ""))).resolve() != ctx["root"]
        or Path(str(owner.get("git_dir", ""))).resolve() != ctx["git_dir"]
    ):
        raise GuardError(
            "SessionEnd 정리 대상 owner의 worktree 범위가 일치하지 않습니다.",
            reason="session_end_owner_scope_mismatch",
            lock_path=str(lock_dir),
        )
    entries = sorted(path.name for path in lock_dir.iterdir())
    if entries != [owner_file.name]:
        raise GuardError(
            "SessionEnd 잠금 디렉터리에 알 수 없는 항목이 있어 해제를 거부합니다.",
            reason="session_end_lock_contents_unexpected",
            lock_path=str(lock_dir),
            unexpected_entries=[name for name in entries if name != owner_file.name],
        )
    if owner_file.read_bytes() != owner_bytes:
        raise GuardError(
            "SessionEnd 확인 중 잠금 owner가 바뀌어 해제를 거부합니다.",
            reason="session_end_owner_changed",
            lock_path=str(lock_dir),
        )

    owner_file.unlink()
    lock_dir.rmdir()
    emit(
        {
            "ok": True,
            "reason": "session_end_owner_released",
            "session": session,
            "session_end_reason": args.reason,
            "project_root": str(ctx["root"]),
            "lock_found": True,
            "lock_released": True,
            "snapshot_removed": False,
            "message": "종료된 Claude 세션의 잠금을 해제하고 Diff 스냅샷은 보존했습니다.",
        }
    )


def cmd_clean(args: argparse.Namespace) -> None:
    """Explicitly release only the current worktree's CommitForge lock."""
    ctx = repo_context(Path.cwd().resolve())
    lock_dir, owner_file = lock_paths(ctx)
    initial_git_locks = external_lock_details(
        ctx["git_dir"],
        ctx["common_dir"],
        stale_after=int(
            getattr(args, "git_lock_stale_after", DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS)
        ),
    )
    git_lock_cleanup = remove_stale_git_locks(ctx, initial_git_locks)
    git_locks = external_lock_details(
        ctx["git_dir"],
        ctx["common_dir"],
        stale_after=int(
            getattr(args, "git_lock_stale_after", DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS)
        ),
    )
    removed_git_lock_note = (
        " 안전 조건을 충족한 stale Git lock을 제거했습니다: "
        f"{git_lock_cleanup['removed']}."
        if git_lock_cleanup["removed"]
        else ""
    )
    git_lock_note = (
        " 다만 Git 자체 lock이 남아 있어 명령 실행은 여전히 차단됩니다: "
        f"{[entry['path'] for entry in git_locks]}. 안전 조건을 충족하지 않아 "
        "이 파일은 보존했습니다."
        if git_locks
        else ""
    )
    if not lock_dir.exists():
        emit(
            {
                "ok": True,
                "project_root": str(ctx["root"]),
                "git_dir": str(ctx["git_dir"]),
                "lock_scope": "worktree_git_dir",
                "lock_path": str(lock_dir),
                "lock_found": False,
                "lock_released": False,
                "snapshots_removed": 0,
                "git_locks_removed": git_lock_cleanup["removed"],
                "git_lock_cleanup": git_lock_cleanup,
                "git_locks": git_locks,
                "git_lock_recovery": git_lock_recovery(git_locks) if git_locks else None,
                "message": (
                    "현재 Git worktree에 CommitForge 잠금이 없습니다."
                    + removed_git_lock_note
                    + git_lock_note
                ),
            }
        )
    if lock_dir.is_symlink() or not lock_dir.is_dir():
        raise GuardError(
            "현재 worktree 잠금 경로가 일반 디렉터리가 아니어서 clean을 거부합니다.",
            reason="clean_lock_path_unsafe",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            lock_path=str(lock_dir),
        )
    if owner_file.is_symlink():
        raise GuardError(
            "잠금 owner 경로가 symbolic link여서 clean을 거부합니다.",
            reason="clean_owner_path_unsafe",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            lock_path=str(lock_dir),
        )

    owner_bytes: bytes | None = None
    try:
        owner_bytes = owner_file.read_bytes()
    except FileNotFoundError:
        pass
    owner = read_json(owner_file) if owner_bytes is not None else None

    if owner:
        owner_worktree = owner.get("worktree")
        owner_git_dir = owner.get("git_dir")
        if (
            not isinstance(owner_worktree, str)
            or Path(owner_worktree).resolve() != ctx["root"]
        ):
            raise GuardError(
                "잠금 owner의 worktree가 현재 저장소와 일치하지 않아 clean을 거부합니다.",
                reason="clean_owner_scope_mismatch",
                project_root=str(ctx["root"]),
                git_dir=str(ctx["git_dir"]),
                lock_path=str(lock_dir),
                lock_owner=owner,
            )
        if (
            isinstance(owner_git_dir, str)
            and Path(owner_git_dir).resolve() != ctx["git_dir"]
        ):
            raise GuardError(
                "잠금 owner의 git_dir가 현재 worktree와 일치하지 않아 clean을 거부합니다.",
                reason="clean_owner_scope_mismatch",
                project_root=str(ctx["root"]),
                git_dir=str(ctx["git_dir"]),
                lock_path=str(lock_dir),
                lock_owner=owner,
            )

    owner_snapshots: list[str] = []
    if owner:
        owner_session = owner.get("session")
        owner_token = owner.get("token")
        if isinstance(owner_session, str) and isinstance(owner_token, str):
            owner_snapshots = [
                str(path) for path in owned_snapshots(ctx, owner_session, owner_token)
            ]

    if not lock_dir.exists():
        emit(
            {
                "ok": True,
                "project_root": str(ctx["root"]),
                "git_dir": str(ctx["git_dir"]),
                "lock_scope": "worktree_git_dir",
                "lock_path": str(lock_dir),
                "lock_found": True,
                "lock_released": True,
                "released_by_other": True,
                "lock_owner": owner,
                "lock_owner_snapshots": owner_snapshots,
                "snapshots_removed": 0,
                "git_locks_removed": git_lock_cleanup["removed"],
                "git_lock_cleanup": git_lock_cleanup,
                "git_locks": git_locks,
                "git_lock_recovery": git_lock_recovery(git_locks) if git_locks else None,
                "message": (
                    "확인 중 다른 실행이 현재 worktree 잠금을 해제했습니다."
                    + removed_git_lock_note
                    + git_lock_note
                ),
            }
        )

    current_owner_bytes: bytes | None = None
    try:
        current_owner_bytes = owner_file.read_bytes()
    except FileNotFoundError:
        pass
    if current_owner_bytes != owner_bytes:
        raise GuardError(
            "확인 중 잠금 owner가 바뀌어 clean을 중단합니다.",
            reason="clean_lock_owner_changed",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            lock_path=str(lock_dir),
        )

    entries = sorted(path.name for path in lock_dir.iterdir())
    unexpected = [name for name in entries if name != owner_file.name]
    if unexpected:
        raise GuardError(
            "잠금 디렉터리에 알 수 없는 항목이 있어 clean을 거부합니다.",
            reason="clean_lock_contents_unexpected",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            lock_path=str(lock_dir),
            unexpected_entries=unexpected,
        )

    try:
        if owner_file.exists():
            owner_file.unlink()
        lock_dir.rmdir()
    except OSError as exc:
        if owner_bytes is not None and lock_dir.exists() and not owner_file.exists():
            try:
                owner_file.write_bytes(owner_bytes)
            except OSError:
                pass
        raise GuardError(
            "현재 worktree 잠금을 원자적으로 정리하지 못했습니다.",
            reason="clean_release_failed",
            project_root=str(ctx["root"]),
            git_dir=str(ctx["git_dir"]),
            lock_path=str(lock_dir),
        ) from exc

    emit(
        {
            "ok": True,
            "project_root": str(ctx["root"]),
            "git_dir": str(ctx["git_dir"]),
            "lock_scope": "worktree_git_dir",
            "lock_path": str(lock_dir),
            "lock_found": True,
            "lock_released": True,
            "lock_owner": owner,
            "lock_owner_readable": owner is not None,
            "lock_owner_snapshots": owner_snapshots,
            "snapshots_removed": 0,
            "requested_by_session": safe_session(args.request_session),
            "git_locks_removed": git_lock_cleanup["removed"],
            "git_lock_cleanup": git_lock_cleanup,
            "git_locks": git_locks,
            "git_lock_recovery": git_lock_recovery(git_locks) if git_locks else None,
            "warning": (
                "기존 세션이 실행 중이었다면 해당 실행은 더 이상 Guard 잠금을 "
                "소유하지 않습니다."
            ),
            "message": (
                "현재 Git worktree의 CommitForge 잠금을 해제했습니다."
                + removed_git_lock_note
                + git_lock_note
            ),
        }
    )


def cmd_status(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    lock_dir, owner_file = lock_paths(ctx)
    owner = read_json(owner_file) if lock_dir.exists() else None
    owner_snapshots = []
    if owner:
        owner_session = owner.get("session")
        owner_token = owner.get("token")
        if isinstance(owner_session, str) and isinstance(owner_token, str):
            owner_snapshots = [
                str(path) for path in owned_snapshots(ctx, owner_session, owner_token)
            ]
    snapshot_root = ctx["git_dir"] / SNAPSHOT_DIR_NAME
    snapshots = []
    if snapshot_root.exists():
        snapshots = sorted(str(p) for p in snapshot_root.iterdir() if p.is_dir())
    stale_after = int(getattr(args, "stale_after", DEFAULT_STALE_AFTER_SECONDS))
    git_locks = external_lock_details(
        ctx["git_dir"],
        ctx["common_dir"],
        stale_after=int(
            getattr(args, "git_lock_stale_after", DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS)
        ),
    )
    profile = (
        lock_owner_profile(lock_dir, owner, session="", stale_after=stale_after)
        if lock_dir.exists()
        else None
    )
    emit(
        {
            "ok": True,
            "project_root": str(ctx["root"]),
            "git_dir": str(ctx["git_dir"]),
            "common_dir": str(ctx["common_dir"]),
            "lock_scope": "worktree_git_dir",
            "lock_path": str(lock_dir),
            "claude_atomic_lock": owner,
            "lock_created_at": owner.get("created_at") if owner else None,
            "lock_age_seconds": lock_age_seconds(owner),
            "lock_owner_hostname": profile["hostname"] if profile else None,
            "lock_owner_same_host": profile["same_host"] if profile else None,
            "current_hostname": socket.gethostname(),
            "stale_after_seconds": stale_after,
            "stale_candidate": bool(profile and profile["stale_candidate"]),
            "lock_owner_snapshots": owner_snapshots,
            "recovery": recovery_details(ctx, owner, owner_snapshots),
            "snapshots": snapshots,
            "operations": operation_state(ctx["git_dir"]),
            "git_lock_files": external_locks(ctx["git_dir"], ctx["common_dir"]),
            "git_locks": git_locks,
            "git_lock_recovery": git_lock_recovery(git_locks) if git_locks else None,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="Read-only repository and lock inspection")

    begin = sub.add_parser("begin", help="Acquire lock and capture a Diff snapshot")
    begin.add_argument("--session", required=True)
    begin.add_argument("--max-untracked-mib", type=int, default=256)
    begin.add_argument(
        "--reclaim-stale",
        action="store_true",
        help=(
            "Take over an existing lock only when it is on this host and is either "
            "older than --stale-after or owned by the same session"
        ),
    )
    begin.add_argument(
        "--stale-after",
        type=positive_seconds,
        default=DEFAULT_STALE_AFTER_SECONDS,
        help="Seconds after which an existing lock becomes a stale candidate",
    )
    begin.add_argument(
        "--git-lock-stale-after",
        type=positive_seconds,
        default=DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS,
        help="Seconds after which an empty, unheld Git lock file is reported as stale",
    )

    sub.add_parser("fingerprint", help="Compute a read-only repository fingerprint")

    finish = sub.add_parser("finish", help="Delete owned snapshot and release lock")
    finish.add_argument("--session", required=True)
    finish.add_argument(
        "--token",
        help="Owned token; omitted to use the matching current-worktree lock owner",
    )
    finish.add_argument(
        "--snapshot",
        help="Owned snapshot path; omitted when the owner identifies exactly one snapshot",
    )
    finish.add_argument("--allow-dirty", action="store_true")
    finish.add_argument(
        "--review-only",
        action="store_true",
        help="Require HEAD, branch, and staged diff to match the snapshot",
    )
    finish.add_argument(
        "--source-read-only",
        action="store_true",
        help="Also require working diff, status, and untracked content to match",
    )
    finish.add_argument(
        "--expected-branch",
        help="Allow only this branch change when the snapshot began on main/master",
    )
    finish.add_argument("--keep-snapshot", action="store_true")

    verify_review = sub.add_parser(
        "verify-review",
        help="Verify /cr HEAD, branch, and staged diff invariants",
    )
    verify_review.add_argument("--session", required=True)
    verify_review.add_argument(
        "--token",
        help="Owned token; omitted to use the matching current-worktree lock owner",
    )
    verify_review.add_argument(
        "--snapshot",
        help="Owned snapshot path; omitted when the owner identifies exactly one snapshot",
    )
    verify_review.add_argument("--source-read-only", action="store_true")
    verify_review.add_argument(
        "--expected-branch",
        help="Allow only this branch change when the snapshot began on main/master",
    )

    audit = sub.add_parser(
        "audit-snapshot",
        help="Verify owned snapshot file sizes and SHA-256 hashes",
    )
    audit.add_argument("--session", required=True)
    audit.add_argument("--token", required=True)
    audit.add_argument("--snapshot", required=True)

    abort = sub.add_parser("abort", help="Keep snapshot but release owned lock")
    abort.add_argument("--session", required=True)
    abort.add_argument("--token", required=True)
    abort.add_argument(
        "--snapshot",
        help="Owned snapshot path; omitted when session/token identify exactly one snapshot",
    )

    session_end = sub.add_parser(
        "session-end",
        help="Release a matching Claude session lock while preserving snapshots",
    )
    session_end.add_argument("--session", required=True)
    session_end.add_argument(
        "--reason",
        required=True,
    )

    clean = sub.add_parser(
        "clean",
        help="Explicitly release only the current worktree lock and preserve snapshots",
    )
    clean.add_argument("--request-session", default="manual-clean")
    clean.add_argument(
        "--git-lock-stale-after",
        type=positive_seconds,
        default=DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS,
        help="Seconds after which an empty, unheld Git lock file is reported as stale",
    )

    status = sub.add_parser("status", help="Show lock and snapshot status")
    status.add_argument(
        "--stale-after",
        type=positive_seconds,
        default=DEFAULT_STALE_AFTER_SECONDS,
        help="Seconds after which an existing lock is reported as a stale candidate",
    )
    status.add_argument(
        "--git-lock-stale-after",
        type=positive_seconds,
        default=DEFAULT_GIT_LOCK_STALE_AFTER_SECONDS,
        help="Seconds after which an empty, unheld Git lock file is reported as stale",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "probe": cmd_probe,
        "begin": cmd_begin,
        "fingerprint": cmd_fingerprint,
        "verify-review": cmd_verify_review,
        "audit-snapshot": cmd_audit_snapshot,
        "finish": cmd_finish,
        "abort": cmd_abort,
        "session-end": cmd_session_end,
        "clean": cmd_clean,
        "status": cmd_status,
    }
    try:
        handlers[args.command](args)
    except GuardError as exc:
        emit({"ok": False, "error": str(exc), **exc.details}, exit_code=2)
    except KeyboardInterrupt:
        emit({"ok": False, "error": "사용자 중단"}, exit_code=130)
    except Exception as exc:
        emit(
            {
                "ok": False,
                "error": f"예기치 않은 guard 오류: {type(exc).__name__}: {exc}",
            },
            exit_code=3,
        )


if __name__ == "__main__":
    main()
