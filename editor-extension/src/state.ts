import * as vscode from "vscode";
import { access } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { loadCatalog, type CommandSpec } from "./core/catalog";
import { detectInstall, type InstallReport } from "./core/detect";
import { nodeRunner, runGuardStatus, type GuardStatus } from "./core/guard";
import { commandNames, loadManifest, type Manifest } from "./core/payload";
import { resolvePython, spawnProbe, type PythonResolution } from "./core/python";

export interface WorkspaceState {
  folder: string;
  isGitRepo: boolean;
  python: PythonResolution | null;
  project: InstallReport;
  global: InstallReport;
  guard: GuardStatus | null;
  guardError: string | null;
  catalog: CommandSpec[];
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

/** 설치가 있으면 그 skills 디렉터리를, 없으면 번들 페이로드를 카탈로그 원천으로 쓴다. */
function catalogSource(
  project: InstallReport,
  globalReport: InstallReport,
  payloadRoot: string,
): string {
  if (project.state !== "missing") return join(project.claudeDir, "skills");
  if (globalReport.state !== "missing") return join(globalReport.claudeDir, "skills");
  return join(payloadRoot, ".claude", "skills");
}

export class StateStore implements vscode.Disposable {
  private readonly emitter = new vscode.EventEmitter<WorkspaceState | null>();
  private state: WorkspaceState | null = null;
  private manifest: Manifest | null = null;
  private running = false;

  readonly onDidChange = this.emitter.event;

  constructor(
    private readonly payloadRoot: string,
    private readonly folder: string,
  ) {}

  get current(): WorkspaceState | null {
    return this.state;
  }

  get payloadDir(): string {
    return this.payloadRoot;
  }

  async refresh(): Promise<void> {
    if (this.running) return;
    this.running = true;
    try {
      this.manifest ??= await loadManifest(this.payloadRoot);
      const manifest = this.manifest;

      const isGitRepo = await exists(join(this.folder, ".git"));
      const configured = vscode.workspace
        .getConfiguration("commitforge")
        .get<string>("pythonPath");
      const python = await resolvePython(configured, spawnProbe);

      const project = await detectInstall(
        join(this.folder, ".claude"),
        manifest,
        "project",
      );
      const globalReport = await detectInstall(
        join(homedir(), ".claude"),
        manifest,
        "global",
      );

      let guard: GuardStatus | null = null;
      let guardError: string | null = null;
      const guardScript = join(
        project.state === "missing" ? globalReport.claudeDir : project.claudeDir,
        "skills",
        "_git-atomic-core",
        "scripts",
        "guard.py",
      );

      if (isGitRepo && python && (await exists(guardScript))) {
        try {
          guard = await runGuardStatus(python.executable, guardScript, this.folder, nodeRunner);
        } catch (error) {
          guardError = error instanceof Error ? error.message : String(error);
          // spec §8: 실패해도 마지막 성공 상태를 유지한다. 오래된 값이라도
          // 아무것도 없는 것보다 낫고, guardError가 신선하지 않음을 알린다.
          guard = this.state?.guard ?? null;
        }
      }

      this.state = {
        folder: this.folder,
        isGitRepo,
        python,
        project,
        global: globalReport,
        guard,
        guardError,
        catalog: await loadCatalog(
          catalogSource(project, globalReport, this.payloadRoot),
          commandNames(manifest),
        ),
      };
      this.emitter.fire(this.state);
    } finally {
      this.running = false;
    }
  }

  dispose(): void {
    this.emitter.dispose();
  }
}
