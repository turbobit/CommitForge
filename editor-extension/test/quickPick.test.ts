import { describe, expect, it } from "vitest";
import { groupOptionsByMode, pushRecent } from "../src/vscode/quickPick";
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
