import { describe, expect, it } from "vitest";
import { buildTree, humanAge, type Node } from "../src/vscode/treeView";
import type { WorkspaceState } from "../src/state";
import type { InstallReport } from "../src/core/detect";
import type { GuardStatus } from "../src/core/guard";

const baseReport: InstallReport = {
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
    project: baseReport,
    global: { ...baseReport, scope: "global", state: "missing", installedVersion: null },
    guard: idleGuard,
    guardError: null,
    catalog: [],
    ...overrides,
  };
}

function labels(node: Node): string[] {
  return node.children.map((child) => String(child.label));
}

function findChild(nodes: Node[], label: string): Node | undefined {
  return nodes.find((node) => node.label === label);
}

describe("humanAge", () => {
  it("60초 미만은 초로 표시한다", () => {
    expect(humanAge(30)).toBe("30초");
  });

  it("60초 이상 3600초 미만은 분으로 표시한다", () => {
    expect(humanAge(240)).toBe("4분");
  });

  it("3600초 이상은 시간으로 표시한다", () => {
    expect(humanAge(7200)).toBe("2시간");
  });
});

describe("buildTree - 상태를 모를 때", () => {
  it("로딩 노드를 보여준다", () => {
    const nodes = buildTree(null);
    expect(nodes).toHaveLength(1);
    expect(nodes[0]?.iconPath).toMatchObject({ id: "sync~spin" });
  });
});

describe("buildTree - 설치 상태 5가지", () => {
  const install = findInstallNodeFor;

  it("missing: 회색 원 아이콘과 미설치 배지, 상세 없음", () => {
    const report: InstallReport = { ...baseReport, state: "missing", installedVersion: null };
    const node = install(report);
    expect(node.iconPath).toMatchObject({ id: "circle-outline" });
    expect(node.description).toBe("미설치");
    expect(node.children).toHaveLength(0);
  });

  it("ok: 체크 아이콘과 버전, 상세 없음", () => {
    const node = install(baseReport);
    expect(node.iconPath).toMatchObject({ id: "pass-filled" });
    expect(node.description).toBe("v1.15.0 정상");
    expect(node.children).toHaveLength(0);
  });

  it("version-mismatch: 경고 아이콘과 버전 다름 배지", () => {
    const report: InstallReport = {
      ...baseReport,
      state: "version-mismatch",
      installedVersion: "1.14.0",
      mismatchedFiles: ["file.md"],
    };
    const node = install(report);
    expect(node.iconPath).toMatchObject({ id: "warning" });
    expect(node.description).toBe("v1.14.0 버전 다름");
    expect(labels(node)).toContain("불일치: file.md");
  });

  it("misconfigured: 경고 아이콘과 설정 불완전, corePathOk/hooksRegistered 상세", () => {
    const report: InstallReport = {
      ...baseReport,
      state: "misconfigured",
      corePathOk: false,
      hooksRegistered: false,
    };
    const node = install(report);
    expect(node.iconPath).toMatchObject({ id: "warning" });
    expect(node.description).toBe("v1.15.0 설정 불완전");
    expect(labels(node)).toEqual(
      expect.arrayContaining([
        "skill의 core 경로가 이 설치를 가리키지 않습니다",
        "SessionEnd hook이 등록되지 않았습니다",
      ]),
    );
  });

  it("corrupt: 오류 아이콘과 손상 배지, 누락·불일치 목록은 앞 5개만", () => {
    const report: InstallReport = {
      ...baseReport,
      state: "corrupt",
      missingFiles: Array.from({ length: 8 }, (_, i) => `missing-${i}.md`),
      mismatchedFiles: ["mismatched.md"],
    };
    const node = install(report);
    expect(node.iconPath).toMatchObject({ id: "error" });
    expect(node.description).toBe("v1.15.0 손상");
    const missingLabels = labels(node).filter((label) => label.startsWith("누락:"));
    expect(missingLabels).toHaveLength(5);
    expect(labels(node)).toContain("불일치: mismatched.md");
  });
});

function findInstallNodeFor(report: InstallReport): Node {
  const nodes = buildTree(
    state({
      project: report,
      global: { ...baseReport, scope: "global", state: "missing", installedVersion: null },
    }),
  );
  const installGroup = findChild(nodes, "설치") ?? nodes[0];
  const projectNode = installGroup?.children.find((child) => child.label === "project");
  if (!projectNode) throw new Error("project 노드를 찾지 못했습니다");
  return projectNode;
}

describe("buildTree - git 저장소가 아닐 때", () => {
  it("잠금·스냅샷·경고 노드를 숨긴다", () => {
    const nodes = buildTree(state({ isGitRepo: false, guard: null }));
    expect(nodes).toHaveLength(1);
    expect(findChild(nodes, "잠금")).toBeUndefined();
    expect(findChild(nodes, "스냅샷")).toBeUndefined();
    expect(findChild(nodes, "경고")).toBeUndefined();
  });
});

