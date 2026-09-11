import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  claudeEntries,
  exactEntries,
  REWRITTEN_SKILL_PATHS,
  type Manifest,
} from "./payload";

export type InstallState =
  | "missing"
  | "ok"
  | "version-mismatch"
  | "misconfigured"
  | "corrupt";

export type Scope = "project" | "global";

export interface InstallMarker {
  schema: string;
  version: string;
  scope: Scope;
  installed_at: string;
  python: string;
  core_path: string;
}

export interface InstallReport {
  state: InstallState;
  scope: Scope;
  claudeDir: string;
  bundleVersion: string;
  installedVersion: string | null;
  missingFiles: string[];
  mismatchedFiles: string[];
  corePathOk: boolean;
  hooksRegistered: boolean;
  warnings: string[];
}

const MARKER_NAME = ".commitforge-install.json";
const LIFECYCLE_SCRIPT = "session_lifecycle.py";

async function readIfPresent(path: string): Promise<string | null> {
  try {
    return await readFile(path, "utf8");
  } catch {
    return null;
  }
}

/**
 * 해시 대조 전용. release.py의 sha256()은 파일의 raw bytes를 해시하므로,
 * 여기서도 UTF-8 디코딩 없이 Buffer 그대로 해시해야 한다. `readIfPresent`
 * (문자열)로 읽으면 잘못된 UTF-8 바이트가 U+FFFD로 치환되어 해시가 달라지고,
 * 멀쩡한 설치가 손상으로 오판된다.
 */
async function readBytesIfPresent(path: string): Promise<Buffer | null> {
  try {
    return await readFile(path);
  } catch {
    return null;
  }
}

