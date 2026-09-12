import { describe, expect, it, vi } from "vitest";
import * as vscode from "vscode";
import { createWatchers } from "../src/vscode/watchers";
import type { StateStore, WorkspaceState } from "../src/state";

interface WatcherRecord {
  base: unknown;
  pattern: string;
  fireChange: () => void;
  fireCreate: () => void;
  fireDelete: () => void;
  dispose: ReturnType<typeof vi.fn>;
}

/** createFileSystemWatcher를 가로채, 어떤 base/pattern으로 몇 개가 만들어졌는지와
 * dispose 여부를 추적하고, 등록된 핸들러를 테스트에서 직접 발화할 수 있게 한다. */
function spyOnWatchers() {
  const records: WatcherRecord[] = [];
  const spy = vi
    .spyOn(vscode.workspace, "createFileSystemWatcher")
    .mockImplementation((globPattern: unknown) => {
      const pattern = globPattern as vscode.RelativePattern;
      const changeHandlers: Array<() => void> = [];
      const createHandlers: Array<() => void> = [];
      const deleteHandlers: Array<() => void> = [];
      const disposeSpy = vi.fn();
      const record: WatcherRecord = {
        base: pattern.base,
        pattern: pattern.pattern,
        fireChange: () => changeHandlers.forEach((h) => h()),
        fireCreate: () => createHandlers.forEach((h) => h()),
        fireDelete: () => deleteHandlers.forEach((h) => h()),
        dispose: disposeSpy,
      };
      records.push(record);
      return {
        onDidChange: vi.fn((h: () => void) => {
          changeHandlers.push(h);
          return { dispose: vi.fn() };
        }),
        onDidCreate: vi.fn((h: () => void) => {
          createHandlers.push(h);
          return { dispose: vi.fn() };
        }),
        onDidDelete: vi.fn((h: () => void) => {
          deleteHandlers.push(h);
          return { dispose: vi.fn() };
        }),
        dispose: disposeSpy,
      } as unknown as vscode.FileSystemWatcher;
    });
  return { records, spy };
}

/** store.onDidChange 구독자에게 상태를 밀어 넣을 수 있는 최소 StateStore 대역. */
function makeStore(initial: WorkspaceState | null = null) {
  const listeners: Array<(state: WorkspaceState | null) => void> = [];
  const refresh = vi.fn();
  const store = {
    refresh,
    get current() {
      return initial;
    },
    onDidChange: vi.fn((cb: (state: WorkspaceState | null) => void) => {
      listeners.push(cb);
      return { dispose: vi.fn() };
    }),
  };
  return {
    store: store as unknown as StateStore,
    refresh,
    fire: (state: WorkspaceState | null) => listeners.forEach((cb) => cb(state)),
  };
}

function stateWithGitDir(gitDir: string): WorkspaceState {
  return { guard: { gitDir } } as unknown as WorkspaceState;
}

const folder = {
  uri: { fsPath: "/repo" },
  name: "repo",
  index: 0,
} as unknown as vscode.WorkspaceFolder;

