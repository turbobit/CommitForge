import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { findOption, loadCatalog, parseArgumentHint, parseSkillFile } from "../src/core/catalog";
import { commandNames, loadManifest } from "../src/core/payload";

describe("parseArgumentHint", () => {
  it("모드 목록을 읽는다", () => {
    const parsed = parseArgumentHint("[clean|today|weekly] [추가 맥락] [--strict]");

    expect(parsed.modes).toEqual(["clean", "today", "weekly"]);
  });

  it("모드가 하나뿐이어도 모드로 본다", () => {
    const parsed = parseArgumentHint("[clean] [추가 맥락]");

    expect(parsed.modes).toEqual(["clean"]);
  });

  it("자유 텍스트 허용 여부를 읽는다", () => {
    expect(parseArgumentHint("[clean] [추가 맥락]").acceptsFreeText).toBe(true);
    expect(parseArgumentHint("[clean] [--strict]").acceptsFreeText).toBe(false);
  });

  it("불리언 플래그를 읽는다", () => {
    const parsed = parseArgumentHint("[--strict] [--no-verify]");

    expect(parsed.options).toEqual([
      { name: "--strict", kind: "flag" },
      { name: "--no-verify", kind: "flag" },
    ]);
  });

  it("자리표시자 값 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--base <ref>] [--scope <경로...>]");

    expect(parsed.options).toEqual([
      { name: "--base", kind: "value", placeholder: "<ref>" },
      { name: "--scope", kind: "value", placeholder: "<경로...>" },
    ]);
  });

  it("열거형 값 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--format human|json|sarif]");

    expect(parsed.options).toEqual([
      { name: "--format", kind: "enum", values: ["human", "json", "sarif"] },
    ]);
  });

  it("수치 범위 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--commits 20-500] [--iterations 1-5]");

    expect(parsed.options).toEqual([
      { name: "--commits", kind: "range", range: [20, 500] },
      { name: "--iterations", kind: "range", range: [1, 5] },
    ]);
  });

  it("배타 플래그 쌍을 서로 연결한다", () => {
    const parsed = parseArgumentHint("[--team|--no-team]");

    expect(parsed.options).toEqual([
      { name: "--team", kind: "flag", exclusiveWith: "--no-team" },
      { name: "--no-team", kind: "flag", exclusiveWith: "--team" },
    ]);
  });

  it("배타 값 옵션 쌍을 잃지 않고 서로 연결한다 (/cr --base|--range)", () => {
    const parsed = parseArgumentHint("[--base <ref>|--range <A..B>]");

    expect(parsed.options).toEqual([
      { name: "--base", kind: "value", placeholder: "<ref>", exclusiveWith: "--range" },
      { name: "--range", kind: "value", placeholder: "<A..B>", exclusiveWith: "--base" },
    ]);
  });

  it("자리표시자 안의 파이프는 분할하지 않는다", () => {
    const parsed = parseArgumentHint("[--timezone <IANA|±HH:MM>]");

    expect(parsed.options).toEqual([
      { name: "--timezone", kind: "value", placeholder: "<IANA|±HH:MM>" },
    ]);
  });

  it("여전히 열거형은 배타 그룹으로 오인하지 않는다", () => {
    const parsed = parseArgumentHint("[--format human|json|sarif]");

    expect(parsed.options).toEqual([
      { name: "--format", kind: "enum", values: ["human", "json", "sarif"] },
    ]);
  });
});

describe("parseSkillFile", () => {
  const ccaText = readFileSync(join(__dirname, "fixtures", "skill-cca.md"), "utf8");
  const ccText = readFileSync(join(__dirname, "fixtures", "skill-cc.md"), "utf8");

  it("실제 /cca frontmatter를 파싱한다", () => {
    const spec = parseSkillFile(ccaText, "cca");

    expect(spec.name).toBe("cca");
    expect(spec.description.length).toBeGreaterThan(10);
    expect(spec.modes).toEqual([
      "clean",
      "today",
      "3days",
      "weekly",
      "release",
      "emergency",
      "learn",
    ]);
    expect(findOption(spec, "--bump")).toEqual({
      name: "--bump",
      kind: "enum",
      values: ["auto", "major", "minor", "patch"],
    });
    expect(findOption(spec, "--commits")).toEqual({
      name: "--commits",
      kind: "range",
      range: [20, 500],
    });
    expect(findOption(spec, "--team")?.exclusiveWith).toBe("--no-team");
  });

  it("실제 /cc frontmatter를 파싱한다", () => {
    const spec = parseSkillFile(ccText, "cc");

    expect(spec.modes).toEqual(["clean"]);
    expect(findOption(spec, "--keep-snapshot")).toEqual({
      name: "--keep-snapshot",
      kind: "flag",
    });
  });

  it("description은 첫 문장만 쓴다", () => {
    const spec = parseSkillFile(ccaText, "cca");

    expect(spec.description).not.toContain("\n");
    expect(spec.description.split(". ").length).toBeLessThanOrEqual(2);
  });

  it("frontmatter가 없으면 실패한다", () => {
    expect(() => parseSkillFile("본문만 있음", "cc")).toThrow(/frontmatter/);
  });

  it("argument-hint가 없으면 옵션 없는 명령으로 본다", () => {
    const spec = parseSkillFile("---\nname: xx\ndescription: 설명이다\n---\n본문\n", "xx");

    expect(spec.options).toEqual([]);
    expect(spec.modes).toEqual([]);
  });
});

