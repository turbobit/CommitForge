import { execFile } from "node:child_process";

export interface GuardRunner {
  (
    executable: string,
    args: string[],
    cwd: string,
  ): Promise<{ stdout: string; stderr: string; code: number }>;
}

export interface LockOwner {
  session: string | null;
  created_at: string | null;
}

export interface GuardStatus {
  ok: boolean;
  projectRoot: string;
  gitDir: string;
  lockOwner: LockOwner | null;
  lockAgeSeconds: number | null;
  lockOwnerHostname: string | null;
  lockOwnerSameHost: boolean | null;
  currentHostname: string;
  staleCandidate: boolean;
  snapshots: string[];
  operations: string[];
  gitLockFiles: string[];
}

export function parseGuardStatus(stdout: string): GuardStatus {
  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(stdout) as Record<string, unknown>;
  } catch {
    throw new Error(`guard.py status 출력이 JSON이 아닙니다: ${stdout.slice(0, 200)}`);
  }

  const lock = raw["claude_atomic_lock"] as Record<string, unknown> | null | undefined;

  return {
    ok: raw["ok"] === true,
    projectRoot: String(raw["project_root"] ?? ""),
    gitDir: String(raw["git_dir"] ?? ""),
    lockOwner: lock
      ? {
          session: (lock["session"] as string | undefined) ?? null,
          created_at: (lock["created_at"] as string | undefined) ?? null,
        }
      : null,
    lockAgeSeconds: (raw["lock_age_seconds"] as number | null | undefined) ?? null,
    lockOwnerHostname: (raw["lock_owner_hostname"] as string | null | undefined) ?? null,
    lockOwnerSameHost: (raw["lock_owner_same_host"] as boolean | null | undefined) ?? null,
    currentHostname: String(raw["current_hostname"] ?? ""),
    staleCandidate: raw["stale_candidate"] === true,
    snapshots: (raw["snapshots"] as string[] | undefined) ?? [],
    operations: (raw["operations"] as string[] | undefined) ?? [],
    gitLockFiles: (raw["git_lock_files"] as string[] | undefined) ?? [],
  };
}

export async function runGuardStatus(
  python: string,
  guardScript: string,
  cwd: string,
  run: GuardRunner,
): Promise<GuardStatus> {
  const result = await run(python, [guardScript, "status"], cwd);
  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || `guard.py status 실패 (exit ${result.code})`);
  }
  return parseGuardStatus(result.stdout);
}

export const nodeRunner: GuardRunner = (executable, args, cwd) =>
  new Promise((resolve) => {
    execFile(
      executable,
      args,
      { cwd, timeout: 15000, maxBuffer: 8 * 1024 * 1024 },
      (error, stdout, stderr) => {
        const code =
          error && typeof (error as { code?: unknown }).code === "number"
            ? (error as { code: number }).code
            : error
              ? 1
              : 0;
        resolve({ stdout, stderr, code });
      },
    );
  });
