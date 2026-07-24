#!/usr/bin/env python3
"""Inspect deterministic local Git context for PR preview and creation."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} 실패")
    return result.stdout.strip()


def valid_branch(value: str) -> str:
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", value],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"잘못된 branch 이름: {value}")
    return value


def resolve_base(base: str, remote: str) -> str:
    candidates = (
        f"refs/remotes/{remote}/{base}",
        f"refs/heads/{base}",
    )
    for candidate in candidates:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    raise ValueError(
        f"base branch를 로컬에서 찾을 수 없습니다: {base} "
        f"(먼저 안전하게 fetch한 뒤 다시 실행하세요)"
    )


def parse_numstat(raw: str) -> tuple[int, int, int]:
    files = additions = deletions = 0
    for line in raw.splitlines():
        if not line:
            continue
        added, deleted, _path = line.split("\t", 2)
        files += 1
        if added.isdigit():
            additions += int(added)
        if deleted.isdigit():
            deletions += int(deleted)
    return files, additions, deletions


def inspect(base: str, remote: str, allow_base_head: bool = False) -> dict[str, object]:
    root = Path(git("rev-parse", "--show-toplevel"))
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if not branch:
        raise ValueError("detached HEAD에서는 PR을 준비할 수 없습니다")
    valid_branch(branch)
    valid_branch(base)
    same_as_base = branch == base
    if same_as_base and not allow_base_head:
        raise ValueError("현재 branch와 base branch가 같습니다")
    if same_as_base and branch not in {"main", "master"}:
        raise ValueError(
            "base와 같은 branch의 자동 분기는 main 또는 master에서만 허용됩니다"
        )
    if subprocess.run(
        ["git", "remote", "get-url", remote],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0:
        raise ValueError(f"Git remote를 찾을 수 없습니다: {remote}")

    base_ref = resolve_base(base, remote)
    if same_as_base and not base_ref.startswith(f"refs/remotes/{remote}/"):
        raise ValueError(
            "main/master 자동 분기에는 최신 remote tracking base가 필요합니다"
        )
    head = git("rev-parse", "HEAD")
    merge_base = git("merge-base", base_ref, "HEAD")
    range_text = f"{merge_base}..HEAD"
    commits = [
        {"sha": sha, "subject": subject}
        for line in git(
            "log",
            "--reverse",
            "--format=%H%x09%s",
            range_text,
        ).splitlines()
        if line
        for sha, subject in [line.split("\t", 1)]
    ]
    files, additions, deletions = parse_numstat(
        git("diff", "--numstat", range_text)
    )
    status = git("status", "--porcelain=v2", "--untracked-files=all")

    return {
        "ok": True,
        "root": str(root),
        "remote": remote,
        "remote_url": git("remote", "get-url", remote),
        "base": base,
        "base_ref": base_ref,
        "branch": branch,
        "branch_needs_creation": same_as_base,
        "head": head,
        "merge_base": merge_base,
        "range": range_text,
        "clean": not bool(status),
        "status": status.splitlines(),
        "commit_count": len(commits),
        "commits": commits,
        "files": files,
        "additions": additions,
        "deletions": deletions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--allow-base-head", action="store_true")
    args = parser.parse_args()
    try:
        payload = inspect(args.base, args.remote, args.allow_base_head)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
