import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export async function syncVersion(repoRoot, packageJsonPath) {
  const version = (await readFile(join(repoRoot, "VERSION"), "utf8")).trim();
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`VERSION이 semver가 아닙니다: ${version}`);
  }

  const pkg = JSON.parse(await readFile(packageJsonPath, "utf8"));
  pkg.version = version;
  await writeFile(packageJsonPath, `${JSON.stringify(pkg, null, 2)}\n`, "utf8");
  return version;
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  const here = dirname(fileURLToPath(import.meta.url));
  const extensionRoot = join(here, "..");
  const version = await syncVersion(join(extensionRoot, ".."), join(extensionRoot, "package.json"));
  console.log(`확장 버전을 ${version} 으로 맞췄습니다`);
}
