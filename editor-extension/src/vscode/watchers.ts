import * as vscode from "vscode";
import type { StateStore } from "../state";

/**
 * 연속 호출을 하나로 합쳐 마지막 호출 후 ms만큼 조용해지면 한 번만 실행한다.
 * dispose 이후에는 예약된 실행도, 새 call()도 아무 효과가 없다.
 */
export function debounce(
  fn: () => void,
  ms: number,
): { call: () => void; dispose: () => void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;

  return {
    call: () => {
      if (disposed) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = undefined;
        if (!disposed) fn();
      }, ms);
    },
    dispose: () => {
      disposed = true;
      if (timer) clearTimeout(timer);
    },
  };
}

/**
 * 폴링하지 않는다. 창 포커스 복귀와 파일 변화(§7.1)에만 반응해 store를 갱신한다.
 * guard.py는 프로세스를 새로 띄우는 비용이 있으므로, 몰려 들어오는 변화를
 * 200ms 동안 모아 한 번만 실행한다(디바운스 — 반복 타이머가 아니다).
 */
export function createWatchers(
  store: StateStore,
  folder: vscode.WorkspaceFolder,
): vscode.Disposable {
  const refresh = debounce(() => void store.refresh(), 200);

  const patterns = [
    ".git/claude-atomic.lock/**",
    ".git/claude-atomic-snapshots/**",
    ".claude/**",
  ];

  const watchers = patterns.map((pattern) => {
    const watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(folder, pattern),
    );
    watcher.onDidChange(refresh.call);
    watcher.onDidCreate(refresh.call);
    watcher.onDidDelete(refresh.call);
    return watcher;
  });

  const focus = vscode.window.onDidChangeWindowState((windowState) => {
    if (windowState.focused) refresh.call();
  });

  return vscode.Disposable.from(...watchers, focus, { dispose: refresh.dispose });
}
