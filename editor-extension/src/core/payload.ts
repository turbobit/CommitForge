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

/** install.py가 CORE_REFERENCE를 치환하므로 설치 후 해시가 달라지는 파일들. */
export const COMMAND_NAMES: readonly string[] = [
  "cc",
  "ccr",
  "cf",
  "cfr",
  "ccf",
  "cr",
  "cca",
  "cp",
  "cpr",
];

export const REWRITTEN_SKILL_PATHS: readonly string[] = COMMAND_NAMES.map(
  (name) => `.claude/skills/${name}/SKILL.md`,
);

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
  const rewritten = new Set(REWRITTEN_SKILL_PATHS);
  return claudeEntries(manifest).filter((entry) => !rewritten.has(entry.path));
}
