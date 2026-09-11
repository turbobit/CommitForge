import { cp, mkdir, rm, access, readdir, readFile } from "node:fs/promises";
import { basename, dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const FILES = ["install.py", "uninstall.py", "MANIFEST.json", "VERSION"];
const DIRS = [join(".claude", "skills"), join(".claude", "agents")];

const EXCLUDED_DIR_NAMES = new Set(["__pycache__"]);
const EXCLUDED_FILE_NAMES = new Set([".DS_Store"]);

function shouldExclude(path) {
  const name = basename(path);
  if (EXCLUDED_DIR_NAMES.has(name)) return true;
  if (EXCLUDED_FILE_NAMES.has(name)) return true;
  if (name.endsWith(".pyc")) return true;
  return false;
}

async function listFiles(root, dir) {
  const out = [];
  for (const entry of await readdir(join(root, dir), { withFileTypes: true })) {
    const rel = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listFiles(root, rel)));
    else out.push(rel);
  }
  return out;
}

function toPosixPath(path) {
  return path.split(sep).join("/");
}

async function verifyClaudeMatchesManifest(payloadDir) {
  const manifestRaw = await readFile(join(payloadDir, "MANIFEST.json"), "utf8");
  const manifest = JSON.parse(manifestRaw);
  const manifestFiles = Array.isArray(manifest.files) ? manifest.files : [];
  const manifestClaudePaths = new Set(
    manifestFiles
      .map((entry) => (typeof entry === "string" ? entry : entry.path))
      .filter((path) => typeof path === "string" && path.startsWith(".claude/"))
  );

  const actualClaudePaths = new Set(
    (await listFiles(payloadDir, ".claude")).map(toPosixPath)
  );

  const onlyInPayload = [...actualClaudePaths].filter((path) => !manifestClaudePaths.has(path)).sort();
  const onlyInManifest = [...manifestClaudePaths].filter((path) => !actualClaudePaths.has(path)).sort();

  if (onlyInPayload.length > 0 || onlyInManifest.length > 0) {
    const details = [];
    if (onlyInPayload.length > 0) {
      details.push(`payload에만 있음: ${onlyInPayload.join(", ")}`);
    }
    if (onlyInManifest.length > 0) {
      details.push(`MANIFEST에만 있음: ${onlyInManifest.join(", ")}`);
    }
    throw new Error(`payload/.claude가 MANIFEST.json과 일치하지 않습니다 (${details.join(" / ")})`);
  }
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
    await cp(join(repoRoot, dir), join(payloadDir, dir), {
      recursive: true,
      filter: (src) => !shouldExclude(src),
    });
    copied.push(...(await listFiles(payloadDir, dir)));
  }

  await verifyClaudeMatchesManifest(payloadDir);

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
