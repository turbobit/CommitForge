/**
 * 실행 중에 들어온 요청을 버리지 않고 병합한다.
 *
 * `fn`이 실행 중일 때 다시 호출되면 그 요청은 실행하지 않고 `pending` 플래그만
 * 세운다. 실행이 끝나면 `pending`이 서 있을 경우 한 번만 더 실행한다. 실행 중에
 * 몇 번을 더 호출해도 플래그 하나로 합쳐지므로 뒤이은 실행은 항상 최대 1회다.
 *
 * StateStore.refresh()처럼 "실행 중이면 조용히 버린다"는 재진입 가드만 있으면,
 * 실행 도중 들어온 마지막 변화가 다음 트리거 없이는 영영 반영되지 않을 수 있다.
 * 이 헬퍼는 그 마지막 변화를 잃지 않고 한 번 더 실행해 반영한다.
 */
export function coalesceAsync(fn: () => Promise<void>): () => Promise<void> {
  let running = false;
  let pending = false;

  const run = async (): Promise<void> => {
    if (running) {
      pending = true;
      return;
    }
    running = true;
    try {
      await fn();
    } finally {
      running = false;
      if (pending) {
        pending = false;
        void run();
      }
    }
  };

  return run;
}
