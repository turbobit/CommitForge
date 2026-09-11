export interface PythonProbe {
  (executable: string): Promise<boolean>;
}

export interface PythonResolution {
  executable: string;
  source: "setting" | "probe";
}

export const DEFAULT_CANDIDATES: readonly string[] = ["python3", "python"];

export async function resolvePython(
  configured: string | undefined,
  probe: PythonProbe,
  candidates: readonly string[] = DEFAULT_CANDIDATES,
): Promise<PythonResolution | null> {
  const setting = configured?.trim();
  if (setting && (await probe(setting))) {
    return { executable: setting, source: "setting" };
  }

  for (const candidate of candidates) {
    if (await probe(candidate)) {
      return { executable: candidate, source: "probe" };
    }
  }
  return null;
}

import { execFile } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(execFile);

/** Python 3.9 이상을 요구한다. CommitForge의 최소 버전이다. */
export const spawnProbe: PythonProbe = async (executable) => {
  try {
    const { stdout } = await run(
      executable,
      ["-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
      { timeout: 5000 },
    );
    const [major, minor] = stdout.trim().split(/\s+/).map(Number);
    return major === 3 && minor !== undefined && minor >= 9;
  } catch {
    return false;
  }
};
