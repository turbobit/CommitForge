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

  it("현재 환경의 python3를 찾으면 true다", async () => {
    const found = (await spawnProbe("python3")) || (await spawnProbe("python"));
    expect(found).toBe(true);
  });
});
