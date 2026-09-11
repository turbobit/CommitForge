import { describe, expect, it } from "vitest";
import {
  parseManifest,
  claudeEntries,
  exactEntries,
  REWRITTEN_SKILL_PATHS,
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

describe("REWRITTEN_SKILL_PATHS", () => {
  it("명령 9개를 모두 담는다", () => {
    expect(REWRITTEN_SKILL_PATHS).toHaveLength(9);
    expect(REWRITTEN_SKILL_PATHS).toContain(".claude/skills/cca/SKILL.md");
    expect(REWRITTEN_SKILL_PATHS).not.toContain(".claude/skills/_git-atomic-core/SKILL.md");
  });
});

const payloadRoot = join(__dirname, "..", "payload");

describe.skipIf(!existsSync(join(payloadRoot, "MANIFEST.json")))("실제 payload", () => {
  it(".claude/ 항목이 61개고 그중 52개가 해시 대조 대상이다", async () => {
    const manifest = await loadManifest(payloadRoot);

    expect(claudeEntries(manifest)).toHaveLength(61);
    expect(exactEntries(manifest)).toHaveLength(52);
  });
});
