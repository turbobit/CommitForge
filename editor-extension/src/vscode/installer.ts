import * as vscode from "vscode";
import { join } from "node:path";
import { nodeRunner } from "../core/guard";
import type { Scope } from "../core/detect";
import type { StateStore } from "../state";

export type InstallAction = "install" | "uninstall";

const SCRIPT: Record<InstallAction, string> = {
  install: "install.py",
  uninstall: "uninstall.py",
};

export function installerArgs(
  action: InstallAction,
  payloadRoot: string,
  scope: Scope,
  target: string,
  dryRun: boolean,
): string[] {
  const args = [join(payloadRoot, SCRIPT[action]), "--scope", scope];
  if (scope === "project") args.push("--target", target);
  if (dryRun) args.push("--dry-run");
  return args;
}

const ACTION_LABEL: Record<InstallAction, string> = {
  install: "설치",
  uninstall: "제거",
};

/**
 * 버전 문자열을 비교한다. 숫자로 읽히지 않는 부분이 있으면 비교 불가로 보고 0을
 * 반환한다. 이 결과는 경고 문구를 붙일지만 정하므로, 확신할 수 없을 때 잘못된
 * 단정을 보여주는 것보다 아무 말도 하지 않는 편이 낫다.
 */
function compareVersions(a: string, b: string): number {
  const left = a.split(".");
  const right = b.split(".");
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const x = Number.parseInt(left[i] ?? "0", 10);
    const y = Number.parseInt(right[i] ?? "0", 10);
    if (Number.isNaN(x) || Number.isNaN(y)) return 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

/**
 * 설치본이 번들보다 최신이면 설치는 사실상 다운그레이드다. install.py는 번들
 * payload를 그대로 덮어쓰므로, 손상 표시를 보고 "정리"를 누른 사용자가 고친다고
 * 생각하면서 버전이 뒤로 밀릴 수 있다. 막지는 않되 확인 문구에서 분명히 한다.
 */
export function downgradeNotice(
  installedVersion: string | null,
  bundleVersion: string,
): string | null {
  if (!installedVersion) return null;
  if (compareVersions(installedVersion, bundleVersion) <= 0) return null;
  return (
    `설치본 v${installedVersion}이 번들 v${bundleVersion}보다 최신입니다. ` +
    `계속하면 v${bundleVersion}으로 다운그레이드됩니다.`
  );
}

/**
 * spec §7.4: 실행 전 --dry-run으로 변경 예정 내용을 보여주고 확인을 받은 뒤에만
 * 실제로 실행한다. 출력은 CommitForge Output 채널에 그대로 흘린다.
 */
export async function runInstaller(
  store: StateStore,
  action: InstallAction,
  scope: Scope,
  output: vscode.OutputChannel,
): Promise<void> {
  const state = store.current;
  if (!state) return;

  if (!state.python) {
    void vscode.window.showErrorMessage(
      "Python을 찾지 못했습니다. commitforge.pythonPath 설정을 확인하십시오.",
    );
    return;
  }

  const label = ACTION_LABEL[action];
  const python = state.python.executable;

  const preview = await nodeRunner(
    python,
    installerArgs(action, store.payloadDir, scope, state.folder, true),
    state.folder,
  );

  output.show(true);
  output.appendLine(`--- ${label} 예정 내용 (${scope}) ---`);
  output.appendLine(preview.stdout || preview.stderr);

  if (preview.code !== 0) {
    void vscode.window.showErrorMessage(`${label} 사전 확인 실패. 출력을 확인하십시오.`);
    return;
  }

  const report = scope === "project" ? state.project : state.global;
  const downgrade =
    action === "install"
      ? downgradeNotice(report.installedVersion, report.bundleVersion)
      : null;
  if (downgrade) output.appendLine(`경고: ${downgrade}`);

  const detail = downgrade
    ? `${downgrade}\n\n변경 예정 내용은 CommitForge 출력 채널에 있습니다.`
    : "변경 예정 내용은 CommitForge 출력 채널에 있습니다.";

  const confirmed = await vscode.window.showWarningMessage(
    `CommitForge를 ${scope} 범위에 ${label}합니다. 계속할까요?`,
    { modal: true, detail },
    "계속",
  );
  if (confirmed !== "계속") return;

  const result = await nodeRunner(
    python,
    installerArgs(action, store.payloadDir, scope, state.folder, false),
    state.folder,
  );

  output.appendLine(`--- ${label} 실행 결과 ---`);
  output.appendLine(result.stdout || result.stderr);

  if (result.code === 0) {
    void vscode.window.showInformationMessage(`CommitForge ${label} 완료 (${scope})`);
  } else {
    void vscode.window.showErrorMessage(`CommitForge ${label} 실패. 출력을 확인하십시오.`);
  }

  await store.refresh();
}
