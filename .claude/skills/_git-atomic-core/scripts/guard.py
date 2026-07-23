#!/usr/bin/env python3
"""Safety guard for the Claude Code atomic Git skills.

The guard provides:
- a per-worktree advisory lock;
- a session-unique snapshot of staged/unstaged diffs and untracked files;
- repository fingerprints for TOCTOU detection;
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
import subprocess
import sys
import tarfile
from typing import Any


SCHEMA_VERSION = 1
LOCK_DIR_NAME = "claude-atomic.lock"
SNAPSHOT_DIR_NAME = "claude-atomic-snapshots"
MARKER_NAME = ".cca-snapshot.json"


class GuardError(RuntimeError):
    """Expected safety failure."""


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


def lock_paths(ctx: dict[str, Path]) -> tuple[Path, Path]:
    lock_dir = ctx["git_dir"] / LOCK_DIR_NAME
    owner_file = lock_dir / "owner.json"
    return lock_dir, owner_file


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def safe_session(value: str) -> str:
    value = value.strip() or "unknown-session"
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)[:80]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


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


def acquire_lock(ctx: dict[str, Path], session: str) -> tuple[str, Path]:
    lock_dir, owner_file = lock_paths(ctx)
    token = secrets.token_hex(24)
    owner = {
        "schema": SCHEMA_VERSION,
        "session": session,
        "token": token,
        "created_at": utc_now(),
        "worktree": str(ctx["root"]),
        "git_dir": str(ctx["git_dir"]),
    }
    try:
        lock_dir.mkdir(mode=0o700)
    except FileExistsError:
        existing = read_json(owner_file)
        raise GuardError(
            "이 작업 트리에서 다른 /cc 또는 /cca 실행이 진행 중입니다. "
            f"lock={lock_dir}, owner={existing or 'unreadable'}"
        )
    try:
        owner_file.write_text(json.dumps(owner, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(lock_dir, ignore_errors=True)
        raise
    return token, lock_dir


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
    locks = external_locks(ctx["git_dir"], ctx["common_dir"])
    if operations:
        raise GuardError(f"진행 중인 Git 작업이 있어 중단합니다: {', '.join(operations)}")
    if locks:
        raise GuardError(f"다른 Git 프로세스의 잠금이 있어 중단합니다: {locks}")

    session = safe_session(args.session)
    token, _ = acquire_lock(ctx, session)
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


def cmd_finish(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    verify_owner(ctx, session, args.token)
    snapshot = Path(args.snapshot)
    validate_snapshot(ctx, snapshot, session, args.token)

    dirty = decode(
        run_git(["status", "--porcelain", "--untracked-files=all"], cwd=ctx["root"])
    )
    if dirty and not args.allow_dirty:
        raise GuardError(
            "작업 트리가 깨끗하지 않아 스냅샷을 삭제하지 않습니다. "
            "모든 의도된 변경이 커밋되었는지 확인하십시오."
        )

    if not args.keep_snapshot:
        shutil.rmtree(snapshot)
    release_lock(ctx, session, args.token)
    emit(
        {
            "ok": True,
            "snapshot_removed": not args.keep_snapshot,
            "snapshot": str(snapshot),
            "lock_released": True,
            "worktree_clean": not bool(dirty),
        }
    )


def cmd_abort(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    session = safe_session(args.session)
    verify_owner(ctx, session, args.token)
    snapshot = Path(args.snapshot)
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


def cmd_status(args: argparse.Namespace) -> None:
    ctx = repo_context(Path.cwd().resolve())
    lock_dir, owner_file = lock_paths(ctx)
    snapshot_root = ctx["git_dir"] / SNAPSHOT_DIR_NAME
    snapshots = []
    if snapshot_root.exists():
        snapshots = sorted(str(p) for p in snapshot_root.iterdir() if p.is_dir())
    emit(
        {
            "ok": True,
            "project_root": str(ctx["root"]),
            "claude_atomic_lock": read_json(owner_file) if lock_dir.exists() else None,
            "snapshots": snapshots,
            "operations": operation_state(ctx["git_dir"]),
            "git_lock_files": external_locks(ctx["git_dir"], ctx["common_dir"]),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("probe", help="Read-only repository and lock inspection")

    begin = sub.add_parser("begin", help="Acquire lock and capture a Diff snapshot")
    begin.add_argument("--session", required=True)
    begin.add_argument("--max-untracked-mib", type=int, default=256)

    sub.add_parser("fingerprint", help="Compute a read-only repository fingerprint")

    finish = sub.add_parser("finish", help="Delete owned snapshot and release lock")
    finish.add_argument("--session", required=True)
    finish.add_argument("--token", required=True)
    finish.add_argument("--snapshot", required=True)
    finish.add_argument("--allow-dirty", action="store_true")
    finish.add_argument("--keep-snapshot", action="store_true")

    abort = sub.add_parser("abort", help="Keep snapshot but release owned lock")
    abort.add_argument("--session", required=True)
    abort.add_argument("--token", required=True)
    abort.add_argument("--snapshot", required=True)

    sub.add_parser("status", help="Show lock and snapshot status")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "probe": cmd_probe,
        "begin": cmd_begin,
        "fingerprint": cmd_fingerprint,
        "finish": cmd_finish,
        "abort": cmd_abort,
        "status": cmd_status,
    }
    try:
        handlers[args.command](args)
    except GuardError as exc:
        emit({"ok": False, "error": str(exc)}, exit_code=2)
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
