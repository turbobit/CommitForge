/**
 * 실행 중에 들어온 요청을 버리지 않고 병합한다.
 *
 * `fn`이 실행 중일 때 다시 호출되면(joiner) 그 요청은 바로 실행하지 않고
 * `pending` 플래그만 세운다. 실행 중이던 호출(leader)이 끝나면 `pending`이
 * 서 있을 경우 한 번만 더(트레일링) 실행한다. 실행 중에 몇 번을 더 호출해도
 * 플래그 하나로 합쳐지므로 뒤이은 실행은 항상 최대 1회다.
 *
 * StateStore.refresh()처럼 "실행 중이면 조용히 버린다"는 재진입 가드만 있으면,
 * 실행 도중 들어온 마지막 변화가 다음 트리거 없이는 영영 반영되지 않을 수 있다.
 * 이 헬퍼는 그 마지막 변화를 잃지 않고 한 번 더 실행해 반영한다.
 *
 * **완료 보장**: joiner로 들어온 호출이 반환하는 promise는 자신이 트리거한
 * 트레일링 실행이 "끝날 때까지" resolve/reject하지 않는다. 예전에는 즉시
 * resolve해, 예를 들어 `commitforge.verify`가 `await store.refresh()` 직후
 * 상태를 읽을 때 재판정 이전 상태를 읽어버리는 계약 위반이 있었다(spec §7.4:
 * 검증은 판정을 전체 재실행해야 한다). leader(실행 시작 시점에 실행 중이 아니던
 * 호출)는 예전처럼 자신이 시작한 실행 결과만 책임지고 끝난다 — 그 결과는
 * 호출 시점 기준으로 이미 최신이라 트레일링까지 기다릴 이유가 없다.
 *
 * 트레일링 실행은 leader가 fire-and-forget으로 던지지 않는다 — joiner들의
 * promise를 채워야 하고, 그러지 않으면 트레일링이 실패했을 때 아무도 처리하지
 * 않는 rejected promise가 남는다.
 *
 * 구현 메모: `run`/`runTrailing`을 일부러 `async function`이 아니라 일반
 * 함수로 짜서 promise를 `.then()`으로 직접 잇는다. `async function`이
 * `return someOtherPromise`를 하면 JS가 그 promise를 감싸는 새 promise를
 * 하나 더 만들어 그 결과를 "입양"하는데(PromiseResolveThenableJob), 이
 * 입양은 마이크로태스크 한 틱이 더 걸린다. joiner가 받는 promise에
 * 미리 `.catch(() => {})`를 붙여도, 실제로 호출자가 받는 것은 그 promise가
 * 아니라 그걸 감싼 바깥 promise라서 그 바깥 promise에는 핸들러가 없어
 * unhandled rejection이 새는 걸 실제로 겪었다. 일반 함수로 promise를 그대로
 * 반환하면 감싸는 계층이 없어 이 문제가 없다.
 */
export function coalesceAsync(fn: () => Promise<void>): () => Promise<void> {
  let running = false;
  let pending = false;
  // 다음 트레일링 실행을 기다리는 joiner들이 공유하는 promise. joiner가 여럿
  // 도착해도 같은 트레일링 한 번에 합류하도록 지연 생성하고, 그 실행이
  // 시작되면(트레일링을 실제로 돌리기 시작하는 시점에) 다음 도착자를 위해
  // 비운다.
  let trailingWaiters: { resolve: () => void; reject: (err: unknown) => void } | null = null;
  let trailingPromise: Promise<void> | null = null;

  function joinTrailing(): Promise<void> {
    if (!trailingPromise) {
      trailingPromise = new Promise<void>((resolve, reject) => {
        trailingWaiters = { resolve, reject };
      });
      // watchers.ts의 `void store.refresh()`처럼 이 반환값을 아무도 관찰하지
      // 않는 호출부가 실제로 있다. 그 경우에도 트레일링 실패가 Node의
      // unhandledRejection으로 새지 않도록 내부적으로 핸들러 하나를 미리
      // 붙여 둔다 — 원본 promise에 핸들러가 있으면 되므로, 이후 호출자가
      // 이 promise를 await/catch해도 reject는 그대로 정상 전달된다.
      trailingPromise.catch(() => {});
    }
    return trailingPromise;
  }

  /**
   * pending을 하나 소비해 한 번 실행하고, 그 실행이 끝난 뒤에도 pending이 또
   * 서 있으면(트레일링 도중 새 joiner가 도착한 경우) 재귀적으로 이어간다.
   * 반환하는 promise는 이 재귀 사슬 전체가 끝나야 settle된다.
   */
  function runTrailing(): Promise<void> {
    pending = false;
    const waiters = trailingWaiters;
    trailingWaiters = null;
    trailingPromise = null;
    running = true;
    return fn().then(
      () => {
        running = false;
        waiters?.resolve();
        if (pending) return runTrailing();
      },
      (err: unknown) => {
        running = false;
        waiters?.reject(err);
        throw err;
      },
    );
  }

  function run(): Promise<void> {
    if (running) {
      pending = true;
      return joinTrailing();
    }
    running = true;
    return fn().then(
      () => {
        running = false;
        if (pending) {
          // leader 자신은 대기하지 않는다(fire-and-forget이지만, catch로
          // 받아 unhandled rejection을 남기지 않는다 — 실패는
          // joinTrailing()으로 대기 중인 joiner에게 이미 reject로
          // 전달된다).
          void runTrailing().catch(() => {});
        }
      },
      (err: unknown) => {
        running = false;
        if (pending) void runTrailing().catch(() => {});
        throw err;
      },
    );
  }

  return run;
}
