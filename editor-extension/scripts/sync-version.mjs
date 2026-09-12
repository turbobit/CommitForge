import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * lockfile에도 같은 버전을 반영한다. package.json만 고치면 다음 npm install이
 * lockfile을 되돌려 작업 트리가 더러워지고 release.py --check가 깨진다.
 */
async function syncLockfile(lockfilePath, version) {
  let text;
  try {
    text = await readFile(lockfilePath, "utf8");
  } catch {
    return false;
  }

  const lock = JSON.parse(text);
  lock.version = version;
  if (lock.packages?.[""]) lock.packages[""].version = version;
  await writeFile(lockfilePath, `${JSON.stringify(lock, null, 2)}\n`, "utf8");
  return true;
}

export async function syncVersion(repoRoot, packageJsonPath) {
  const version = (await readFile(join(repoRoot, "VERSION"), "utf8")).trim();
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`VERSION이 semver가 아닙니다: ${version}`);
  }

  const pkg = JSON.parse(await readFile(packageJsonPath, "utf8"));
  pkg.version = version;
  await writeFile(packageJsonPath, `${JSON.stringify(pkg, null, 2)}\n`, "utf8");

  await syncLockfile(join(dirname(packageJsonPath), "package-lock.json"), version);
  return version;
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  const here = dirname(fileURLToPath(import.meta.url));
  const extensionRoot = join(here, "..");
  const version = await syncVersion(join(extensionRoot, ".."), join(extensionRoot, "package.json"));
  console.log(`확장 버전을 ${version} 으로 맞췄습니다`);
}
