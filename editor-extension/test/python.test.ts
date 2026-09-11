import { describe, expect, it } from "vitest";
import { resolvePython, DEFAULT_CANDIDATES } from "../src/core/python";
import { spawnProbe } from "../src/core/python";

const accept = (ok: string[]) => async (exe: string) => ok.includes(exe);

describe("resolvePython", () => {
  it("설정값이 동작하면 그것을 쓴다", async () => {
    const result = await resolvePython("/opt/py/bin/python3", accept(["/opt/py/bin/python3"]));

    expect(result).toEqual({ executable: "/opt/py/bin/python3", source: "setting" });
  });

  it("설정값이 동작하지 않으면 탐색으로 넘어간다", async () => {
    const result = await resolvePython("/nope/python", accept(["python3"]));

    expect(result).toEqual({ executable: "python3", source: "probe" });
  });

  it("설정이 없으면 후보를 순서대로 시도한다", async () => {
    const result = await resolvePython(undefined, accept(["python"]));

    expect(result).toEqual({ executable: "python", source: "probe" });
  });

  it("먼저 성공한 후보에서 멈춘다", async () => {
    const tried: string[] = [];
    const probe = async (exe: string) => {
      tried.push(exe);
      return exe === DEFAULT_CANDIDATES[0];
    };

    await resolvePython(undefined, probe);

    expect(tried).toEqual([DEFAULT_CANDIDATES[0]]);
  });

  it("전부 실패하면 null을 반환한다", async () => {
    const result = await resolvePython(undefined, accept([]));

    expect(result).toBeNull();
  });

  it("빈 문자열 설정은 무시한다", async () => {
    const result = await resolvePython("   ", accept(["python3"]));

    expect(result).toEqual({ executable: "python3", source: "probe" });
  });
});

describe("spawnProbe", () => {
  it("존재하지 않는 실행 파일은 false다", async () => {
    expect(await spawnProbe("/definitely/not/a/python")).toBe(false);
  });

  it("현재 환경에 Python 3.9+가 있으면 spawnProbe가 그 인터프리터에 true를 돌려준다", async (ctx) => {
    // 이 테스트는 코드가 아니라 실행 환경에 Python이 있는지를 전제로 한다.
    // Python이 없는 머신에서는 코드가 멀쩡해도 실패하므로, 찾은 인터프리터가
    // 있을 때만 의미 있는 단언을 하고 없으면 건너뛴다 (조용히 통과시키지
    // 않고 skip 사실을 출력에 남긴다).
    const interpreter =
      (await spawnProbe("python3")) ? "python3" : (await spawnProbe("python")) ? "python" : null;

    if (interpreter === null) {
      console.warn("[skip] 이 환경에서는 python3/python을 찾지 못해 이 테스트를 건너뜁니다");
      ctx.skip();
      return;
    }

    expect(await spawnProbe(interpreter)).toBe(true);
  });
});
