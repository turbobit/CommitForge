import * as vscode from "vscode";
import { StateStore } from "./state";
import { createStatusBar } from "./vscode/statusBar";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) return;

  const payloadRoot = vscode.Uri.joinPath(context.extensionUri, "payload").fsPath;
  const store = new StateStore(payloadRoot, folder.uri.fsPath);

  context.subscriptions.push(
    store,
    createStatusBar(store),
    vscode.commands.registerCommand("commitforge.refresh", () => store.refresh()),
    vscode.commands.registerCommand("commitforge.focusView", () =>
      vscode.commands.executeCommand("workbench.view.explorer"),
    ),
  );

  await store.refresh();
}

export function deactivate(): void {}
