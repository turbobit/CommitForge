import { describe, expect, it } from "vitest";
import { StateStore } from "../src/state";

/** doRefresh() 호출마다 독립된 resolver/rejecter를 큐에 쌓아, 완료 시점을 제어한다. */
function deferredDoRefresh() {
  const resolvers: Array<() => void> = [];
  const rejecters: Array<(err: unknown) => void> = [];
  const fn = () =>
    new Promise<void>((resolve, reject) => {
      resolvers.push(resolve);
      rejecters.push(reject);
    });
  return { fn, resolvers, rejecters };
}

/**
 * Node의 `unhandledRejection`은 마이크로태스크 큐가 아니라 이벤트 루프 한 턴이
 * 끝나는 시점에 판정된다. `.catch()`가 늦게(다른 async 함수의 await 체인 등으로)
 * 붙는 경우를 검증하려면 순수 마이크로태스크 반복(`await Promise.resolve()`)만으로는
 * 부족하고, 매크로태스크 경계(`setImmediate`)를 최소 한 번 넘겨야 한다.
 */
async function flushEventLoopTurn(): Promise<void> {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

describe("StateStore.refresh", () => {
  // 회귀 1 재현: watchers.ts는 `void store.refresh()`처럼 반환값을 관찰하지
  // 않는다. refresh()가 `async refresh() { await this.runRefresh(); }`
  // 형태였을 때는(직전 라운드가 만든 회귀), coalesceAsync가 트레일링
  // promise에 미리 붙여 둔 `.catch(() => {})`가 원본 promise만 보호할 뿐,
  // `await`가 그 promise를 감싸며 새로 만드는 바깥 promise(= refresh()가
  // 실제로 반환하는 promise)는 보호하지 못해 unhandled rejection이 샜다.
  // watchers.test.ts는 StateStore를 대역(makeStore)으로 바꿔 쓰므로 이
  // 갭을 덮지 못하고, coalesce.test.ts의 run()을 직접 호출하는 테스트도
  // state.ts가 추가하는 이 감쌈 자체를 재현하지 못한다.
  it("트레일링 실행이 실패해도 `void store.refresh()`가 unhandled rejection을 남기지 않는다", async () => {
    const store = new StateStore("/payload", "/repo");
    const { fn, resolvers, rejecters } = deferredDoRefresh();
    // doRefresh는 private이라 TS 타입 체크로는 접근할 수 없지만, 런타임에는
    // 평범한 인스턴스 메서드라 테스트에서 실제 vscode API를 태우지 않고
    // coalesceAsync 연동만 검증하도록 이렇게 갈아끼운다.
    (store as unknown as { doRefresh: () => Promise<void> }).doRefresh = fn;

    const unhandled: unknown[] = [];
    const onUnhandled = (reason: unknown) => unhandled.push(reason);
    process.on("unhandledRejection", onUnhandled);

    try {
      void store.refresh(); // leader
      void store.refresh(); // joiner: watchers.ts의 `void store.refresh()`와 동일한 패턴

      resolvers[0]?.(); // leader 성공 → 트레일링 시작
      await flushEventLoopTurn();

      rejecters[1]?.(new Error("doRefresh 실패")); // 아무도 안 지켜보는 트레일링이 실패
      await flushEventLoopTurn();

      expect(unhandled).toHaveLength(0);
    } finally {
      process.off("unhandledRejection", onUnhandled);
    }
  });
});
