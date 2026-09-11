import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseGuardStatus, runGuardStatus, type GuardRunner } from "../src/core/guard";

/**
 * spec §10: "guard.ts: guard.py status 실제 출력 샘플 파싱". 두 픽스처는
 * `.claude/skills/_git-atomic-core/scripts/guard.py status`를 임시 git 저장소에서
 * 직접 실행해 얻은 실제 출력이다 (경로·호스트명만 재현 가능하도록 다듬었다).
 */
const idle = readFileSync(join(__dirname, "fixtures", "guard-status-idle.json"), "utf8");
const held = readFileSync(join(__dirname, "fixtures", "guard-status-held.json"), "utf8");

describe("parseGuardStatus", () => {
  it("유휴 상태를 읽는다", () => {
    const status = parseGuardStatus(idle);

    expect(status.ok).toBe(true);
    expect(status.projectRoot).toBe("/private/tmp/guard-fixture-repo");
    expect(status.lockOwner).toBeNull();
    expect(status.snapshots).toHaveLength(1);
    expect(status.currentHostname).toBe("dev-mac.local");
    expect(status.recovery).toBeNull();
    expect(status.gitLocks).toEqual([]);
  });

  it("lock 보유 상태를 읽는다", () => {
    const status = parseGuardStatus(held);

    expect(status.lockOwner).toEqual({
      session: "fixture-session-abc123",
      created_at: "2026-09-11T22:47:27.902164+00:00",
    });
    expect(status.lockAgeSeconds).toBe(240);
    expect(status.lockOwnerSameHost).toBe(true);
    expect(status.operations).toEqual([]);
    expect(status.gitLockFiles).toEqual(["/private/tmp/guard-fixture-repo/.git/index.lock"]);
  });

  it("spec §7.3 트리의 복구 제안에 필요한 recovery를 구조적으로 노출한다", () => {
    // spec §4 표의 "복구 제안"과 §7.3 트리 데이터 매핑 목록(recovery 포함)이 요구하는
    // 필드다. 지금까지 GuardStatus는 이를 아예 노출하지 않았다.
    const idleStatus = parseGuardStatus(idle);
    expect(idleStatus.recovery).toBeNull();

    const heldStatus = parseGuardStatus(held);
    expect(heldStatus.recovery).not.toBeNull();
    expect(heldStatus.recovery?.cleanHint).toContain("clean");
    expect(heldStatus.recovery?.abortArgv).toContain("abort");
    expect(heldStatus.recovery?.snapshot).toContain("claude-atomic-snapshots");
  });

  it(
    "spec §7.3 트리 예시 'git index.lock 존재 (4분)'을 렌더링할 수 있도록 " +
      "git_locks의 path/age_seconds/stale_candidate를 구조적으로 노출한다",
    () => {
      // git_lock_files는 경로 문자열만 담아 "4분"을 렌더링할 수 없다. git_locks의
      // age_seconds가 있어야 트리 예시를 그대로 그릴 수 있다.
      const status = parseGuardStatus(held);

      expect(status.gitLocks).toHaveLength(1);
      const [lock] = status.gitLocks;
      expect(lock?.path).toContain("index.lock");
      expect(lock?.ageSeconds).toBe(240);
      expect(lock?.staleCandidate).toBe(false);
    },
  );

  it("JSON이 아니면 실패한다", () => {
    expect(() => parseGuardStatus("보통 에러 메시지")).toThrow(/guard/);
  });

  it("누락된 선택 필드는 기본값으로 채운다", () => {
    const status = parseGuardStatus('{"ok":true,"project_root":"/r","git_dir":"/r/.git"}');

    expect(status.snapshots).toEqual([]);
    expect(status.operations).toEqual([]);
    expect(status.staleCandidate).toBe(false);
    expect(status.recovery).toBeNull();
    expect(status.gitLocks).toEqual([]);
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
