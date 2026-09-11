import { describe, expect, it } from "vitest";
import { statusText } from "../src/vscode/statusBar";
import type { WorkspaceState } from "../src/state";
import type { InstallReport } from "../src/core/detect";
import type { GuardStatus } from "../src/core/guard";

const okReport: InstallReport = {
  state: "ok",
  scope: "project",
  claudeDir: "/repo/.claude",
  bundleVersion: "1.15.0",
  installedVersion: "1.15.0",
  missingFiles: [],
  mismatchedFiles: [],
  corePathOk: true,
  hooksRegistered: true,
  warnings: [],
};

const missingReport: InstallReport = { ...okReport, state: "missing", installedVersion: null };

const idleGuard: GuardStatus = {
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

function state(overrides: Partial<WorkspaceState> = {}): WorkspaceState {
  return {
    folder: "/repo",
    isGitRepo: true,
    python: { executable: "python3", source: "probe" },
    project: okReport,
    global: { ...missingReport, scope: "global" },
    guard: idleGuard,
    guardError: null,
    catalog: [],
    ...overrides,
  };
}

describe("statusText", () => {
  it("상태를 모르면 로딩으로 표시한다", () => {
    expect(statusText(null).text).toContain("$(sync~spin)");
  });

  it("정상이고 lock이 없으면 버전을 보여준다", () => {
    const { text } = statusText(state());

    expect(text).toBe("$(check) CommitForge v1.15.0");
  });

  it("미설치면 알린다", () => {
    const { text } = statusText(state({ project: missingReport, global: { ...missingReport, scope: "global" } }));

    expect(text).toBe("$(alert) CommitForge 미설치");
  });

  it("project가 미설치여도 global이 정상이면 정상으로 본다", () => {
    const { text } = statusText(
      state({ project: missingReport, global: { ...okReport, scope: "global" } }),
    );

    expect(text).toBe("$(check) CommitForge v1.15.0");
  });

  it("같은 호스트 lock은 보유 시간을 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "abc", created_at: null }, lockAgeSeconds: 742, lockOwnerSameHost: true },
      }),
    );

    expect(text).toBe("$(lock) CommitForge · 12분");
  });

  it("다른 호스트 lock은 경고로 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "abc", created_at: null }, lockAgeSeconds: 60, lockOwnerSameHost: false },
      }),
    );

    expect(text).toBe("$(warning) CommitForge · 다른 세션");
  });

  it("버전이 다르면 경고한다", () => {
    const { text } = statusText(
      state({ project: { ...okReport, state: "version-mismatch", installedVersion: "1.14.2" } }),
    );

    expect(text).toBe("$(warning) CommitForge v1.14.2 → v1.15.0");
  });

  it("설치 버전을 모르면 물음표로 둔다", () => {
    const { text } = statusText(
      state({ project: { ...okReport, state: "version-mismatch", installedVersion: null } }),
    );

    expect(text).toBe("$(warning) CommitForge ? → v1.15.0");
  });

  it("1분 미만은 초로 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "a", created_at: null }, lockAgeSeconds: 45, lockOwnerSameHost: true },
      }),
    );

    expect(text).toBe("$(lock) CommitForge · 45초");
  });

  it("tooltip에 범위별 상태를 담는다", () => {
    const { tooltip } = statusText(state());

    expect(tooltip).toContain("project");
    expect(tooltip).toContain("global");
  });

  it("정상이지만 마커 버전이 번들과 다르면(해시는 일치) 배지는 번들 버전을 보여주고 tooltip에 마커를 알린다", () => {
    // detect.ts: state === "ok" && marker.version !== manifest.version 인 경우.
    // 해시가 일치한다는 것은 파일이 실제로 번들 버전과 같다는 뜻이므로,
    // 배지는 (낡았을 수 있는) 마커가 아니라 번들 버전을 따라야 한다 (spec §5.1, §5.3).
    const staleMarkerReport: InstallReport = {
      ...okReport,
      installedVersion: "1.14.2",
      warnings: ["설치 마커는 v1.14.2이라고 하지만 파일은 번들 v1.15.0과 같습니다."],
    };

    const { text, tooltip } = statusText(state({ project: staleMarkerReport }));

    expect(text).toBe("$(check) CommitForge v1.15.0");
    expect(tooltip).toContain("1.14.2");
  });
});
