# CommitForge 에디터 확장 1단계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CommitForge의 설치 관리·잠금 상태·명령 실행을 VS Code 확장 UI에서 할 수 있게 만든다.

**Architecture:** 확장은 상태를 소유하지 않는 얇은 어댑터다. 진실의 원천은 번들 페이로드(`payload/MANIFEST.json`), 워크스페이스 `.claude/`, `guard.py status` 세 곳이며 확장은 읽어서 그린다. 설치 쓰기 작업은 전부 번들된 `install.py`/`uninstall.py`에 위임하고, 명령 실행은 통합 터미널 `sendText`로 보낸다. `src/core/`는 VS Code API에 의존하지 않는 순수 로직이라 단위 테스트 대상이고, `src/vscode/`는 얇은 UI 층이다.

**Tech Stack:** TypeScript 5.x, Node 20, esbuild(번들), vitest(단위 테스트), @vscode/test-electron(E2E), @vscode/vsce(패키징), Python 3.9+(기존 CommitForge 스크립트)

**Spec:** `docs/superpowers/specs/2026-09-11-vscode-extension-design.md`

## Global Constraints

- 확장은 `.claude/` 아래에 **쓰지 않는다.** 모든 쓰기는 번들된 `install.py`/`uninstall.py`가 수행한다. 확장의 파일 작업은 읽기와 sha256 계산뿐이다.
- 명령·옵션 목록을 **하드코딩하지 않는다.** `SKILL.md` frontmatter의 `argument-hint`를 파싱해 생성한다.
- 확장은 `guard.py clean`을 **직접 호출하지 않는다.** `/cr clean`을 터미널로 보낸다.
- **폴링 금지.** 상태 갱신은 이벤트 기반으로만 한다.
- Python 최소 버전은 **3.9**다. `install.py`/`uninstall.py` 수정 시 3.9에서 동작해야 한다 (CI portability 매트릭스: ubuntu/3.9, macos/3.11, windows/3.11).
- Python 테스트는 **`unittest`** 로 작성한다. 실행은 `python -m unittest discover -s tests -v`다. pytest를 도입하지 않는다.
- `engines.vscode`는 `^1.94.0`으로 고정한다. 동일 VSIX가 Cursor에서도 동작해야 한다.
- 사용자 대면 문자열은 **한국어**로 쓴다. 기존 CommitForge CLI 출력과 톤을 맞춘다.
- `install.py`를 수정하면 `python release.py`로 `MANIFEST.json`과 `checksums.sha256`을 재생성해야 한다. CI가 `python release.py --check`로 검증한다.
- `release.py`의 `source_paths()`는 `git ls-files --cached --others --exclude-standard`를 사용한다. **gitignore되지 않은 모든 파일이 MANIFEST에 들어간다.** 빌드 산출물과 의존성은 반드시 gitignore해야 한다.

## 파일 구조

| 경로 | 책임 |
|---|---|
| `install.py` (수정) | 설치 마커 기록 추가 |
| `uninstall.py` (수정) | 설치 마커 제거 추가 |
| `tests/test_install_marker.py` (신규) | 마커 기록·제거·dry-run 검증 |
| `.gitignore` (수정) | 확장 빌드 산출물·의존성·설치 마커 제외 |
| `editor-extension/package.json` | 확장 매니페스트: 명령·뷰·상태바·설정 |
| `editor-extension/scripts/sync-payload.mjs` | 저장소 → `payload/` 복사 |
| `editor-extension/src/core/python.ts` | Python 인터프리터 탐색 |
| `editor-extension/src/core/payload.ts` | 번들 MANIFEST 로딩·분류 |
| `editor-extension/src/core/detect.ts` | 설치 상태 판정 |
| `editor-extension/src/core/guard.ts` | `guard.py status` 실행·파싱 |
| `editor-extension/src/core/catalog.ts` | `SKILL.md` → 명령·옵션 카탈로그 |
| `editor-extension/src/core/composer.ts` | 선택 조합 → 명령 문자열 |
| `editor-extension/src/vscode/installer.ts` | `install.py`/`uninstall.py` 실행 + Output |
| `editor-extension/src/vscode/statusBar.ts` | 상태바 항목 |
| `editor-extension/src/vscode/treeView.ts` | 사이드바 트리 |
| `editor-extension/src/vscode/terminal.ts` | 대상 터미널 확보·전송 |
| `editor-extension/src/vscode/quickPick.ts` | 명령 조립 대화 흐름 |
| `editor-extension/src/state.ts` | 워크스페이스 상태 집계·갱신 이벤트 |
| `editor-extension/src/extension.ts` | activate 배선 |

---

### Task 1: `install.py` 설치 마커

설치본의 버전을 알 방법이 지금은 없다. 설치 시 `.claude/.commitforge-install.json`을 기록하고 제거 시 지운다. 확장뿐 아니라 CLI 사용자에게도 "지금 뭐가 깔렸는지"를 알려준다.

**Files:**
- Modify: `install.py`
- Modify: `uninstall.py`
- Modify: `.gitignore`
- Create: `tests/test_install_marker.py`

**Interfaces:**
- Consumes: 없음
- Produces: `.claude/.commitforge-install.json` 파일 형식. 확장의 `detect.ts`(Task 5)가 읽는다.
  ```json
  {
    "schema": "commitforge-install/v1",
    "version": "1.15.0",
    "scope": "project",
    "installed_at": "2026-09-11T08:12:03Z",
    "python": "/usr/local/bin/python3.13",
    "core_path": "/repo/.claude/skills/_git-atomic-core"
  }
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_install_marker.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INSTALL = PACKAGE_ROOT / "install.py"
UNINSTALL = PACKAGE_ROOT / "uninstall.py"
MARKER_NAME = ".commitforge-install.json"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(f"failed: {args}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


class InstallMarkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cf-marker-test-"))
        self.marker = self.tmp / ".claude" / MARKER_NAME

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_writes_marker_with_package_version(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))

        self.assertTrue(self.marker.is_file(), "설치 마커가 기록되지 않았습니다")
        payload = json.loads(self.marker.read_text(encoding="utf-8"))
        version = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(payload["schema"], "commitforge-install/v1")
        self.assertEqual(payload["version"], version)
        self.assertEqual(payload["scope"], "project")
        self.assertEqual(
            payload["core_path"],
            str((self.tmp / ".claude" / "skills" / "_git-atomic-core").resolve()),
        )
        self.assertTrue(payload["installed_at"].endswith("Z"))
        self.assertTrue(Path(payload["python"]).name.startswith("python"))

    def test_dry_run_does_not_write_marker(self) -> None:
        proc = run(INSTALL, "--scope", "project", "--target", str(self.tmp), "--dry-run")

        self.assertFalse(self.marker.exists(), "dry-run이 마커를 기록했습니다")
        self.assertIn(MARKER_NAME, proc.stdout)

    def test_uninstall_removes_marker(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))
        self.assertTrue(self.marker.is_file())

        run(UNINSTALL, "--scope", "project", "--target", str(self.tmp))

        self.assertFalse(self.marker.exists(), "제거 후에도 마커가 남았습니다")

    def test_reinstall_refreshes_marker_timestamp(self) -> None:
        run(INSTALL, "--scope", "project", "--target", str(self.tmp))
        first = json.loads(self.marker.read_text(encoding="utf-8"))
        self.marker.write_text(
            json.dumps({**first, "version": "0.0.1"}, ensure_ascii=False),
            encoding="utf-8",
        )

        run(INSTALL, "--scope", "project", "--target", str(self.tmp))

        second = json.loads(self.marker.read_text(encoding="utf-8"))
        self.assertEqual(second["version"], first["version"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest tests.test_install_marker -v`
Expected: FAIL — `설치 마커가 기록되지 않았습니다`

- [ ] **Step 3: `install.py`에 마커 기록 구현**

`install.py`의 `CORE_REFERENCE = ".claude/skills/_git-atomic-core"` 아래에 상수를 추가한다:

```python
MARKER_NAME = ".commitforge-install.json"
MARKER_SCHEMA = "commitforge-install/v1"
```

`configure_lifecycle_hooks` 함수 정의 바로 뒤에 함수를 추가한다:

```python
def package_version() -> str:
    return (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def write_install_marker(claude_dir: Path, *, scope: str, dry_run: bool) -> None:
    """Record what this installation placed, for upgrade and tooling checks."""
    marker_path = claude_dir / MARKER_NAME
    if dry_run:
        print(f"[dry-run] write install marker -> {marker_path}")
        return

    payload = {
        "schema": MARKER_SCHEMA,
        "version": package_version(),
        "scope": scope,
        "installed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": str(Path(sys.executable)),
        "core_path": str((claude_dir / "skills" / "_git-atomic-core").resolve()),
    }
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

`main()`에서 `configure_lifecycle_hooks(...)` 호출 직후, `print()` 블록 앞에 호출을 넣는다:

```python
    write_install_marker(claude_dir, scope=args.scope, dry_run=args.dry_run)
```

- [ ] **Step 4: `uninstall.py`에 마커 제거 구현**

`uninstall.py`의 `POWERSHELL_ENCODED_PREFIX` 정의 위에 상수를 추가한다:

```python
MARKER_NAME = ".commitforge-install.json"
```

`main()`에서 skills·agents 제거 루프가 끝난 뒤, `print(f"제거 범위: ...")` 앞에 추가한다:

```python
    backup_and_remove(
        claude_dir / MARKER_NAME,
        backup_root / MARKER_NAME,
        args.dry_run,
    )
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m unittest tests.test_install_marker -v`
Expected: PASS (4 tests)

- [ ] **Step 6: `.gitignore`에 마커 추가**

이 저장소 자체에 CommitForge를 설치하면 마커가 untracked 파일로 남고, `release.py`가 이를 MANIFEST에 넣어 `release.py --check`가 깨진다. `.gitignore`의 `# CommitForge runtime files` 블록에 추가한다:

```
# CommitForge runtime files
.claude-atomic.lock
.claude-atomic-snapshots/
.claude/.commitforge-install.json
```

- [ ] **Step 7: 릴리스 메타데이터 재생성**

Run: `python release.py`
Then: `python release.py --check`
Expected: `--check`가 성공한다. `install.py`와 `uninstall.py`의 sha256이 `MANIFEST.json`·`checksums.sha256`에서 갱신된다.

- [ ] **Step 8: 전체 테스트와 패키지 검증**

Run:
```bash
python verify.py
python -m unittest discover -s tests -v
```
Expected: 둘 다 성공.

- [ ] **Step 9: 커밋**

```bash
git add install.py uninstall.py tests/test_install_marker.py .gitignore MANIFEST.json checksums.sha256
git commit -m "feat(install): 설치 마커 기록으로 설치본 버전 식별 가능하게 함"
```

---

### Task 2: 확장 스캐폴드와 페이로드 동기화

확장 프로젝트를 만들고, 저장소의 CommitForge 페이로드를 `payload/`로 복사하는 빌드 단계를 세운다. 이 태스크가 끝나면 `npm test`와 `npm run build`가 돈다.

**Files:**
- Modify: `.gitignore`
- Create: `editor-extension/package.json`
- Create: `editor-extension/tsconfig.json`
- Create: `editor-extension/vitest.config.ts`
- Create: `editor-extension/esbuild.mjs`
- Create: `editor-extension/.vscodeignore`
- Create: `editor-extension/scripts/sync-payload.mjs`
- Create: `editor-extension/src/extension.ts`
- Test: `editor-extension/test/sync-payload.test.ts`

**Interfaces:**
- Consumes: Task 1의 `install.py`(페이로드에 포함됨)
- Produces: `payload/` 레이아웃. 이후 모든 태스크가 의존한다.
  - `payload/.claude/**`, `payload/install.py`, `payload/uninstall.py`, `payload/MANIFEST.json`, `payload/VERSION`
  - `syncPayload(repoRoot: string, payloadDir: string): Promise<string[]>` — 복사한 상대 경로 목록 반환

- [ ] **Step 1: `.gitignore`에 확장 산출물 추가**

파일 끝에 추가한다:

```
# Editor extension
node_modules/
editor-extension/payload/
editor-extension/dist/
editor-extension/*.vsix
editor-extension/.vscode-test/
```

`node_modules/`가 현재 `.gitignore`에 없다. 이게 없으면 `release.py`가 수만 개 파일을 MANIFEST에 넣는다. 반드시 먼저 넣는다.

- [ ] **Step 2: `package.json` 작성**

`editor-extension/package.json`:

```json
{
  "name": "commitforge",
  "displayName": "CommitForge",
  "description": "Claude Code용 Atomic Git Assistant를 설치·관리하고 명령을 실행합니다",
  "version": "0.0.0",
  "publisher": "commitforge",
  "license": "MIT",
  "engines": { "vscode": "^1.94.0" },
  "categories": ["SCM Providers", "Other"],
  "main": "./dist/extension.js",
  "activationEvents": ["onStartupFinished"],
  "contributes": {},
  "scripts": {
    "sync-payload": "node scripts/sync-payload.mjs",
    "build": "npm run sync-payload && node esbuild.mjs",
    "watch": "node esbuild.mjs --watch",
    "test": "vitest run",
    "typecheck": "tsc --noEmit",
    "package": "npm run build && vsce package --out commitforge.vsix"
  },
  "devDependencies": {
    "@types/node": "^20.14.0",
    "@types/vscode": "^1.94.0",
    "@vscode/vsce": "^3.2.0",
    "esbuild": "^0.24.0",
    "typescript": "^5.6.0",
    "vitest": "^2.1.0"
  }
}
```

`version`은 Task 13에서 루트 `VERSION`을 따라가도록 자동화한다. 지금은 `0.0.0`으로 둔다.

- [ ] **Step 3: `tsconfig.json`·`vitest.config.ts`·`esbuild.mjs`·`.vscodeignore` 작성**

`editor-extension/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "lib": ["ES2022"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "."
  },
  "include": ["src/**/*.ts", "test/**/*.ts"]
}
```

`editor-extension/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});
```

`editor-extension/esbuild.mjs`:

```js
import esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: ["src/extension.ts"],
  bundle: true,
  outfile: "dist/extension.js",
  platform: "node",
  target: "node20",
  format: "cjs",
  external: ["vscode"],
  sourcemap: true,
  minify: !watch,
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("watching...");
} else {
  await esbuild.build(options);
}
```

`editor-extension/.vscodeignore` — `payload/`는 VSIX에 반드시 포함되어야 하므로 제외하지 않는다:

```
src/**
test/**
scripts/**
node_modules/**
.vscode-test/**
tsconfig.json
vitest.config.ts
esbuild.mjs
**/*.map
```

- [ ] **Step 4: 실패하는 테스트 작성**

`editor-extension/test/sync-payload.test.ts`:

