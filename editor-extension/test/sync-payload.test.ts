import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { syncPayload } from "../scripts/sync-payload.mjs";

async function makeRepo(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "cf-payload-"));
  await mkdir(join(root, ".claude", "skills", "cr"), { recursive: true });
  await mkdir(join(root, ".claude", "agents"), { recursive: true });
  await writeFile(join(root, ".claude", "skills", "cr", "SKILL.md"), "---\nname: cr\n---\n");
  await writeFile(join(root, ".claude", "agents", "cca-git-reviewer.md"), "agent\n");
  await writeFile(join(root, "install.py"), "# install\n");
  await writeFile(join(root, "uninstall.py"), "# uninstall\n");
  await writeFile(join(root, "MANIFEST.json"), '{"version":"1.15.0","files":[]}\n');
  await writeFile(join(root, "VERSION"), "1.15.0\n");
  return root;
}

describe("syncPayload", () => {
  let root: string;
  let payload: string;

  beforeEach(async () => {
    root = await makeRepo();
    payload = join(root, "editor-extension", "payload");
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("복사한 상대 경로를 모두 반환한다", async () => {
    const copied = await syncPayload(root, payload);

    expect(copied).toContain("install.py");
    expect(copied).toContain("uninstall.py");
    expect(copied).toContain("MANIFEST.json");
    expect(copied).toContain("VERSION");
    expect(copied).toContain(join(".claude", "skills", "cr", "SKILL.md"));
    expect(copied).toContain(join(".claude", "agents", "cca-git-reviewer.md"));
  });

  it("내용을 그대로 복사한다", async () => {
    await syncPayload(root, payload);

    const text = await readFile(join(payload, ".claude", "skills", "cr", "SKILL.md"), "utf8");
    expect(text).toBe("---\nname: cr\n---\n");
  });

  it("이전 payload 내용을 지우고 다시 만든다", async () => {
    await mkdir(payload, { recursive: true });
    await writeFile(join(payload, "stale.txt"), "old\n");

    await syncPayload(root, payload);

    await expect(access(join(payload, "stale.txt"))).rejects.toThrow();
  });

  it("원본 파일이 없으면 실패한다", async () => {
    await rm(join(root, "install.py"));

    await expect(syncPayload(root, payload)).rejects.toThrow(/install\.py/);
  });
});
