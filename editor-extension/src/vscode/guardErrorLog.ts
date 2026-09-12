import type * as vscode from "vscode";
import type { StateStore, WorkspaceState } from "../state";

/**
 * spec §8 표: "`guard.py status` 실패 → 마지막 성공 상태를 회색 표시 + stderr를
 * Output에". guardError는 예전에 treeView.ts의 경고 노드에만 반영됐고, Output
 * 채널에 쓰는 곳은 installer.ts와 commitforge.verify뿐이었다 — guard.py 실패의
 * stderr가 Output에 영영 도달하지 못했다.
 *
 * store.onDidChange를 구독해 guardError가 "새로" 생겼을 때만 Output에 적는다.
 * 매 갱신(포커스 복귀·watcher debounce 등)마다 같은 이유로 계속 실패해도
 * 채널이 도배되지 않도록, 직전에 기록한 오류 문자열과 같으면 건너뛴다. 오류가
 * 한 번 회복(null)됐다가 같은 메시지로 다시 나면 별개의 실패이므로 다시 적는다.
 */
export function createGuardErrorLog(
  store: StateStore,
  output: vscode.OutputChannel,
): vscode.Disposable {
  let lastLogged: string | null = null;

  const handle = (state: WorkspaceState | null): void => {
    const guardError = state?.guardError ?? null;
    if (guardError !== null && guardError !== lastLogged) {
      output.appendLine(`CommitForge: guard.py status 실패 — ${guardError}`);
    }
    lastLogged = guardError;
  };

  handle(store.current);
  return store.onDidChange(handle);
}