```ts
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { syncPayload } from "../scripts/sync-payload.mjs";

async function makeRepo(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "cf-payload-"));
  await mkdir(join(root, ".claude", "skills", "cr"), { recursive: true });
  await mkdir(join(root, ".claude", "agents"), { recursive: true });
  await writeFile(join(root, ".claude", "skills", "cr", "SKILL.md"), "---\nname: cr\n---\n");
  await writeFile(join(root, ".claude", "agents", "cca-git-reviewer.md"), "agent\n");
  await writeFile(join(root, "install.py"), "# install\n");
  await writeFile(join(root, "uninstall.py"), "# uninstall\n");
  await writeFile(join(root, "MANIFEST.json"), '{"version":"1.15.0","files":[]}\n');
  await writeFile(join(root, "VERSION"), "1.15.0\n");
  return root;
}

describe("syncPayload", () => {
  let root: string;
  let payload: string;

  beforeEach(async () => {
    root = await makeRepo();
    payload = join(root, "editor-extension", "payload");
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("복사한 상대 경로를 모두 반환한다", async () => {
    const copied = await syncPayload(root, payload);

    expect(copied).toContain("install.py");
    expect(copied).toContain("uninstall.py");
    expect(copied).toContain("MANIFEST.json");
    expect(copied).toContain("VERSION");
    expect(copied).toContain(join(".claude", "skills", "cr", "SKILL.md"));
    expect(copied).toContain(join(".claude", "agents", "cca-git-reviewer.md"));
  });

  it("내용을 그대로 복사한다", async () => {
    await syncPayload(root, payload);

    const text = await readFile(join(payload, ".claude", "skills", "cr", "SKILL.md"), "utf8");
    expect(text).toBe("---\nname: cr\n---\n");
  });

  it("이전 payload 내용을 지우고 다시 만든다", async () => {
    await mkdir(payload, { recursive: true });
    await writeFile(join(payload, "stale.txt"), "old\n");

    await syncPayload(root, payload);

    await expect(access(join(payload, "stale.txt"))).rejects.toThrow();
  });

  it("원본 파일이 없으면 실패한다", async () => {
    await rm(join(root, "install.py"));

    await expect(syncPayload(root, payload)).rejects.toThrow(/install\.py/);
  });
});
```

- [ ] **Step 5: 실패 확인**

Run: `cd editor-extension && npm install && npm test`
Expected: FAIL — `Cannot find module '../scripts/sync-payload.mjs'`

- [ ] **Step 6: `sync-payload.mjs` 구현**

`editor-extension/scripts/sync-payload.mjs`:

```js
import { cp, mkdir, rm, access, readdir } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const FILES = ["install.py", "uninstall.py", "MANIFEST.json", "VERSION"];
const DIRS = [join(".claude", "skills"), join(".claude", "agents")];

async function listFiles(root, dir) {
  const out = [];
  for (const entry of await readdir(join(root, dir), { withFileTypes: true })) {
    const rel = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listFiles(root, rel)));
    else out.push(rel);
  }
  return out;
}

export async function syncPayload(repoRoot, payloadDir) {
  for (const file of [...FILES, ...DIRS]) {
    try {
      await access(join(repoRoot, file));
    } catch {
      throw new Error(`페이로드 원본이 없습니다: ${file}`);
    }
  }

  await rm(payloadDir, { recursive: true, force: true });
  await mkdir(payloadDir, { recursive: true });

  const copied = [];
  for (const file of FILES) {
    await cp(join(repoRoot, file), join(payloadDir, file));
    copied.push(file);
  }
  for (const dir of DIRS) {
    await cp(join(repoRoot, dir), join(payloadDir, dir), { recursive: true });
    copied.push(...(await listFiles(payloadDir, dir)));
  }
  return copied;
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);
if (isMain) {
  const here = dirname(fileURLToPath(import.meta.url));
  const extensionRoot = join(here, "..");
  const repoRoot = join(extensionRoot, "..");
  const copied = await syncPayload(repoRoot, join(extensionRoot, "payload"));
  console.log(`payload 동기화 완료: ${copied.length}개 파일`);
  console.log(`  원본: ${relative(process.cwd(), repoRoot) || "."}`);
}
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd editor-extension && npm test`
Expected: PASS (4 tests)

- [ ] **Step 8: 최소 진입점과 실제 동기화 확인**

`editor-extension/src/extension.ts`:

```ts
import * as vscode from "vscode";

export function activate(_context: vscode.ExtensionContext): void {
  console.log("CommitForge 확장이 활성화되었습니다");
}

export function deactivate(): void {}
```

Run:
```bash
cd editor-extension
npm run sync-payload
npm run typecheck
npm run build
```
Expected: `payload 동기화 완료: 61개 파일` 이상이 출력되고, `dist/extension.js`가 생성된다.

- [ ] **Step 9: 커밋**

```bash
git add .gitignore editor-extension
git commit -m "feat(extension): VS Code 확장 스캐폴드와 페이로드 동기화 추가"
```

주의: `package-lock.json`은 커밋하고 `node_modules/`와 `payload/`는 커밋하지 않는다. `git status`로 확인한다.

---

### Task 3: Python 인터프리터 탐색 (`core/python.ts`)

`spawn`은 대화형 셸을 거치지 않으므로 alias·함수·rc 설정이 적용되지 않는다. 인터프리터 경로를 명시적으로 해결해야 한다.

**Files:**
- Create: `editor-extension/src/core/python.ts`
- Test: `editor-extension/test/python.test.ts`

**Interfaces:**
- Consumes: 없음
- Produces:
  ```ts
  export interface PythonProbe { (executable: string): Promise<boolean>; }
  export interface PythonResolution { executable: string; source: "setting" | "probe"; }
  export async function resolvePython(
    configured: string | undefined,
    probe: PythonProbe,
    candidates?: string[],
  ): Promise<PythonResolution | null>;
  export const DEFAULT_CANDIDATES: readonly string[];
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/python.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { resolvePython, DEFAULT_CANDIDATES } from "../src/core/python";

const accept = (ok: string[]) => async (exe: string) => ok.includes(exe);

describe("resolvePython", () => {
  it("설정값이 동작하면 그것을 쓴다", async () => {
    const result = await resolvePython("/opt/py/bin/python3", accept(["/opt/py/bin/python3"]));

    expect(result).toEqual({ executable: "/opt/py/bin/python3", source: "setting" });
  });

  it("설정값이 동작하지 않으면 탐색으로 넘어간다", async () => {
    const result = await resolvePython("/nope/python", accept(["python3"]));

    expect(result).toEqual({ executable: "python3", source: "probe" });
  });

  it("설정이 없으면 후보를 순서대로 시도한다", async () => {
    const result = await resolvePython(undefined, accept(["python"]));

    expect(result).toEqual({ executable: "python", source: "probe" });
  });

  it("먼저 성공한 후보에서 멈춘다", async () => {
    const tried: string[] = [];
    const probe = async (exe: string) => {
      tried.push(exe);
      return exe === DEFAULT_CANDIDATES[0];
    };

    await resolvePython(undefined, probe);

    expect(tried).toEqual([DEFAULT_CANDIDATES[0]]);
  });

  it("전부 실패하면 null을 반환한다", async () => {
    const result = await resolvePython(undefined, accept([]));

    expect(result).toBeNull();
  });

  it("빈 문자열 설정은 무시한다", async () => {
    const result = await resolvePython("   ", accept(["python3"]));

    expect(result).toEqual({ executable: "python3", source: "probe" });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/python.test.ts`
Expected: FAIL — `Cannot find module '../src/core/python'`

- [ ] **Step 3: 구현**

`editor-extension/src/core/python.ts`:

```ts
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
```

- [ ] **Step 4: 실제 probe 구현 추가**

같은 파일 끝에 붙인다. `python.ts`가 Node 표준 모듈만 쓰므로 여전히 VS Code 비의존이다.

```ts
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
    return major === 3 && minor >= 9;
  } catch {
    return false;
  }
};
```

- [ ] **Step 5: probe 테스트 추가**

`editor-extension/test/python.test.ts` 끝에 추가한다:

```ts
import { spawnProbe } from "../src/core/python";

describe("spawnProbe", () => {
  it("존재하지 않는 실행 파일은 false다", async () => {
    expect(await spawnProbe("/definitely/not/a/python")).toBe(false);
  });

  it("현재 환경의 python3를 찾으면 true다", async () => {
    const found = (await spawnProbe("python3")) || (await spawnProbe("python"));
    expect(found).toBe(true);
  });
});
```

- [ ] **Step 6: 통과 확인**

Run: `cd editor-extension && npx vitest run test/python.test.ts`
Expected: PASS (8 tests)

- [ ] **Step 7: 커밋**

```bash
git add editor-extension/src/core/python.ts editor-extension/test/python.test.ts
git commit -m "feat(extension): Python 인터프리터 탐색 추가"
```

---

### Task 4: 번들 페이로드 로딩 (`core/payload.ts`)

`MANIFEST.json`에는 저장소 전체 파일이 들어 있다. 설치 판정에 필요한 건 `.claude/` 항목뿐이고, 그중 9개 `SKILL.md`는 설치 시 재작성되므로 해시 대조 대상에서 빼야 한다.

**Files:**
- Create: `editor-extension/src/core/payload.ts`
- Test: `editor-extension/test/payload.test.ts`

**Interfaces:**
- Consumes: Task 2의 `payload/MANIFEST.json`
- Produces:
  ```ts
  export interface ManifestEntry { path: string; size: number; sha256: string }
  export interface Manifest { name: string; version: string; file_count: number; files: ManifestEntry[] }
  export const REWRITTEN_SKILL_PATHS: readonly string[];   // 9개
  export function parseManifest(text: string): Manifest;
  export async function loadManifest(payloadRoot: string): Promise<Manifest>;
  export function claudeEntries(manifest: Manifest): ManifestEntry[];   // 61개
  export function exactEntries(manifest: Manifest): ManifestEntry[];    // 52개
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/payload.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  parseManifest,
  claudeEntries,
  exactEntries,
  REWRITTEN_SKILL_PATHS,
} from "../src/core/payload";

const manifestText = JSON.stringify({
  name: "CommitForge",
  version: "1.15.0",
  file_count: 5,
  files: [
    { path: "README.md", size: 10, sha256: "a".repeat(64) },
    { path: ".claude/agents/cca-git-reviewer.md", size: 20, sha256: "b".repeat(64) },
    { path: ".claude/skills/cr/SKILL.md", size: 30, sha256: "c".repeat(64) },
    { path: ".claude/skills/_git-atomic-core/guard.md", size: 40, sha256: "d".repeat(64) },
    { path: "install.py", size: 50, sha256: "e".repeat(64) },
  ],
});

describe("parseManifest", () => {
  it("버전과 파일 목록을 읽는다", () => {
    const manifest = parseManifest(manifestText);

    expect(manifest.version).toBe("1.15.0");
    expect(manifest.files).toHaveLength(5);
  });

  it("schema가 아니면 실패한다", () => {
    expect(() => parseManifest("{}")).toThrow(/MANIFEST/);
  });

  it("JSON이 아니면 실패한다", () => {
    expect(() => parseManifest("nope")).toThrow();
  });
});

describe("claudeEntries", () => {
  it(".claude/ 항목만 남긴다", () => {
    const paths = claudeEntries(parseManifest(manifestText)).map((e) => e.path);

    expect(paths).toEqual([
      ".claude/agents/cca-git-reviewer.md",
      ".claude/skills/cr/SKILL.md",
      ".claude/skills/_git-atomic-core/guard.md",
    ]);
  });
});

describe("exactEntries", () => {
  it("설치 시 재작성되는 SKILL.md를 제외한다", () => {
    const paths = exactEntries(parseManifest(manifestText)).map((e) => e.path);

    expect(paths).not.toContain(".claude/skills/cr/SKILL.md");
    expect(paths).toContain(".claude/agents/cca-git-reviewer.md");
    expect(paths).toContain(".claude/skills/_git-atomic-core/guard.md");
  });
});

describe("REWRITTEN_SKILL_PATHS", () => {
  it("명령 9개를 모두 담는다", () => {
    expect(REWRITTEN_SKILL_PATHS).toHaveLength(9);
    expect(REWRITTEN_SKILL_PATHS).toContain(".claude/skills/cca/SKILL.md");
    expect(REWRITTEN_SKILL_PATHS).not.toContain(".claude/skills/_git-atomic-core/SKILL.md");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/payload.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/src/core/payload.ts`:

```ts
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd editor-extension && npx vitest run test/payload.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: 실제 MANIFEST로 개수 검증 테스트 추가**

spec §3.4의 61/52 분류가 실제와 맞는지 고정한다. `editor-extension/test/payload.test.ts` 끝에 추가한다:

```ts
import { loadManifest } from "../src/core/payload";
import { join } from "node:path";
import { existsSync } from "node:fs";

const payloadRoot = join(__dirname, "..", "payload");

describe.skipIf(!existsSync(join(payloadRoot, "MANIFEST.json")))("실제 payload", () => {
  it(".claude/ 항목이 61개고 그중 52개가 해시 대조 대상이다", async () => {
    const manifest = await loadManifest(payloadRoot);

    expect(claudeEntries(manifest)).toHaveLength(61);
    expect(exactEntries(manifest)).toHaveLength(52);
  });
});
```

`payload/`가 없으면 건너뛴다. CI에서는 `npm run sync-payload`를 먼저 돌려 실행되게 한다.

- [ ] **Step 6: 동기화 후 통과 확인**

Run: `cd editor-extension && npm run sync-payload && npx vitest run test/payload.test.ts`
Expected: PASS (7 tests). 개수가 다르면 spec §3.4와 실제가 어긋난 것이므로 숫자를 실제에 맞추고 spec을 갱신한다.

- [ ] **Step 7: 커밋**

```bash
git add editor-extension/src/core/payload.ts editor-extension/test/payload.test.ts
git commit -m "feat(extension): 번들 MANIFEST 로딩과 설치 파일 분류 추가"
```

---

### Task 5: 설치 상태 판정 (`core/detect.ts`)

spec §5의 판정 절차를 구현한다. 해시가 판정 근거이고 마커는 표시용이다.

**Files:**
- Create: `editor-extension/src/core/detect.ts`
- Test: `editor-extension/test/detect.test.ts`

**Interfaces:**
- Consumes: Task 4의 `Manifest`, `exactEntries`, `REWRITTEN_SKILL_PATHS`, `COMMAND_NAMES`. Task 1의 마커 형식.
- Produces:
  ```ts
  export type InstallState = "missing" | "ok" | "version-mismatch" | "misconfigured" | "corrupt";
  export type Scope = "project" | "global";
  export interface InstallMarker {
    schema: string; version: string; scope: Scope;
    installed_at: string; python: string; core_path: string;
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
  export async function detectInstall(
    claudeDir: string, manifest: Manifest, scope: Scope,
  ): Promise<InstallReport>;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/detect.test.ts`:

```ts
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { detectInstall } from "../src/core/detect";
import { parseManifest, type Manifest } from "../src/core/payload";

const sha = (text: string) => createHash("sha256").update(text).digest("hex");

const AGENT_BODY = "agent body\n";
const CORE_BODY = "core body\n";

function buildManifest(coreTemplatePath: string): Manifest {
  return parseManifest(
    JSON.stringify({
      name: "CommitForge",
      version: "1.15.0",
      file_count: 3,
      files: [
        {
          path: ".claude/agents/cca-git-reviewer.md",
          size: AGENT_BODY.length,
          sha256: sha(AGENT_BODY),
        },
        {
          path: ".claude/skills/_git-atomic-core/guard.md",
          size: CORE_BODY.length,
          sha256: sha(CORE_BODY),
        },
        {
          path: ".claude/skills/cr/SKILL.md",
          size: coreTemplatePath.length,
          sha256: sha(coreTemplatePath),
        },
      ],
    }),
  );
}

/** 정상 설치 상태를 임시 디렉터리에 만든다. */
async function makeInstall(
  root: string,
  opts: { marker?: boolean; corePath?: string; hooks?: boolean } = {},
): Promise<string> {
  const claudeDir = join(root, ".claude");
  const corePath = opts.corePath ?? join(claudeDir, "skills", "_git-atomic-core");

  await mkdir(join(claudeDir, "agents"), { recursive: true });
  await mkdir(join(claudeDir, "skills", "_git-atomic-core"), { recursive: true });
  await mkdir(join(claudeDir, "skills", "cr"), { recursive: true });

  await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), AGENT_BODY);
  await writeFile(join(claudeDir, "skills", "_git-atomic-core", "guard.md"), CORE_BODY);
  await writeFile(
    join(claudeDir, "skills", "cr", "SKILL.md"),
    `---\nname: cr\nallowed-tools:\n  - Read\n---\n\n${corePath}/deep-review-protocol.md 를 읽는다\n`,
  );

  if (opts.marker !== false) {
    await writeFile(
      join(claudeDir, ".commitforge-install.json"),
      JSON.stringify({
        schema: "commitforge-install/v1",
        version: "1.15.0",
        scope: "project",
        installed_at: "2026-09-11T08:12:03Z",
        python: "/usr/bin/python3",
        core_path: corePath,
      }),
    );
  }

  if (opts.hooks !== false) {
    await writeFile(
      join(claudeDir, "settings.local.json"),
      JSON.stringify({
        hooks: {
          SessionEnd: [
            {
              hooks: [
                {
                  type: "command",
                  command: `/usr/bin/python3 ${corePath}/scripts/session_lifecycle.py`,
                },
              ],
            },
          ],
        },
      }),
    );
  }
  return claudeDir;
}