describe("createWatchers", () => {
  it(".claude/**는 gitDir을 몰라도 즉시 만들고, 이벤트가 발화하면 디바운스 후 refresh를 호출한다", () => {
    vi.useFakeTimers();
    const { records, spy } = spyOnWatchers();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: vi.fn() }));
    const { store, refresh } = makeStore(null);

    createWatchers(store, folder);

    expect(records).toHaveLength(1);
    expect(records[0]?.pattern).toBe(".claude/**");
    expect(refresh).not.toHaveBeenCalled();

    records[0]?.fireChange();
    expect(refresh).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    spy.mockRestore();
    focusSpy.mockRestore();
    vi.useRealTimers();
  });

  it("gitDir이 store.onDidChange로 나중에 도착하면 그때 git 감시자를 만든다", () => {
    vi.useFakeTimers();
    const { records, spy } = spyOnWatchers();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: vi.fn() }));
    const { store, fire, refresh } = makeStore(null);

    createWatchers(store, folder);
    expect(records).toHaveLength(1); // .claude/** 뿐

    fire(stateWithGitDir("/repo/.git/worktrees/editor-extension-ui"));

    const patterns = records.map((r) => r.pattern).sort();
    expect(patterns).toEqual(
      [".claude/**", "claude-atomic.lock/**", "claude-atomic-snapshots/**"].sort(),
    );
    const gitRecord = records.find((r) => r.pattern === "claude-atomic.lock/**");
    expect((gitRecord?.base as { fsPath: string }).fsPath).toBe(
      "/repo/.git/worktrees/editor-extension-ui",
    );

    // git 감시자 이벤트도 refresh로 이어진다.
    gitRecord?.fireCreate();
    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    spy.mockRestore();
    focusSpy.mockRestore();
    vi.useRealTimers();
  });

  it("gitDir이 이미 알려진 상태로 시작하면 처음부터 git 감시자를 만든다", () => {
    const { records, spy } = spyOnWatchers();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: vi.fn() }));
    const { store } = makeStore(stateWithGitDir("/repo/.git"));

    createWatchers(store, folder);

    expect(records).toHaveLength(3);

    spy.mockRestore();
    focusSpy.mockRestore();
  });

  it("gitDir이 바뀌면 이전 git 감시자를 dispose하고 새로 만든다", () => {
    const { records, spy } = spyOnWatchers();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: vi.fn() }));
    const { store, fire } = makeStore(null);

    createWatchers(store, folder);
    fire(stateWithGitDir("/repo/.git/worktrees/a"));
    const firstGitRecords = records.filter((r) => r.pattern !== ".claude/**");
    expect(firstGitRecords).toHaveLength(2);

    fire(stateWithGitDir("/repo/.git/worktrees/b"));
    for (const r of firstGitRecords) expect(r.dispose).toHaveBeenCalledTimes(1);

    const currentGitRecords = records.filter(
      (r) => r.pattern !== ".claude/**" && !r.dispose.mock.calls.length,
    );
    expect(currentGitRecords).toHaveLength(2);
    for (const r of currentGitRecords) {
      expect((r.base as { fsPath: string }).fsPath).toBe("/repo/.git/worktrees/b");
    }

    spy.mockRestore();
    focusSpy.mockRestore();
  });

  it("gitDir을 모르는 동안에도 예외 없이 동작하고, 그 상태로 dispose해도 문제없다", () => {
    const { spy } = spyOnWatchers();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: vi.fn() }));
    const { store, fire } = makeStore(null);

    const subscription = createWatchers(store, folder);
    expect(() => fire(null)).not.toThrow();
    expect(() => subscription.dispose()).not.toThrow();

    spy.mockRestore();
    focusSpy.mockRestore();
  });

  it("watcher 전체와 포커스 구독을 dispose가 전부 정리한다", () => {
    const { records, spy } = spyOnWatchers();
    const focusDisposeSpy = vi.fn();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: focusDisposeSpy }));
    const { store, fire } = makeStore(null);

    const subscription = createWatchers(store, folder);
    fire(stateWithGitDir("/repo/.git/worktrees/a"));
    expect(records).toHaveLength(3);

    subscription.dispose();

    for (const r of records) expect(r.dispose).toHaveBeenCalledTimes(1);
    expect(focusDisposeSpy).toHaveBeenCalledTimes(1);

    spy.mockRestore();
    focusSpy.mockRestore();
  });

  it("포커스 복귀 시에만 debounce를 거쳐 store.refresh를 호출한다", () => {
    vi.useFakeTimers();

    let focusHandler: ((state: { focused: boolean }) => void) | undefined;
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(((handler: (state: { focused: boolean }) => void) => {
        focusHandler = handler;
        return { dispose: vi.fn() };
      }) as unknown as typeof vscode.window.onDidChangeWindowState);
    const { spy } = spyOnWatchers();
    const { store, refresh } = makeStore(null);

    createWatchers(store, folder);

    expect(focusHandler).toBeDefined();
    focusHandler?.({ focused: true });
    expect(refresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    focusHandler?.({ focused: false });
    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    spy.mockRestore();
    focusSpy.mockRestore();
    vi.useRealTimers();
  });
});
