import { createHash } from "node:crypto";
import { access, readFile, realpath as fsRealpath } from "node:fs/promises";
import { join, resolve } from "node:path";
import { exactEntries, rewrittenSkillPaths, type Manifest } from "./payload";

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

/**
 * spec §5.1: 해시 대조가 판정의 근거이고 마커는 표시용이다. "설치된 버전"으로
 * 어떤 번호를 보여줄지는 상태에 따라 다르다:
 *
 * - `ok`: 파일 해시가 번들과 일치한다고 이미 보증했으므로 번들 버전을 보여준다.
 *   마커가 낡았거나(구버전 마커) 손으로 편집됐어도 무시한다 — 해시가 근거다.
 * - `version-mismatch`: 마커가 있으면 마커의 버전을 보여주고, 마커가 없으면
 *   설치 버전을 알 길이 없으므로 `null`을 돌려준다. 번들 버전을 대신
 *   보여주면 "번들 버전이 곧 설치 버전"이라는 잘못된 인상을 준다.
 * - 그 외(`missing`/`misconfigured`/`corrupt`): spec이 규정하지 않으므로
 *   기존 동작(마커 우선, 없으면 번들 버전)을 유지한다.
 *
 * statusBar.ts와 treeView.ts가 같은 규칙을 따르도록 여기 한 곳에 모은다 —
 * 예전에는 두 파일이 각자 계산해 트리와 상태바가 같은 입력에 다른 버전
 * 번호를 보여주는 모순이 있었다.
 */
export function displayedVersion(report: InstallReport): string | null {
  if (report.state === "missing") return null;
  if (report.state === "ok") return report.bundleVersion;
  if (report.state === "version-mismatch") return report.installedVersion;
  return report.installedVersion ?? report.bundleVersion;
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
 * 매니페스트가 기대하는 CommitForge 파일 전체 (해시 대조 대상 + 치환되는
 * SKILL.md). `.claude/skills/` 존재 여부만으로 판정하면 자기 skill을 쓰는
 * 사용자를 corrupt로 오판하므로, 이 목록에 든 파일이 하나도 없을 때만
 * missing으로 본다.
 */
function expectedFilePaths(manifest: Manifest): string[] {
  return [...exactEntries(manifest).map((entry) => entry.path), ...rewrittenSkillPaths(manifest)];
}

/**
 * install.py:87은 core_path를 `.resolve()`(심링크 해석)로 기록한다. Node의
 * `path.resolve()`는 어휘적이라 심링크를 풀지 않으므로, 워크스페이스 경로 자체가
 * 심링크(또는 macOS의 `/tmp`·`/var`처럼 실경로와 다른 별칭)이면 어휘적 비교만으로는
 * 정상 설치도 못 알아본다. 어휘적 경로와 realpath 둘 다 후보로 두고 SKILL.md 내용이
 * 그중 하나라도 포함하면 통과로 본다. realpath 계산이 실패하면(경로가 아직 없는 등)
 * 어휘적 경로만 쓴다.
 */
async function corePathCandidates(claudeDir: string): Promise<string[]> {
  const lexical = resolve(join(claudeDir, "skills", "_git-atomic-core"));
  const candidates = [lexical];
  try {
    const real = await fsRealpath(lexical);
    if (real !== lexical) candidates.push(real);
  } catch {
    // 경로가 아직 존재하지 않거나 접근할 수 없으면 어휘적 경로만 후보로 남긴다.
  }
  return candidates;
}

/** Windows는 드라이브 문자·경로 대소문자가 뒤섞일 수 있어(`c:\` vs `C:\`) 무시하고 비교한다. */
function textIncludesPath(text: string, candidate: string): boolean {
  if (process.platform === "win32") {
    return text.toLowerCase().includes(candidate.toLowerCase());
  }
  return text.includes(candidate);
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
  const candidates = await corePathCandidates(claudeDir);
  let allOk = true;

  for (const relative of paths) {
    const text = await readIfPresent(join(claudeDir, relative.replace(/^\.claude\//, "")));
    if (text === null) {
      missing.push(relative);
      continue;
    }
    if (!candidates.some((candidate) => textIncludesPath(text, candidate))) allOk = false;
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
