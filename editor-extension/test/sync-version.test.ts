import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { syncVersion } from "../scripts/sync-version.mjs";

describe("syncVersion", () => {
  let root: string;

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), "cf-version-"));
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("VERSION을 package.json에 반영한다", async () => {
    await writeFile(join(root, "VERSION"), "1.16.0\n");
    const pkg = join(root, "package.json");
    await writeFile(pkg, JSON.stringify({ name: "commitforge", version: "0.0.0" }, null, 2));

    const version = await syncVersion(root, pkg);

    expect(version).toBe("1.16.0");
    const updated = JSON.parse(await readFile(pkg, "utf8"));
    expect(updated.version).toBe("1.16.0");
    expect(updated.name).toBe("commitforge");
  });

  it("semver가 아니면 실패한다", async () => {
    await writeFile(join(root, "VERSION"), "not-a-version\n");
    const pkg = join(root, "package.json");
    await writeFile(pkg, JSON.stringify({ version: "0.0.0" }));

    await expect(syncVersion(root, pkg)).rejects.toThrow(/semver/);
  });

  it("package-lock.json의 두 version 필드도 함께 갱신한다", async () => {
    await writeFile(join(root, "VERSION"), "1.16.0\n");
    const pkg = join(root, "package.json");
    const lock = join(root, "package-lock.json");
    await writeFile(pkg, JSON.stringify({ name: "commitforge", version: "0.0.0" }, null, 2));
    await writeFile(
      lock,
      JSON.stringify(
        {
          name: "commitforge",
          version: "0.0.0",
          lockfileVersion: 3,
          packages: { "": { name: "commitforge", version: "0.0.0" }, "node_modules/x": {} },
        },
        null,
        2,
      ),
    );

    await syncVersion(root, pkg);

    const updated = JSON.parse(await readFile(lock, "utf8"));
    expect(updated.version).toBe("1.16.0");
    expect(updated.packages[""].version).toBe("1.16.0");
    // 나머지 항목은 건드리지 않는다.
    expect(updated.lockfileVersion).toBe(3);
    expect(updated.packages["node_modules/x"]).toEqual({});
  });

  it("package-lock.json이 없어도 실패하지 않는다", async () => {
    await writeFile(join(root, "VERSION"), "1.16.0\n");
    const pkg = join(root, "package.json");
    await writeFile(pkg, JSON.stringify({ name: "commitforge", version: "0.0.0" }, null, 2));

    await expect(syncVersion(root, pkg)).resolves.toBe("1.16.0");
  });
});
