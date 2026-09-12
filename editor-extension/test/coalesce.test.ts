import { describe, expect, it, vi } from "vitest";
import { coalesceAsync } from "../src/core/coalesce";

/** fn() 호출마다 독립된 resolver를 큐에 쌓아, 테스트에서 완료 시점을 제어한다. */
function deferredFn() {
  const resolvers: Array<() => void> = [];
  const fn = vi.fn(() => new Promise<void>((resolve) => resolvers.push(resolve)));
  return { fn, resolvers };
}

describe("coalesceAsync", () => {
  it("실행 중이 아니면 즉시 실행한다", async () => {
    const fn = vi.fn().mockResolvedValue(undefined);
    const run = coalesceAsync(fn);

    await run();
    await run();

    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("실행 중 들어온 요청은 버려지지 않고 완료 후 한 번 더 실행된다", async () => {
    const { fn, resolvers } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run();
    expect(fn).toHaveBeenCalledTimes(1);

    const p2 = run(); // 실행 중에 도착 → pending만 세우고 즉시 반환
    await p2;
    expect(fn).toHaveBeenCalledTimes(1); // 아직 재실행 전

    resolvers[0]?.(); // 첫 실행 종료
    await p1;

    expect(fn).toHaveBeenCalledTimes(2); // pending이 있었으니 한 번 더 실행됨

    resolvers[1]?.(); // 트레일링 실행도 정리
  });

  it("실행 중 여러 번 요청해도 재실행은 한 번으로 합친다", async () => {
    const { fn, resolvers } = deferredFn();
    const run = coalesceAsync(fn);

    const p1 = run();
    const p2 = run();
    const p3 = run();
    const p4 = run();
    await Promise.all([p2, p3, p4]);
    expect(fn).toHaveBeenCalledTimes(1);

    resolvers[0]?.();
    await p1;

    expect(fn).toHaveBeenCalledTimes(2); // 4번 요청됐어도 재실행은 1회

    resolvers[1]?.();
  });
});
