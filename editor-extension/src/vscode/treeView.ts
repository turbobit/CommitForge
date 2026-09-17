import * as vscode from "vscode";
import { basename, join } from "node:path";
import { displayedVersion, primaryInstall, type InstallReport, type Scope } from "../core/detect";
import type { StateStore, WorkspaceState } from "../state";
import type { GuardStatus } from "../core/guard";

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
/** 값 복사(commitforge.copyValue)만 필요한 잠금 자식(session·호스트)의 contextValue. */
const LOCK_VALUE_CONTEXT = "commitforge.node.lockValue";
/** 폴더 열기·경로 복사가 모두 필요한 스냅샷 자식 항목의 contextValue. */
const SNAPSHOT_ITEM_CONTEXT = "commitforge.node.snapshotItem";

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
  /** 마우스를 올렸을 때 보여줄 설명. 잘린 값의 전체 내용이나 판단 근거를 담는다. */
  tooltip?: string;
  /** 항목 자체를 클릭했을 때 실행할 명령. 자식 항목(세션·스냅샷 등)에 동작을 붙일 때 쓴다. */
  command?: vscode.Command;
  /**
   * 우클릭 메뉴의 "값 복사"(commitforge.copyValue)가 클립보드에 넣을 전체
   * 텍스트. 잘린 라벨과 달리 자르지 않은 원본 값이다(세션 ID, 호스트명,
   * 스냅샷 경로 등). 이 필드가 없으면(undefined) 그 노드에는 복사 메뉴가
   * 뜨지 않는다 — contextValue로 구분한다.
   */
  copyText?: string;
}

export class Node extends vscode.TreeItem {
  readonly children: Node[];
  readonly scope?: Scope;
  readonly resourcePath?: string;
  readonly copyText?: string;

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
    this.copyText = options.copyText;
    if (options.icon) this.iconPath = new vscode.ThemeIcon(options.icon, options.color);
    if (options.description) this.description = options.description;
    if (options.contextValue) this.contextValue = options.contextValue;
    if (options.tooltip) this.tooltip = options.tooltip;
    if (options.command) this.command = options.command;
  }
}

/** "v1.15.0" 또는(설치 버전을 알 수 없으면) "?"로 표시한다. */
function formatVersionBadge(report: InstallReport): string {
  const known = displayedVersion(report);
  return known ? `v${known}` : "?";
}

/**
 * "이 범위가 실제로 명령을 제공한다"고 말할 수 있는 상태인지. `missing`이
 * 아니라는 것만으로는 부족하다 — `misconfigured`·`corrupt`는 파일이 없거나
 * hook·core 경로가 깨져 있어 명령이 동작하지 않을 수 있다(statusBar.ts가
 * 이 둘을 별도 경고로 다루는 이유와 같다).
 *
 * `version-mismatch`는 사용 가능 쪽으로 본다: classify()가 이 상태를 매기는
 * 것은 기대 파일이 전부 존재하고 해시가 **일관되게 전부** 다를 때뿐이라
 * (일부만 다르면 corrupt다), 다른 버전이 통째로 깔려 있다는 뜻이고 명령
 * 자체는 동작한다 — statusBar.ts도 이 상태에서 배지에 버전 차이만 얹지
 * "손상"으로 취급하지 않는다.
 *
 * 다만 classify()는 해시 불일치를 먼저 판정하고 반환하므로, 이 상태에서
 * corePathOk·hooksRegistered가 검사되지 않은 채 남을 수 있다. 즉 hook이
 * 등록되지 않은 다른 버전 설치도 여기로 온다. statusBar.ts가 예전부터
 * 가진 것과 같은 맹점이라 두 위젯이 어긋나지는 않는다.
 */
function isUsable(report: InstallReport): boolean {
  return report.state === "ok" || report.state === "version-mismatch";
}

/** 각 범위(project/global)가 무엇을 뜻하는지 — 트리에서 헷갈리지 않도록. */
const SCOPE_MEANING: Record<Scope, string> = {
  project: "이 저장소에서만 명령을 제공합니다.",
  global: "모든 프로젝트에서 명령을 제공합니다.",
};