describe("detectInstall", () => {
  let root: string;

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), "cf-detect-"));
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("설치가 없으면 missing이다", async () => {
    const report = await detectInstall(join(root, ".claude"), buildManifest("/x"), "project");

    expect(report.state).toBe("missing");
    expect(report.installedVersion).toBeNull();
  });

  it("정상 설치는 ok다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.installedVersion).toBe("1.15.0");
    expect(report.corePathOk).toBe(true);
    expect(report.hooksRegistered).toBe(true);
  });

  it("해시가 전부 다르면 version-mismatch다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "agents", "cca-git-reviewer.md"), "changed\n");
    await writeFile(join(claudeDir, "skills", "_git-atomic-core", "guard.md"), "changed\n");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("version-mismatch");
    expect(report.mismatchedFiles).toHaveLength(2);
  });

  it("core 경로가 남을 가리키면 misconfigured다", async () => {
    const claudeDir = await makeInstall(root, { corePath: "/other/machine/_git-atomic-core" });

    const report = await detectInstall(
      claudeDir,
      buildManifest("/other/machine/_git-atomic-core"),
      "project",
    );

    expect(report.state).toBe("misconfigured");
    expect(report.corePathOk).toBe(false);
  });

  it("hook이 없으면 misconfigured다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("misconfigured");
    expect(report.hooksRegistered).toBe(false);
  });

  it("파일이 누락되면 corrupt다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await rm(join(claudeDir, "agents", "cca-git-reviewer.md"));

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("corrupt");
    expect(report.missingFiles).toContain(".claude/agents/cca-git-reviewer.md");
  });

  it("마커가 없어도 해시가 맞으면 ok이고 번들 버전을 쓴다", async () => {
    const claudeDir = await makeInstall(root, { marker: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.installedVersion).toBe("1.15.0");
  });

  it("마커 버전이 번들과 달라도 해시가 맞으면 ok이되 경고를 남긴다", async () => {
    const claudeDir = await makeInstall(root);
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(
      join(claudeDir, ".commitforge-install.json"),
      JSON.stringify({
        schema: "commitforge-install/v1",
        version: "9.9.9",
        scope: "project",
        installed_at: "2026-01-01T00:00:00Z",
        python: "/usr/bin/python3",
        core_path: corePath,
      }),
    );

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.state).toBe("ok");
    expect(report.warnings.join(" ")).toMatch(/9\.9\.9/);
  });

  it("global 범위는 settings.json에서 hook을 찾는다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(
      join(claudeDir, "settings.json"),
      JSON.stringify({
        hooks: {
          SessionEnd: [
            {
              hooks: [
                { type: "command", command: `python3 ${corePath}/scripts/session_lifecycle.py` },
              ],
            },
          ],
        },
      }),
    );

    const report = await detectInstall(claudeDir, buildManifest(corePath), "global");

    expect(report.hooksRegistered).toBe(true);
    expect(report.state).toBe("ok");
  });

  it("손상된 settings JSON은 hook 미등록으로 보고 경고한다", async () => {
    const claudeDir = await makeInstall(root, { hooks: false });
    const corePath = join(claudeDir, "skills", "_git-atomic-core");
    await writeFile(join(claudeDir, "settings.local.json"), "{ broken");

    const report = await detectInstall(claudeDir, buildManifest(corePath), "project");

    expect(report.hooksRegistered).toBe(false);
    expect(report.warnings.join(" ")).toMatch(/settings\.local\.json/);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/detect.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/src/core/detect.ts`:

```ts
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  COMMAND_NAMES,
  exactEntries,
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

/**
 * 설치된 SKILL.md는 install.py가 core 경로를 치환하므로 해시가 달라진다.
 * 대신 치환된 경로가 이 설치를 가리키는지를 본다. 다른 머신에서 클론한
 * .claude/ 를 그대로 쓰는 경우를 잡기 위해서다.
 */
async function checkCorePaths(
  claudeDir: string,
  missing: string[],
): Promise<boolean> {
  const expected = resolve(join(claudeDir, "skills", "_git-atomic-core"));
  let allOk = true;

  for (const name of COMMAND_NAMES) {
    const relative = `.claude/skills/${name}/SKILL.md`;
    const text = await readIfPresent(join(claudeDir, "skills", name, "SKILL.md"));
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

  const anchor = await readIfPresent(join(claudeDir, "skills", "cr", "SKILL.md"));
  if (anchor === null) {
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
    const text = await readIfPresent(absolute);
    if (text === null) {
      missingFiles.push(entry.path);
      continue;
    }
    const digest = createHash("sha256").update(text, "utf8").digest("hex");
    if (digest !== entry.sha256) mismatchedFiles.push(entry.path);
  }

  const corePathOk = await checkCorePaths(claudeDir, missingFiles);
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
```

`installedVersion`의 규칙은 spec §5.1을 따른다. `version-mismatch`에서 마커가 없으면 `null`(알 수 없음)이고, `ok`에서 마커가 없으면 번들 버전이다.

- [ ] **Step 4: 통과 확인**

Run: `cd editor-extension && npx vitest run test/detect.test.ts`
Expected: PASS (10 tests)

- [ ] **Step 5: 커밋**

```bash
git add editor-extension/src/core/detect.ts editor-extension/test/detect.test.ts
git commit -m "feat(extension): 설치 상태 판정 추가"
```

---

### Task 6: guard 상태 읽기 (`core/guard.ts`)

`guard.py status`는 이미 필요한 정보를 JSON으로 준다. 확장은 실행하고 파싱만 한다.

**Files:**
- Create: `editor-extension/src/core/guard.ts`
- Test: `editor-extension/test/guard.test.ts`

**Interfaces:**
- Consumes: Task 3의 `PythonResolution`
- Produces:
  ```ts
  export interface GuardRunner {
    (executable: string, args: string[], cwd: string): Promise<{ stdout: string; stderr: string; code: number }>;
  }
  export interface LockOwner { session: string | null; created_at: string | null }
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
  export function parseGuardStatus(stdout: string): GuardStatus;
  export async function runGuardStatus(
    python: string, guardScript: string, cwd: string, run: GuardRunner,
  ): Promise<GuardStatus>;
  export const nodeRunner: GuardRunner;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/guard.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseGuardStatus, runGuardStatus, type GuardRunner } from "../src/core/guard";

const idle = JSON.stringify({
  ok: true,
  project_root: "/repo",
  git_dir: "/repo/.git",
  common_dir: "/repo/.git",
  lock_scope: "worktree_git_dir",
  lock_path: "/repo/.git/claude-atomic.lock",
  claude_atomic_lock: null,
  lock_created_at: null,
  lock_age_seconds: null,
  lock_owner_hostname: null,
  lock_owner_same_host: null,
  current_hostname: "mac.local",
  stale_after_seconds: 3600,
  stale_candidate: false,
  lock_owner_snapshots: [],
  recovery: null,
  snapshots: [],
  operations: [],
  git_lock_files: [],
  git_locks: [],
  git_lock_recovery: null,
});

const held = JSON.stringify({
  ok: true,
  project_root: "/repo",
  git_dir: "/repo/.git",
  claude_atomic_lock: { session: "abc123", token: "t", created_at: "2026-09-11T08:00:00Z" },
  lock_age_seconds: 742,
  lock_owner_hostname: "other.local",
  lock_owner_same_host: false,
  current_hostname: "mac.local",
  stale_candidate: false,
  snapshots: ["/repo/.git/claude-atomic-snapshots/abc123"],
  operations: ["rebase-merge"],
  git_lock_files: ["/repo/.git/index.lock"],
});

describe("parseGuardStatus", () => {
  it("유휴 상태를 읽는다", () => {
    const status = parseGuardStatus(idle);

    expect(status.ok).toBe(true);
    expect(status.projectRoot).toBe("/repo");
    expect(status.lockOwner).toBeNull();
    expect(status.snapshots).toEqual([]);
    expect(status.currentHostname).toBe("mac.local");
  });

  it("lock 보유 상태를 읽는다", () => {
    const status = parseGuardStatus(held);

    expect(status.lockOwner).toEqual({ session: "abc123", created_at: "2026-09-11T08:00:00Z" });
    expect(status.lockAgeSeconds).toBe(742);
    expect(status.lockOwnerSameHost).toBe(false);
    expect(status.operations).toEqual(["rebase-merge"]);
    expect(status.gitLockFiles).toEqual(["/repo/.git/index.lock"]);
  });

  it("JSON이 아니면 실패한다", () => {
    expect(() => parseGuardStatus("보통 에러 메시지")).toThrow(/guard/);
  });

  it("누락된 선택 필드는 기본값으로 채운다", () => {
    const status = parseGuardStatus('{"ok":true,"project_root":"/r","git_dir":"/r/.git"}');

    expect(status.snapshots).toEqual([]);
    expect(status.operations).toEqual([]);
    expect(status.staleCandidate).toBe(false);
  });
});

describe("runGuardStatus", () => {
  it("guard.py status를 올바른 인자로 실행한다", async () => {
    const calls: Array<{ exe: string; args: string[]; cwd: string }> = [];
    const run: GuardRunner = async (exe, args, cwd) => {
      calls.push({ exe, args, cwd });
      return { stdout: idle, stderr: "", code: 0 };
    };

    await runGuardStatus("python3", "/repo/.claude/g/guard.py", "/repo", run);

    expect(calls).toEqual([
      { exe: "python3", args: ["/repo/.claude/g/guard.py", "status"], cwd: "/repo" },
    ]);
  });

  it("0이 아닌 종료 코드는 stderr를 담아 실패한다", async () => {
    const run: GuardRunner = async () => ({
      stdout: "",
      stderr: "현재 디렉터리는 Git 작업 트리가 아닙니다.",
      code: 1,
    });

    await expect(runGuardStatus("python3", "/g.py", "/tmp", run)).rejects.toThrow(
      /Git 작업 트리가 아닙니다/,
    );
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/guard.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/src/core/guard.ts`:

```ts
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd editor-extension && npx vitest run test/guard.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: 커밋**

```bash
git add editor-extension/src/core/guard.ts editor-extension/test/guard.test.ts
git commit -m "feat(extension): guard.py status 실행과 파싱 추가"
```

---

### Task 7: 명령 카탈로그 (`core/catalog.ts`)

`SKILL.md` frontmatter의 `argument-hint`를 파싱해 명령과 옵션을 생성한다. 하드코딩하지 않는 것이 핵심이다.

**Files:**
- Create: `editor-extension/src/core/catalog.ts`
- Test: `editor-extension/test/catalog.test.ts`
- Create: `editor-extension/test/fixtures/skill-cca.md`

**Interfaces:**
- Consumes: Task 4의 `COMMAND_NAMES`
- Produces:
  ```ts
  export type OptionKind = "flag" | "value" | "enum" | "range";
  export interface CommandOption {
    name: string;                 // "--base"
    kind: OptionKind;
    values?: string[];            // enum
    placeholder?: string;         // "<ref>"
    range?: [number, number];     // [20, 500]
    exclusiveWith?: string;       // "--no-team"
  }
  export interface CommandSpec {
    name: string;                 // "cca"
    description: string;
    modes: string[];
    acceptsFreeText: boolean;
    options: CommandOption[];
  }
  export function parseArgumentHint(hint: string): Omit<CommandSpec, "name" | "description">;
  export function parseSkillFile(text: string, name: string): CommandSpec;
  export async function loadCatalog(skillsDir: string): Promise<CommandSpec[]>;
  export function findOption(spec: CommandSpec, name: string): CommandOption | undefined;
  ```

- [ ] **Step 1: 픽스처 만들기**

`editor-extension/test/fixtures/skill-cca.md` — 실제 `.claude/skills/cca/SKILL.md`의 frontmatter 앞부분만 복사한다. 명령으로 만든다:

```bash
cd editor-extension
mkdir -p test/fixtures
head -6 ../.claude/skills/cca/SKILL.md > test/fixtures/skill-cca.md
head -6 ../.claude/skills/cc/SKILL.md > test/fixtures/skill-cc.md
```

두 파일 모두 `---`로 시작해 `argument-hint:` 줄을 포함해야 한다. 포함되지 않았으면 `head` 줄 수를 늘린다. 끝에 `---` 줄이 없으면 손으로 추가한다.

- [ ] **Step 2: 실패하는 테스트 작성**

`editor-extension/test/catalog.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseArgumentHint, parseSkillFile, findOption } from "../src/core/catalog";

describe("parseArgumentHint", () => {
  it("모드 목록을 읽는다", () => {
    const parsed = parseArgumentHint("[clean|today|weekly] [추가 맥락] [--strict]");

    expect(parsed.modes).toEqual(["clean", "today", "weekly"]);
  });

  it("모드가 하나뿐이어도 모드로 본다", () => {
    const parsed = parseArgumentHint("[clean] [추가 맥락]");

    expect(parsed.modes).toEqual(["clean"]);
  });

  it("자유 텍스트 허용 여부를 읽는다", () => {
    expect(parseArgumentHint("[clean] [추가 맥락]").acceptsFreeText).toBe(true);
    expect(parseArgumentHint("[clean] [--strict]").acceptsFreeText).toBe(false);
  });

  it("불리언 플래그를 읽는다", () => {
    const parsed = parseArgumentHint("[--strict] [--no-verify]");

    expect(parsed.options).toEqual([
      { name: "--strict", kind: "flag" },
      { name: "--no-verify", kind: "flag" },
    ]);
  });

  it("자리표시자 값 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--base <ref>] [--scope <경로...>]");

    expect(parsed.options).toEqual([
      { name: "--base", kind: "value", placeholder: "<ref>" },
      { name: "--scope", kind: "value", placeholder: "<경로...>" },
    ]);
  });

  it("열거형 값 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--format human|json|sarif]");

    expect(parsed.options).toEqual([
      { name: "--format", kind: "enum", values: ["human", "json", "sarif"] },
    ]);
  });

  it("수치 범위 옵션을 읽는다", () => {
    const parsed = parseArgumentHint("[--commits 20-500] [--iterations 1-5]");

    expect(parsed.options).toEqual([
      { name: "--commits", kind: "range", range: [20, 500] },
      { name: "--iterations", kind: "range", range: [1, 5] },
    ]);
  });

  it("배타 플래그 쌍을 서로 연결한다", () => {
    const parsed = parseArgumentHint("[--team|--no-team]");

    expect(parsed.options).toEqual([
      { name: "--team", kind: "flag", exclusiveWith: "--no-team" },
      { name: "--no-team", kind: "flag", exclusiveWith: "--team" },
    ]);
  });
});

describe("parseSkillFile", () => {
  const ccaText = readFileSync(join(__dirname, "fixtures", "skill-cca.md"), "utf8");
  const ccText = readFileSync(join(__dirname, "fixtures", "skill-cc.md"), "utf8");

  it("실제 /cca frontmatter를 파싱한다", () => {
    const spec = parseSkillFile(ccaText, "cca");

    expect(spec.name).toBe("cca");
    expect(spec.description.length).toBeGreaterThan(10);
    expect(spec.modes).toEqual([
      "clean",
      "today",
      "3days",
      "weekly",
      "release",
      "emergency",
      "learn",
    ]);
    expect(findOption(spec, "--bump")).toEqual({
      name: "--bump",
      kind: "enum",
      values: ["auto", "major", "minor", "patch"],
    });
    expect(findOption(spec, "--commits")).toEqual({
      name: "--commits",
      kind: "range",
      range: [20, 500],
    });
    expect(findOption(spec, "--team")?.exclusiveWith).toBe("--no-team");
  });

  it("실제 /cc frontmatter를 파싱한다", () => {
    const spec = parseSkillFile(ccText, "cc");

    expect(spec.modes).toEqual(["clean"]);
    expect(findOption(spec, "--keep-snapshot")).toEqual({
      name: "--keep-snapshot",
      kind: "flag",
    });
  });

  it("description은 첫 문장만 쓴다", () => {
    const spec = parseSkillFile(ccaText, "cca");

    expect(spec.description).not.toContain("\n");
    expect(spec.description.split(". ").length).toBeLessThanOrEqual(2);
  });

  it("frontmatter가 없으면 실패한다", () => {
    expect(() => parseSkillFile("본문만 있음", "cc")).toThrow(/frontmatter/);
  });

  it("argument-hint가 없으면 옵션 없는 명령으로 본다", () => {
    const spec = parseSkillFile("---\nname: xx\ndescription: 설명이다\n---\n본문\n", "xx");

    expect(spec.options).toEqual([]);
    expect(spec.modes).toEqual([]);
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `cd editor-extension && npx vitest run test/catalog.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 4: 구현**

`editor-extension/src/core/catalog.ts`:

```ts
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { COMMAND_NAMES } from "./payload";

export type OptionKind = "flag" | "value" | "enum" | "range";

export interface CommandOption {
  name: string;
  kind: OptionKind;
  values?: string[];
  placeholder?: string;
  range?: [number, number];
  exclusiveWith?: string;
}

export interface CommandSpec {
  name: string;
  description: string;
  modes: string[];
  acceptsFreeText: boolean;
  options: CommandOption[];
}

const FREE_TEXT_TOKEN = "추가 맥락";
const RANGE_PATTERN = /^(\d+)-(\d+)$/;

/** "[...]" 단위로 쪼갠다. 중첩 대괄호는 argument-hint 문법에 없다. */
function bracketGroups(hint: string): string[] {
  return Array.from(hint.matchAll(/\[([^\]]*)\]/g), (m) => m[1]!.trim());
}

function parseGroup(group: string): CommandOption[] | { mode: string[] } | null {
  if (group === FREE_TEXT_TOKEN) return null;

  if (!group.startsWith("--")) {
    // "[clean|today|weekly]" 또는 "[clean]" — 모드 목록
    return { mode: group.split("|").map((s) => s.trim()).filter(Boolean) };
  }

  const parts = group.split(/\s+/);
  const head = parts[0]!;

  // "[--team|--no-team]" — 배타 플래그 쌍
  if (parts.length === 1 && head.includes("|")) {
    const names = head.split("|").map((s) => s.trim());
    return names.map((name, index) => ({
      name,
      kind: "flag" as const,
      exclusiveWith: names[index === 0 ? 1 : 0],
    }));
  }

  // "[--strict]" — 불리언
  if (parts.length === 1) return [{ name: head, kind: "flag" }];

  const rest = parts.slice(1).join(" ");

  // "[--base <ref>]" — 자유 입력 값
  if (rest.startsWith("<")) return [{ name: head, kind: "value", placeholder: rest }];

  // "[--commits 20-500]" — 수치 범위
  const range = RANGE_PATTERN.exec(rest);
  if (range) {
    return [{ name: head, kind: "range", range: [Number(range[1]), Number(range[2])] }];
  }

  // "[--format human|json|sarif]" — 열거형
  return [
    { name: head, kind: "enum", values: rest.split("|").map((s) => s.trim()).filter(Boolean) },
  ];
}

export function parseArgumentHint(hint: string): Omit<CommandSpec, "name" | "description"> {
  const modes: string[] = [];
  const options: CommandOption[] = [];
  let acceptsFreeText = false;

  for (const group of bracketGroups(hint)) {
    if (group === FREE_TEXT_TOKEN) {
      acceptsFreeText = true;
      continue;
    }
    const parsed = parseGroup(group);
    if (parsed === null) continue;
    if (Array.isArray(parsed)) options.push(...parsed);
    else modes.push(...parsed.mode);
  }
  return { modes, acceptsFreeText, options };
}

function frontmatter(text: string): string {
  if (!text.startsWith("---\n")) throw new Error("SKILL.md frontmatter가 없습니다");
  const end = text.indexOf("\n---", 4);
  if (end < 0) throw new Error("SKILL.md frontmatter 종료가 없습니다");
  return text.slice(4, end);
}

/** YAML 파서를 들이지 않는다. 필요한 두 스칼라 필드만 읽는다. */
function scalarField(fm: string, key: string): string | null {
  const match = new RegExp(`^${key}:\\s*(.*)$`, "m").exec(fm);
  if (!match) return null;
  let value = match[1]!.trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  return value;
}

function firstSentence(text: string): string {
  const trimmed = text.replace(/\s+/g, " ").trim();
  const stop = trimmed.search(/[.。]\s/);
  return stop < 0 ? trimmed : trimmed.slice(0, stop + 1);
}

export function parseSkillFile(text: string, name: string): CommandSpec {
  const fm = frontmatter(text);
  const hint = scalarField(fm, "argument-hint");
  const parsed = hint
    ? parseArgumentHint(hint)
    : { modes: [], acceptsFreeText: false, options: [] };

  return {
    name,
    description: firstSentence(scalarField(fm, "description") ?? ""),
    ...parsed,
  };
}

export async function loadCatalog(skillsDir: string): Promise<CommandSpec[]> {
  const specs: CommandSpec[] = [];
  for (const name of COMMAND_NAMES) {
    try {
      const text = await readFile(join(skillsDir, name, "SKILL.md"), "utf8");
      specs.push(parseSkillFile(text, name));
    } catch {
      // 설치가 불완전하면 해당 명령만 빠진다. 나머지는 계속 제공한다.
    }
  }
  return specs;
}

export function findOption(spec: CommandSpec, name: string): CommandOption | undefined {
  return spec.options.find((option) => option.name === name);
}
```

- [ ] **Step 5: 통과 확인**

Run: `cd editor-extension && npx vitest run test/catalog.test.ts`
Expected: PASS (13 tests)

- [ ] **Step 6: 전체 카탈로그 로딩 테스트 추가**

`editor-extension/test/catalog.test.ts` 끝에 추가한다:

```ts
import { loadCatalog } from "../src/core/catalog";
import { existsSync } from "node:fs";

const skillsDir = join(__dirname, "..", "payload", ".claude", "skills");

describe.skipIf(!existsSync(skillsDir))("loadCatalog", () => {
  it("실제 페이로드에서 명령 9개를 모두 읽는다", async () => {
    const specs = await loadCatalog(skillsDir);

    expect(specs.map((s) => s.name).sort()).toEqual(
      ["cc", "cca", "ccf", "ccr", "cf", "cfr", "cp", "cpr", "cr"],
    );
    for (const spec of specs) {
      expect(spec.description.length).toBeGreaterThan(0);
    }
  });

  it("모든 옵션 이름이 -- 로 시작한다", async () => {
    const specs = await loadCatalog(skillsDir);

    for (const spec of specs) {
      for (const option of spec.options) {
        expect(option.name, `${spec.name} ${option.name}`).toMatch(/^--[a-z-]+$/);
      }
    }
  });
});
```

- [ ] **Step 7: 통과 확인**

Run: `cd editor-extension && npm run sync-payload && npx vitest run test/catalog.test.ts`
Expected: PASS (15 tests). 실패하면 `argument-hint` 문법에 새 형태가 생긴 것이므로 `parseGroup`을 보강한다.

- [ ] **Step 8: 커밋**

```bash
git add editor-extension/src/core/catalog.ts editor-extension/test/catalog.test.ts editor-extension/test/fixtures
git commit -m "feat(extension): SKILL.md argument-hint 기반 명령 카탈로그 추가"
```

---

### Task 8: 명령 문자열 조립 (`core/composer.ts`)

선택 결과를 실제 전송할 문자열로 만든다. 잘못된 조합은 전송 전에 막는다.

**Files:**
- Create: `editor-extension/src/core/composer.ts`
- Test: `editor-extension/test/composer.test.ts`

**Interfaces:**
- Consumes: Task 7의 `CommandSpec`, `CommandOption`, `findOption`
- Produces:
  ```ts
  export interface SelectedOption { name: string; value?: string }
  export interface Selection { mode?: string; freeText?: string; options: SelectedOption[] }
  export function compose(spec: CommandSpec, selection: Selection): string;
  export function sanitizeFreeText(input: string): string;
  export const WRITE_COMMANDS: readonly string[];
  export function isWriteCommand(name: string): boolean;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/composer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { compose, sanitizeFreeText, isWriteCommand } from "../src/core/composer";
import { parseSkillFile } from "../src/core/catalog";

const cca = parseSkillFile(
  [
    "---",
    "name: cca",
    "description: 리뷰부터 commit까지 실행한다. 자세한 내용은 문서를 본다.",
    'argument-hint: "[clean|today|release] [추가 맥락] [--team|--no-team] [--bump auto|major|minor|patch] [--base <ref>] [--commits 20-500] [--strict]"',
    "---",
    "본문",
  ].join("\n"),
  "cca",
);

describe("compose", () => {
  it("옵션이 없으면 명령만 낸다", () => {
    expect(compose(cca, { options: [] })).toBe("/cca");
  });

  it("모드를 첫 토큰으로 둔다", () => {
    expect(compose(cca, { mode: "today", options: [] })).toBe("/cca today");
  });

  it("모드 다음에 자유 텍스트를 둔다", () => {
    expect(compose(cca, { mode: "today", freeText: "결제 모듈만", options: [] })).toBe(
      "/cca today 결제 모듈만",
    );
  });

  it("플래그를 붙인다", () => {
    expect(compose(cca, { options: [{ name: "--strict" }] })).toBe("/cca --strict");
  });

  it("값 옵션을 붙인다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "main" }] })).toBe(
      "/cca --base main",
    );
  });

  it("공백이 있는 값은 따옴표로 감싼다", () => {
    expect(compose(cca, { options: [{ name: "--base", value: "my branch" }] })).toBe(
      '/cca --base "my branch"',
    );
  });

  it("옵션 순서는 spec 정의 순서를 따른다", () => {
    const result = compose(cca, {
      options: [{ name: "--strict" }, { name: "--team" }],
    });

    expect(result).toBe("/cca --team --strict");
  });

  it("정의되지 않은 모드를 거부한다", () => {
    expect(() => compose(cca, { mode: "nope", options: [] })).toThrow(/nope/);
  });

  it("정의되지 않은 옵션을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--wat" }] })).toThrow(/--wat/);
  });

  it("배타 옵션을 함께 고르면 거부한다", () => {
    expect(() =>
      compose(cca, { options: [{ name: "--team" }, { name: "--no-team" }] }),
    ).toThrow(/--team.*--no-team|--no-team.*--team/);
  });

  it("값이 필요한 옵션에 값이 없으면 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--base" }] })).toThrow(/--base/);
  });

  it("플래그에 값을 주면 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--strict", value: "yes" }] })).toThrow(
      /--strict/,
    );
  });

  it("열거형 밖의 값을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--bump", value: "huge" }] })).toThrow(
      /huge/,
    );
  });

  it("범위 밖의 수치를 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--commits", value: "5" }] })).toThrow(
      /20-500/,
    );
    expect(compose(cca, { options: [{ name: "--commits", value: "100" }] })).toBe(
      "/cca --commits 100",
    );
  });

  it("수치가 아닌 범위 값을 거부한다", () => {
    expect(() => compose(cca, { options: [{ name: "--commits", value: "많이" }] })).toThrow(
      /--commits/,
    );
  });
});

describe("sanitizeFreeText", () => {
  it("개행을 공백으로 바꾼다", () => {
    expect(sanitizeFreeText("첫 줄\n둘째 줄\r\n셋째")).toBe("첫 줄 둘째 줄 셋째");
  });

  it("앞뒤 공백을 없애고 연속 공백을 줄인다", () => {
    expect(sanitizeFreeText("  많은   공백  ")).toBe("많은 공백");
  });
});

describe("isWriteCommand", () => {
  it("쓰기 명령을 구분한다", () => {
    expect(isWriteCommand("cca")).toBe(true);
    expect(isWriteCommand("cc")).toBe(true);
    expect(isWriteCommand("cf")).toBe(true);
    expect(isWriteCommand("ccf")).toBe(true);
    expect(isWriteCommand("cp")).toBe(true);
  });

  it("읽기 전용 명령을 구분한다", () => {
    expect(isWriteCommand("cr")).toBe(false);
    expect(isWriteCommand("ccr")).toBe(false);
    expect(isWriteCommand("cfr")).toBe(false);
    expect(isWriteCommand("cpr")).toBe(false);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/composer.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/src/core/composer.ts`:

```ts
import { findOption, type CommandOption, type CommandSpec } from "./catalog";

export interface SelectedOption {
  name: string;
  value?: string;
}

export interface Selection {
  mode?: string;
  freeText?: string;
  options: SelectedOption[];
}

/** working tree나 Git history를 바꾸는 명령. 전송 전 lock 확인이 필요하다. */
export const WRITE_COMMANDS: readonly string[] = ["cc", "cf", "ccf", "cca", "cp"];

export function isWriteCommand(name: string): boolean {
  return WRITE_COMMANDS.includes(name);
}

/** sendText에서 개행은 Enter다. 명령이 절반만 전송되는 것을 막는다. */
export function sanitizeFreeText(input: string): string {
  return input.replace(/[\r\n]+/g, " ").replace(/\s+/g, " ").trim();
}

function quote(value: string): string {
  return /\s/.test(value) ? `"${value}"` : value;
}

function validateValue(option: CommandOption, selected: SelectedOption): void {
  if (option.kind === "flag") {
    if (selected.value !== undefined) {
      throw new Error(`${option.name} 은 값을 받지 않습니다`);
    }
    return;
  }

  const value = selected.value?.trim();
  if (!value) throw new Error(`${option.name} 에 값이 필요합니다`);

  if (option.kind === "enum" && !option.values?.includes(value)) {
    throw new Error(
      `${option.name} 값 "${value}" 은 허용되지 않습니다. 가능한 값: ${option.values?.join(", ")}`,
    );
  }

  if (option.kind === "range") {
    const [min, max] = option.range ?? [0, 0];
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) {
      throw new Error(`${option.name} 은 정수여야 합니다`);
    }
    if (parsed < min || parsed > max) {
      throw new Error(`${option.name} 은 ${min}-${max} 범위여야 합니다`);
    }
  }
}

export function compose(spec: CommandSpec, selection: Selection): string {
  const parts = [`/${spec.name}`];

  if (selection.mode !== undefined) {
    if (!spec.modes.includes(selection.mode)) {
      throw new Error(`/${spec.name} 에 없는 모드입니다: ${selection.mode}`);
    }
    parts.push(selection.mode);
  }

  if (selection.freeText) {
    const text = sanitizeFreeText(selection.freeText);
    if (text) parts.push(text);
  }

  const chosen = new Set(selection.options.map((option) => option.name));
  for (const selected of selection.options) {
    const option = findOption(spec, selected.name);
    if (!option) throw new Error(`/${spec.name} 에 없는 옵션입니다: ${selected.name}`);
    if (option.exclusiveWith && chosen.has(option.exclusiveWith)) {
      throw new Error(`${option.name} 과 ${option.exclusiveWith} 는 함께 쓸 수 없습니다`);
    }
    validateValue(option, selected);
  }

  // spec 정의 순서로 정렬해 같은 선택이 항상 같은 문자열이 되게 한다.
  const order = new Map(spec.options.map((option, index) => [option.name, index]));
  const sorted = [...selection.options].sort(
    (a, b) => (order.get(a.name) ?? 0) - (order.get(b.name) ?? 0),
  );

  for (const selected of sorted) {
    parts.push(selected.name);
    if (selected.value !== undefined) parts.push(quote(selected.value.trim()));
  }

  return parts.join(" ");
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd editor-extension && npx vitest run test/composer.test.ts`
Expected: PASS (19 tests)

- [ ] **Step 5: 커밋**

```bash
git add editor-extension/src/core/composer.ts editor-extension/test/composer.test.ts
git commit -m "feat(extension): 명령 문자열 조립과 검증 추가"
```

---

### Task 9: 워크스페이스 상태 집계와 상태바

core 모듈을 묶어 하나의 상태로 만들고 상태바에 띄운다. 이 태스크가 끝나면 확장을 실제로 실행해 볼 수 있다.

**Files:**
- Create: `editor-extension/src/state.ts`
- Create: `editor-extension/src/vscode/statusBar.ts`
- Modify: `editor-extension/src/extension.ts`
- Modify: `editor-extension/package.json`
- Test: `editor-extension/test/statusText.test.ts`

**Interfaces:**
- Consumes: Task 3~8 전부
- Produces:
  ```ts
  // state.ts
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
  export class StateStore {
    readonly onDidChange: vscode.Event<WorkspaceState | null>;
    get current(): WorkspaceState | null;
    refresh(): Promise<void>;
    dispose(): void;
  }
  // statusBar.ts
  export function statusText(state: WorkspaceState | null): { text: string; tooltip: string };
  export function createStatusBar(store: StateStore): vscode.Disposable;
  ```

- [ ] **Step 1: `vscode` 모듈 stub과 별칭 설정**

`statusBar.ts`는 `import * as vscode`를 하므로 vitest가 `vscode` 모듈을 해석하지 못한다. `vscode`는 에디터가 런타임에 주입하는 모듈이라 npm에 없다. 테스트용 stub을 만들고 별칭으로 물린다.

`editor-extension/test/stubs/vscode.ts`:

```ts
export class EventEmitter<T> {
  private handlers: Array<(value: T) => void> = [];
  readonly event = (handler: (value: T) => void) => {
    this.handlers.push(handler);
    return { dispose: () => {} };
  };
  fire(value: T): void {
    for (const handler of this.handlers) handler(value);
  }
  dispose(): void {
    this.handlers = [];
  }
}

export class ThemeIcon {
  constructor(public id: string) {}
}

export class TreeItem {
  description?: string;
  iconPath?: unknown;
  constructor(
    public label: string,
    public collapsibleState?: number,
  ) {}
}

export const TreeItemCollapsibleState = { None: 0, Collapsed: 1, Expanded: 2 };
export const StatusBarAlignment = { Left: 1, Right: 2 };
export const QuickPickItemKind = { Separator: -1, Default: 0 };

export const Disposable = {
  from: (...items: Array<{ dispose: () => void }>) => ({
    dispose: () => items.forEach((item) => item.dispose()),
  }),
};

export const workspace = {
  createFileSystemWatcher: () => ({
    onDidChange: () => ({ dispose: () => {} }),
    onDidCreate: () => ({ dispose: () => {} }),
    onDidDelete: () => ({ dispose: () => {} }),
    dispose: () => {},
  }),
  getConfiguration: () => ({ get: <T>(_key: string, fallback?: T) => fallback }),
  workspaceFolders: undefined as unknown,
};

export const window = {
  onDidChangeWindowState: () => ({ dispose: () => {} }),
  createStatusBarItem: () => ({
    text: "",
    tooltip: "",
    command: "",
    show: () => {},
    hide: () => {},
    dispose: () => {},
  }),
  createTreeView: () => ({ dispose: () => {} }),
  terminals: [] as unknown[],
};

export class RelativePattern {
  constructor(
    public base: unknown,
    public pattern: string,
  ) {}
}
```

`editor-extension/vitest.config.ts`를 수정한다:

```ts
import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
  resolve: {
    alias: { vscode: resolve(__dirname, "test/stubs/vscode.ts") },
  },
});
```

- [ ] **Step 2: 상태바 문구 테스트 작성**

`statusText`는 순수 함수라 VS Code 없이 테스트한다.

`editor-extension/test/statusText.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { statusText } from "../src/vscode/statusBar";
import type { WorkspaceState } from "../src/state";
import type { InstallReport } from "../src/core/detect";
import type { GuardStatus } from "../src/core/guard";

const okReport: InstallReport = {
  state: "ok",
  scope: "project",
  claudeDir: "/repo/.claude",
  bundleVersion: "1.15.0",
  installedVersion: "1.15.0",
  missingFiles: [],
  mismatchedFiles: [],
  corePathOk: true,
  hooksRegistered: true,
  warnings: [],
};

const missingReport: InstallReport = { ...okReport, state: "missing", installedVersion: null };

const idleGuard: GuardStatus = {
  ok: true,
  projectRoot: "/repo",
  gitDir: "/repo/.git",
  lockOwner: null,
  lockAgeSeconds: null,
  lockOwnerHostname: null,
  lockOwnerSameHost: null,
  currentHostname: "mac.local",
  staleCandidate: false,
  snapshots: [],
  operations: [],
  gitLockFiles: [],
};

function state(overrides: Partial<WorkspaceState> = {}): WorkspaceState {
  return {
    folder: "/repo",
    isGitRepo: true,
    python: { executable: "python3", source: "probe" },
    project: okReport,
    global: { ...missingReport, scope: "global" },
    guard: idleGuard,
    guardError: null,
    catalog: [],
    ...overrides,
  };
}

describe("statusText", () => {
  it("상태를 모르면 로딩으로 표시한다", () => {
    expect(statusText(null).text).toContain("$(sync~spin)");
  });

  it("정상이고 lock이 없으면 버전을 보여준다", () => {
    const { text } = statusText(state());

    expect(text).toBe("$(check) CommitForge v1.15.0");
  });

  it("미설치면 알린다", () => {
    const { text } = statusText(state({ project: missingReport, global: { ...missingReport, scope: "global" } }));

    expect(text).toBe("$(alert) CommitForge 미설치");
  });

  it("project가 미설치여도 global이 정상이면 정상으로 본다", () => {
    const { text } = statusText(
      state({ project: missingReport, global: { ...okReport, scope: "global" } }),
    );

    expect(text).toBe("$(check) CommitForge v1.15.0");
  });

  it("같은 호스트 lock은 보유 시간을 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "abc", created_at: null }, lockAgeSeconds: 742, lockOwnerSameHost: true },
      }),
    );

    expect(text).toBe("$(lock) CommitForge · 12분");
  });

  it("다른 호스트 lock은 경고로 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "abc", created_at: null }, lockAgeSeconds: 60, lockOwnerSameHost: false },
      }),
    );

    expect(text).toBe("$(warning) CommitForge · 다른 세션");
  });

  it("버전이 다르면 경고한다", () => {
    const { text } = statusText(
      state({ project: { ...okReport, state: "version-mismatch", installedVersion: "1.14.2" } }),
    );

    expect(text).toBe("$(warning) CommitForge v1.14.2 → v1.15.0");
  });

  it("설치 버전을 모르면 물음표로 둔다", () => {
    const { text } = statusText(
      state({ project: { ...okReport, state: "version-mismatch", installedVersion: null } }),
    );

    expect(text).toBe("$(warning) CommitForge ? → v1.15.0");
  });

  it("1분 미만은 초로 보여준다", () => {
    const { text } = statusText(
      state({
        guard: { ...idleGuard, lockOwner: { session: "a", created_at: null }, lockAgeSeconds: 45, lockOwnerSameHost: true },
      }),
    );

    expect(text).toBe("$(lock) CommitForge · 45초");
  });

  it("tooltip에 범위별 상태를 담는다", () => {
    const { tooltip } = statusText(state());

    expect(tooltip).toContain("project");
    expect(tooltip).toContain("global");
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `cd editor-extension && npx vitest run test/statusText.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 4: `state.ts` 구현**

`editor-extension/src/state.ts`:

```ts
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
```

- [ ] **Step 5: `statusBar.ts` 구현**

`editor-extension/src/vscode/statusBar.ts`:

```ts
import * as vscode from "vscode";
import type { InstallReport } from "../core/detect";
import type { StateStore, WorkspaceState } from "../state";

const STATE_LABEL: Record<InstallReport["state"], string> = {
  missing: "미설치",
  ok: "정상",
  "version-mismatch": "버전 다름",
  misconfigured: "설정 불완전",
  corrupt: "손상",
};

function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

/** project 설치를 우선하고, 없으면 global을 본다. */
function primary(state: WorkspaceState): InstallReport {
  return state.project.state === "missing" ? state.global : state.project;
}

export function statusText(state: WorkspaceState | null): {
  text: string;
  tooltip: string;
} {
  if (!state) {
    return { text: "$(sync~spin) CommitForge", tooltip: "CommitForge 상태를 읽는 중입니다" };
  }

  const install = primary(state);
  const tooltip = [
    `project: ${STATE_LABEL[state.project.state]}`,
    `global: ${STATE_LABEL[state.global.state]}`,
    `번들 버전: v${install.bundleVersion}`,
    state.python ? `Python: ${state.python.executable}` : "Python: 찾지 못함",
  ].join("\n");

  if (install.state === "missing") {
    return { text: "$(alert) CommitForge 미설치", tooltip };
  }

  if (install.state === "version-mismatch") {
    const installed = install.installedVersion ? `v${install.installedVersion}` : "?";
    return {
      text: `$(warning) CommitForge ${installed} → v${install.bundleVersion}`,
      tooltip,
    };
  }

  if (install.state === "misconfigured" || install.state === "corrupt") {
    return { text: `$(warning) CommitForge ${STATE_LABEL[install.state]}`, tooltip };
  }

  const lock = state.guard?.lockOwner;
  if (lock) {
    if (state.guard?.lockOwnerSameHost === false) {
      return { text: "$(warning) CommitForge · 다른 세션", tooltip };
    }
    const age = state.guard?.lockAgeSeconds ?? 0;
    return { text: `$(lock) CommitForge · ${humanAge(age)}`, tooltip };
  }

  return { text: `$(check) CommitForge v${install.installedVersion ?? install.bundleVersion}`, tooltip };
}

export function createStatusBar(store: StateStore): vscode.Disposable {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  item.command = "commitforge.focusView";

  const render = (state: WorkspaceState | null) => {
    const { text, tooltip } = statusText(state);
    item.text = text;
    item.tooltip = tooltip;
    const enabled = vscode.workspace
      .getConfiguration("commitforge")
      .get<boolean>("statusBar.enabled", true);
    if (enabled) item.show();
    else item.hide();
  };

  render(store.current);
  const subscription = store.onDidChange(render);

  return vscode.Disposable.from(subscription, item);
}
```

- [ ] **Step 6: `extension.ts`와 `package.json` 배선**

`editor-extension/src/extension.ts`:

```ts
import * as vscode from "vscode";
import { StateStore } from "./state";
import { createStatusBar } from "./vscode/statusBar";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) return;

  const payloadRoot = vscode.Uri.joinPath(context.extensionUri, "payload").fsPath;
  const store = new StateStore(payloadRoot, folder.uri.fsPath);

  context.subscriptions.push(
    store,
    createStatusBar(store),
    vscode.commands.registerCommand("commitforge.refresh", () => store.refresh()),
    vscode.commands.registerCommand("commitforge.focusView", () =>
      vscode.commands.executeCommand("workbench.view.explorer"),
    ),
  );

  await store.refresh();
}

export function deactivate(): void {}
```

다중 루트 워크스페이스 처리와 페이로드 누락 처리는 Task 10 Step 6에서 완성한다. 지금은 첫 폴더만 본다.

`editor-extension/package.json`의 `contributes`를 채운다:

```json
  "contributes": {
    "commands": [
      { "command": "commitforge.refresh", "title": "CommitForge: 상태 새로고침" },
      { "command": "commitforge.focusView", "title": "CommitForge: 뷰 열기" }
    ],
    "configuration": {
      "title": "CommitForge",
      "properties": {
        "commitforge.pythonPath": {
          "type": "string",
          "default": "",
          "description": "Python 인터프리터 경로. 비우면 python3, python 순으로 찾습니다."
        },
        "commitforge.terminal.name": {
          "type": "string",
          "default": "CommitForge",
          "description": "확장이 만드는 터미널 이름"
        },
        "commitforge.terminal.launchCommand": {
          "type": "string",
          "default": "claude",
          "description": "새 터미널에서 실행할 명령"
        },
        "commitforge.statusBar.enabled": {
          "type": "boolean",
          "default": true,
          "description": "상태바 표시 여부"
        },
        "commitforge.confirmBeforeSend": {
          "type": "boolean",
          "default": true,
          "description": "터미널로 보내기 전 명령을 확인합니다"
        }
      }
    }
  },
```

- [ ] **Step 7: 통과 확인**

Run: `cd editor-extension && npx vitest run && npm run typecheck && npm run build`
Expected: 모든 테스트 PASS (10 tests 추가), 타입 검사와 빌드 성공

- [ ] **Step 8: 실제 실행 확인**

VS Code 또는 Cursor에서 `editor-extension/` 을 열고 F5(Extension Development Host)를 눌러 새 창을 띄운다. 새 창에서 CommitForge 저장소를 열고 상태바 왼쪽에 `$(check) CommitForge v...` 가 보이는지 확인한다.

- [ ] **Step 9: 커밋**

```bash
git add editor-extension/src editor-extension/test editor-extension/package.json
git commit -m "feat(extension): 워크스페이스 상태 집계와 상태바 추가"
```

---

### Task 10: 트리 뷰와 설치 실행

트리를 띄우고 설치·업그레이드·검증·제거 버튼을 붙인다.

**Files:**
- Create: `editor-extension/src/vscode/installer.ts`
- Create: `editor-extension/src/vscode/treeView.ts`
- Modify: `editor-extension/src/extension.ts`
- Modify: `editor-extension/package.json`
- Test: `editor-extension/test/installerArgs.test.ts`

**Interfaces:**
- Consumes: Task 9의 `StateStore`, `WorkspaceState`
- Produces:
  ```ts
  // installer.ts
  export type InstallAction = "install" | "uninstall";
  export function installerArgs(
    action: InstallAction, payloadRoot: string, scope: Scope, target: string, dryRun: boolean,
  ): string[];
  export async function runInstaller(
    store: StateStore, action: InstallAction, scope: Scope, output: vscode.OutputChannel,
  ): Promise<void>;
  // treeView.ts
  export function createTreeView(store: StateStore): vscode.Disposable;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/installerArgs.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { join } from "node:path";
import { installerArgs } from "../src/vscode/installer";

const payload = join("/ext", "payload");

describe("installerArgs", () => {
  it("project 설치 인자를 만든다", () => {
    expect(installerArgs("install", payload, "project", "/repo", false)).toEqual([
      join(payload, "install.py"),
      "--scope",
      "project",
      "--target",
      "/repo",
    ]);
  });

  it("dry-run 플래그를 붙인다", () => {
    expect(installerArgs("install", payload, "project", "/repo", true)).toContain("--dry-run");
  });

  it("global 범위에는 --target을 넘기지 않는다", () => {
    expect(installerArgs("install", payload, "global", "/repo", false)).toEqual([
      join(payload, "install.py"),
      "--scope",
      "global",
    ]);
  });

  it("제거는 uninstall.py를 쓴다", () => {
    expect(installerArgs("uninstall", payload, "project", "/repo", false)[0]).toBe(
      join(payload, "uninstall.py"),
    );
  });
});
```

`install.py`는 global 범위에서 `--target`을 무시하지만, 넘기지 않는 편이 의도가 분명하다.

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/installerArgs.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: `installer.ts` 구현**

`editor-extension/src/vscode/installer.ts`:

```ts
import * as vscode from "vscode";
import { join } from "node:path";
import { nodeRunner } from "../core/guard";
import type { Scope } from "../core/detect";
import type { StateStore } from "../state";

export type InstallAction = "install" | "uninstall";

const SCRIPT: Record<InstallAction, string> = {
  install: "install.py",
  uninstall: "uninstall.py",
};

export function installerArgs(
  action: InstallAction,
  payloadRoot: string,
  scope: Scope,
  target: string,
  dryRun: boolean,
): string[] {
  const args = [join(payloadRoot, SCRIPT[action]), "--scope", scope];
  if (scope === "project") args.push("--target", target);
  if (dryRun) args.push("--dry-run");
  return args;
}

const ACTION_LABEL: Record<InstallAction, string> = {
  install: "설치",
  uninstall: "제거",
};

export async function runInstaller(
  store: StateStore,
  action: InstallAction,
  scope: Scope,
  output: vscode.OutputChannel,
): Promise<void> {
  const state = store.current;
  if (!state) return;

  if (!state.python) {
    void vscode.window.showErrorMessage(
      "Python을 찾지 못했습니다. commitforge.pythonPath 설정을 확인하십시오.",
    );
    return;
  }

  const label = ACTION_LABEL[action];
  const python = state.python.executable;

  const preview = await nodeRunner(
    python,
    installerArgs(action, store.payloadDir, scope, state.folder, true),
    state.folder,
  );

  output.show(true);
  output.appendLine(`--- ${label} 예정 내용 (${scope}) ---`);
  output.appendLine(preview.stdout || preview.stderr);

  if (preview.code !== 0) {
    void vscode.window.showErrorMessage(`${label} 사전 확인 실패. 출력을 확인하십시오.`);
    return;
  }

  const confirmed = await vscode.window.showWarningMessage(
    `CommitForge를 ${scope} 범위에 ${label}합니다. 계속할까요?`,
    { modal: true, detail: "변경 예정 내용은 CommitForge 출력 채널에 있습니다." },
    "계속",
  );
  if (confirmed !== "계속") return;

  const result = await nodeRunner(
    python,
    installerArgs(action, store.payloadDir, scope, state.folder, false),
    state.folder,
  );

  output.appendLine(`--- ${label} 실행 결과 ---`);
  output.appendLine(result.stdout || result.stderr);

  if (result.code === 0) {
    void vscode.window.showInformationMessage(`CommitForge ${label} 완료 (${scope})`);
  } else {
    void vscode.window.showErrorMessage(`CommitForge ${label} 실패. 출력을 확인하십시오.`);
  }

  await store.refresh();
}
```

- [ ] **Step 4: `treeView.ts` 구현**

`editor-extension/src/vscode/treeView.ts`:

```ts
import * as vscode from "vscode";
import type { InstallReport } from "../core/detect";
import type { StateStore, WorkspaceState } from "../state";

const STATE_ICON: Record<InstallReport["state"], string> = {
  missing: "circle-outline",
  ok: "pass-filled",
  "version-mismatch": "warning",
  misconfigured: "warning",
  corrupt: "error",
};

const STATE_LABEL: Record<InstallReport["state"], string> = {
  missing: "미설치",
  ok: "정상",
  "version-mismatch": "버전 다름",
  misconfigured: "설정 불완전",
  corrupt: "손상",
};

class Node extends vscode.TreeItem {
  constructor(
    label: string,
    public readonly children: Node[] = [],
    icon?: string,
    description?: string,
  ) {
    super(
      label,
      children.length > 0
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None,
    );
    if (icon) this.iconPath = new vscode.ThemeIcon(icon);
    if (description) this.description = description;
  }
}

function installNode(report: InstallReport): Node {
  const version =
    report.state === "missing"
      ? ""
      : `v${report.installedVersion ?? report.bundleVersion}`;

  const details: string[] = [];
  if (!report.corePathOk && report.state !== "missing") {
    details.push("skill의 core 경로가 이 설치를 가리키지 않습니다");
  }
  if (!report.hooksRegistered && report.state !== "missing") {
    details.push("SessionEnd hook이 등록되지 않았습니다");
  }
  for (const path of report.missingFiles.slice(0, 5)) details.push(`누락: ${path}`);
  for (const path of report.mismatchedFiles.slice(0, 5)) details.push(`불일치: ${path}`);

  return new Node(
    report.scope,
    details.map((detail) => new Node(detail)),
    STATE_ICON[report.state],
    `${version} ${STATE_LABEL[report.state]}`.trim(),
  );
}

function buildTree(state: WorkspaceState | null): Node[] {
  if (!state) return [new Node("상태를 읽는 중입니다", [], "sync~spin")];

  const nodes: Node[] = [
    new Node("설치", [installNode(state.project), installNode(state.global)], "package"),
  ];

  if (!state.isGitRepo) return nodes;

  const guard = state.guard;
  const stale = state.guardError !== null;

  if (!guard) {
    if (stale) {
      nodes.push(new Node("잠금", [new Node(state.guardError!)], "error", "읽기 실패"));
    }
  } else {
    const lock = guard.lockOwner;
    const lockChildren = lock
      ? [
          new Node(`session ${lock.session ?? "?"}`),
          new Node(`${guard.lockAgeSeconds ?? 0}초 경과`),
          new Node(guard.lockOwnerSameHost === false ? "다른 호스트" : "이 호스트"),
        ]
      : [];
    const lockLabel = lock ? "보유 중" : "보유자 없음";
    nodes.push(
      new Node(
        "잠금",
        lockChildren,
        lock ? "lock" : "unlock",
        stale ? `${lockLabel} (오래된 값)` : lockLabel,
      ),
    );

    nodes.push(
      new Node(
        "스냅샷",
        guard.snapshots.map((path) => new Node(path)),
        "archive",
        `${guard.snapshots.length}개`,
      ),
    );

    const warnings = [
      ...(stale ? [`guard.py status 실패: ${state.guardError}`] : []),
      ...guard.operations.map((op) => `${op} 진행 중`),
      ...guard.gitLockFiles.map((path) => `git lock: ${path}`),
      ...state.project.warnings,
      ...state.global.warnings,
    ];
    if (warnings.length > 0) {
      nodes.push(
        new Node("경고", warnings.map((w) => new Node(w)), "warning", `${warnings.length}건`),
      );
    }
  }

  return nodes;
}

export function createTreeView(store: StateStore): vscode.Disposable {
  const emitter = new vscode.EventEmitter<void>();
  let roots = buildTree(store.current);

  const provider: vscode.TreeDataProvider<Node> = {
    onDidChangeTreeData: emitter.event as vscode.Event<undefined>,
    getTreeItem: (node) => node,
    getChildren: (node) => (node ? node.children : roots),
  };

  const view = vscode.window.createTreeView("commitforge.view", {
    treeDataProvider: provider,
  });

  const subscription = store.onDidChange((state) => {
    roots = buildTree(state);
    emitter.fire();
  });

  return vscode.Disposable.from(subscription, view, emitter);
}
```

- [ ] **Step 5: `package.json`에 뷰와 명령 추가**

`contributes`에 다음을 병합한다:

```json
    "viewsContainers": {
      "activitybar": [
        {
          "id": "commitforge",
          "title": "CommitForge",
          "icon": "$(git-commit)"
        }
      ]
    },
    "views": {
      "commitforge": [
        { "id": "commitforge.view", "name": "상태" }
      ]
    },
    "menus": {
      "view/title": [
        { "command": "commitforge.refresh", "when": "view == commitforge.view", "group": "navigation" }
      ]
    }
```

`commands` 배열에 추가한다:

```json
      { "command": "commitforge.install", "title": "CommitForge: 설치" },
      { "command": "commitforge.uninstall", "title": "CommitForge: 제거" },
      { "command": "commitforge.verify", "title": "CommitForge: 설치 검증" }
```

`commitforge.focusView`의 구현도 이제 실제 뷰를 연다.

- [ ] **Step 6: `extension.ts` 갱신**

```ts
import * as vscode from "vscode";
import { StateStore } from "./state";
import { createStatusBar } from "./vscode/statusBar";
import { createTreeView } from "./vscode/treeView";
import { runInstaller } from "./vscode/installer";
import type { Scope } from "./core/detect";

const FOLDER_KEY = "commitforge.activeFolder";

async function pickScope(): Promise<Scope | undefined> {
  const picked = await vscode.window.showQuickPick(
    [
      { label: "project", description: "이 워크스페이스에만 설치" },
      { label: "global", description: "모든 프로젝트에서 사용" },
    ],
    { placeHolder: "설치 범위를 고르십시오" },
  );
  return picked?.label as Scope | undefined;
}

/**
 * 다중 루트 워크스페이스에서는 어느 폴더를 대상으로 할지 한 번 묻고 기억한다.
 * 기억한 폴더가 사라졌으면 다시 묻는다.
 */
async function resolveFolder(
  context: vscode.ExtensionContext,
): Promise<vscode.WorkspaceFolder | undefined> {
  const folders = vscode.workspace.workspaceFolders ?? [];
  if (folders.length === 0) return undefined;
  if (folders.length === 1) return folders[0];

  const remembered = context.workspaceState.get<string>(FOLDER_KEY);
  const found = folders.find((folder) => folder.uri.fsPath === remembered);
  if (found) return found;

  const picked = await vscode.window.showQuickPick(
    folders.map((folder) => ({ label: folder.name, description: folder.uri.fsPath, folder })),
    { placeHolder: "CommitForge를 사용할 폴더를 고르십시오" },
  );
  if (!picked) return undefined;

  await context.workspaceState.update(FOLDER_KEY, picked.folder.uri.fsPath);
  return picked.folder;
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const folder = await resolveFolder(context);
  if (!folder) return;

  const payloadRoot = vscode.Uri.joinPath(context.extensionUri, "payload").fsPath;
  const store = new StateStore(payloadRoot, folder.uri.fsPath);
  const output = vscode.window.createOutputChannel("CommitForge");

  context.subscriptions.push(
    store,
    output,
    createStatusBar(store),
    createTreeView(store),
    vscode.commands.registerCommand("commitforge.refresh", () => store.refresh()),
    vscode.commands.registerCommand("commitforge.focusView", () =>
      vscode.commands.executeCommand("commitforge.view.focus"),
    ),
    vscode.commands.registerCommand("commitforge.install", async () => {
      const scope = await pickScope();
      if (scope) await runInstaller(store, "install", scope, output);
    }),
    vscode.commands.registerCommand("commitforge.uninstall", async () => {
      const scope = await pickScope();
      if (scope) await runInstaller(store, "uninstall", scope, output);
    }),
    vscode.commands.registerCommand("commitforge.verify", async () => {
      await store.refresh();
      const state = store.current;
      if (!state) return;
      output.show(true);
      for (const report of [state.project, state.global]) {
        output.appendLine(`[${report.scope}] 상태: ${report.state}`);
        for (const path of report.missingFiles) output.appendLine(`  누락: ${path}`);
        for (const path of report.mismatchedFiles) output.appendLine(`  불일치: ${path}`);
        for (const warning of report.warnings) output.appendLine(`  경고: ${warning}`);
      }
    }),
  );

  try {
    await store.refresh();
  } catch (error) {
    // payload/ 가 없으면 sync-payload 없이 패키징된 것이다. 빌드 실패로 본다.
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`CommitForge 초기화 실패: ${message}`);
    void vscode.window.showErrorMessage(
      `CommitForge 확장을 초기화하지 못했습니다: ${message}`,
    );
  }
}

export function deactivate(): void {}
```

`commitforge.verify`가 `verify.py`를 호출하지 않는 것은 의도다. `verify.py`는 소스 패키지 검사 도구이고 여기서 필요한 것은 설치본 검사다 (spec §7.4).

- [ ] **Step 7: 통과 확인**

Run: `cd editor-extension && npx vitest run && npm run typecheck && npm run build`
Expected: 전부 성공

- [ ] **Step 8: 실제 실행 확인**

F5로 Extension Development Host를 띄우고, CommitForge가 설치되지 않은 임시 git 저장소를 연다. 사이드바 CommitForge 아이콘 → 설치 노드가 `미설치`인지 확인한다. `CommitForge: 설치` 명령으로 project 설치를 실행해 dry-run 확인 후 설치되고, 트리가 `정상 v1.15.0`으로 바뀌는지 확인한다.

- [ ] **Step 9: 커밋**

```bash
git add editor-extension/src editor-extension/test editor-extension/package.json
git commit -m "feat(extension): 상태 트리 뷰와 설치 실행 추가"
```

---

### Task 11: 이벤트 기반 상태 갱신

폴링 없이 상태를 최신으로 유지한다.

**Files:**
- Create: `editor-extension/src/vscode/watchers.ts`
- Modify: `editor-extension/src/extension.ts`
- Test: `editor-extension/test/debounce.test.ts`

**Interfaces:**
- Consumes: Task 9의 `StateStore`
- Produces:
  ```ts
  export function debounce(fn: () => void, ms: number): { call: () => void; dispose: () => void };
  export function createWatchers(store: StateStore, folder: vscode.WorkspaceFolder): vscode.Disposable;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/debounce.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { debounce } from "../src/vscode/watchers";

describe("debounce", () => {
  it("연속 호출을 한 번으로 합친다", async () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    debounced.call();
    debounced.call();
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("간격을 두면 각각 실행한다", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    vi.advanceTimersByTime(100);
    debounced.call();
    vi.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("dispose 후에는 실행하지 않는다", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.call();
    debounced.dispose();
    vi.advanceTimersByTime(500);

    expect(fn).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});
```

`vscode` stub과 vitest 별칭은 Task 9 Step 1에서 이미 만들었다. `watchers.ts`가 쓰는 `createFileSystemWatcher`, `onDidChangeWindowState`, `RelativePattern`, `Disposable.from`이 모두 stub에 들어 있으므로 추가 작업이 없다. 없으면 Task 9 Step 1의 stub을 다시 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/debounce.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/src/vscode/watchers.ts`:

```ts
import * as vscode from "vscode";
import type { StateStore } from "../state";

export function debounce(
  fn: () => void,
  ms: number,
): { call: () => void; dispose: () => void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;

  return {
    call: () => {
      if (disposed) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = undefined;
        if (!disposed) fn();
      }, ms);
    },
    dispose: () => {
      disposed = true;
      if (timer) clearTimeout(timer);
    },
  };
}

/**
 * 폴링하지 않는다. 창 포커스 복귀와 파일 변화에만 반응한다.
 * guard.py는 프로세스를 띄우므로 변화를 200ms 모아 한 번만 실행한다.
 */
export function createWatchers(
  store: StateStore,
  folder: vscode.WorkspaceFolder,
): vscode.Disposable {
  const refresh = debounce(() => void store.refresh(), 200);

  const patterns = [
    ".git/claude-atomic.lock/**",
    ".git/claude-atomic-snapshots/**",
    ".claude/**",
  ];

  const watchers = patterns.map((pattern) => {
    const watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(folder, pattern),
    );
    watcher.onDidChange(refresh.call);
    watcher.onDidCreate(refresh.call);
    watcher.onDidDelete(refresh.call);
    return watcher;
  });

  const focus = vscode.window.onDidChangeWindowState((windowState) => {
    if (windowState.focused) refresh.call();
  });

  return vscode.Disposable.from(...watchers, focus, { dispose: refresh.dispose });
}
```

- [ ] **Step 4: `extension.ts`에 배선**

`createTreeView(store),` 다음 줄에 추가한다:

```ts
    createWatchers(store, folder),
```

import도 추가한다:

```ts
import { createWatchers } from "./vscode/watchers";
```

- [ ] **Step 5: 통과 확인**

Run: `cd editor-extension && npx vitest run && npm run typecheck && npm run build`
Expected: 전부 성공 (3 tests 추가)

- [ ] **Step 6: 커밋**

```bash
git add editor-extension/src editor-extension/test editor-extension/vitest.config.ts
git commit -m "feat(extension): 폴링 없는 이벤트 기반 상태 갱신 추가"
```

---

### Task 12: 명령 실행 흐름

명령 조립기와 터미널 전송을 붙인다. 이 태스크가 MVP의 마지막 기능이다.

**Files:**
- Create: `editor-extension/src/vscode/terminal.ts`
- Create: `editor-extension/src/vscode/quickPick.ts`
- Modify: `editor-extension/src/extension.ts`
- Modify: `editor-extension/package.json`
- Test: `editor-extension/test/lockWarning.test.ts`

**Interfaces:**
- Consumes: Task 6의 `GuardStatus`, Task 7의 `CommandSpec`, Task 8의 `compose`·`isWriteCommand`, Task 9의 `StateStore`
- Produces:
  ```ts
  // terminal.ts
  export interface TerminalTarget { terminal: vscode.Terminal; created: boolean }
  export async function resolveTarget(context: vscode.ExtensionContext): Promise<vscode.Terminal | undefined>;
  export function sendCommand(terminal: vscode.Terminal, command: string): void;
  // quickPick.ts
  export function lockWarning(guard: GuardStatus | null, command: string): string | null;
  export async function runCommandFlow(store: StateStore, context: vscode.ExtensionContext): Promise<void>;
  ```

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/lockWarning.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { lockWarning } from "../src/vscode/quickPick";
import type { GuardStatus } from "../src/core/guard";

const base: GuardStatus = {
  ok: true,
  projectRoot: "/repo",
  gitDir: "/repo/.git",
  lockOwner: null,
  lockAgeSeconds: null,
  lockOwnerHostname: null,
  lockOwnerSameHost: null,
  currentHostname: "mac.local",
  staleCandidate: false,
  snapshots: [],
  operations: [],
  gitLockFiles: [],
};

const held: GuardStatus = {
  ...base,
  lockOwner: { session: "abc123", created_at: "2026-09-11T08:00:00Z" },
  lockAgeSeconds: 742,
  lockOwnerHostname: "other.local",
  lockOwnerSameHost: false,
};

describe("lockWarning", () => {
  it("lock이 없으면 경고하지 않는다", () => {
    expect(lockWarning(base, "cca")).toBeNull();
  });

  it("읽기 전용 명령은 lock이 있어도 경고하지 않는다", () => {
    expect(lockWarning(held, "cr")).toBeNull();
    expect(lockWarning(held, "ccr")).toBeNull();
  });

  it("쓰기 명령은 lock 보유자 정보를 담아 경고한다", () => {
    const warning = lockWarning(held, "cca");

    expect(warning).toContain("abc123");
    expect(warning).toContain("12분");
    expect(warning).toContain("other.local");
  });

  it("guard 상태를 모르면 경고하지 않는다", () => {
    expect(lockWarning(null, "cca")).toBeNull();
  });

  it("같은 호스트 lock도 쓰기 명령이면 경고한다", () => {
    const sameHost = { ...held, lockOwnerSameHost: true, lockOwnerHostname: "mac.local" };

    expect(lockWarning(sameHost, "cc")).toContain("abc123");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/lockWarning.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: `terminal.ts` 구현**

`editor-extension/src/vscode/terminal.ts`:

```ts
import * as vscode from "vscode";

const TARGET_KEY = "commitforge.terminalName";

function config<T>(key: string, fallback: T): T {
  return vscode.workspace.getConfiguration("commitforge").get<T>(key, fallback);
}

function createTerminal(): vscode.Terminal {
  const name = config("terminal.name", "CommitForge");
  const launch = config("terminal.launchCommand", "claude");
  const terminal = vscode.window.createTerminal({ name });
  terminal.show(true);
  // 사용자의 대화형 셸을 거치므로 claude가 alias나 함수여도 동작한다.
  terminal.sendText(launch, true);
  return terminal;
}

/**
 * 확장이 만든 터미널을 우선 쓴다. Claude Code가 다른 터미널에서 돌고 있는지는
 * 알 수 없으므로, 열린 터미널이 있으면 한 번 물어보고 선택을 기억한다.
 */
export async function resolveTarget(
  context: vscode.ExtensionContext,
): Promise<vscode.Terminal | undefined> {
  const remembered = context.workspaceState.get<string>(TARGET_KEY);
  if (remembered) {
    const found = vscode.window.terminals.find((t) => t.name === remembered);
    if (found) return found;
  }

  const own = config("terminal.name", "CommitForge");
  const existing = vscode.window.terminals.find((t) => t.name === own);
  if (existing) {
    await context.workspaceState.update(TARGET_KEY, own);
    return existing;
  }

  if (vscode.window.terminals.length === 0) {
    const created = createTerminal();
    await context.workspaceState.update(TARGET_KEY, created.name);
    return created;
  }

  const picked = await vscode.window.showQuickPick(
    [
      ...vscode.window.terminals.map((t) => ({
        label: t.name,
        description: "이미 열린 터미널",
      })),
      { label: `$(add) 새 터미널 "${own}"`, description: "claude를 새로 실행합니다" },
    ],
    { placeHolder: "명령을 보낼 터미널을 고르십시오" },
  );
  if (!picked) return undefined;

  if (picked.label.startsWith("$(add)")) {
    const created = createTerminal();
    await context.workspaceState.update(TARGET_KEY, created.name);
    return created;
  }

  await context.workspaceState.update(TARGET_KEY, picked.label);
  return vscode.window.terminals.find((t) => t.name === picked.label);
}

export function sendCommand(terminal: vscode.Terminal, command: string): void {
  terminal.show(true);
  terminal.sendText(command, true);
}
```

- [ ] **Step 4: `quickPick.ts` 구현**

`editor-extension/src/vscode/quickPick.ts`:

```ts
import * as vscode from "vscode";
import type { CommandOption, CommandSpec } from "../core/catalog";
import { compose, isWriteCommand, type SelectedOption } from "../core/composer";
import type { GuardStatus } from "../core/guard";
import type { StateStore } from "../state";
import { resolveTarget, sendCommand } from "./terminal";

const RECENT_KEY = "commitforge.recentCommands";
const RECENT_MAX = 5;

/**
 * 모드별 관련 옵션. 정렬과 그룹 헤더에만 쓰고 필터로는 쓰지 않는다.
 * 여기 없는 옵션은 "기타"에 나타나므로 새 옵션이 숨겨지지 않는다.
 */
const MODE_GROUPS: Record<string, string[]> = {
  release: ["--target", "--bump", "--channel", "--package", "--tag-prefix", "--from", "--prepare", "--tag", "--dry-run"],
  emergency: ["--incident", "--severity", "--diagnose", "--rollback-first"],
  today: ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
  "3days": ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
  weekly: ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
};

function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

export function lockWarning(guard: GuardStatus | null, command: string): string | null {
  if (!guard?.lockOwner) return null;
  if (!isWriteCommand(command)) return null;

  const session = guard.lockOwner.session ?? "알 수 없음";
  const age = humanAge(guard.lockAgeSeconds ?? 0);
  const host = guard.lockOwnerHostname ?? "알 수 없는 호스트";

  return `다른 세션이 lock을 보유 중입니다: session ${session} · ${age} 경과 · ${host}`;
}

function groupedOptions(spec: CommandSpec, mode: string | undefined): CommandOption[] {
  const preferred = new Set(mode ? (MODE_GROUPS[mode] ?? []) : []);
  const related = spec.options.filter((option) => preferred.has(option.name));
  const rest = spec.options.filter((option) => !preferred.has(option.name));
  return [...related, ...rest];
}

function optionDetail(option: CommandOption): string {
  switch (option.kind) {
    case "flag":
      return option.exclusiveWith ? `${option.exclusiveWith} 와 배타` : "플래그";
    case "value":
      return `값 필요 ${option.placeholder ?? ""}`.trim();
    case "enum":
      return `값: ${option.values?.join(", ")}`;
    case "range":
      return `${option.range?.[0]}-${option.range?.[1]} 범위의 정수`;
  }
}

async function askValue(option: CommandOption): Promise<string | undefined> {
  if (option.kind === "enum") {
    return vscode.window.showQuickPick(option.values ?? [], {
      placeHolder: `${option.name} 값`,
    });
  }
  return vscode.window.showInputBox({
    prompt: `${option.name} 값`,
    placeHolder: option.kind === "range" ? `${option.range?.[0]}-${option.range?.[1]}` : option.placeholder,
    ignoreFocusOut: true,
  });
}

async function buildWithOptions(spec: CommandSpec): Promise<string | undefined> {
  let mode: string | undefined;
  if (spec.modes.length > 0) {
    const picked = await vscode.window.showQuickPick(
      [{ label: "(모드 없음)" }, ...spec.modes.map((m) => ({ label: m }))],
      { placeHolder: `/${spec.name} 모드` },
    );
    if (!picked) return undefined;
    if (picked.label !== "(모드 없음)") mode = picked.label;
  }

  const chosen = await vscode.window.showQuickPick(
    groupedOptions(spec, mode).map((option) => ({
      label: option.name,
      detail: optionDetail(option),
      option,
    })),
    { placeHolder: `/${spec.name} 옵션 (여러 개 선택 가능)`, canPickMany: true },
  );
  if (!chosen) return undefined;

  const options: SelectedOption[] = [];
  for (const item of chosen) {
    if (item.option.kind === "flag") {
      options.push({ name: item.option.name });
      continue;
    }
    const value = await askValue(item.option);
    if (value === undefined) return undefined;
    options.push({ name: item.option.name, value });
  }

  let freeText: string | undefined;
  if (spec.acceptsFreeText) {
    freeText = await vscode.window.showInputBox({
      prompt: "추가 맥락 (선택)",
      ignoreFocusOut: true,
    });
    if (freeText === undefined) return undefined;
  }

  try {
    return compose(spec, { mode, freeText, options });
  } catch (error) {
    void vscode.window.showErrorMessage(
      error instanceof Error ? error.message : String(error),
    );
    return undefined;
  }
}

export async function runCommandFlow(
  store: StateStore,
  context: vscode.ExtensionContext,
): Promise<void> {
  const state = store.current;
  if (!state) return;

  if (state.catalog.length === 0) {
    void vscode.window.showWarningMessage(
      "CommitForge 명령을 찾지 못했습니다. 먼저 설치하십시오.",
    );
    return;
  }

  const recent = context.workspaceState.get<string[]>(RECENT_KEY, []);
  const items: Array<vscode.QuickPickItem & { spec?: CommandSpec; literal?: string }> = [
    ...state.catalog.map((spec) => ({
      label: `/${spec.name}`,
      description: spec.description,
      buttons: [{ iconPath: new vscode.ThemeIcon("gear"), tooltip: "옵션 지정" }],
      spec,
    })),
  ];
  if (recent.length > 0) {
    items.push({ label: "최근", kind: vscode.QuickPickItemKind.Separator });
    items.push(...recent.map((literal) => ({ label: literal, literal })));
  }

  const picked = await new Promise<
    { item: (typeof items)[number]; withOptions: boolean } | undefined
  >((resolve) => {
    const quickPick = vscode.window.createQuickPick<(typeof items)[number]>();
    quickPick.items = items;
    quickPick.placeholder = "실행할 CommitForge 명령";
    quickPick.onDidTriggerItemButton((event) => {
      resolve({ item: event.item, withOptions: true });
      quickPick.hide();
    });
    quickPick.onDidAccept(() => {
      const selected = quickPick.selectedItems[0];
      resolve(selected ? { item: selected, withOptions: false } : undefined);
      quickPick.hide();
    });
    quickPick.onDidHide(() => {
      resolve(undefined);
      quickPick.dispose();
    });
    quickPick.show();
  });

  if (!picked) return;

  let command: string | undefined;
  let commandName: string;

  if (picked.item.literal) {
    command = picked.item.literal;
    commandName = command.slice(1).split(/\s/)[0] ?? "";
  } else if (picked.item.spec) {
    commandName = picked.item.spec.name;
    command = picked.withOptions
      ? await buildWithOptions(picked.item.spec)
      : `/${picked.item.spec.name}`;
  } else {
    return;
  }

  if (!command) return;

  const warning = lockWarning(state.guard, commandName);
  if (warning) {
    const answer = await vscode.window.showWarningMessage(
      warning,
      { modal: true, detail: "그래도 보내면 Claude가 거부할 수 있습니다." },
      "그래도 보내기",
      "clean 실행",
    );
    if (answer === "clean 실행") command = "/cr clean";
    else if (answer !== "그래도 보내기") return;
  }

  const confirm = vscode.workspace
    .getConfiguration("commitforge")
    .get<boolean>("confirmBeforeSend", true);
  if (confirm) {
    const answer = await vscode.window.showInformationMessage(
      `터미널로 보냅니다: ${command}`,
      { modal: true },
      "보내기",
    );
    if (answer !== "보내기") return;
  }

  const terminal = await resolveTarget(context);
  if (!terminal) return;

  sendCommand(terminal, command);

  const next = [command, ...recent.filter((item) => item !== command)].slice(0, RECENT_MAX);
  await context.workspaceState.update(RECENT_KEY, next);
  setTimeout(() => void store.refresh(), 1000);
}
```

- [ ] **Step 5: `extension.ts`와 `package.json` 배선**

`extension.ts`에 import와 명령 등록을 추가한다:

```ts
import { runCommandFlow } from "./vscode/quickPick";
```

```ts
    vscode.commands.registerCommand("commitforge.run", () => runCommandFlow(store, context)),
```

`package.json`의 `commands` 배열에 추가한다:

```json
      { "command": "commitforge.run", "title": "CommitForge: 명령 실행" }
```

`menus.view/title`에도 추가한다:

```json
        { "command": "commitforge.run", "when": "view == commitforge.view", "group": "navigation" }
```

- [ ] **Step 6: 통과 확인**

Run: `cd editor-extension && npx vitest run && npm run typecheck && npm run build`
Expected: 전부 성공 (5 tests 추가)

`test/stubs/vscode.ts`에 `ThemeIcon`, `QuickPickItemKind` 등이 없어 `quickPick.ts` import가 실패하면 stub에 추가한다:

```ts
export class ThemeIcon {
  constructor(public id: string) {}
}
export const QuickPickItemKind = { Separator: -1, Default: 0 };
```

- [ ] **Step 7: 실제 실행 확인**

F5로 Extension Development Host를 띄우고 CommitForge가 설치된 저장소를 연다.

1. `CommitForge: 명령 실행` → `/cr` 선택 → 확인 → 터미널 선택 → `claude`가 뜨고 `/cr`이 입력되는지 확인
2. 같은 명령에서 `/cca`의 `⚙` 버튼 → `release` 모드 → 옵션에 `--bump`가 위쪽 그룹에 오는지 확인
3. `--commits`에 `5`를 넣으면 `20-500 범위여야 합니다` 오류가 뜨는지 확인

- [ ] **Step 8: 커밋**

```bash
git add editor-extension/src editor-extension/test
git commit -m "feat(extension): 명령 조립기와 터미널 전송 추가"
```

---

### Task 13: 버전 동기화, 문서, 패키징

확장 버전을 루트 `VERSION`에 맞추고, 문서를 갱신하고, VSIX를 만든다.

**Files:**
- Create: `editor-extension/scripts/sync-version.mjs`
- Create: `editor-extension/README.md`
- Modify: `editor-extension/package.json`
- Modify: `README.md`
- Modify: `MANUAL-TEST-CHECKLIST.md`
- Modify: `CHANGELOG.md`
- Test: `editor-extension/test/sync-version.test.ts`

**Interfaces:**
- Consumes: Task 2의 `payload/VERSION`
- Produces: `syncVersion(repoRoot: string, packageJsonPath: string): Promise<string>`

- [ ] **Step 1: 실패하는 테스트 작성**

`editor-extension/test/sync-version.test.ts`:

```ts
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { syncVersion } from "../scripts/sync-version.mjs";

describe("syncVersion", () => {
  let root: string;

  beforeEach(async () => {
    root = await mkdtemp(join(tmpdir(), "cf-version-"));
  });

  afterEach(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("VERSION을 package.json에 반영한다", async () => {
    await writeFile(join(root, "VERSION"), "1.16.0\n");
    const pkg = join(root, "package.json");
    await writeFile(pkg, JSON.stringify({ name: "commitforge", version: "0.0.0" }, null, 2));

    const version = await syncVersion(root, pkg);

    expect(version).toBe("1.16.0");
    const updated = JSON.parse(await readFile(pkg, "utf8"));
    expect(updated.version).toBe("1.16.0");
    expect(updated.name).toBe("commitforge");
  });

  it("semver가 아니면 실패한다", async () => {
    await writeFile(join(root, "VERSION"), "not-a-version\n");
    const pkg = join(root, "package.json");
    await writeFile(pkg, JSON.stringify({ version: "0.0.0" }));

    await expect(syncVersion(root, pkg)).rejects.toThrow(/semver/);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd editor-extension && npx vitest run test/sync-version.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`editor-extension/scripts/sync-version.mjs`:

```js
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
```

`package.json`의 `scripts`를 수정한다:

```json
    "sync-version": "node scripts/sync-version.mjs",
    "build": "npm run sync-version && npm run sync-payload && node esbuild.mjs",
```

- [ ] **Step 4: 통과 확인**

Run: `cd editor-extension && npx vitest run test/sync-version.test.ts && npm run build`
Expected: PASS. `package.json`의 `version`이 루트 `VERSION` 값으로 바뀐다.

- [ ] **Step 5: 확장 README 작성**

`editor-extension/README.md`:

```markdown
# CommitForge 확장

CommitForge를 VS Code와 Cursor에서 설치·관리하고 명령을 실행합니다.

## 기능

- **설치 관리** — project·global 범위의 설치 상태를 표시하고 설치·업그레이드·검증·제거를 실행합니다.
- **상태 표시** — lock 보유 여부, Diff snapshot, 진행 중인 Git 작업을 상태바와 사이드바에 보여줍니다.
- **명령 실행** — 명령 9개와 옵션을 골라 Claude Code가 실행 중인 터미널로 보냅니다.

## 요구사항

- Python 3.9 이상
- Claude Code

확장은 CommitForge 패키지를 내장하고 있어 별도 체크아웃이 필요 없습니다.

## 명령

| 명령 | 설명 |
|---|---|
| `CommitForge: 명령 실행` | 명령과 옵션을 골라 터미널로 전송 |
| `CommitForge: 설치` | 선택한 범위에 설치 |
| `CommitForge: 제거` | 선택한 범위에서 제거 |
| `CommitForge: 설치 검증` | 설치본 무결성을 검사하고 결과를 출력 |
| `CommitForge: 상태 새로고침` | 상태를 다시 읽음 |

## 설정

| 키 | 기본값 | 설명 |
|---|---|---|
| `commitforge.pythonPath` | (자동) | Python 인터프리터 경로 |
| `commitforge.terminal.name` | `CommitForge` | 확장이 만드는 터미널 이름 |
| `commitforge.terminal.launchCommand` | `claude` | 새 터미널에서 실행할 명령 |
| `commitforge.statusBar.enabled` | `true` | 상태바 표시 여부 |
| `commitforge.confirmBeforeSend` | `true` | 전송 전 확인 |

## 개발

```bash
npm install
npm test          # 단위 테스트
npm run typecheck
npm run build     # 버전·페이로드 동기화 후 번들
npm run package   # commitforge.vsix 생성
```

F5를 누르면 Extension Development Host가 뜹니다.
```

- [ ] **Step 6: 루트 README에 확장 안내 추가**

루트 `README.md`의 "30초 빠른 시작" 섹션 끝, "Windows PowerShell에서는" 문단 뒤에 추가한다:

```markdown
### 에디터 확장

VS Code나 Cursor를 쓴다면 확장으로 설치·상태 확인·명령 실행을 GUI에서 할 수 있습니다.

```bash
cd editor-extension
npm install && npm run package
```

생성된 `commitforge.vsix`를 에디터에서 설치합니다. 자세한 내용은 [editor-extension/README.md](editor-extension/README.md)를 참고하십시오.
```

"문서 바로가기" 목록에도 한 줄 추가한다:

```markdown
- [에디터 확장](editor-extension/README.md)
```

- [ ] **Step 7: 수동 테스트 체크리스트 추가**

`MANUAL-TEST-CHECKLIST.md` 끝에 섹션을 추가한다:

```markdown
## 에디터 확장

터미널 전송은 자동 검증이 어려우므로 수동으로 확인한다.

- [ ] CommitForge 미설치 저장소를 열면 상태바가 `CommitForge 미설치`를 보여준다
- [ ] `CommitForge: 설치` → project 선택 → dry-run 내용이 Output에 나오고, 확인 후 설치된다
- [ ] 설치 후 상태바가 `$(check) CommitForge v<버전>` 으로 바뀐다
- [ ] `.claude/.commitforge-install.json` 이 생성되고 version이 루트 VERSION과 같다
- [ ] `CommitForge: 명령 실행` → `/cr` Enter → 터미널 선택 → claude가 뜨고 `/cr`이 입력된다
- [ ] 두 번째 전송부터는 터미널을 다시 묻지 않는다
- [ ] `/cca`의 톱니 버튼 → `release` 모드에서 `--bump`가 목록 위쪽에 온다
- [ ] `--commits` 에 `5`를 넣으면 범위 오류가 뜨고 전송되지 않는다
- [ ] 다른 세션이 lock을 쥔 상태에서 `/cca`를 고르면 전송 전에 경고가 뜬다
- [ ] 경고에서 `clean 실행`을 고르면 `/cr clean` 이 전송된다
- [ ] 최근 실행 목록에 직전 명령이 남는다
- [ ] `CommitForge: 제거` 후 상태바가 미설치로 돌아가고 마커가 사라진다
- [ ] Git 저장소가 아닌 폴더를 열면 잠금·스냅샷 노드가 보이지 않는다
- [ ] `commitforge.pythonPath` 에 잘못된 경로를 넣어도 확장이 죽지 않고 명령 전송은 동작한다
- [ ] 다중 루트 워크스페이스를 열면 폴더를 한 번 묻고, 다시 열면 묻지 않는다
- [ ] guard.py를 일시적으로 옮겨 `상태 새로고침`을 하면 경고가 뜨되 직전 잠금 정보가 `(오래된 값)`으로 남는다
```

- [ ] **Step 8: CHANGELOG 갱신**

`CHANGELOG.md` 최상단 미배포 섹션에 추가한다. 기존 형식을 그대로 따른다.

```markdown
### Added

- VS Code·Cursor용 에디터 확장 (`editor-extension/`). 설치 관리, lock·snapshot 상태 표시, 명령 조립과 터미널 전송을 제공한다.
- `install.py`가 `.claude/.commitforge-install.json` 설치 마커를 기록하고 `uninstall.py`가 제거한다.
```

- [ ] **Step 9: 전체 검증**

Run:
```bash
cd editor-extension && npm run build && npx vitest run && npm run typecheck && npm run package
cd .. && python verify.py && python -m unittest discover -s tests -v && python release.py --check
```
Expected: 전부 성공. `editor-extension/commitforge.vsix`가 생성된다.

`python release.py --check`가 실패하면 `editor-extension/`의 새 소스가 MANIFEST에 없기 때문이다. `python release.py`로 재생성한 뒤 다시 확인한다. `node_modules/`, `payload/`, `dist/`, `*.vsix`가 MANIFEST에 들어가면 Task 2 Step 1의 `.gitignore` 항목이 빠진 것이다.

- [ ] **Step 10: VSIX 설치 확인**

Cursor에서 명령 팔레트 → `Extensions: Install from VSIX...` → `editor-extension/commitforge.vsix` 선택. 설치 후 창을 다시 불러 상태바와 사이드바가 나타나는지 확인한다.

- [ ] **Step 11: 커밋**

```bash
git add editor-extension README.md MANUAL-TEST-CHECKLIST.md CHANGELOG.md MANIFEST.json checksums.sha256
git commit -m "feat(extension): 버전 동기화와 문서, VSIX 패키징 추가"
```

---

## spec과 다르게 정한 것

계획을 쓰면서 spec의 두 지점을 바꿨다. 실행자는 이 결정을 따른다.

**1. `@vscode/test-electron` E2E를 넣지 않는다.** spec §10은 활성화·트리 렌더·명령 등록을 얕게 확인하는 E2E를 두라고 한다. 대신 Task 9·10·12의 "실제 실행 확인" 단계(F5 Extension Development Host)와 `MANUAL-TEST-CHECKLIST.md` 항목으로 대체한다. 이유는 test-electron이 에디터 바이너리를 내려받아 헤드리스로 띄우는 무거운 장치인데, MVP에서 확장용 CI를 돌리지 않기로 했으므로 자동화의 수혜자가 없기 때문이다. 확장을 CI에 넣는 시점에 함께 도입한다.

**2. 확장 빌드를 CI와 `release.py`에 통합하지 않는다.** spec §11이 "구현 계획에서 결정한다"고 남긴 항목이다. MVP는 수동 빌드로 간다. `.github/workflows/verify.yml`에 Node 설치와 `npm ci && npm test`를 더하면 모든 Python PR의 CI 시간이 늘고, 지금은 확장이 아직 배포 경로에 없다. `release.py`는 확장 소스를 MANIFEST에 포함하지만 VSIX를 만들지는 않는다.

두 결정 모두 2단계에서 재검토할 것이다.

## 완료 기준

1단계가 끝났다고 말하려면 다음이 모두 참이어야 한다.

- `python -m unittest discover -s tests -v` 통과
- `python verify.py` 통과
- `python release.py --check` 통과
- `cd editor-extension && npx vitest run` 통과
- `cd editor-extension && npm run typecheck` 통과
- `cd editor-extension && npm run package` 로 VSIX 생성
- `MANUAL-TEST-CHECKLIST.md`의 「에디터 확장」 항목 16개를 실제로 확인
- spec §2의 성공 기준 3개 충족:
  - 새 저장소에서 확장만으로 설치하고 `/cr` 실행까지 터미널 타이핑 0회
  - 설치 버전과 번들 버전이 다를 때 두 버전 번호를 모두 표시
  - 다른 세션이 lock을 쥔 상태에서 쓰기 명령 전송 **전에** 경고
