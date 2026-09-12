import { describe, expect, it, vi } from "vitest";
import { createGuardErrorLog } from "../src/vscode/guardErrorLog";
import type { StateStore, WorkspaceState } from "../src/state";

/** store.onDidChange 구독자에게 상태를 밀어 넣을 수 있는 최소 StateStore 대역. */
function makeStore(initial: WorkspaceState | null = null) {
  let current = initial;
  const listeners: Array<(state: WorkspaceState | null) => void> = [];
  const store = {
    get current() {
      return current;
    },
    onDidChange: vi.fn((cb: (state: WorkspaceState | null) => void) => {
      listeners.push(cb);
      return { dispose: vi.fn() };
    }),
  };
  return {
    store: store as unknown as StateStore,
    fire: (state: WorkspaceState | null) => {
      current = state;
      listeners.forEach((cb) => cb(state));
    },
  };
}

function withGuardError(guardError: string | null): WorkspaceState {
  return { guardError } as unknown as WorkspaceState;
}

function makeOutput() {
  const lines: string[] = [];
  return { appendLine: vi.fn((line: string) => lines.push(line)), lines };
}

// spec §8: "guard.py status 실패 → 마지막 성공 상태를 회색 표시 + stderr를
// Output에". guardError는 트리 경고 노드에만 반영되고 Output 채널에 쓰는
// 곳은 installer/verify뿐이라, guard.py 실패의 stderr가 Output에 전혀
// 도달하지 못했다.
describe("createGuardErrorLog", () => {
  it("guardError가 새로 생기면 Output에 기록한다", () => {
    const { store, fire } = makeStore(null);
    const output = makeOutput();

    createGuardErrorLog(store, output as never);
    expect(output.appendLine).not.toHaveBeenCalled();

    fire(withGuardError("guard.py status 실패 (exit 1): 뭔가 잘못됨"));

    expect(output.lines).toHaveLength(1);
    expect(output.lines[0]).toContain("뭔가 잘못됨");
  });

  it("같은 오류가 반복돼도 한 번만 기록한다(채널 도배 방지)", () => {
    const { store, fire } = makeStore(null);
    const output = makeOutput();

    createGuardErrorLog(store, output as never);

    fire(withGuardError("boom"));
    fire(withGuardError("boom"));
    fire(withGuardError("boom"));

    expect(output.appendLine).toHaveBeenCalledTimes(1);
  });

  it("오류가 사라졌다가 다시 나면(같은 메시지라도) 다시 기록한다", () => {
    const { store, fire } = makeStore(null);
    const output = makeOutput();

    createGuardErrorLog(store, output as never);

    fire(withGuardError("boom"));
    fire(withGuardError(null)); // 회복
    fire(withGuardError("boom")); // 다시 실패

    expect(output.appendLine).toHaveBeenCalledTimes(2);
  });

  it("오류 메시지가 바뀌면 다시 기록한다", () => {
    const { store, fire } = makeStore(null);
    const output = makeOutput();

    createGuardErrorLog(store, output as never);

    fire(withGuardError("first"));
    fire(withGuardError("second"));

    expect(output.appendLine).toHaveBeenCalledTimes(2);
  });

  it("guardError가 없으면 아무것도 기록하지 않는다", () => {
    const { store, fire } = makeStore(null);
    const output = makeOutput();

    createGuardErrorLog(store, output as never);
    fire(withGuardError(null));
    fire(null);

    expect(output.appendLine).not.toHaveBeenCalled();
  });

  it("생성 시점에 이미 guardError가 있으면(store.current) 그때도 기록한다", () => {
    const { store } = makeStore(withGuardError("이미 실패 상태"));
    const output = makeOutput();

    createGuardErrorLog(store, output as never);

    expect(output.lines).toHaveLength(1);
    expect(output.lines[0]).toContain("이미 실패 상태");
  });
});
