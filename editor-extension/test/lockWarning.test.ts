import { describe, expect, it } from "vitest";
import { lockWarning } from "../src/vscode/quickPick";
import type { GuardStatus } from "../src/core/guard";

const base: GuardStatus = {
  ok: true,
  projectRoot: "/repo",
  gitDir: "/repo/.git",
  lockOwner: null,
  lockAgeSeconds: null,
  lockOwnerHostname: null,
  lockOwnerSameHost: null,
  currentHostname: "mac.local",
  staleCandidate: false,
  snapshots: [],
  recovery: null,
  operations: [],
  gitLockFiles: [],
  gitLocks: [],
};

const held: GuardStatus = {
  ...base,
  lockOwner: { session: "abc123", created_at: "2026-09-11T08:00:00Z" },
  lockAgeSeconds: 742,
  lockOwnerHostname: "other.local",
  lockOwnerSameHost: false,
};

describe("lockWarning", () => {
  it("lock이 없으면 경고하지 않는다", () => {
    expect(lockWarning(base, "cca")).toBeNull();
  });

  it("읽기 전용 명령은 lock이 있어도 경고하지 않는다", () => {
    expect(lockWarning(held, "cr")).toBeNull();
    expect(lockWarning(held, "ccr")).toBeNull();
  });

  it("쓰기 명령은 lock 보유자 정보를 담아 경고한다", () => {
    const warning = lockWarning(held, "cca");

    expect(warning).toContain("abc123");
    expect(warning).toContain("12분");
    expect(warning).toContain("other.local");
  });

  it("guard 상태를 모르면 경고하지 않는다", () => {
    expect(lockWarning(null, "cca")).toBeNull();
  });

  it("같은 호스트 lock도 쓰기 명령이면 경고한다", () => {
    const sameHost = { ...held, lockOwnerSameHost: true, lockOwnerHostname: "mac.local" };

    expect(lockWarning(sameHost, "cc")).toContain("abc123");
  });
});
