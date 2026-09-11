import { describe, expect, it, vi } from "vitest";
import { debounce } from "../src/vscode/watchers";

describe("debounce", () => {
  it("연속 호출을 한 번으로 합친다", async () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    debounced.call();
    debounced.call();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("간격을 두면 각각 실행한다", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    vi.advanceTimersByTime(100);
    debounced.call();
    vi.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("dispose 후에는 실행하지 않는다", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    debounced.dispose();
    vi.advanceTimersByTime(500);

    expect(fn).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});