/**
 * 설치 행의 tooltip. `redundant`(이 범위는 미설치지만 다른 범위가 이미
 * 있어 없어도 되는 경우)일 때는 그 사실을 한 줄 더 덧붙인다 — 피드백 1:
 * "미설치"가 마치 할 일이 남은 것처럼 보이지 않도록.
 */
function scopeTooltip(scope: Scope, redundant: boolean): string {
  const base = `${scope}: ${SCOPE_MEANING[scope]}`;
  return redundant ? `${base}\n\n다른 범위가 이미 설치돼 있어 지금은 없어도 됩니다.` : base;
}

/**
 * 설치 상태별 상세 항목. corePathOk·hooksRegistered가 거짓이거나 파일 목록에
 * 항목이 있을 때만 채워진다 (§5.1 판정 근거를 그대로 보여준다). 목록이 길면
 * 앞 5개만 보여준다 — 전체 목록은 Output 채널(검증 버튼)에서 확인한다.
 *
 * `otherUsable`은 반대쪽 범위(project↔global)가 실제로 명령을 제공할 수
 * 있는 상태인지(`isUsable`)를 나타낸다. 이 범위가 미설치이고 반대쪽이
 * 건강하면 "없어도 됨"임을 설명과 색(disabledForeground)으로 드러낸다 —
 * CommitForge는 둘 중 하나만 정상이면 되기 때문이다(피드백 1). 반대쪽이
 * `misconfigured`·`corrupt`처럼 손상됐을 때는 "없어도 됨"이라고 하면 안
 * 된다 — 실제로는 아무 쪽도 동작하지 않을 수 있다(리뷰 재현 1).
 */
const FILE_DETAIL_LIMIT = 5;

/**
 * 목록을 앞 5개로 자르되, 잘렸으면 총계와 남은 수를 함께 알린다. 총계를 숨기면
 * 37건이 깨진 설치가 "5건만 깨졌다"로 읽혀 심각도를 잘못 판단하게 된다.
 */
function pushFileDetails(details: string[], label: string, paths: string[]): void {
  for (const path of paths.slice(0, FILE_DETAIL_LIMIT)) details.push(`${label}: ${path}`);
  const hidden = paths.length - FILE_DETAIL_LIMIT;
  if (hidden > 0) {
    details.push(
      `${label} ${paths.length}건 중 ${FILE_DETAIL_LIMIT}건 표시, ${hidden}건 더 있음`,
    );
  }
}

function installNode(report: InstallReport, otherUsable: boolean): Node {
  // statusBar.ts와 같은 규칙(displayedVersion, spec §5.1)을 쓴다 — 해시가
  // 판정 근거이므로 ok는 번들 버전을, version-mismatch는 마커 버전(없으면
  // "알 수 없음"에 해당하는 "?")을 보여준다. 두 위젯이 같은 입력에 다른
  // 버전 번호를 보여주는 모순을 막는다.
  const version = report.state === "missing" ? "" : formatVersionBadge(report);
  const redundant = report.state === "missing" && otherUsable;

  const details: string[] = [];
  if (!report.corePathOk && report.state !== "missing") {
    details.push("skill의 core 경로가 이 설치를 가리키지 않습니다");
  }
  if (!report.hooksRegistered && report.state !== "missing") {
    details.push("SessionEnd hook이 등록되지 않았습니다");
  }
  pushFileDetails(details, "누락", report.missingFiles);
  pushFileDetails(details, "불일치", report.mismatchedFiles);

  const description = redundant
    ? `${STATE_LABEL[report.state]} · 없어도 됨`
    : `${version} ${STATE_LABEL[report.state]}`.trim();

  return new Node(report.scope, {
    children: details.map((detail) => new Node(detail)),
    icon: STATE_ICON[report.state],
    description,
    color: redundant ? new vscode.ThemeColor("disabledForeground") : undefined,
    contextValue: INSTALL_CONTEXT[report.state],
    scope: report.scope,
    tooltip: scopeTooltip(report.scope, redundant),
  });
}