describe("buildTree - guardError가 있을 때 (낡은 값)", () => {
  it("guard 값이 있으면 잠금 배지에 낡은 값임을 표시한다", () => {
    const nodes = buildTree(state({ guardError: "guard.py status 실패 (exit 1)" }));
    const lockNode = findChild(nodes, "잠금");
    expect(lockNode?.description).toContain("오래된 값");
  });

  it("경고 노드에 guard.py status 실패 메시지를 포함한다", () => {
    const nodes = buildTree(state({ guardError: "boom" }));
    const warningNode = findChild(nodes, "경고");
    expect(labels(warningNode!)).toContain("guard.py status 실패: boom");
  });

  it("guard 값 자체가 없으면(첫 갱신 실패) 잠금 노드에 오류를 보여준다", () => {
    const nodes = buildTree(state({ guardError: "boom", guard: null }));
    const lockNode = findChild(nodes, "잠금");
    expect(lockNode?.description).toBe("읽기 실패");
    expect(labels(lockNode!)).toContain("boom");
  });
});

describe("buildTree - gitLocks 경과 시간", () => {
  it("사람이 읽는 형태(분)로 경고에 나타난다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          gitLocks: [
            {
              path: "/repo/.git/index.lock",
              ageSeconds: 240,
              staleCandidate: false,
            },
          ],
        },
      }),
    );
    const warningNode = findChild(nodes, "경고");
    expect(labels(warningNode!)).toContain("git index.lock 존재 (4분)");
  });
});

describe("buildTree - 설치 상태별 contextValue와 scope", () => {
  it("missing → commitforge.node.install", () => {
    const report: InstallReport = { ...baseReport, state: "missing", installedVersion: null };
    expect(findInstallNodeFor(report).contextValue).toBe("commitforge.node.install");
  });

  it("ok → commitforge.node.installed", () => {
    expect(findInstallNodeFor(baseReport).contextValue).toBe("commitforge.node.installed");
  });

  it("version-mismatch → commitforge.node.upgrade", () => {
    const report: InstallReport = { ...baseReport, state: "version-mismatch" };
    expect(findInstallNodeFor(report).contextValue).toBe("commitforge.node.upgrade");
  });

  it("misconfigured → commitforge.node.reinstall", () => {
    const report: InstallReport = { ...baseReport, state: "misconfigured" };
    expect(findInstallNodeFor(report).contextValue).toBe("commitforge.node.reinstall");
  });

  it("corrupt → commitforge.node.reinstall", () => {
    const report: InstallReport = { ...baseReport, state: "corrupt" };
    expect(findInstallNodeFor(report).contextValue).toBe("commitforge.node.reinstall");
  });

  it("project/global 각 노드는 자신의 scope를 담아, 트리에서 호출 시 다시 묻지 않게 한다", () => {
    const nodes = buildTree(state());
    const installGroup = findChild(nodes, "설치")!;
    const project = installGroup.children.find((n) => n.label === "project");
    const global = installGroup.children.find((n) => n.label === "global");
    expect(project?.scope).toBe("project");
    expect(global?.scope).toBe("global");
  });
});

describe("buildTree - 잠금·스냅샷 contextValue", () => {
  it("잠금 노드는 commitforge.node.lock을 받는다 (버튼은 아직 없음, Task 12 대비)", () => {
    const nodes = buildTree(state());
    expect(findChild(nodes, "잠금")?.contextValue).toBe("commitforge.node.lock");
  });

  it("스냅샷 노드는 commitforge.node.snapshots와 절대 경로(resourcePath)를 받는다", () => {
    const nodes = buildTree(state());
    const snapshotsNode = findChild(nodes, "스냅샷");
    expect(snapshotsNode?.contextValue).toBe("commitforge.node.snapshots");
    expect(snapshotsNode?.resourcePath).toBe("/repo/.git/claude-atomic-snapshots");
  });

  it("git 저장소가 아니면 잠금·스냅샷 contextValue 자체가 존재하지 않는다", () => {
    const nodes = buildTree(state({ isGitRepo: false, guard: null }));
    const allContextValues = nodes.flatMap((n) => [n.contextValue, ...n.children.map((c) => c.contextValue)]);
    expect(allContextValues).not.toContain("commitforge.node.lock");
    expect(allContextValues).not.toContain("commitforge.node.snapshots");
  });
});

describe("buildTree - 잠금 보유 중", () => {
  it("세션·경과 시간·호스트 정보를 자식으로 보여준다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "abc123", created_at: "2026-09-11T00:00:00Z" },
          lockAgeSeconds: 720,
          lockOwnerSameHost: true,
        },
      }),
    );
    const lockNode = findChild(nodes, "잠금");
    expect(lockNode?.description).toBe("보유 중");
    expect(labels(lockNode!)).toEqual(["session abc123", "12분 경과", "이 호스트"]);
  });
});
