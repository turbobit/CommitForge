import { describe, expect, it } from "vitest";
import { parseGuardStatus, runGuardStatus, type GuardRunner } from "../src/core/guard";

const idle = JSON.stringify({
  ok: true,
  project_root: "/repo",
  git_dir: "/repo/.git",
  common_dir: "/repo/.git",
  lock_scope: "worktree_git_dir",
  lock_path: "/repo/.git/claude-atomic.lock",
  claude_atomic_lock: null,
  lock_created_at: null,
  lock_age_seconds: null,
  lock_owner_hostname: null,
  lock_owner_same_host: null,
  current_hostname: "mac.local",
  stale_after_seconds: 3600,
  stale_candidate: false,
  lock_owner_snapshots: [],
  recovery: null,
  snapshots: [],
  operations: [],
  git_lock_files: [],
  git_locks: [],
  git_lock_recovery: null,
});

const held = JSON.stringify({
  ok: true,
  project_root: "/repo",
  git_dir: "/repo/.git",
  claude_atomic_lock: { session: "abc123", token: "t", created_at: "2026-09-11T08:00:00Z" },
  lock_age_seconds: 742,
  lock_owner_hostname: "other.local",
  lock_owner_same_host: false,
  current_hostname: "mac.local",
  stale_candidate: false,
  snapshots: ["/repo/.git/claude-atomic-snapshots/abc123"],
  operations: ["rebase-merge"],
  git_lock_files: ["/repo/.git/index.lock"],
});

describe("parseGuardStatus", () => {
  it("유휴 상태를 읽는다", () => {
    const status = parseGuardStatus(idle);

    expect(status.ok).toBe(true);
    expect(status.projectRoot).toBe("/repo");
    expect(status.lockOwner).toBeNull();
    expect(status.snapshots).toEqual([]);
    expect(status.currentHostname).toBe("mac.local");
  });

  it("lock 보유 상태를 읽는다", () => {
    const status = parseGuardStatus(held);

    expect(status.lockOwner).toEqual({ session: "abc123", created_at: "2026-09-11T08:00:00Z" });
    expect(status.lockAgeSeconds).toBe(742);
    expect(status.lockOwnerSameHost).toBe(false);
    expect(status.operations).toEqual(["rebase-merge"]);
    expect(status.gitLockFiles).toEqual(["/repo/.git/index.lock"]);
  });

  it("JSON이 아니면 실패한다", () => {
    expect(() => parseGuardStatus("보통 에러 메시지")).toThrow(/guard/);
  });

  it("누락된 선택 필드는 기본값으로 채운다", () => {
    const status = parseGuardStatus('{"ok":true,"project_root":"/r","git_dir":"/r/.git"}');

    expect(status.snapshots).toEqual([]);
    expect(status.operations).toEqual([]);
    expect(status.staleCandidate).toBe(false);
  });
});

describe("runGuardStatus", () => {
  it("guard.py status를 올바른 인자로 실행한다", async () => {
    const calls: Array<{ exe: string; args: string[]; cwd: string }> = [];
    const run: GuardRunner = async (exe, args, cwd) => {
      calls.push({ exe, args, cwd });
      return { stdout: idle, stderr: "", code: 0 };
    };

    await runGuardStatus("python3", "/repo/.claude/g/guard.py", "/repo", run);

    expect(calls).toEqual([
      { exe: "python3", args: ["/repo/.claude/g/guard.py", "status"], cwd: "/repo" },
    ]);
  });

  it("0이 아닌 종료 코드는 stderr를 담아 실패한다", async () => {
    const run: GuardRunner = async () => ({
      stdout: "",
      stderr: "현재 디렉터리는 Git 작업 트리가 아닙니다.",
      code: 1,
    });

    await expect(runGuardStatus("python3", "/g.py", "/tmp", run)).rejects.toThrow(
      /Git 작업 트리가 아닙니다/,
    );
  });
});