/**
 * "설치" 그룹 행 자체가 결론을 말한다: project·global 중 하나만 있으면
 * 되므로, 어느 쪽이 실제로 명령을 제공하는지(primaryInstall, statusBar.ts와
 * 공유하는 규칙) 보여준다. 둘 다 미설치일 때만 설치를 권한다(피드백 1).
 *
 * 리뷰 재현 1: primaryInstall은 "missing이 아닌 쪽"을 고를 뿐 그 쪽이
 * 실제로 건강한지는 보지 않는다 — project 미설치 + global corrupt이면
 * primary는 (missing이 아닌) global이 된다. 이 함수가 `primary.state ===
 * "missing"`만 보고 나머지를 전부 "사용 중"이라 말하면, 실제로는 동작하지
 * 않을 수 있는 손상된 설치를 정상처럼 보여주게 된다. `isUsable`로 건강
 * 여부를 따로 확인해, 건강하지 않으면 그 사실을 그룹 행이 직접 말한다 —
 * statusBar.ts가 같은 입력에서 misconfigured·corrupt를 경고로 보여주는
 * 것과 모순되지 않도록.
 */
function installGroupNode(project: InstallReport, global: InstallReport): Node {
  const primary = primaryInstall(project, global);
  const bothMissing = project.state === "missing" && global.state === "missing";
  const primaryUsable = isUsable(primary);

  const description = bothMissing
    ? "설치 필요"
    : primaryUsable
      ? `${primary.scope} 사용 중`
      : `${primary.scope} ${STATE_LABEL[primary.state]} · 확인 필요`;

  const tooltip = bothMissing
    ? "project 또는 global 중 하나만 설치하면 됩니다. 지금은 둘 다 미설치입니다."
    : primaryUsable
      ? `project 또는 global 중 하나만 있으면 됩니다. 지금은 ${primary.scope}을(를) 사용합니다.`
      : `${primary.scope} 설치가 ${STATE_LABEL[primary.state]} 상태라 CommitForge가 동작하지 않을 ` +
        "수 있습니다. 아래 project/global 항목에서 원인을 확인하세요.";

  return new Node("설치", {
    children: [
      installNode(project, isUsable(global)),
      installNode(global, isUsable(project)),
    ],
    icon: bothMissing || primaryUsable ? "package" : "warning",
    description,
    tooltip,
  });
}

/**
 * 잠금 보유 중일 때 자식 3개(session·경과 시간·호스트)에 tooltip을 붙인다.
 * 잘린 라벨만으로는 전체 세션 ID·실제 시각·호스트명을 알 수 없어(피드백 2)
 * 각각의 전체 값과 의미를 tooltip에 담는다.
 */
function lockChildNodes(guard: GuardStatus): Node[] {
  const lock = guard.lockOwner;
  if (!lock) return [];

  const session = lock.session ?? "?";
  // false만 "다른 호스트"로 취급한다 — null(알 수 없음)은 기존 라벨 규칙과
  // 동일하게 "이 호스트"로 본다.
  const sameHost = guard.lockOwnerSameHost !== false;
  const hostname = guard.lockOwnerHostname ?? (sameHost ? guard.currentHostname : "알 수 없음");

  const ageNode = new Node(
    `${guard.lockAgeSeconds !== null ? humanAge(guard.lockAgeSeconds) : "0초"} 경과`,
    {
      tooltip: lock.created_at
        ? `잠금 생성 시각: ${lock.created_at}\n\n1시간 이상 지나면 이전 세션이 비정상 종료됐을 가능성이 있습니다.`
        : "잠금이 생성된 시각을 확인할 수 없습니다.",
    },
  );

  const hostNode = new Node(sameHost ? "이 호스트" : "다른 호스트", {
    tooltip: sameHost
      ? `잠금을 쥔 호스트: ${hostname}\n\n이 컴퓨터와 같은 호스트입니다.`
      : `잠금을 쥔 호스트: ${hostname}\n\n이 컴퓨터(${guard.currentHostname})와 다른 머신입니다. ` +
        "다른 세션이 실행 중일 수 있으니 여기서 해제(clean)하면 안 됩니다.",
    // 우클릭 "값 복사"용. 라벨은 "이 호스트"/"다른 호스트"로 잘려 보이므로
    // 실제 호스트명을 복사할 수 있게 한다(피드백: 세션 ID·호스트명 복사 불가).
    contextValue: LOCK_VALUE_CONTEXT,
    copyText: hostname,
  });

  return [
    new Node(`session ${session}`, {
      tooltip: `Claude Code 세션 식별자입니다.\n전체 값: ${session}`,
      contextValue: LOCK_VALUE_CONTEXT,
      copyText: session,
    }),
    ageNode,
    hostNode,
  ];
}

