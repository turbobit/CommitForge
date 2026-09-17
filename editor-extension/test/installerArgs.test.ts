import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { downgradeNotice, installerArgs } from "../src/vscode/installer";

const payload = join("/ext", "payload");

describe("installerArgs", () => {
  it("project 설치 인자를 만든다", () => {
    expect(installerArgs("install", payload, "project", "/repo", false)).toEqual([
      join(payload, "install.py"),
      "--scope",
      "project",
      "--target",
      "/repo",
    ]);
  });

  it("dry-run 플래그를 붙인다", () => {
    expect(installerArgs("install", payload, "project", "/repo", true)).toContain("--dry-run");
  });

  it("global 범위에는 --target을 넘기지 않는다", () => {
    expect(installerArgs("install", payload, "global", "/repo", false)).toEqual([
      join(payload, "install.py"),
      "--scope",
      "global",
    ]);
  });

  it("제거는 uninstall.py를 쓴다", () => {
    expect(installerArgs("uninstall", payload, "project", "/repo", false)[0]).toBe(
      join(payload, "uninstall.py"),
    );
  });
});

describe("downgradeNotice", () => {
  it("설치본이 번들보다 최신이면 다운그레이드를 알린다", () => {
    expect(downgradeNotice("1.18.0", "1.16.0")).toMatch(/다운그레이드/);
    expect(downgradeNotice("1.18.0", "1.16.0")).toContain("v1.18.0");
    expect(downgradeNotice("1.18.0", "1.16.0")).toContain("v1.16.0");
  });

  it("같거나 낮은 버전이면 알리지 않는다", () => {
    expect(downgradeNotice("1.16.0", "1.16.0")).toBeNull();
    expect(downgradeNotice("1.15.9", "1.16.0")).toBeNull();
  });

  it("자리수가 달라도 숫자로 비교한다", () => {
    expect(downgradeNotice("1.9.0", "1.10.0")).toBeNull();
    expect(downgradeNotice("1.10.0", "1.9.0")).toMatch(/다운그레이드/);
  });

  it("마커가 없으면 알리지 않는다", () => {
    expect(downgradeNotice(null, "1.16.0")).toBeNull();
  });

  it("비교할 수 없는 버전이면 단정하지 않는다", () => {
    expect(downgradeNotice("알수없음", "1.16.0")).toBeNull();
  });
});
