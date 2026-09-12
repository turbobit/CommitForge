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

  // spec §5.1: 마커 없음 + 해시 불일치 → 설치 버전은 "알 수 없음"으로
  // 표시한다. statusBar.ts는 이 경우 "?"를 쓴다 — 트리도 번들 버전을
  // 설치 버전인 양 보여주면 안 된다.
  it("version-mismatch + 마커 없음: 번들 버전이 아니라 알 수 없음 표시", () => {
    const report: InstallReport = {
      ...baseReport,
      state: "version-mismatch",
      installedVersion: null,
      mismatchedFiles: ["file.md"],
    };
    const node = install(report);
    expect(node.description).toBe("? 버전 다름");
  });

  // spec §5.1: 마커 있음 + 해시 일치 + 마커 버전 ≠ 번들 버전 → `정상`
  // 판정이며 배지는 해시가 보증하는 번들 버전을 따른다(statusBar.ts와
  // 동일 규칙). 마커가 낡았다고 트리가 그 낡은 버전을 보여주면 안 된다.
  it("ok + 낡은 마커: 마커 버전이 아니라 번들 버전 표시", () => {
    const report: InstallReport = {
      ...baseReport,
      state: "ok",
      installedVersion: "1.14.0",
      bundleVersion: "1.15.0",
    };
    const node = install(report);
    expect(node.description).toBe("v1.15.0 정상");
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
  it("잠금 노드는 lock 유무와 무관하게 commitforge.node.lock을 받는다([해제(clean)] 버튼은 항상 보인다)", () => {
    const nodes = buildTree(state());
    expect(findChild(nodes, "잠금")?.contextValue).toBe("commitforge.node.lock");
  });

  it("lock을 다른 세션이 보유 중이어도 잠금 노드는 여전히 commitforge.node.lock을 받는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "abc123", created_at: null },
          lockAgeSeconds: 30,
        },
      }),
    );
    expect(findChild(nodes, "잠금")?.contextValue).toBe("commitforge.node.lock");
  });

  it("스냅샷이 있으면 commitforge.node.snapshots와 절대 경로(resourcePath)를 받는다", () => {
    const nodes = buildTree(
      state({ guard: { ...idleGuard, snapshots: ["/repo/.git/claude-atomic-snapshots/abc"] } }),
    );
    const snapshotsNode = findChild(nodes, "스냅샷");
    expect(snapshotsNode?.contextValue).toBe("commitforge.node.snapshots");
    expect(snapshotsNode?.resourcePath).toBe("/repo/.git/claude-atomic-snapshots");
  });

  it("스냅샷이 없으면 폴더 열기 버튼용 contextValue가 없다 (열 폴더가 없다)", () => {
    const nodes = buildTree(state({ guard: { ...idleGuard, snapshots: [] } }));
    const snapshotsNode = findChild(nodes, "스냅샷");
    expect(snapshotsNode?.contextValue).toBeUndefined();
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

// 피드백 1: "설치" 그룹 행 자체가 결론(어느 범위를 실제로 쓰는지)을 말해야
// 하고, 정상인 반대쪽이 있으면 "미설치"가 문제로 보이면 안 된다.
describe("buildTree - 설치 그룹 행: project/global 중 하나만 있으면 된다", () => {
  const missingProject: InstallReport = { ...baseReport, state: "missing", installedVersion: null };
  const missingGlobal: InstallReport = {
    ...baseReport,
    scope: "global",
    state: "missing",
    installedVersion: null,
  };
  const okGlobal: InstallReport = { ...baseReport, scope: "global" };

  it("project 미설치 + global 정상 → 그룹 행이 global 사용 중이라 말한다", () => {
    const nodes = buildTree(state({ project: missingProject, global: okGlobal }));
    const group = findChild(nodes, "설치")!;
    expect(group.description).toBe("global 사용 중");
  });

  it("project 미설치 + global 정상 → project 행이 문제로 보이지 않는다(색이 죽고, 없어도 된다는 단서가 붙는다)", () => {
    const nodes = buildTree(state({ project: missingProject, global: okGlobal }));
    const group = findChild(nodes, "설치")!;
    const projectNode = group.children.find((n) => n.label === "project")!;
    expect(projectNode.description).toContain("없어도 됨");
    expect(projectNode.iconPath).toMatchObject({ color: { id: "disabledForeground" } });
  });

  it("project 정상 + global 미설치 → 그룹 행이 project 사용 중이라 말하고, global 행이 문제로 보이지 않는다", () => {
    const nodes = buildTree(state({ project: baseReport, global: missingGlobal }));
    const group = findChild(nodes, "설치")!;
    expect(group.description).toBe("project 사용 중");
    const globalNode = group.children.find((n) => n.label === "global")!;
    expect(globalNode.description).toContain("없어도 됨");
    expect(globalNode.iconPath).toMatchObject({ color: { id: "disabledForeground" } });
  });

  it("둘 다 미설치 → 설치를 권한다", () => {
    const nodes = buildTree(state({ project: missingProject, global: missingGlobal }));
    const group = findChild(nodes, "설치")!;
    expect(group.description).toBe("설치 필요");
    const projectNode = group.children.find((n) => n.label === "project")!;
    const globalNode = group.children.find((n) => n.label === "global")!;
    // 둘 다 미설치일 때는 "없어도 됨" 단서를 붙이지 않는다 — 실제로 할 일이다.
    expect(projectNode.description).not.toContain("없어도 됨");
    expect(globalNode.description).not.toContain("없어도 됨");
  });

  it("둘 다 정상 → project를 우선해 쓰고 있음이 분명하다(statusBar.ts와 같은 규칙)", () => {
    const nodes = buildTree(state({ project: baseReport, global: okGlobal }));
    const group = findChild(nodes, "설치")!;
    expect(group.description).toBe("project 사용 중");
  });

  it("각 범위 행에 tooltip이 붙어 project/global이 무엇을 뜻하는지 설명한다", () => {
    const nodes = buildTree(state({ project: baseReport, global: missingGlobal }));
    const group = findChild(nodes, "설치")!;
    const projectNode = group.children.find((n) => n.label === "project")!;
    const globalNode = group.children.find((n) => n.label === "global")!;
    expect(projectNode.tooltip).toContain("이 저장소에서만");
    expect(globalNode.tooltip).toContain("모든 프로젝트");
  });
});

// 피드백 2: 잠금 자식 3개(session/경과 시간/호스트)에 tooltip이 있어야
// 전체 세션 ID·실제 생성 시각·호스트명을 알 수 있다.
describe("buildTree - 잠금 자식 tooltip", () => {
  it("session 노드는 전체 세션 ID를 tooltip에 담는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "3641b138-43ed-4d2f-9b1a-000000000000", created_at: null },
          lockAgeSeconds: 30,
        },
      }),
    );
    const lockNode = findChild(nodes, "잠금")!;
    const sessionNode = lockNode.children.find((n) => String(n.label).startsWith("session"))!;
    expect(sessionNode.tooltip).toContain("3641b138-43ed-4d2f-9b1a-000000000000");
  });

  it("경과 시간 노드는 실제 생성 시각(created_at)을 tooltip에 담는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "abc", created_at: "2026-09-11T00:00:00Z" },
          lockAgeSeconds: 4000,
        },
      }),
    );
    const lockNode = findChild(nodes, "잠금")!;
    const ageNode = lockNode.children.find((n) => String(n.label).endsWith("경과"))!;
    expect(ageNode.tooltip).toContain("2026-09-11T00:00:00Z");
  });

  it("이 호스트 노드는 호스트명을 tooltip에 담는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "abc", created_at: null },
          lockAgeSeconds: 30,
          lockOwnerHostname: "mac.local",
          lockOwnerSameHost: true,
        },
      }),
    );
    const lockNode = findChild(nodes, "잠금")!;
    const hostNode = lockNode.children.find((n) => n.label === "이 호스트")!;
    expect(hostNode.tooltip).toContain("mac.local");
  });

  it("다른 호스트 노드는 실제 호스트명과 경고를 tooltip에 담는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          lockOwner: { session: "abc", created_at: null },
          lockAgeSeconds: 30,
          lockOwnerHostname: "other-machine.local",
          lockOwnerSameHost: false,
        },
      }),
    );
    const lockNode = findChild(nodes, "잠금")!;
    const hostNode = lockNode.children.find((n) => n.label === "다른 호스트")!;
    expect(hostNode.tooltip).toContain("other-machine.local");
    expect(hostNode.tooltip).toContain("해제(clean)하면 안 됩니다");
  });
});

