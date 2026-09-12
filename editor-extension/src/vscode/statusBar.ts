import * as vscode from "vscode";
import { displayedVersion, primaryInstall, type InstallReport } from "../core/detect";
import type { StateStore, WorkspaceState } from "../state";

const STATE_LABEL: Record<InstallReport["state"], string> = {
  missing: "미설치",
  ok: "정상",
  "version-mismatch": "버전 다름",
  misconfigured: "설정 불완전",
  corrupt: "손상",
};

function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

export function statusText(state: WorkspaceState | null): {
  text: string;
  tooltip: string;
} {
  if (!state) {
    return { text: "$(sync~spin) CommitForge", tooltip: "CommitForge 상태를 읽는 중입니다" };
  }

  const install = primaryInstall(state.project, state.global);
  const tooltipLines = [
    `project: ${STATE_LABEL[state.project.state]}`,
    `global: ${STATE_LABEL[state.global.state]}`,
    `번들 버전: v${install.bundleVersion}`,
    state.python ? `Python: ${state.python.executable}` : "Python: 찾지 못함",
  ];

  // spec §5.1: 해시 대조가 판정의 근거이고 마커는 표시용이다. `정상` 상태에서
  // installedVersion이 bundleVersion과 다르면(detect.ts가 마커·해시 불일치를
  // 경고로만 남기고 ok로 판정한 경우) 낡았거나 손으로 편집됐을 수 있는 마커다.
  // 배지는 해시가 보증하는 번들 버전을 따르고, 마커는 tooltip에만 알린다.
  if (
    install.state === "ok" &&
    install.installedVersion !== null &&
    install.installedVersion !== install.bundleVersion
  ) {
    tooltipLines.push(
      `설치 마커: v${install.installedVersion} (파일은 해시상 번들과 일치 — 마커가 낡았을 수 있습니다)`,
    );
  }

  const tooltip = tooltipLines.join("\n");

  if (install.state === "missing") {
    return { text: "$(alert) CommitForge 미설치", tooltip };
  }

  if (install.state === "version-mismatch") {
    // spec §5.1: 마커가 없으면 설치 버전은 알 수 없다 — displayedVersion이
    // 이 규칙을 treeView.ts와 공유한다.
    const known = displayedVersion(install);
    const installed = known ? `v${known}` : "?";
    return {
      text: `$(warning) CommitForge ${installed} → v${install.bundleVersion}`,
      tooltip,
    };
  }

  if (install.state === "misconfigured" || install.state === "corrupt") {
    return { text: `$(warning) CommitForge ${STATE_LABEL[install.state]}`, tooltip };
  }

  const lock = state.guard?.lockOwner;
  if (lock) {
    if (state.guard?.lockOwnerSameHost === false) {
      return { text: "$(warning) CommitForge · 다른 세션", tooltip };
    }
    const age = state.guard?.lockAgeSeconds ?? 0;
    return { text: `$(lock) CommitForge · ${humanAge(age)}`, tooltip };
  }

  // 정상 상태의 배지는 항상 번들 버전을 보여준다 (해시가 판정 근거이므로).
  return { text: `$(check) CommitForge v${install.bundleVersion}`, tooltip };
}

export function createStatusBar(store: StateStore): vscode.Disposable {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  item.command = "commitforge.focusView";

  const render = (state: WorkspaceState | null) => {
    const { text, tooltip } = statusText(state);
    item.text = text;
    item.tooltip = tooltip;
    const enabled = vscode.workspace
      .getConfiguration("commitforge")
      .get<boolean>("statusBar.enabled", true);
    if (enabled) item.show();
    else item.hide();
  };

  render(store.current);
  const subscription = store.onDidChange(render);

  return vscode.Disposable.from(subscription, item);
}
