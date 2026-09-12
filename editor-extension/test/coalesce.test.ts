import { describe, expect, it, vi } from "vitest";
import { coalesceAsync } from "../src/core/coalesce";

/** fn() 호출마다 독립된 resolver/rejecter를 큐에 쌓아, 테스트에서 완료 시점을 제어한다. */
function deferredFn() {
  const resolvers: Array<() => void> = [];
  const rejecters: Array<(err: unknown) => void> = [];
  const fn = vi.fn(
    () =>
      new Promise<void>((resolve, reject) => {
        resolvers.push(resolve);
        rejecters.push(reject);
      }),
  );
  return { fn, resolvers, rejecters };
}

/** 아직 settle되지 않았는지 확인하기 위해, 마이크로태스크 몇 바퀴를 흘려보낸다. */
async function flushMicrotasks(times = 3): Promise<void> {
  for (let i = 0; i < times; i++) await Promise.resolve();
}

describe("coalesceAsync", () => {
  it("실행 중이 아니면 즉시 실행한다", async () => {
    const fn = vi.fn().mockResolvedValue(undefined);
    const run = coalesceAsync(fn);

    await run();
    await run();

    expect(fn).toHaveBeenCalledTimes(2);
  });

  // spec §7.4: 검증은 §5.1 판정을 "전체 재실행"해야 한다. extension.ts의
  // commitforge.verify는 `await store.refresh()` 직후 store.current를 읽는데,
  // refresh()가 실행 중일 때 도착한 호출이 즉시 resolve되면(예전 동작)
  // 재판정 이전 상태를 검증 결과로 출력하게 된다. 실행 중에 도착한 호출은
  // 트레일링(한 번 더) 실행이 끝날 때까지 기다려야 한다.
  it("실행 중 들어온 요청은 트레일링 실행이 끝날 때까지 기다린다", async () => {
    const { fn, resolvers } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run(); // leader: fn 1회차를 즉시 시작
    expect(fn).toHaveBeenCalledTimes(1);

    const p2 = run(); // 실행 중 도착 → pending만 세우고 트레일링을 기다려야 한다

    let p2Settled = false;
    void p2.finally(() => {
      p2Settled = true;
    });

    resolvers[0]?.(); // leader의 fn 1회차 종료
    await p1;

    // leader(p1)는 예전처럼 자신의 fn() 호출 결과만 책임지고 끝난다.
    expect(fn).toHaveBeenCalledTimes(2); // pending이 있었으니 트레일링(2회차)이 이미 시작됨

    // 하지만 p2는 트레일링(2회차)이 끝나기 전까지는 settle되면 안 된다.
    await flushMicrotasks();
    expect(p2Settled).toBe(false);

    resolvers[1]?.(); // 트레일링 실행 종료
    await p2;

    expect(p2Settled).toBe(true);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("실행 중 여러 번 요청해도 재실행은 한 번으로 합치고, 그 한 번을 모두 함께 기다린다", async () => {
    const { fn, resolvers } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run();
    const p2 = run();
    const p3 = run();
    const p4 = run();

    let joinersSettled = false;
    void Promise.all([p2, p3, p4]).finally(() => {
      joinersSettled = true;
    });

    resolvers[0]?.();
    await p1;

    expect(fn).toHaveBeenCalledTimes(2); // 4번 요청됐어도 재실행(트레일링)은 1회

    await flushMicrotasks();
    expect(joinersSettled).toBe(false); // 트레일링이 아직 안 끝났다

    resolvers[1]?.();
    await Promise.all([p2, p3, p4]);

    expect(joinersSettled).toBe(true);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("트레일링 실행이 실패하면 기다리던 호출에 그 에러가 전파된다", async () => {
    const { fn, resolvers, rejecters } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run();
    const p2 = run(); // 트레일링을 기다리게 될 joiner

    resolvers[0]?.(); // leader 성공
    await p1;

    expect(fn).toHaveBeenCalledTimes(2); // 트레일링 시작됨

    const failure = new Error("guard.py status 실패");
    rejecters[1]?.(failure); // 트레일링 실패

    await expect(p2).rejects.toThrow("guard.py status 실패");
  });

  it("leader의 fn()이 실패해도 running/pending 상태가 새지 않고, 대기 중이던 pending은 트레일링으로 이어진다", async () => {
    const { fn, resolvers, rejecters } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run();
    const p2 = run(); // pending을 세워 트레일링을 기다리게 됨

    const leaderFailure = new Error("첫 실행 실패");
    rejecters[0]?.(leaderFailure);

    await expect(p1).rejects.toThrow("첫 실행 실패");

    // leader가 실패했어도 pending이 있었으니 트레일링(2회차)이 시작돼야 한다.
    await flushMicrotasks();
    expect(fn).toHaveBeenCalledTimes(2);

    resolvers[1]?.();
    await expect(p2).resolves.toBeUndefined();

    // 상태가 깨끗해졌는지, 새 호출이 다시 즉시 실행되는지로 확인한다.
    const p3 = run();
    expect(fn).toHaveBeenCalledTimes(3);
    resolvers[2]?.();
    await p3;
  });

  it("트레일링 실행 실패가 unhandled rejection을 남기지 않는다(leader 자신은 성공한 채로 끝난다)", async () => {
    const { fn, resolvers, rejecters } = deferredFn();
    const run = coalesceAsync(fn);

    const unhandled: unknown[] = [];
    const onUnhandled = (reason: unknown) => unhandled.push(reason);
    process.on("unhandledRejection", onUnhandled);

    try {
      const p1 = run();
      run(); // joiner: pending만 세우고 트레일링 promise는 버려둔다(관찰 안 함)

      resolvers[0]?.();
      await p1; // leader 자신은 성공

      await flushMicrotasks();
      rejecters[1]?.(new Error("트레일링 실패")); // 아무도 안 지켜보는 트레일링이 실패
      await flushMicrotasks();

      expect(unhandled).toHaveLength(0);
    } finally {
      process.off("unhandledRejection", onUnhandled);
    }
  });
});
