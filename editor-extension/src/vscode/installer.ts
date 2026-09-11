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

  const confirmed = await vscode.window.showWarningMessage(
    `CommitForge를 ${scope} 범위에 ${label}합니다. 계속할까요?`,
    { modal: true, detail: "변경 예정 내용은 CommitForge 출력 채널에 있습니다." },
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
