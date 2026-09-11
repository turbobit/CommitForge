import { describe, expect, it, vi } from "vitest";
import * as vscode from "vscode";
import { createWatchers } from "../src/vscode/watchers";
import type { StateStore } from "../src/state";

describe("createWatchers", () => {
  it("watcher 3개와 포커스 구독 1개를 등록하고, dispose가 전부 정리한다", () => {
    const watcherDisposeSpies: Array<ReturnType<typeof vi.fn>> = [];

    const watcherSpy = vi
      .spyOn(vscode.workspace, "createFileSystemWatcher")
      .mockImplementation(() => {
        const disposeSpy = vi.fn();
        watcherDisposeSpies.push(disposeSpy);
        return {
          onDidChange: vi.fn(() => ({ dispose: vi.fn() })),
          onDidCreate: vi.fn(() => ({ dispose: vi.fn() })),
          onDidDelete: vi.fn(() => ({ dispose: vi.fn() })),
          dispose: disposeSpy,
        } as unknown as vscode.FileSystemWatcher;
      });

    const focusDisposeSpy = vi.fn();
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(() => ({ dispose: focusDisposeSpy }) as unknown as vscode.Disposable);

    const store = { refresh: vi.fn() } as unknown as StateStore;
    const folder = {
      uri: { fsPath: "/repo" },
      name: "repo",
      index: 0,
    } as unknown as vscode.WorkspaceFolder;

    const subscription = createWatchers(store, folder);

    expect(watcherSpy).toHaveBeenCalledTimes(3);
    expect(focusSpy).toHaveBeenCalledTimes(1);

    subscription.dispose();

    expect(watcherDisposeSpies).toHaveLength(3);
    for (const spy of watcherDisposeSpies) expect(spy).toHaveBeenCalledTimes(1);
    expect(focusDisposeSpy).toHaveBeenCalledTimes(1);

    watcherSpy.mockRestore();
    focusSpy.mockRestore();
  });

  it("포커스 복귀 시 store.refresh를 debounce하여 호출한다", () => {
    vi.useFakeTimers();

    let focusHandler: ((state: { focused: boolean }) => void) | undefined;
    const focusSpy = vi
      .spyOn(vscode.window, "onDidChangeWindowState")
      .mockImplementation(((handler: (state: { focused: boolean }) => void) => {
        focusHandler = handler;
        return { dispose: vi.fn() };
      }) as unknown as typeof vscode.window.onDidChangeWindowState);
    const watcherSpy = vi
      .spyOn(vscode.workspace, "createFileSystemWatcher")
      .mockImplementation(() => ({
        onDidChange: vi.fn(() => ({ dispose: vi.fn() })),
        onDidCreate: vi.fn(() => ({ dispose: vi.fn() })),
        onDidDelete: vi.fn(() => ({ dispose: vi.fn() })),
        dispose: vi.fn(),
      }) as unknown as vscode.FileSystemWatcher);

    const refresh = vi.fn();
    const store = { refresh } as unknown as StateStore;
    const folder = {
      uri: { fsPath: "/repo" },
      name: "repo",
      index: 0,
    } as unknown as vscode.WorkspaceFolder;

    createWatchers(store, folder);

    expect(focusHandler).toBeDefined();
    focusHandler?.({ focused: true });
    expect(refresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    // 포커스를 잃을 때는 갱신하지 않는다.
    focusHandler?.({ focused: false });
    vi.advanceTimersByTime(200);
    expect(refresh).toHaveBeenCalledTimes(1);

    watcherSpy.mockRestore();
    focusSpy.mockRestore();
    vi.useRealTimers();
  });
});
