import * as vscode from "vscode";
import { basename, join } from "node:path";
import type { InstallReport, Scope } from "../core/detect";
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

/**
 * 설치 상태별로 트리 항목에 붙는 contextValue. package.json의
 * `view/item/context` 메뉴가 이 값으로 어떤 버튼을 보여줄지 고른다
 * (spec §5.3 "제안 행동" ↔ §7.4 "버튼별 동작"의 다리 역할).
 *
 * `[업그레이드]`·`[재설치]`는 `commitforge.upgrade`·`commitforge.reinstall`
 * 별칭 명령이다 — 셋 다 `extension.ts`의 같은 핸들러(`runInstaller`
 * 호출부)에 위임하므로 로직은 한 벌만 유지된다. 명령을 나눈 이유는 오직
 * VS Code 메뉴 기여가 명령별 title을 하나만 가지기 때문이다(버튼 tooltip이
 * "설치/업그레이드/재설치"로 자리마다 다르게 뜨려면 각각 등록된 명령이어야
 * 한다). 별칭 두 개는 `commandPalette`에서 `when: false`로 숨겨 팔레트에는
 * "설치" 하나만 보인다.
 */
const INSTALL_CONTEXT: Record<InstallReport["state"], string> = {
  missing: "commitforge.node.install",
  ok: "commitforge.node.installed",
  "version-mismatch": "commitforge.node.upgrade",
  misconfigured: "commitforge.node.reinstall",
  corrupt: "commitforge.node.reinstall",
};

const LOCK_CONTEXT = "commitforge.node.lock";
const SNAPSHOTS_CONTEXT = "commitforge.node.snapshots";

/** guard.py의 SNAPSHOT_DIR_NAME 상수와 같다 (scripts/guard.py:33). */
const SNAPSHOT_DIR_NAME = "claude-atomic-snapshots";

/** spec §7.3 예시 "git index.lock 존재 (4분)", "session abc123 · 12분"의 경과 시간 표기. */
export function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

interface NodeOptions {
  children?: Node[];
  icon?: string;
  description?: string;
  color?: vscode.ThemeColor;
  /** package.json view/item/context 메뉴가 매칭하는 값. */
  contextValue?: string;
  /** 설치·제거 명령을 트리에서 바로 호출할 때 다시 묻지 않도록 담아 두는 범위. */
  scope?: Scope;
  /** "[Finder에서 열기]" 등 OS 파일 탐색기로 열 때 쓰는 절대 경로. */
  resourcePath?: string;
}

export class Node extends vscode.TreeItem {
  readonly children: Node[];
  readonly scope?: Scope;
  readonly resourcePath?: string;

  constructor(label: string, options: NodeOptions = {}) {
    const children = options.children ?? [];
    super(
      label,
      children.length > 0
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None,
    );
    this.children = children;
    this.scope = options.scope;
    this.resourcePath = options.resourcePath;
    if (options.icon) this.iconPath = new vscode.ThemeIcon(options.icon, options.color);
    if (options.description) this.description = options.description;
    if (options.contextValue) this.contextValue = options.contextValue;
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

  return new Node(report.scope, {
    children: details.map((detail) => new Node(detail)),
    icon: STATE_ICON[report.state],
    description: `${version} ${STATE_LABEL[report.state]}`.trim(),
    contextValue: INSTALL_CONTEXT[report.state],
    scope: report.scope,
  });
}

export function buildTree(state: WorkspaceState | null): Node[] {
  if (!state) return [new Node("상태를 읽는 중입니다", { icon: "sync~spin" })];

  const nodes: Node[] = [
    new Node("설치", {
      children: [installNode(state.project), installNode(state.global)],
      icon: "package",
    }),
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
        new Node("잠금", {
          children: [new Node(state.guardError ?? "")],
          icon: "error",
          description: "읽기 실패",
          color: staleColor,
          contextValue: LOCK_CONTEXT,
        }),
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
    new Node("잠금", {
      children: lockChildren,
      icon: lock ? "lock" : "unlock",
      description: stale ? `${lockLabel} (오래된 값)` : lockLabel,
      color: staleColor,
      // [해제(clean)] 메뉴·명령은 아직 붙이지 않는다 — guard.py clean 직접
      // 호출은 spec §4.2가 금지하고, 실제 동작(§6.3 터미널 전송)은 Task 12다.
      contextValue: LOCK_CONTEXT,
    }),
  );

  nodes.push(
    new Node("스냅샷", {
      children: guard.snapshots.map((path) => new Node(path)),
      icon: "archive",
      description: `${guard.snapshots.length}개`,
      color: staleColor,
      // 스냅샷이 없으면 열 폴더도 없다 — contextValue를 아예 붙이지 않아
      // view/item/context의 when 절이 "[스냅샷 폴더 열기]" 버튼 자체를
      // 감추게 한다(존재 확인 없이 revealFileInOS를 부르는 상황을 방지).
      contextValue: guard.snapshots.length > 0 ? SNAPSHOTS_CONTEXT : undefined,
      resourcePath: join(guard.gitDir, SNAPSHOT_DIR_NAME),
    }),
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
      new Node("경고", {
        children: warnings.map((w) => new Node(w)),
        icon: "warning",
        description: `${warnings.length}건`,
        color: staleColor,
      }),
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