/**
 * guard.recovery(guard.py recovery_details())의 cleanHint·reclaimHint는
 * 사용자에게 그대로 보여줄 가치가 있는 한국어 문장이다 — 잠금 그룹 행의
 * tooltip으로 노출한다.
 *
 * reclaimHint(`begin --reclaim-stale`)는 호스트가 확실히 같을 때만 보여준다.
 * guard.py의 `reclaim_refusal()`(scripts/guard.py)은 `same_host`가 `False`일
 * 때는 물론, `None`(호스트 불명)일 때도 세션이 같지 않으면 `owner_host_
 * unknown`으로 회수 자체를 거부한다. 이 tooltip에는 세션 일치 여부가 없으니
 * (트리에는 세션 문자열만 있고 "현재 세션과 같은지"는 계산하지 않는다) 안전
 * 쪽으로 판단한다 — `lockOwnerSameHost === true`일 때만 회수를 안내한다.
 * 리뷰 재현 2: 예전에는 `!== false`(true 또는 null)일 때 보여줘, 호스트가
 * 불명(null)이라 실제로는 거부되는 경우에도 "회수할 수 있다"고 잘못 알렸다.
 */
function lockGroupTooltip(guard: GuardStatus): string | undefined {
  if (!guard.lockOwner) return undefined;
  const lines: string[] = [];
  if (guard.recovery?.cleanHint) lines.push(guard.recovery.cleanHint);
  if (guard.recovery?.reclaimHint && guard.lockOwnerSameHost === true) {
    lines.push(guard.recovery.reclaimHint);
  }
  return lines.length > 0 ? lines.join("\n\n") : undefined;
}

/**
 * 스냅샷 자식 항목. 전체 경로는 라벨로 쓰면 잘려서 못 알아보므로(피드백 2)
 * 디렉터리 이름만 라벨로 쓰고 전체 경로는 description·tooltip에 둔다.
 * 클릭하면 commitforge.revealSnapshots가 바로 이 스냅샷 폴더를 연다 —
 * extension.ts:114가 `node.resourcePath`만 읽으므로, 이 노드 자신을
 * 인자로 넘기면 된다.
 */
function snapshotNode(path: string): Node {
  const node = new Node(basename(path), {
    description: path,
    tooltip: `스냅샷 경로: ${path}\n\n클릭하면 이 폴더를 엽니다.`,
    resourcePath: path,
    // 우클릭 메뉴의 "폴더 열기"·"경로 복사" 둘 다 이 contextValue로 노출된다.
    contextValue: SNAPSHOT_ITEM_CONTEXT,
    copyText: path,
  });
  node.command = {
    command: "commitforge.revealSnapshots",
    title: "스냅샷 폴더 열기",
    arguments: [node],
  };
  return node;
}

export function buildTree(state: WorkspaceState | null): Node[] {
  if (!state) return [new Node("상태를 읽는 중입니다", { icon: "sync~spin" })];

  const nodes: Node[] = [installGroupNode(state.project, state.global)];

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
  const lockChildren = lockChildNodes(guard);
  const lockLabel = lock ? "보유 중" : "보유자 없음";
  nodes.push(
    new Node("잠금", {
      children: lockChildren,
      icon: lock ? "lock" : "unlock",
      description: stale ? `${lockLabel} (오래된 값)` : lockLabel,
      color: staleColor,
      tooltip: lockGroupTooltip(guard),
      // lock 유무와 무관하게 항상 붙인다 — [해제(clean)] 버튼(commitforge.
      // cleanLock)은 guard.py clean을 직접 부르지 않고 항상 /cr clean을
      // 터미널로 보낸다(spec §4.2, §6.3).
      contextValue: LOCK_CONTEXT,
    }),
  );

  nodes.push(
    new Node("스냅샷", {
      children: guard.snapshots.map(snapshotNode),
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
