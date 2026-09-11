import * as vscode from "vscode";
import { StateStore } from "./state";
import { createStatusBar } from "./vscode/statusBar";
import { createTreeView, type Node } from "./vscode/treeView";
import { runInstaller } from "./vscode/installer";
import type { Scope } from "./core/detect";

const FOLDER_KEY = "commitforge.activeFolder";

/**
 * commitforge.install/upgrade/reinstall이 공유하는 실제 동작. 트리에서
 * 호출되면 그 행의 scope로 바로 실행하고, 인자 없이(팔레트에서) 호출되면
 * QuickPick으로 묻는다.
 */
async function handleInstall(
  store: StateStore,
  output: vscode.OutputChannel,
  node?: Node,
): Promise<void> {
  const scope = node?.scope ?? (await pickScope());
  if (scope) await runInstaller(store, "install", scope, output);
}

async function pickScope(): Promise<Scope | undefined> {
  const picked = await vscode.window.showQuickPick(
    [
      { label: "project", description: "이 워크스페이스에만 설치" },
      { label: "global", description: "모든 프로젝트에서 사용" },
    ],
    { placeHolder: "설치 범위를 고르십시오" },
  );
  return picked?.label as Scope | undefined;
}

/**
 * 다중 루트 워크스페이스에서는 어느 폴더를 대상으로 할지 한 번 묻고 기억한다.
 * 기억한 폴더가 사라졌으면 다시 묻는다.
 */
async function resolveFolder(
  context: vscode.ExtensionContext,
): Promise<vscode.WorkspaceFolder | undefined> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (folders.length === 0) return undefined;
  if (folders.length === 1) return folders[0];

  const remembered = context.workspaceState.get<string>(FOLDER_KEY);
  const found = folders.find((folder) => folder.uri.fsPath === remembered);
  if (found) return found;

  const picked = await vscode.window.showQuickPick(
    folders.map((folder) => ({ label: folder.name, description: folder.uri.fsPath, folder })),
    { placeHolder: "CommitForge를 사용할 폴더를 고르십시오" },
  );
  if (!picked) return undefined;

  await context.workspaceState.update(FOLDER_KEY, picked.folder.uri.fsPath);
  return picked.folder;
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const folder = await resolveFolder(context);
  if (!folder) return;

  const payloadRoot = vscode.Uri.joinPath(context.extensionUri, "payload").fsPath;
  const store = new StateStore(payloadRoot, folder.uri.fsPath);
  const output = vscode.window.createOutputChannel("CommitForge");

  context.subscriptions.push(
    store,
    output,
    createStatusBar(store),
    createTreeView(store),
    vscode.commands.registerCommand("commitforge.refresh", () => store.refresh()),
    vscode.commands.registerCommand("commitforge.focusView", () =>
      vscode.commands.executeCommand("commitforge.view.focus"),
    ),
    // 트리의 project/global 행에서 호출되면 VS Code가 그 TreeItem(Node)을
    // 첫 인자로 넘긴다. 이미 범위를 아는 상태이므로 QuickPick으로 다시
    // 묻지 않는다. 명령 팔레트에서 인자 없이 호출됐을 때만 묻는다.
    //
    // commitforge.install/upgrade/reinstall은 셋 다 이 핸들러 하나에
    // 위임한다(install.py가 항상 같은 백업 후 덮어쓰기를 한다). 명령을
    // 나눈 것은 오직 VS Code 메뉴 title이 명령별로 고정되기 때문이며,
    // 팔레트에는 별칭 두 개를 숨겨(package.json commandPalette when:false)
    // "설치" 하나만 남긴다.
    vscode.commands.registerCommand("commitforge.install", (node?: Node) =>
      handleInstall(store, output, node),
    ),
    vscode.commands.registerCommand("commitforge.upgrade", (node?: Node) =>
      handleInstall(store, output, node),
    ),
    vscode.commands.registerCommand("commitforge.reinstall", (node?: Node) =>
      handleInstall(store, output, node),
    ),
    vscode.commands.registerCommand("commitforge.uninstall", async (node?: Node) => {
      const scope = node?.scope ?? (await pickScope());
      if (scope) await runInstaller(store, "uninstall", scope, output);
    }),
    // spec §7.3 "[Finder에서 열기]": revealFileInOS는 Uri를 받지만
    // view/item/context 메뉴는 TreeItem(Node)을 넘기므로, 얇은 래퍼로
    // resourcePath를 Uri로 바꿔 표준 명령에 위임한다.
    vscode.commands.registerCommand("commitforge.revealSnapshots", async (node?: Node) => {
      if (!node?.resourcePath) return;
      await vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(node.resourcePath),
      );
    }),
    vscode.commands.registerCommand("commitforge.verify", async () => {
      // spec §7.4: 검증은 verify.py(소스 패키지 검사)가 아니라 §5.1 판정을
      // 재실행해 설치본을 검사한다. StateStore.refresh()가 그 판정이다.
      await store.refresh();
      const state = store.current;
      if (!state) return;
      output.show(true);
      for (const report of [state.project, state.global]) {
        output.appendLine(`[${report.scope}] 상태: ${report.state}`);
        for (const path of report.missingFiles) output.appendLine(`  누락: ${path}`);
        for (const path of report.mismatchedFiles) output.appendLine(`  불일치: ${path}`);
        for (const warning of report.warnings) output.appendLine(`  경고: ${warning}`);
      }
    }),
  );

  try {
    await store.refresh();
  } catch (error) {
    // payload/ 가 없으면 sync-payload 없이 패키징된 것이다. 빌드 실패로 본다.
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`CommitForge 초기화 실패: ${message}`);
    void vscode.window.showErrorMessage(
      `CommitForge 확장을 초기화하지 못했습니다: ${message}`,
    );
  }
}

export function deactivate(): void {}