async function readMarker(
  claudeDir: string,
  warnings: string[],
): Promise<InstallMarker | null> {
  const text = await readIfPresent(join(claudeDir, MARKER_NAME));
  if (text === null) return null;
  try {
    return JSON.parse(text) as InstallMarker;
  } catch {
    warnings.push(`${MARKER_NAME} 을 읽을 수 없습니다. 버전 표시를 건너뜁니다.`);
    return null;
  }
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

/**
 * 매니페스트에 실제로 포함된 rewritten SKILL.md 경로만 추린다. install.py가
 * core 경로를 치환하는 9개 명령 중, 이 매니페스트에 실려온 것만 검사 대상이다
 * (테스트처럼 축소된 매니페스트를 넘기는 경우를 포함해 COMMAND_NAMES 전체를
 * 고정으로 검사하면 실제로 없는 항목까지 "누락"으로 오판하게 된다).
 */
function rewrittenSkillPaths(manifest: Manifest): string[] {
  const rewritten = new Set(REWRITTEN_SKILL_PATHS);
  return claudeEntries(manifest)
    .map((entry) => entry.path)
    .filter((path) => rewritten.has(path));
}

/**
 * 매니페스트가 기대하는 CommitForge 파일 전체 (해시 대조 대상 + 치환되는
 * SKILL.md). `.claude/skills/` 존재 여부만으로 판정하면 자기 skill을 쓰는
 * 사용자를 corrupt로 오판하므로, 이 목록에 든 파일이 하나도 없을 때만
 * missing으로 본다.
 */
function expectedFilePaths(manifest: Manifest): string[] {
  return [...exactEntries(manifest).map((entry) => entry.path), ...rewrittenSkillPaths(manifest)];
}

/**
 * 설치된 SKILL.md는 install.py가 core 경로를 치환하므로 해시가 달라진다.
 * 대신 치환된 경로가 이 설치를 가리키는지를 본다. 다른 머신에서 클론한
 * .claude/ 를 그대로 쓰는 경우를 잡기 위해서다.
 */
async function checkCorePaths(
  claudeDir: string,
  paths: string[],
  missing: string[],
): Promise<boolean> {
  const expected = resolve(join(claudeDir, "skills", "_git-atomic-core"));
  let allOk = true;

  for (const relative of paths) {
    const text = await readIfPresent(join(claudeDir, relative.replace(/^\.claude\//, "")));
    if (text === null) {
      missing.push(relative);
      continue;
    }
    if (!text.includes(expected)) allOk = false;
  }
  return allOk;
}

async function checkHooks(
  claudeDir: string,
  scope: Scope,
  warnings: string[],
): Promise<boolean> {
  const name = scope === "global" ? "settings.json" : "settings.local.json";
  const text = await readIfPresent(join(claudeDir, name));
  if (text === null) return false;

  try {
    return JSON.stringify(JSON.parse(text)).includes(LIFECYCLE_SCRIPT);
  } catch {
    warnings.push(`${name} 이 올바른 JSON이 아닙니다. 재설치가 필요합니다.`);
    return false;
  }
}

export async function detectInstall(
  claudeDir: string,
  manifest: Manifest,
  scope: Scope,
): Promise<InstallReport> {
  const warnings: string[] = [];
  const missingFiles: string[] = [];
  const mismatchedFiles: string[] = [];

  // 존재 여부만 가볍게 확인한다 (access, 내용 읽기 아님). 기대 파일이 하나도
  // 없으면 미설치, 일부만 있으면 아래 일반 로직이 missingFiles를 채워 corrupt로
  // 분류한다.
  const expected = expectedFilePaths(manifest);
  const presentCount = (
    await Promise.all(
      expected.map((relative) => exists(join(claudeDir, relative.replace(/^\.claude\//, "")))),
    )
  ).filter(Boolean).length;

  if (expected.length > 0 && presentCount === 0) {
    return {
      state: "missing",
      scope,
      claudeDir,
      bundleVersion: manifest.version,
      installedVersion: null,
      missingFiles: [],
      mismatchedFiles: [],
      corePathOk: false,
      hooksRegistered: false,
      warnings,
    };
  }

  for (const entry of exactEntries(manifest)) {
    const absolute = join(claudeDir, entry.path.replace(/^\.claude\//, ""));
    const bytes = await readBytesIfPresent(absolute);
    if (bytes === null) {
      missingFiles.push(entry.path);
      continue;
    }
    const digest = createHash("sha256").update(bytes).digest("hex");
    if (digest !== entry.sha256) mismatchedFiles.push(entry.path);
  }

  const corePathOk = await checkCorePaths(
    claudeDir,
    rewrittenSkillPaths(manifest),
    missingFiles,
  );
  const hooksRegistered = await checkHooks(claudeDir, scope, warnings);
  const marker = await readMarker(claudeDir, warnings);

  const total = exactEntries(manifest).length;
  const state = classify({
    missingCount: missingFiles.length,
    mismatchedCount: mismatchedFiles.length,
    totalExact: total,
    corePathOk,
    hooksRegistered,
  });

  if (state === "ok" && marker && marker.version !== manifest.version) {
    warnings.push(
      `설치 마커는 v${marker.version}이라고 하지만 파일은 번들 v${manifest.version}과 같습니다. ` +
        "마커가 낡았을 수 있습니다.",
    );
  }

  return {
    state,
    scope,
    claudeDir,
    bundleVersion: manifest.version,
    installedVersion:
      state === "version-mismatch"
        ? marker?.version ?? null
        : marker?.version ?? manifest.version,
    missingFiles,
    mismatchedFiles,
    corePathOk,
    hooksRegistered,
    warnings,
  };
}

function classify(input: {
  missingCount: number;
  mismatchedCount: number;
  totalExact: number;
  corePathOk: boolean;
  hooksRegistered: boolean;
}): InstallState {
  if (input.missingCount > 0) return "corrupt";

  // 전부 다르면 다른 버전, 일부만 다르면 손상으로 본다.
  if (input.mismatchedCount > 0) {
    return input.mismatchedCount === input.totalExact ? "version-mismatch" : "corrupt";
  }
  if (!input.corePathOk || !input.hooksRegistered) return "misconfigured";
  return "ok";
}
