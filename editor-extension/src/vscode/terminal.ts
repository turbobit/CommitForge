import * as vscode from "vscode";

const TARGET_KEY = "commitforge.terminalName";

function config<T>(key: string, fallback: T): T {
  return vscode.workspace.getConfiguration("commitforge").get<T>(key, fallback);
}

export type TerminalDecision =
  | { kind: "reuse"; name: string }
  | { kind: "create" }
  | { kind: "ask" };

/**
 * 어떤 터미널로 보낼지 결정하는 순수 로직. 실제 터미널 생성이나 QuickPick
 * 표시 같은 부작용은 `resolveTarget`이 맡는다.
 *
 * spec §6.3: 확장은 자기가 만든 터미널만 신뢰한다. Claude Code가 이미 다른
 * 터미널에서 돌고 있는지는 감지할 수 없으므로, 첫 전송 때 한 번 물어보고
 * 선택을 워크스페이스 세션 동안 기억한다.
 */
export function decideTerminal(
  terminalNames: readonly string[],
  remembered: string | undefined,
  ownName: string,
): TerminalDecision {
  if (remembered !== undefined && terminalNames.includes(remembered)) {
    return { kind: "reuse", name: remembered };
  }
  if (terminalNames.includes(ownName)) return { kind: "reuse", name: ownName };
  if (terminalNames.length === 0) return { kind: "create" };
  return { kind: "ask" };
}

function createTerminal(): vscode.Terminal {
  const name = config("terminal.name", "CommitForge");
  const launch = config("terminal.launchCommand", "claude");
  const terminal = vscode.window.createTerminal({ name });
  terminal.show(true);
  // 사용자의 대화형 셸을 그대로 거치므로 claude가 zsh 함수나 alias여도
  // 동작한다(spec §3.6). child_process.spawn으로는 이 래핑이 적용되지 않는다.
  terminal.sendText(launch, true);
  return terminal;
}

/**
 * 확장이 만든(또는 이미 기억해 둔) 터미널을 우선 쓴다. 후보가 여럿이면
 * 사용자에게 한 번 물어보고 선택을 워크스페이스 세션 동안 기억한다.
 */
export async function resolveTarget(
  context: vscode.ExtensionContext,
): Promise<vscode.Terminal | undefined> {
  const own = config("terminal.name", "CommitForge");
  const remembered = context.workspaceState.get<string>(TARGET_KEY);
  const names = vscode.window.terminals.map((terminal) => terminal.name);
  const decision = decideTerminal(names, remembered, own);

  if (decision.kind === "reuse") {
    const found = vscode.window.terminals.find((terminal) => terminal.name === decision.name);
    if (found) {
      await context.workspaceState.update(TARGET_KEY, decision.name);
      return found;
    }
    // 기억해 둔(또는 이름이 같은) 터미널이 그 사이 닫혔다면 새로 만든다.
  }

  if (decision.kind !== "ask") {
    const created = createTerminal();
    await context.workspaceState.update(TARGET_KEY, created.name);
    return created;
  }

  const picked = await vscode.window.showQuickPick(
    [
      ...vscode.window.terminals.map((terminal) => ({
        label: terminal.name,
        description: "이미 열린 터미널",
      })),
      { label: `$(add) 새 터미널 "${own}"`, description: "claude를 새로 실행합니다" },
    ],
    { placeHolder: "명령을 보낼 터미널을 고르십시오" },
  );
  if (!picked) return undefined;

  if (picked.label.startsWith("$(add)")) {
    const created = createTerminal();
    await context.workspaceState.update(TARGET_KEY, created.name);
    return created;
  }

  await context.workspaceState.update(TARGET_KEY, picked.label);
  return vscode.window.terminals.find((terminal) => terminal.name === picked.label);
}

export function sendCommand(terminal: vscode.Terminal, command: string): void {
  terminal.show(true);
  terminal.sendText(command, true);
}
