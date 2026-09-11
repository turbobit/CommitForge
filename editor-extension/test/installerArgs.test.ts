import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { installerArgs } from "../src/vscode/installer";

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
