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

/**
 * guard.py의 `recovery_details()`가 만드는 복구 제안. spec §4·§7.3이 요구하는
 * "복구 제안"의 원천이다 (claude_atomic_lock을 쥔 세션이 있을 때만 채워진다).
 * 필드는 guard.py의 실제 출력을 그대로 옮긴 것이며, 알려지지 않은 추가 필드가
 * 와도 잃지 않도록 인덱스 시그니처를 열어 둔다.
 */
export interface LockRecovery {
  cwd: string | null;
  statusArgv: string[];
  abortArgv: string[];
  cleanHint: string | null;
  cleanArgv: string[];
  reclaimHint: string | null;
  snapshot: string | null;
  autoSnapshotLookup: boolean;
  requiresOwnerInactiveConfirmation: boolean;
  [key: string]: unknown;
}

/**
 * guard.py의 `external_lock_details()`가 만드는 Git 자체 lock 파일 상세. 트리 뷰가
 * "git index.lock 존재 (4분)"을 그리려면 `path`·`ageSeconds`·`staleCandidate`가
 * 구조적으로 있어야 한다 (문자열만 담는 `gitLockFiles`로는 나이를 알 수 없다).
 */
export interface GitLockDetail {
  path: string;
  ageSeconds: number;
  staleCandidate: boolean;
  size?: number;
  modifiedAt?: string;
  writerPids?: number[] | null;
  staleAfterSeconds?: number;
  [key: string]: unknown;
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
  recovery: LockRecovery | null;
  operations: string[];
  /** @deprecated 경로 문자열만 담는다. 나이·stale 여부가 필요하면 `gitLocks`를 쓴다. */
  gitLockFiles: string[];
  gitLocks: GitLockDetail[];
}

function mapRecovery(raw: unknown): LockRecovery | null {
  if (raw === null || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  return {
    ...r,
    cwd: (r["cwd"] as string | undefined) ?? null,
    statusArgv: Array.isArray(r["status_argv"]) ? (r["status_argv"] as string[]) : [],
    abortArgv: Array.isArray(r["abort_argv"]) ? (r["abort_argv"] as string[]) : [],
    cleanHint: (r["clean_hint"] as string | undefined) ?? null,
    cleanArgv: Array.isArray(r["clean_argv"]) ? (r["clean_argv"] as string[]) : [],
    reclaimHint: (r["reclaim_hint"] as string | undefined) ?? null,
    snapshot: (r["snapshot"] as string | null | undefined) ?? null,
    autoSnapshotLookup: r["auto_snapshot_lookup"] === true,
    requiresOwnerInactiveConfirmation: r["requires_owner_inactive_confirmation"] === true,
  };
}

function mapGitLock(raw: unknown): GitLockDetail | null {
  if (raw === null || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r["path"] !== "string") return null;
  return {
    ...r,
    path: r["path"],
    ageSeconds: typeof r["age_seconds"] === "number" ? r["age_seconds"] : 0,
    staleCandidate: r["stale_candidate"] === true,
    size: typeof r["size"] === "number" ? r["size"] : undefined,
    modifiedAt: typeof r["modified_at"] === "string" ? r["modified_at"] : undefined,
    writerPids: Array.isArray(r["writer_pids"]) ? (r["writer_pids"] as number[]) : null,
    staleAfterSeconds:
      typeof r["stale_after_seconds"] === "number" ? r["stale_after_seconds"] : undefined,
  };
}

export function parseGuardStatus(stdout: string): GuardStatus {
  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(stdout) as Record<string, unknown>;
  } catch {
    throw new Error(`guard.py status 출력이 JSON이 아닙니다: ${stdout.slice(0, 200)}`);
  }

  const lock = raw["claude_atomic_lock"] as Record<string, unknown> | null | undefined;
  const gitLocksRaw = raw["git_locks"];

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
    recovery: mapRecovery(raw["recovery"] ?? null),
    operations: (raw["operations"] as string[] | undefined) ?? [],
    gitLockFiles: (raw["git_lock_files"] as string[] | undefined) ?? [],
    gitLocks: Array.isArray(gitLocksRaw)
      ? gitLocksRaw
          .map(mapGitLock)
          .filter((entry): entry is GitLockDetail => entry !== null)
      : [],
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
