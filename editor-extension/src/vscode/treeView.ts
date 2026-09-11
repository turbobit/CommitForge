import * as vscode from "vscode";
import { basename } from "node:path";
import type { InstallReport } from "../core/detect";
import type { StateStore, WorkspaceState } from "../state";

const STATE_ICON: Record<InstallReport["state"], string> = {
  missing: "circle-outline",
  ok: "pass-filled",
  "version-mismatch": "warning",
  misconfigured: "warning",
  corrupt: "error",
};

const STATE_LABEL: Record<InstallReport["state"], string> = {
  missing: "미설치",
  ok: "정상",
  "version-mismatch": "버전 다름",
  misconfigured: "설정 불완전",
  corrupt: "손상",
};

/** spec §7.3 예시 "git index.lock 존재 (4분)", "session abc123 · 12분"의 경과 시간 표기. */
export function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

export class Node extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly children: Node[] = [],
    icon?: string,
    description?: string,
    color?: vscode.ThemeColor,
  ) {
    super(
      label,
      children.length > 0
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None,
    );
    if (icon) this.iconPath = new vscode.ThemeIcon(icon, color);
    if (description) this.description = description;
  }
}

/**
 * 설치 상태별 상세 항목. corePathOk·hooksRegistered가 거짓이거나 파일 목록에
 * 항목이 있을 때만 채워진다 (§5.1 판정 근거를 그대로 보여준다). 목록이 길면
 * 앞 5개만 보여준다 — 전체 목록은 Output 채널(검증 버튼)에서 확인한다.
 */
function installNode(report: InstallReport): Node {
  const version =
    report.state === "missing"
      ? ""
      : `v${report.installedVersion ?? report.bundleVersion}`;

  const details: string[] = [];
  if (!report.corePathOk && report.state !== "missing") {
    details.push("skill의 core 경로가 이 설치를 가리키지 않습니다");
  }
  if (!report.hooksRegistered && report.state !== "missing") {
    details.push("SessionEnd hook이 등록되지 않았습니다");
  }
  for (const path of report.missingFiles.slice(0, 5)) details.push(`누락: ${path}`);
  for (const path of report.mismatchedFiles.slice(0, 5)) details.push(`불일치: ${path}`);

  return new Node(
    report.scope,
    details.map((detail) => new Node(detail)),
    STATE_ICON[report.state],
    `${version} ${STATE_LABEL[report.state]}`.trim(),
  );
}

export function buildTree(state: WorkspaceState | null): Node[] {
  if (!state) return [new Node("상태를 읽는 중입니다", [], "sync~spin")];

  const nodes: Node[] = [
    new Node("설치", [installNode(state.project), installNode(state.global)], "package"),
  ];

  if (!state.isGitRepo) return nodes;

  const guard = state.guard;
  // spec §8: guard.py status 실패 시 마지막 성공 상태를 회색으로 표시하고
  // stderr를 Output에 남긴다. StateStore는 실패해도 직전 성공 guard 값을
  // 유지하므로, 여기서는 그 값이 낡았음을 라벨과 색으로 드러낸다.
  const stale = state.guardError !== null;
  const staleColor = stale ? new vscode.ThemeColor("disabledForeground") : undefined;

  if (!guard) {
    if (stale) {
      nodes.push(
        new Node("잠금", [new Node(state.guardError ?? "")], "error", "읽기 실패", staleColor),
      );
    }
    return nodes;
  }

  const lock = guard.lockOwner;
  const lockChildren = lock
    ? [
        new Node(`session ${lock.session ?? "?"}`),
        new Node(
          `${guard.lockAgeSeconds !== null ? humanAge(guard.lockAgeSeconds) : "0초"} 경과`,
        ),
        new Node(guard.lockOwnerSameHost === false ? "다른 호스트" : "이 호스트"),
      ]
    : [];
  const lockLabel = lock ? "보유 중" : "보유자 없음";
  nodes.push(
    new Node(
      "잠금",
      lockChildren,
      lock ? "lock" : "unlock",
      stale ? `${lockLabel} (오래된 값)` : lockLabel,
      staleColor,
    ),
  );

  nodes.push(
    new Node(
      "스냅샷",
      guard.snapshots.map((path) => new Node(path)),
      "archive",
      `${guard.snapshots.length}개`,
      staleColor,
    ),
  );

  // gitLockFiles는 경로 문자열뿐이라 나이를 못 나타낸다(§7.3 "(4분)"에는
  // ageSeconds가 필요하다). 구조화된 gitLocks만 쓴다.
  const lockWarnings = guard.gitLocks.map(
    (entry) => `git ${basename(entry.path)} 존재 (${humanAge(entry.ageSeconds)})`,
  );

  const warnings = [
    ...(stale ? [`guard.py status 실패: ${state.guardError}`] : []),
    ...guard.operations.map((op) => `${op} 진행 중`),
    ...lockWarnings,
    ...state.project.warnings,
    ...state.global.warnings,
  ];
  if (warnings.length > 0) {
    nodes.push(
      new Node(
        "경고",
        warnings.map((w) => new Node(w)),
        "warning",
        `${warnings.length}건`,
        staleColor,
      ),
    );
  }

  return nodes;
}

export function createTreeView(store: StateStore): vscode.Disposable {
  const emitter = new vscode.EventEmitter<void>();
  let roots = buildTree(store.current);

  const provider: vscode.TreeDataProvider<Node> = {
    onDidChangeTreeData: emitter.event,
    getTreeItem: (node) => node,
    getChildren: (node) => (node ? node.children : roots),
  };

  const view = vscode.window.createTreeView("commitforge.view", {
    treeDataProvider: provider,
  });

  const subscription = store.onDidChange((state) => {
    roots = buildTree(state);
    emitter.fire();
  });

  return vscode.Disposable.from(subscription, view, emitter);
}
