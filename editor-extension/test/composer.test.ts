import { describe, expect, it } from "vitest";
import { compose, isWriteCommand, sanitizeFreeText } from "../src/core/composer";
import { parseSkillFile } from "../src/core/catalog";

const cca = parseSkillFile(
  [
    "---",
    "name: cca",
    "description: 리뷰부터 commit까지 실행한다. 자세한 내용은 문서를 본다.",
    'argument-hint: "[clean|today|release] [추가 맥락] [--team|--no-team] [--bump auto|major|minor|patch] [--base <ref>] [--commits 20-500] [--strict]"',
    "---",
    "본문",
  ].join("\n"),
  "cca",
);

describe("compose", () => {
  it("옵션이 없으면 명령만 낸다", () => {
    expect(compose(cca, { options: [] })).toBe("/cca");
  });

  it("모드를 첫 토큰으로 둔다", () => {
    expect(compose(cca, { mode: "today", options: [] })).toBe("/cca today");
  });

  it("모드 다음에 자유 텍스트를 둔다", () => {
    expect(compose(cca, { mode: "today", freeText: "결제 모듈만", options: [] })).toBe(
      "/cca today 결제 모듈만",
    );
  });

  it("플래그를 붙인다", () => {
    expect(compose(cca, { options: [{ name: "--strict" }] })).toBe("/cca --strict");
  });

  it("값 옵션을 붙인다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "main" }] })).toBe(
      "/cca --base main",
    );
  });

  it("공백이 있는 값은 따옴표로 감싼다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "my branch" }] })).toBe(
      '/cca --base "my branch"',
    );
  });

  it("옵션 순서는 spec 정의 순서를 따른다", () => {
    const result = compose(cca, {
      options: [{ name: "--strict" }, { name: "--team" }],
    });

    expect(result).toBe("/cca --team --strict");
  });

  it("정의되지 않은 모드를 거부한다", () => {
    expect(() => compose(cca, { mode: "nope", options: [] })).toThrow(/nope/);
  });

  it("정의되지 않은 옵션을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--wat" }] })).toThrow(/--wat/);
  });

  it("배타 옵션을 함께 고르면 거부한다", () => {
    expect(() =>
      compose(cca, { options: [{ name: "--team" }, { name: "--no-team" }] }),
    ).toThrow(/--team.*--no-team|--no-team.*--team/);
  });

  it("값이 필요한 옵션에 값이 없으면 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--base" }] })).toThrow(/--base/);
  });

  it("플래그에 값을 주면 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--strict", value: "yes" }] })).toThrow(
      /--strict/,
    );
  });

  it("열거형 밖의 값을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--bump", value: "huge" }] })).toThrow(
      /huge/,
    );
  });

  it("범위 밖의 수치를 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--commits", value: "5" }] })).toThrow(
      /20-500/,
    );
    expect(compose(cca, { options: [{ name: "--commits", value: "100" }] })).toBe(
      "/cca --commits 100",
    );
  });

  it("수치가 아닌 범위 값을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--commits", value: "많이" }] })).toThrow(
      /--commits/,
    );
  });
});

describe("sanitizeFreeText", () => {
  it("개행을 공백으로 바꾼다", () => {
    expect(sanitizeFreeText("첫 줄\n둘째 줄\r\n셋째")).toBe("첫 줄 둘째 줄 셋째");
  });

  it("앞뒤 공백을 없애고 연속 공백을 줄인다", () => {
    expect(sanitizeFreeText("  많은   공백  ")).toBe("많은 공백");
  });
});

describe("isWriteCommand", () => {
  it("쓰기 명령을 구분한다", () => {
    expect(isWriteCommand("cca")).toBe(true);
    expect(isWriteCommand("cc")).toBe(true);
    expect(isWriteCommand("cf")).toBe(true);
    expect(isWriteCommand("ccf")).toBe(true);
    expect(isWriteCommand("cp")).toBe(true);
  });

  it("읽기 전용 명령을 구분한다", () => {
    expect(isWriteCommand("cr")).toBe(false);
    expect(isWriteCommand("ccr")).toBe(false);
    expect(isWriteCommand("cfr")).toBe(false);
    expect(isWriteCommand("cpr")).toBe(false);
  });
});
