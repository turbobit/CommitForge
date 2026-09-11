import { describe, expect, it } from "vitest";
import {
  parseManifest,
  claudeEntries,
  exactEntries,
  commandNames,
  rewrittenSkillPaths,
} from "../src/core/payload";
import { loadManifest } from "../src/core/payload";
import { join } from "node:path";
import { existsSync } from "node:fs";

const manifestText = JSON.stringify({
  name: "CommitForge",
  version: "1.15.0",
  file_count: 5,
  files: [
    { path: "README.md", size: 10, sha256: "a".repeat(64) },
    { path: ".claude/agents/cca-git-reviewer.md", size: 20, sha256: "b".repeat(64) },
    { path: ".claude/skills/cr/SKILL.md", size: 30, sha256: "c".repeat(64) },
    { path: ".claude/skills/_git-atomic-core/guard.md", size: 40, sha256: "d".repeat(64) },
    { path: "install.py", size: 50, sha256: "e".repeat(64) },
  ],
});

describe("parseManifest", () => {
  it("버전과 파일 목록을 읽는다", () => {
    const manifest = parseManifest(manifestText);

    expect(manifest.version).toBe("1.15.0");
    expect(manifest.files).toHaveLength(5);
  });

  it("schema가 아니면 실패한다", () => {
    expect(() => parseManifest("{}")).toThrow(/MANIFEST/);
  });

  it("JSON이 아니면 실패한다", () => {
    expect(() => parseManifest("nope")).toThrow();
  });
});

describe("claudeEntries", () => {
  it(".claude/ 항목만 남긴다", () => {
    const paths = claudeEntries(parseManifest(manifestText)).map((e) => e.path);

    expect(paths).toEqual([
      ".claude/agents/cca-git-reviewer.md",
      ".claude/skills/cr/SKILL.md",
      ".claude/skills/_git-atomic-core/guard.md",
    ]);
  });
});

describe("exactEntries", () => {
  it("설치 시 재작성되는 SKILL.md를 제외한다", () => {
    const paths = exactEntries(parseManifest(manifestText)).map((e) => e.path);

    expect(paths).not.toContain(".claude/skills/cr/SKILL.md");
    expect(paths).toContain(".claude/agents/cca-git-reviewer.md");
    expect(paths).toContain(".claude/skills/_git-atomic-core/guard.md");
  });
});

describe("commandNames", () => {
  it("매니페스트의 SKILL.md에서 명령 이름을 파생한다 (_ 로 시작하는 항목은 제외)", () => {
    const names = commandNames(parseManifest(manifestText));

    expect(names).toEqual(["cr"]);
  });

  it("매니페스트에 없는 명령은 만들어내지 않는다 (정적 하드코딩 목록 드리프트 방지)", () => {
    // manifestText에는 명령이 cr 하나뿐이다. 정적 COMMAND_NAMES 배열을 쓰던 예전
    // 구현이라면 매니페스트에 없는 나머지 8개 이름까지 그대로 반환했을 것이다.
    const names = commandNames(parseManifest(manifestText));

    expect(names).not.toContain("cca");
    expect(names).toHaveLength(1);
  });
});

describe("rewrittenSkillPaths", () => {
  it("commandNames가 파생한 이름으로 SKILL.md 경로를 만든다", () => {
    const paths = rewrittenSkillPaths(parseManifest(manifestText));

    expect(paths).toEqual([".claude/skills/cr/SKILL.md"]);
    expect(paths).not.toContain(".claude/skills/_git-atomic-core/SKILL.md");
  });
});

const payloadRoot = join(__dirname, "..", "payload");

describe.skipIf(!existsSync(join(payloadRoot, "MANIFEST.json")))("실제 payload", () => {
  it(".claude/ 항목이 61개고 그중 52개가 해시 대조 대상이다", async () => {
    const manifest = await loadManifest(payloadRoot);

    expect(claudeEntries(manifest)).toHaveLength(61);
    expect(exactEntries(manifest)).toHaveLength(52);
  });

  it("실제 페이로드에서 명령 9개를 파생한다", async () => {
    const manifest = await loadManifest(payloadRoot);

    expect(commandNames(manifest).sort()).toEqual(
      ["cc", "cca", "ccf", "ccr", "cf", "cfr", "cp", "cpr", "cr"],
    );
    expect(rewrittenSkillPaths(manifest)).toHaveLength(9);
  });
});