describe("loadCatalog (명령 목록 파라미터)", () => {
  it("호출자가 넘긴 이름만 읽는다 (하드코딩된 목록에 의존하지 않는다)", async () => {
    const { mkdtemp, mkdir, writeFile, rm } = await import("node:fs/promises");
    const { tmpdir } = await import("node:os");
    const dir = await mkdtemp(join(tmpdir(), "cf-catalog-"));
    try {
      await mkdir(join(dir, "aa"), { recursive: true });
      await mkdir(join(dir, "bb"), { recursive: true });
      await writeFile(join(dir, "aa", "SKILL.md"), "---\nname: aa\ndescription: A다\n---\n본문\n");
      await writeFile(join(dir, "bb", "SKILL.md"), "---\nname: bb\ndescription: B다\n---\n본문\n");

      // "bb"는 디렉터리에 실제로 존재하지만 호출자가 넘긴 목록에 없으므로 읽지 않는다.
      const specs = await loadCatalog(dir, ["aa"]);

      expect(specs.map((s) => s.name)).toEqual(["aa"]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

const payloadRoot = join(__dirname, "..", "payload");
const skillsDir = join(payloadRoot, ".claude", "skills");

/** 실제 페이로드 매니페스트에서 명령 목록을 파생해 loadCatalog에 넘긴다 (하드코딩 금지). */
async function loadRealCatalog() {
  const manifest = await loadManifest(payloadRoot);
  return loadCatalog(skillsDir, commandNames(manifest));
}

// payload/가 없으면(빌드 전) 이 블록은 건너뛰지 않고 그대로 실패한다 — spec §10이
// 요구하는 "argument-hint 문법 변경 시 즉시 실패"의 핵심 검증이므로, 조용한 skip으로
// 사라지게 두지 않는다. `npm test`는 pretest에서 sync-payload를 먼저 실행하므로
// 정상 환경에서는 항상 존재해야 한다.
describe("loadCatalog", () => {
  it("실제 페이로드에서 명령 9개를 모두 읽는다", async () => {
    const specs = await loadRealCatalog();

    expect(specs.map((s) => s.name).sort()).toEqual(
      ["cc", "cca", "ccf", "ccr", "cf", "cfr", "cp", "cpr", "cr"],
    );
    for (const spec of specs) {
      expect(spec.description.length).toBeGreaterThan(0);
    }
  });

  it("모든 옵션 이름이 -- 로 시작한다", async () => {
    const specs = await loadRealCatalog();

    for (const spec of specs) {
      for (const option of spec.options) {
        expect(option.name, `${spec.name} ${option.name}`).toMatch(/^--[a-z-]+$/);
      }
    }
  });

  it("/cr 스펙에 --base와 --range가 둘 다 있다 (배타 값 옵션 소실 회귀)", async () => {
    const specs = await loadRealCatalog();
    const cr = specs.find((s) => s.name === "cr");

    expect(findOption(cr!, "--base")).toEqual({
      name: "--base",
      kind: "value",
      placeholder: "<ref>",
      exclusiveWith: "--range",
    });
    expect(findOption(cr!, "--range")).toEqual({
      name: "--range",
      kind: "value",
      placeholder: "<A..B>",
      exclusiveWith: "--base",
    });
  });

  it("어떤 옵션의 placeholder에도 다른 옵션 이름이 섞여 들어가지 않는다", async () => {
    // "<ref>|--range <A..B>"처럼 배타 옵션이 깨져 하나로 뭉치면 placeholder에
    // "--"가 남는다. "<IANA|±HH:MM>"처럼 자리표시자 안의 파이프 자체는 정상이므로
    // "|" 유무가 아니라 "--" 유무로 오염 여부를 가른다.
    const specs = await loadRealCatalog();

    for (const spec of specs) {
      for (const option of spec.options) {
        if (option.placeholder === undefined) continue;
        expect(option.placeholder, `${spec.name} ${option.name}`).not.toContain("--");
      }
    }
  });

  it("exclusiveWith가 가리키는 옵션은 같은 명령의 options 안에 실제로 존재한다", async () => {
    // "[--base <ref>|--range <A..B>]"에서 --range가 통째로 사라지는 것처럼,
    // 옵션이 오염 없이 조용히 사라지는 회귀는 placeholder 오염 검사로는 못
    // 잡는다. exclusiveWith 상호 참조가 끊기지 않았는지를 직접 확인한다.
    const specs = await loadRealCatalog();

    for (const spec of specs) {
      const names = new Set(spec.options.map((option) => option.name));
      for (const option of spec.options) {
        if (option.exclusiveWith === undefined) continue;
        expect(
          names.has(option.exclusiveWith),
          `${spec.name} ${option.name}.exclusiveWith === ${option.exclusiveWith} 인데 ` +
            `${spec.name}의 options 안에 ${option.exclusiveWith}가 없습니다`,
        ).toBe(true);
      }
    }
  });
});
