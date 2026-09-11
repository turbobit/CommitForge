import { readFile } from "node:fs/promises";
import { join } from "node:path";

export interface ManifestEntry {
  path: string;
  size: number;
  sha256: string;
}

export interface Manifest {
  name: string;
  version: string;
  file_count: number;
  files: ManifestEntry[];
}

const SKILL_MD_PATTERN = /^\.claude\/skills\/([^/]+)\/SKILL\.md$/;

/**
 * 매니페스트에서 명령 이름을 파생한다. install.py의 규칙과 정확히 일치해야 한다:
 * `.claude/skills/<name>/SKILL.md` 형태이고 `<name>`이 `_`로 시작하지 않는 것
 * (`_git-atomic-core`는 명령이 아니라 공유 스크립트 묶음이므로 제외).
 *
 * 예전에는 이 목록을 정적 배열로 하드코딩했다. install.py에만 새 명령이 추가되고
 * (실제로 직전 릴리스에서 /cf, /cfr, /ccf가 이렇게 추가됐다) 여기를 갱신하지 않으면,
 * 새 명령의 SKILL.md가 해시 대조 대상(exactEntries)에 잘못 포함되어 정상 설치가
 * corrupt로 오판된다. 매니페스트에서 파생하면 이 드리프트 자체가 불가능하다.
 */
export function commandNames(manifest: Manifest): string[] {
  return claudeEntries(manifest)
    .map((entry) => SKILL_MD_PATTERN.exec(entry.path)?.[1])
    .filter((name): name is string => name !== undefined && !name.startsWith("_"));
}

/** install.py가 CORE_REFERENCE를 치환하므로 설치 후 해시가 달라지는 파일들. */
export function rewrittenSkillPaths(manifest: Manifest): string[] {
  return commandNames(manifest).map((name) => `.claude/skills/${name}/SKILL.md`);
}

export function parseManifest(text: string): Manifest {
  const raw = JSON.parse(text) as Partial<Manifest>;
  if (typeof raw.version !== "string" || !Array.isArray(raw.files)) {
    throw new Error("MANIFEST.json 형식이 올바르지 않습니다");
  }
  return {
    name: raw.name ?? "CommitForge",
    version: raw.version,
    file_count: raw.file_count ?? raw.files.length,
    files: raw.files,
  };
}

export async function loadManifest(payloadRoot: string): Promise<Manifest> {
  return parseManifest(await readFile(join(payloadRoot, "MANIFEST.json"), "utf8"));
}

export function claudeEntries(manifest: Manifest): ManifestEntry[] {
  return manifest.files.filter((entry) => entry.path.startsWith(".claude/"));
}

export function exactEntries(manifest: Manifest): ManifestEntry[] {
  const rewritten = new Set(rewrittenSkillPaths(manifest));
  return claudeEntries(manifest).filter((entry) => !rewritten.has(entry.path));
}
