import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { findOption, loadCatalog, parseArgumentHint, parseSkillFile } from "../src/core/catalog";

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

const skillsDir = join(__dirname, "..", "payload", ".claude", "skills");

describe.skipIf(!existsSync(skillsDir))("loadCatalog", () => {
  it("실제 페이로드에서 명령 9개를 모두 읽는다", async () => {
    const specs = await loadCatalog(skillsDir);

    expect(specs.map((s) => s.name).sort()).toEqual(
      ["cc", "cca", "ccf", "ccr", "cf", "cfr", "cp", "cpr", "cr"],
    );
    for (const spec of specs) {
      expect(spec.description.length).toBeGreaterThan(0);
    }
  });

  it("모든 옵션 이름이 -- 로 시작한다", async () => {
    const specs = await loadCatalog(skillsDir);

    for (const spec of specs) {
      for (const option of spec.options) {
        expect(option.name, `${spec.name} ${option.name}`).toMatch(/^--[a-z-]+$/);
      }
    }
  });
});
