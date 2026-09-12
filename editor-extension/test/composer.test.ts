import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { compose, isWriteCommand, sanitizeFreeText } from "../src/core/composer";
import { parseSkillFile } from "../src/core/catalog";
import { spawnProbe } from "../src/core/python";

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

const cr = parseSkillFile(
  [
    "---",
    "name: cr",
    "description: 코드 리뷰를 실행한다.",
    'argument-hint: "[clean|today] [추가 맥락] [--fix] [--strict]"',
    "---",
    "본문",
  ].join("\n"),
  "cr",
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

  it("공백 없이 따옴표만 있는 값도 감싸고 이스케이프한다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: '"weird"' }] })).toBe(
      '/cca --base "\\"weird\\""',
    );
  });

  it("공백과 따옴표가 함께 있는 값을 올바르게 이스케이프한다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: 'my "branch"' }] })).toBe(
      '/cca --base "my \\"branch\\""',
    );
  });

  it("백슬래시가 든 값을 이스케이프한다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "a\\b c" }] })).toBe(
      '/cca --base "a\\\\b c"',
    );
  });

  it("공백 없이 백슬래시만 있는 값도 감싸고 이스케이프한다", () => {
    // 감싸지 않으면 터미널로 그대로 전송된 뒤 cr_edit_gate.py의 shlex.split이
    // 따옴표 밖 백슬래시를 이스케이프로 취급해 "a\\b"가 "ab"로 뭉개진다.
    expect(compose(cca, { options: [{ name: "--base", value: "a\\b" }] })).toBe(
      '/cca --base "a\\\\b"',
    );
  });

  it("공백·백슬래시·큰따옴표 없이 홑따옴표만 있는 값도 감싼다", () => {
    // 감싸지 않으면 cr_edit_gate.py의 shlex.split(원문 인자)이
    // "No closing quotation"으로 실패해 --fix 인식 자체가 깨진다.
    // 큰따옴표로 감싸면 홑따옴표는 이스케이프 없이도 안전하다.
    expect(compose(cca, { options: [{ name: "--base", value: "o'brien-lib" }] })).toBe(
      `/cca --base "o'brien-lib"`,
    );
  });

  it("안전한 문자(영숫자·- _ . / : = @ + ,)만 있는 값은 감싸지 않는다", () => {
    for (const value of ["main", "feature/foo", "v1.2.3", "a@b.com", "release_1.0-rc1", "a,b"]) {
      expect(compose(cca, { options: [{ name: "--base", value } ] })).toBe(`/cca --base ${value}`);
    }
  });

  it("옵션 값 중간의 개행을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--base", value: "foo\nbar" }] })).toThrow(
      /--base/,
    );
  });

  it("옵션 값 앞뒤의 개행·공백은 trim되어 통과한다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "\n  main  \n" }] })).toBe(
      "/cca --base main",
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

/** cr_edit_gate.py가 실제로 쓰는 Python shlex.split()으로 왕복을 검증한다. */
function shlexSplit(python: string, text: string): string[] {
  const output = execFileSync(python, [
    "-c",
    "import shlex, sys, json; print(json.dumps(shlex.split(sys.argv[1])))",
    text,
  ]);
  return JSON.parse(output.toString()) as string[];
}

describe("compose ↔ 실제 Python shlex.split 왕복", () => {
  // 이 환경에 Python이 있을 때만 의미가 있다 — 없으면 건너뛴다(python.test.ts와
  // 같은 방침).
  it("홑따옴표·백슬래시·따옴표·공백이 섞인 값도 shlex 왕복에서 보존된다", async (ctx) => {
    const python = (await spawnProbe("python3"))
      ? "python3"
      : (await spawnProbe("python"))
        ? "python"
        : null;
    if (!python) {
      console.warn("[skip] 이 환경에서는 python3/python을 찾지 못해 shlex 왕복 테스트를 건너뜁니다");
      ctx.skip();
      return;
    }

    const cases: string[] = [
      "o'brien-lib",
      'my "branch"\\ x',
      "a\\b",
      "main",
      "feature/foo",
      "v1.2.3",
      "a@b.com",
    ];

    for (const value of cases) {
      const composed = compose(cca, { options: [{ name: "--base", value }] });
      expect(shlexSplit(python, composed)).toEqual(["/cca", "--base", value]);
    }
  });

  // cr_edit_gate.py의 exact_fix_requested()는 /cr의 전체 인자 문자열(모드 +
  // freeText + 옵션)을 한 번에 shlex.split()한다. freeText는 quote()를 거치지
  // 않는 산문이라 홑따옴표가 하나만 있어도 예전에는 "No closing quotation"으로
  // 파싱 자체가 깨졌고, --fix가 뒤에 있어도 인식되지 못했다.
  it("freeText에 홑따옴표·큰따옴표·백슬래시·짝이 맞는 따옴표가 있어도 shlex 파싱이 깨지지 않고 --fix가 살아남는다", async (ctx) => {
    const python = (await spawnProbe("python3"))
      ? "python3"
      : (await spawnProbe("python"))
        ? "python"
        : null;
    if (!python) {
      console.warn("[skip] 이 환경에서는 python3/python을 찾지 못해 shlex 왕복 테스트를 건너뜁니다");
      ctx.skip();
      return;
    }

    const freeTexts = [
      "o'brien의 코드",
      '그 "기능" 부분만',
      "경로\\처리 확인",
      '"짝이 맞는" 따옴표 프롬프트',
      "it's a \"quoted\" phrase",
    ];

    for (const freeText of freeTexts) {
      const composed = compose(cr, { freeText, options: [{ name: "--fix" }] });
      expect(() => shlexSplit(python, composed)).not.toThrow();
      expect(shlexSplit(python, composed)).toContain("--fix");
    }
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
