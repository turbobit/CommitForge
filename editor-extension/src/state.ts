import * as vscode from "vscode";
import { access } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { loadCatalog, type CommandSpec } from "./core/catalog";
import { coalesceAsync } from "./core/coalesce";
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
  private readonly runRefresh = coalesceAsync(() => this.doRefresh());

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

  /**
   * 실행 중에 들어온 요청은 버리지 않는다(coalesceAsync). python 콜드스타트를
   * 포함한 guard.py 실행이 debounce 창(200ms)보다 길어지는 일이 드물지 않고,
   * 그 사이 도착한 마지막 변화가 다음 트리거 없이는 반영되지 않을 수 있기
   * 때문이다. 실행이 끝나면 그 변화를 반영하도록 한 번 더 돈다.
   */
  async refresh(): Promise<void> {
    await this.runRefresh();
  }

  private async doRefresh(): Promise<void> {
    this.manifest ??= await loadManifest(this.payloadRoot);
    const manifest = this.manifest;

    const isGitRepo = await exists(join(this.folder, ".git"));
    const configured = vscode.workspace
      .getConfiguration("commitforge")
      .get<string>("pythonPath");
    const python = await resolvePython(configured, spawnProbe);

    const project = await detectInstall(join(this.folder, ".claude"), manifest, "project");
    const globalReport = await detectInstall(join(homedir(), ".claude"), manifest, "global");

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
  }

  dispose(): void {
    this.emitter.dispose();
  }
}
