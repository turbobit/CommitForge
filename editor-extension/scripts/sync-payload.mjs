import { cp, mkdir, rm, access, readdir } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const FILES = ["install.py", "uninstall.py", "MANIFEST.json", "VERSION"];
const DIRS = [join(".claude", "skills"), join(".claude", "agents")];

async function listFiles(root, dir) {
  const out = [];
  for (const entry of await readdir(join(root, dir), { withFileTypes: true })) {
    const rel = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listFiles(root, rel)));
    else out.push(rel);
  }
  return out;
}

export async function syncPayload(repoRoot, payloadDir) {
  for (const file of [...FILES, ...DIRS]) {
    try {
      await access(join(repoRoot, file));
    } catch {
      throw new Error(`페이로드 원본이 없습니다: ${file}`);
    }
  }

  await rm(payloadDir, { recursive: true, force: true });
  await mkdir(payloadDir, { recursive: true });

  const copied = [];
  for (const file of FILES) {
    await cp(join(repoRoot, file), join(payloadDir, file));
    copied.push(file);
  }
  for (const dir of DIRS) {
    await cp(join(repoRoot, dir), join(payloadDir, dir), { recursive: true });
    copied.push(...(await listFiles(payloadDir, dir)));
  }
  return copied;
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  const here = dirname(fileURLToPath(import.meta.url));
  const extensionRoot = join(here, "..");
  const repoRoot = join(extensionRoot, "..");
  const copied = await syncPayload(repoRoot, join(extensionRoot, "payload"));
  console.log(`payload 동기화 완료: ${copied.length}개 파일`);
  console.log(`  원본: ${relative(process.cwd(), repoRoot) || "."}`);
}
