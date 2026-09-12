import { describe, expect, it } from "vitest";
import { groupOptionsByMode, pushRecent, resolveWarningAnswer } from "../src/vscode/quickPick";
import type { CommandOption } from "../src/core/catalog";

function flag(name: string): CommandOption {
  return { name, kind: "flag" };
}

const ccaOptions: CommandOption[] = [
  flag("--team"),
  flag("--no-team"),
  { name: "--target", kind: "value", placeholder: "<semver>" },
  { name: "--bump", kind: "enum", values: ["auto", "major", "minor", "patch"] },
  { name: "--incident", kind: "value", placeholder: "<id>" },
  { name: "--since", kind: "value", placeholder: "<ref>" },
  { name: "--commits", kind: "range", range: [20, 500] },
  flag("--strict"),
];

describe("groupOptionsByMode", () => {
  it("모드가 없으면 옵션 전체를 한 그룹으로 순서 그대로 낸다", () => {
    const groups = groupOptionsByMode({ options: ccaOptions }, undefined);

    expect(groups).toHaveLength(1);
    expect(groups[0]?.label).toBe("옵션");
    expect(groups[0]?.options).toEqual(ccaOptions);
  });

  it("release 모드는 관련 옵션을 먼저, 나머지를 기타로 둔다", () => {
    const groups = groupOptionsByMode({ options: ccaOptions }, "release");

    expect(groups).toHaveLength(2);
    expect(groups[0]?.label).toBe("release 관련");
    expect(groups[0]?.options.map((o) => o.name)).toEqual(["--target", "--bump"]);
    expect(groups[1]?.label).toBe("기타");
    expect(groups[1]?.options.map((o) => o.name)).toEqual([
      "--team",
      "--no-team",
      "--incident",
      "--since",
      "--commits",
      "--strict",
    ]);
  });

  it("힌트에 없는 새 옵션도 기타 그룹에 남는다(필터하지 않는다)", () => {
    const withNewOption = [...ccaOptions, flag("--brand-new-option")];
    const groups = groupOptionsByMode({ options: withNewOption }, "release");

    const others = groups[1]?.options.map((o) => o.name) ?? [];
    expect(others).toContain("--brand-new-option");
  });

  it("힌트 표에 없는 모드는 전체를 하나의 그룹으로 둔다", () => {
    const groups = groupOptionsByMode({ options: ccaOptions }, "learn");

    expect(groups).toHaveLength(1);
    expect(groups[0]?.options).toEqual(ccaOptions);
  });

  it("옵션이 없으면 빈 그룹 목록을 낸다", () => {
    expect(groupOptionsByMode({ options: [] }, "release")).toEqual([]);
  });
});

describe("pushRecent", () => {
  it("새 명령을 맨 앞에 둔다", () => {
    expect(pushRecent([], "/cr")).toEqual(["/cr"]);
    expect(pushRecent(["/cr"], "/cca today")).toEqual(["/cca today", "/cr"]);
  });

  it("이미 있던 항목은 중복 없이 맨 앞으로 옮긴다", () => {
    expect(pushRecent(["/cr", "/cca today"], "/cr")).toEqual(["/cr", "/cca today"]);
  });

  it("최대 개수를 넘으면 뒤를 자른다", () => {
    const recent = ["a", "b", "c", "d", "e"];
    expect(pushRecent(recent, "f", 5)).toEqual(["f", "a", "b", "c", "d"]);
  });
});

// runCleanLock(트리 [해제(clean)] 버튼)은 "/cr clean"을 remember:false로
// 보낸다 — 카탈로그에서 고른 게 아닌 보조 명령은 최근 목록에 남기지 않는다는
// 정책이다. lock 경고 모달에서 "clean 실행"을 고르는 것도 사용자가 카탈로그
// 에서 고른 명령이 아니라 lock 충돌을 피하려는 같은 보조 동작이므로, 같은
// 정책(remember:false)을 따라야 한다. "그래도 보내기"는 사용자가 원래
// 고른 명령을 그대로 보내는 것이므로 기존 remember:true 정책을 유지한다.
describe("resolveWarningAnswer", () => {
  it('"clean 실행"을 고르면 /cr clean을 remember:false로 보낸다', () => {
    expect(resolveWarningAnswer("clean 실행", "/cca today")).toEqual({
      command: "/cr clean",
      remember: false,
    });
  });

  it('"그래도 보내기"를 고르면 원래 명령을 remember:true로 그대로 보낸다', () => {
    expect(resolveWarningAnswer("그래도 보내기", "/cca today")).toEqual({
      command: "/cca today",
      remember: true,
    });
  });

  it("모달을 닫거나 다른 답이면 아무것도 보내지 않는다", () => {
    expect(resolveWarningAnswer(undefined, "/cca today")).toBeUndefined();
  });
});