// 피드백 2: 스냅샷 자식 항목은 눌렀을 때 열려야 하고, 라벨이 읽을 수 있어야
// 한다(전체 경로가 아니라 디렉터리 이름).
describe("buildTree - 스냅샷 자식 항목", () => {
  it("라벨은 디렉터리 이름이고 전체 경로는 description에 남는다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          snapshots: ["/Users/turbobit/dev/kcmi/.git/claude-atomic-snapshots/abc123"],
        },
      }),
    );
    const snapshotsNode = findChild(nodes, "스냅샷")!;
    const snapshotNode = snapshotsNode.children[0]!;
    expect(snapshotNode.label).toBe("abc123");
    expect(snapshotNode.description).toBe(
      "/Users/turbobit/dev/kcmi/.git/claude-atomic-snapshots/abc123",
    );
  });

  it("commitforge.revealSnapshots를 그 스냅샷 경로로 호출하는 command를 가진다", () => {
    const nodes = buildTree(
      state({
        guard: {
          ...idleGuard,
          snapshots: ["/repo/.git/claude-atomic-snapshots/abc123"],
        },
      }),
    );
    const snapshotsNode = findChild(nodes, "스냅샷")!;
    const snapshotNode = snapshotsNode.children[0]!;
    expect(snapshotNode.resourcePath).toBe("/repo/.git/claude-atomic-snapshots/abc123");
    expect(snapshotNode.command?.command).toBe("commitforge.revealSnapshots");
    expect(snapshotNode.command?.arguments?.[0]).toBe(snapshotNode);
  });
});
