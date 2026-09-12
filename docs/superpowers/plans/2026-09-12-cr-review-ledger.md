# `/cr` 리뷰 원장 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/cr`의 hunk 커버리지 분모를 스크립트가 소유하게 만들어, 컴팩트로 원장이 유실되어도 미검토 hunk가 침묵 PASS가 되지 않고 `finish`에서 기계적으로 차단되게 한다.

**Architecture:** Guard 스냅샷 디렉터리 하위에 `ledger/`를 두고 `ledger.py`가 관리한다. 분모(inventory)는 스냅샷 diff와 `git diff <range>`에서 기계 생성하고, 판정은 append-only JSONL에 적재한다. `guard.py verify-review --require-ledger`가 분모와 판정을 대조해 미판정 상태의 성공 종료를 막는다. 소유권 판정은 `guard.py`를 import해 재사용하며 복제하지 않는다.

**Tech Stack:** Python 3 표준 라이브러리만 사용. `unittest` + 임시 git 저장소 + subprocess 통합 테스트. Windows·macOS·Linux 공통.

**Spec:** `docs/superpowers/specs/2026-09-12-cr-review-ledger-design.md`

## Global Constraints

- **표준 라이브러리만 사용한다.** 새 의존성을 추가하지 않는다. 패키지는 파일 복사로 설치된다.
- **Windows에서 동작해야 한다.** CI 매트릭스에 `windows-latest`가 있다. `fcntl`, `os.fork`, POSIX 전용 API를 쓰지 않는다. 잠금은 `Path.mkdir()`의 원자성을 쓴다.
- **소유권 판정을 복제하지 않는다.** `guard.py`를 import해 `repo_context`, `safe_session`, `resolve_owned_review_context`, `validate_snapshot`, `repository_fingerprint`, `list_untracked`, `run_git`, `read_json`, `emit`, `GuardError`를 재사용한다.
- **guard API 계약(검증 완료).** `GuardError(message, **details)`는 임의 kwargs를 `exc.details`에 담는다. `emit(payload, exit_code=0)`은 출력 후 `SystemExit`을 던지므로 조기 반환처럼 쓸 수 있다. `run_git(args, cwd=..., check=True)`는 실패 시 `GuardError`를 던진다.
- **출력은 guard와 동일한 JSON 형식이다.** 성공은 `{"ok": true, ...}`, 실패는 `guard.emit({"ok": false, "error": ..., "reason": ...}, exit_code=2)`.
- **워킹트리에 쓰지 않는다.** 모든 산출물은 `<git_dir>/claude-atomic-snapshots/<snapshot>/ledger/` 아래에만 만든다. 저장소 안에 쓰면 `--source-read-only` 검사에 걸린다.
- **`cca-*` 에이전트에 Bash를 부여하지 않는다.** lead 단독 writer 불변조건이다.
- **판정값은 4개뿐이다.** `PASS`, `FINDING`, `N_A`는 terminal이고 `UNKNOWN`은 차단이다.
- **기존 테스트 스타일을 따른다.** `tests/test_guard.py`처럼 `PACKAGE_ROOT` 상수, `run()` 헬퍼, 임시 git 저장소, JSON 파싱.
- **마지막에 `python3 release.py`로 MANIFEST.json과 checksums.sha256을 재생성한다.** CI가 `release.py --check`로 강제한다.
- **이 저장소는 여러 세션이 동시에 작업할 수 있다.** 각 태스크는 끝나면 즉시 커밋한다. 커밋하지 않은 산출물은 유실될 수 있다.

---

### Task 1: 기반 — guard 무결성 회귀와 원장 골격

이 설계 전체가 "`audit_snapshot`은 하위 디렉터리를 무시한다"에 의존한다. 그 가정을 가장 먼저 고정한 뒤 골격을 만든다.

**Files:**
- Modify: `tests/test_guard.py` (회귀 테스트 추가)
- Create: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Create: `tests/test_ledger.py`

**Interfaces:**
- Consumes: `guard.repo_context`, `guard.safe_session`, `guard.resolve_owned_review_context`, `guard.validate_snapshot`, `guard.read_json`, `guard.emit`, `guard.GuardError`
- Produces: `ledger.py init --session S --scope <s>...`, `ledger.py status --session S`. 내부 함수 `resolve_ledger(session, token) -> tuple[dict[str, Path], Path, Path, str]` (ctx, snapshot, ledger_dir, resolved_token), `LedgerLock(ledger_dir)` 컨텍스트 매니저, `read_run(ledger_dir) -> dict`, `write_run(ledger_dir, data) -> None`. **이후 모든 태스크는 `resolve_ledger`가 4-튜플을 반환한다고 전제한다.**

- [ ] **Step 1: guard 회귀 테스트를 작성한다**

`tests/test_guard.py`의 `GuardIntegrationTest` 클래스 안에 추가한다.

```python
    def test_ledger_subdirectory_survives_audit_and_finish(self) -> None:
        _, started = self.guard("begin", "--session", "session-ledger")
        snapshot = Path(started["snapshot"])

        generation = snapshot / "ledger" / "gen-01-abcdef12"
        generation.mkdir(parents=True)
        (generation / "inventory.jsonl").write_text("{}\n", encoding="utf-8")
        (snapshot / "ledger" / "run.json").write_text("{}", encoding="utf-8")

        _, audited = self.guard(
            "audit-snapshot",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
        )
        self.assertTrue(audited["ok"])

        _, finished = self.guard(
            "finish",
            "--session", started["session"],
            "--token", started["token"],
            "--snapshot", started["snapshot"],
            "--review-only",
            "--source-read-only",
        )
        self.assertTrue(finished["snapshot_removed"])
        self.assertFalse(snapshot.exists())
```

- [ ] **Step 2: 회귀 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_guard.GuardIntegrationTest.test_ledger_subdirectory_survives_audit_and_finish -v`
Expected: PASS. 실패하면 설계 전제가 깨진 것이므로 **즉시 중단하고 보고한다.** 이후 태스크를 진행하지 않는다.

- [ ] **Step 3: 원장 골격 테스트를 작성한다**

`tests/test_ledger.py`를 새로 만든다.

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
SCRIPTS = PACKAGE_ROOT / ".claude/skills/_git-atomic-core/scripts"
GUARD = SCRIPTS / "guard.py"
LEDGER = SCRIPTS / "ledger.py"


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and proc.returncode != 0:
        raise AssertionError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


class LedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cca-ledger-test-"))
        run(["git", "init"], self.tmp)
        run(["git", "config", "user.name", "CCA Test"], self.tmp)
        run(["git", "config", "user.email", "cca@example.invalid"], self.tmp)
        (self.tmp / "tracked.txt").write_text("base\n", encoding="utf-8")
        run(["git", "add", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: initial"], self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def script(
        self, path: Path, *args: str, check: bool = True
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        proc = run([sys.executable, str(path), *args], self.tmp, check=check)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid JSON: {proc.stdout}\n{proc.stderr}") from exc
        return proc, payload

    def guard(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.script(GUARD, *args, check=check)

    def ledger(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.script(LEDGER, *args, check=check)

    def record(self, session: str, payload: dict, check: bool = True):
        proc = subprocess.run(
            [sys.executable, str(LEDGER), "record", "--session", session],
            cwd=self.tmp, text=True, input=json.dumps(payload),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if check and proc.returncode != 0:
            raise AssertionError(f"record failed: {proc.stdout}\n{proc.stderr}")
        return proc, json.loads(proc.stdout)

    def begin(self, session: str = "session-a") -> dict:
        _, started = self.guard("begin", "--session", session)
        return started


class LedgerFoundationTest(LedgerTestCase):
    def test_status_reports_absent_ledger_before_init(self) -> None:
        started = self.begin()
        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["ok"])
        self.assertFalse(status["exists"])

    def test_init_creates_run_metadata(self) -> None:
        started = self.begin()
        _, created = self.ledger(
            "init", "--session", started["session"], "--scope", "working"
        )
        self.assertTrue(created["ok"])
        self.assertEqual(created["stage"], "init")
        self.assertEqual(created["scopes"], ["working"])

        ledger_dir = Path(started["snapshot"]) / "ledger"
        self.assertTrue((ledger_dir / "run.json").is_file())
        run_data = json.loads((ledger_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run_data["session"], started["session"])
        self.assertEqual(run_data["token"], started["token"])
        self.assertEqual(run_data["iteration"], 1)
        self.assertEqual(run_data["active_generation"], "")

        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["exists"])
        self.assertEqual(status["stage"], "init")

    def test_init_rejects_foreign_session(self) -> None:
        self.begin("session-owner")
        proc, refused = self.ledger(
            "init", "--session", "session-other", "--scope", "working", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(refused["ok"])

    def test_init_requires_active_lock(self) -> None:
        proc, refused = self.ledger(
            "init", "--session", "session-a", "--scope", "working", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(refused["ok"])

    def test_init_rejects_unknown_scope(self) -> None:
        started = self.begin()
        proc, refused = self.ledger(
            "init", "--session", started["session"], "--scope", "bogus", check=False
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_scope_invalid")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: FAIL. `ledger.py`가 없어 `run()` 헬퍼가 `command failed`로 `AssertionError`를 낸다.

- [ ] **Step 5: `ledger.py` 골격을 구현한다**

```python
#!/usr/bin/env python3
"""Machine-owned review ledger for /cr.

The ledger lives inside the Guard snapshot directory so it inherits that
directory's ownership, integrity audit and cleanup lifecycle. Only the lead
agent writes to it; reviewer subagents have no Bash tool and cannot.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import guard  # noqa: E402


LEDGER_DIR_NAME = "ledger"
RUN_NAME = "run.json"
LOCK_NAME = ".lock"
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05

STAGES = ("init", "inventory", "review", "fix", "verify", "done")
TERMINAL_VERDICTS = ("PASS", "FINDING", "N_A")
VERDICTS = TERMINAL_VERDICTS + ("UNKNOWN",)


class LedgerLock:
    """Directory-based exclusive lock.

    `fcntl.flock` is POSIX-only and this package is tested on windows-latest,
    so the lock uses `mkdir` atomicity exactly as `guard.acquire_lock` does.
    """

    def __init__(self, ledger_dir: Path) -> None:
        self.path = ledger_dir / LOCK_NAME

    def __enter__(self) -> "LedgerLock":
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self.path.mkdir(mode=0o700)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise guard.GuardError(
                        "원장 잠금을 얻지 못했습니다.",
                        reason="ledger_lock_timeout",
                        lock_path=str(self.path),
                    )
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, *exc_info: object) -> None:
        try:
            self.path.rmdir()
        except OSError:
            pass


def resolve_ledger(
    session: str, token: str | None
) -> tuple[dict[str, Path], Path, Path, str]:
    """Bind to the snapshot owned by this session, token and project root.

    Reuses guard's resolution so a lock-free `/ccf` snapshot, which carries a
    different token, is never selected. The resolved token is returned so
    callers never resolve it a second time.
    """
    ctx = guard.repo_context(Path.cwd().resolve())
    safe = guard.safe_session(session)
    resolved_token, snapshot = guard.resolve_owned_review_context(ctx, safe, token, None)
    guard.validate_snapshot(ctx, snapshot, safe, resolved_token)
    return ctx, snapshot, snapshot / LEDGER_DIR_NAME, resolved_token


def read_run(ledger_dir: Path) -> dict[str, Any]:
    data = guard.read_json(ledger_dir / RUN_NAME)
    if not data:
        raise guard.GuardError("원장이 초기화되지 않았습니다.", reason="ledger_missing")
    return data


def write_run(ledger_dir: Path, data: dict[str, Any]) -> None:
    """Replace run.json atomically; it is the only non-append-only file."""
    tmp = ledger_dir / f"{RUN_NAME}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(tmp, ledger_dir / RUN_NAME)


def validate_scopes(raw: list[str]) -> list[str]:
    scopes = []
    for value in raw:
        if value == "working":
            scopes.append(value)
            continue
        if value.startswith("range:") and ".." in value[len("range:") :]:
            scopes.append(value)
            continue
        raise guard.GuardError(
            f"알 수 없는 scope입니다: {value}", reason="ledger_scope_invalid"
        )
    if not scopes:
        raise guard.GuardError("scope가 비어 있습니다.", reason="ledger_scope_invalid")
    return scopes


def cmd_init(args: argparse.Namespace) -> None:
    scopes = validate_scopes(args.scope)
    _, _, ledger_dir, resolved_token = resolve_ledger(args.session, args.token)
    ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with LedgerLock(ledger_dir):
        data = {
            "session": guard.safe_session(args.session),
            "token": resolved_token,
            "stage": "init",
            "iteration": 1,
            "active_generation": "",
            "scopes": scopes,
        }
        write_run(ledger_dir, data)
    guard.emit({"ok": True, **data})


def cmd_status(args: argparse.Namespace) -> None:
    _, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    if not (ledger_dir / RUN_NAME).is_file():
        guard.emit({"ok": True, "exists": False})
    data = read_run(ledger_dir)
    guard.emit(
        {
            "ok": True,
            "exists": True,
            "stage": data["stage"],
            "iteration": data["iteration"],
            "active_generation": data["active_generation"],
            "scopes": data["scopes"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create the ledger for an owned snapshot")
    init.add_argument("--session", required=True)
    init.add_argument("--token")
    init.add_argument("--scope", action="append", default=[])

    status = sub.add_parser("status", help="Report ledger progress and coverage")
    status.add_argument("--session", required=True)
    status.add_argument("--token")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    handlers = {"init": cmd_init, "status": cmd_status}
    try:
        handlers[args.command](args)
    except guard.GuardError as exc:
        guard.emit({"ok": False, "error": str(exc), **exc.details}, exit_code=2)
    except KeyboardInterrupt:
        guard.emit({"ok": False, "error": "사용자 중단"}, exit_code=130)
    except Exception as exc:
        guard.emit(
            {"ok": False, "error": f"예기치 않은 ledger 오류: {type(exc).__name__}: {exc}"},
            exit_code=3,
        )


if __name__ == "__main__":
    main()
```

`guard.emit`은 `SystemExit`을 던지고 `SystemExit`은 `Exception`이 아니라 `BaseException`을 상속하므로, 위 `except Exception` 절이 정상 출력을 삼키지 않는다.

- [ ] **Step 6: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger tests.test_guard -v`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add tests/test_guard.py tests/test_ledger.py .claude/skills/_git-atomic-core/scripts/ledger.py
git commit -m "feat(ledger): 원장 골격과 스냅샷 소유권 바인딩 추가"
```

---

### Task 2: Inventory — working scope 4종 분류

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 1의 `resolve_ledger`(4-튜플), `LedgerLock`, `read_run`, `write_run`
- Produces: `ledger.py inventory --session S`. 내부 함수 `parse_diff_entries(diff: bytes, source: str) -> list[dict]`, `untracked_entries(snapshot) -> list[dict]`, `working_scope_entries(snapshot) -> list[dict]`, `fingerprint_short(ctx) -> str`, `generation_name(iteration: int, short: str) -> str`. inventory 레코드는 `{"id", "kind", "source", "path", "header"}` 형태다.

- [ ] **Step 1: 4종 분류 테스트를 작성한다**

`tests/test_ledger.py`에 추가한다.

```python
class InventoryWorkingScopeTest(LedgerTestCase):
    def init_ledger(self) -> dict:
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        return started

    def ids_by_kind(self, payload: dict) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for entry in payload["entries"]:
            grouped.setdefault(entry["kind"], []).append(entry["id"])
        return grouped

    def test_text_change_produces_hunk_entries(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        self.assertTrue(built["ok"])
        grouped = self.ids_by_kind(built)
        self.assertIn("hunk", grouped)
        self.assertTrue(
            any(entry.startswith("working:tracked.txt#") for entry in grouped["hunk"])
        )

    def test_untracked_file_produces_untracked_entry(self) -> None:
        (self.tmp / "new.txt").write_text("fresh\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["untracked"], ["untracked:new.txt#0"])

    def test_binary_change_produces_binary_entry(self) -> None:
        target = self.tmp / "blob.bin"
        target.write_bytes(bytes(range(256)))
        run(["git", "add", "blob.bin"], self.tmp)
        run(["git", "commit", "-m", "test: binary"], self.tmp)
        target.write_bytes(bytes(range(255, -1, -1)))
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["binary"], ["working:blob.bin#0"])

    def test_mode_only_change_produces_meta_entry(self) -> None:
        if sys.platform.startswith("win"):
            self.skipTest("Windows는 실행 비트를 추적하지 않는다")
        run(["git", "update-index", "--chmod=+x", "tracked.txt"], self.tmp)
        run(["git", "commit", "-m", "test: chmod"], self.tmp)
        run(["git", "update-index", "--chmod=-x", "tracked.txt"], self.tmp)
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        grouped = self.ids_by_kind(built)
        self.assertEqual(grouped["meta"], ["staged:tracked.txt#0"])

    def test_inventory_is_written_to_active_generation(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, built = self.ledger("inventory", "--session", started["session"])
        generation = built["generation"]
        self.assertTrue(generation.startswith("gen-01-"))
        path = Path(started["snapshot"]) / "ledger" / generation / "inventory.jsonl"
        self.assertTrue(path.is_file())
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(len(lines), built["total"])

    def test_inventory_is_idempotent(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.init_ledger()
        _, first = self.ledger("inventory", "--session", started["session"])
        _, second = self.ledger("inventory", "--session", started["session"])
        self.assertEqual(first["total"], second["total"])
        self.assertEqual(first["generation"], second["generation"])
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.InventoryWorkingScopeTest -v`
Expected: FAIL. `inventory`가 알 수 없는 서브커맨드라 argparse가 exit 2로 끝나고 JSON 파싱이 실패한다.

- [ ] **Step 3: diff 파서를 구현한다**

`ledger.py`에 추가한다.

```python
GENERATION_PREFIX = "gen"
INVENTORY_NAME = "inventory.jsonl"


def decode_path(raw: str) -> str:
    """Undo git's C-style quoting for paths with special characters."""
    if not raw.startswith('"'):
        return raw
    return json.loads(raw)


def parse_diff_entries(diff: bytes, source: str) -> list[dict[str, Any]]:
    """Split a git diff into hunk, binary and meta entries.

    Every changed file yields at least one entry. A file whose diff carries no
    `@@` hunk is a mode or rename change and becomes a `meta` entry, so it can
    never disappear from the denominator.
    """
    entries: list[dict[str, Any]] = []
    state: dict[str, Any] = {"path": None, "index": 0, "saw_hunk": False, "binary": False}

    def flush() -> None:
        path = state["path"]
        if path is None:
            return
        if state["binary"]:
            kind = "binary"
        elif not state["saw_hunk"]:
            kind = "meta"
        else:
            kind = None
        if kind is not None:
            entries.append(
                {
                    "id": f"{source}:{path}#0",
                    "kind": kind,
                    "source": source,
                    "path": path,
                    "header": "",
                }
            )
        state.update({"path": None, "index": 0, "saw_hunk": False, "binary": False})

    for raw_line in diff.split(b"\n"):
        line = raw_line.decode("utf-8", "replace")
        if line.startswith("diff --git "):
            flush()
            remainder = line[len("diff --git ") :]
            state["path"] = (
                decode_path(remainder.split(" b/", 1)[-1])
                if " b/" in remainder
                else remainder
            )
            continue
        if state["path"] is None:
            continue
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            state["binary"] = True
            continue
        if line.startswith("@@"):
            state["saw_hunk"] = True
            state["index"] += 1
            entries.append(
                {
                    "id": f"{source}:{state['path']}#{state['index']}",
                    "kind": "hunk",
                    "source": source,
                    "path": state["path"],
                    "header": line.strip(),
                }
            )
    flush()
    return entries


def untracked_record(path: str) -> dict[str, Any]:
    return {
        "id": f"untracked:{path}#0",
        "kind": "untracked",
        "source": "untracked",
        "path": path,
        "header": "",
    }


def untracked_entries(snapshot: Path) -> list[dict[str, Any]]:
    raw = (snapshot / "untracked.z").read_bytes()
    return [
        untracked_record(chunk.decode("utf-8", "replace"))
        for chunk in raw.split(b"\0")
        if chunk
    ]


def working_scope_entries(snapshot: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    entries.extend(parse_diff_entries((snapshot / "staged.diff").read_bytes(), "staged"))
    entries.extend(parse_diff_entries((snapshot / "working.diff").read_bytes(), "working"))
    entries.extend(untracked_entries(snapshot))
    return entries


def fingerprint_short(ctx: dict[str, Path]) -> str:
    return guard.repository_fingerprint(ctx["root"])["fingerprint"][:8]


def generation_name(iteration: int, short: str) -> str:
    return f"{GENERATION_PREFIX}-{iteration:02d}-{short}"


def write_inventory(gen_dir: Path, entries: list[dict[str, Any]]) -> None:
    with (gen_dir / INVENTORY_NAME).open("w", encoding="utf-8", newline="\n") as stream:
        for entry in entries:
            stream.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
```

- [ ] **Step 4: `inventory` 명령을 구현한다**

```python
def cmd_inventory(args: argparse.Namespace) -> None:
    ctx, snapshot, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        name = data["active_generation"] or generation_name(
            data["iteration"], fingerprint_short(ctx)
        )
        gen_dir = ledger_dir / name
        gen_dir.mkdir(mode=0o700, exist_ok=True)

        entries: list[dict[str, Any]] = []
        for scope in data["scopes"]:
            if scope == "working":
                entries.extend(working_scope_entries(snapshot))
        write_inventory(gen_dir, entries)

        data["active_generation"] = name
        data["stage"] = "inventory"
        write_run(ledger_dir, data)

    guard.emit({"ok": True, "generation": name, "total": len(entries), "entries": entries})
```

`build_parser()`에 추가한다.

```python
    inventory = sub.add_parser("inventory", help="Build the machine-owned denominator")
    inventory.add_argument("--session", required=True)
    inventory.add_argument("--token")
```

`main()`의 `handlers`에 `"inventory": cmd_inventory`를 추가한다.

- [ ] **Step 5: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): working scope inventory와 hunk/binary/meta/untracked 분류 추가"
```

---

### Task 3: Inventory — 커밋 범위 scope

working hunk만 분모로 삼으면 `/cr weekly`나 PR 리뷰에서 동일한 침묵 PASS가 재발한다.

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 2의 `parse_diff_entries`
- Produces: `range_scope_entries(ctx, spec: str) -> list[dict]`. id는 `range:<path>#<n>` 형태다.

- [ ] **Step 1: 범위 scope 테스트를 작성한다**

```python
class InventoryRangeScopeTest(LedgerTestCase):
    def make_range(self) -> str:
        base = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        (self.tmp / "ranged.txt").write_text("one\n", encoding="utf-8")
        run(["git", "add", "ranged.txt"], self.tmp)
        run(["git", "commit", "-m", "test: ranged"], self.tmp)
        head = run(["git", "rev-parse", "HEAD"], self.tmp).stdout.strip()
        return f"{base}..{head}"

    def test_range_scope_covers_committed_hunks(self) -> None:
        spec = self.make_range()
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", "working", "--scope", f"range:{spec}",
        )
        _, built = self.ledger("inventory", "--session", started["session"])
        ranged = [entry for entry in built["entries"] if entry["source"] == "range"]
        self.assertTrue(any(entry["path"] == "ranged.txt" for entry in ranged))

    def test_invalid_range_fails_closed(self) -> None:
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"], "--scope", "range:deadbeef..cafebabe"
        )
        proc, refused = self.ledger("inventory", "--session", started["session"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_range_unresolved")
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.InventoryRangeScopeTest -v`
Expected: FAIL. 범위 scope가 무시되어 `ranged` 리스트가 비고, 잘못된 범위도 통과한다.

- [ ] **Step 3: 범위 수집을 구현한다**

```python
def range_scope_entries(ctx: dict[str, Path], spec: str) -> list[dict[str, Any]]:
    """Enumerate hunks in a committed range.

    The snapshot only captures working state, so `--base`, `--range`, `pr` and
    the period modes need their denominator computed here instead.
    """
    expression = spec[len("range:") :]
    try:
        diff = guard.run_git(
            ["diff", "--binary", "--full-index", "--no-ext-diff", expression],
            cwd=ctx["root"],
        )
    except guard.GuardError as exc:
        raise guard.GuardError(
            f"커밋 범위를 해석하지 못했습니다: {expression}",
            reason="ledger_range_unresolved",
            range=expression,
        ) from exc
    return parse_diff_entries(diff, "range")
```

`cmd_inventory`의 scope 루프를 교체한다.

```python
        for scope in data["scopes"]:
            if scope == "working":
                entries.extend(working_scope_entries(snapshot))
            else:
                entries.extend(range_scope_entries(ctx, scope))
```

- [ ] **Step 4: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: PASS

- [ ] **Step 5: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): 커밋 범위 scope inventory 추가"
```

---

### Task 4: record — 판정 적재와 반-위조 검증

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 2의 `INVENTORY_NAME`
- Produces: `ledger.py record --session S` (stdin JSON). 내부 함수 `read_jsonl(path) -> list[dict]` (마지막 한 줄의 파손만 허용), `append_jsonl(path, records) -> None`, `active_generation_dir(ledger_dir, data) -> Path`, `inventory_ids(gen_dir) -> set[str]`. 상수 `HUNKS_NAME`, `FINDINGS_NAME`, `REVIEWERS_NAME`.

- [ ] **Step 1: record 테스트를 작성한다**

```python
class RecordTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, [entry["id"] for entry in built["entries"]]

    def test_record_accepts_known_ids(self) -> None:
        started, ids = self.prepared()
        _, saved = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "PASS", "reviewer": "cca-line-reviewer"}]},
        )
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["recorded_verdicts"], 1)

    def test_record_rejects_fabricated_id(self) -> None:
        started, _ = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": "working:does-not-exist.py#9", "verdict": "PASS"}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_unknown_id")

    def test_record_rejects_invalid_verdict(self) -> None:
        started, ids = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "LOOKS_FINE"}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_invalid_verdict")

    def test_finding_verdict_requires_finding_record(self) -> None:
        started, ids = self.prepared()
        proc, refused = self.record(
            started["session"],
            {"verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}]},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_finding_missing")

    def test_finding_verdict_accepted_with_finding(self) -> None:
        started, ids = self.prepared()
        _, saved = self.record(
            started["session"],
            {
                "verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}],
                "findings": [{"id": "f-1", "severity": "MAJOR", "file": "tracked.txt"}],
            },
        )
        self.assertEqual(saved["recorded_findings"], 1)

    def test_reader_tolerates_one_truncated_trailing_line(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        hunks = (
            Path(started["snapshot"]) / "ledger" / status["active_generation"] / "hunks.jsonl"
        )
        with hunks.open("a", encoding="utf-8") as stream:
            stream.write('{"id": "truncated"')
        _, again = self.ledger("status", "--session", started["session"])
        self.assertTrue(again["ok"])

    def test_concurrent_records_do_not_lose_entries(self) -> None:
        started, ids = self.prepared()
        processes = [
            subprocess.Popen(
                [sys.executable, str(LEDGER), "record", "--session", started["session"]],
                cwd=self.tmp, text=True, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            for _ in range(4)
        ]
        for index, proc in enumerate(processes):
            proc.communicate(
                json.dumps(
                    {"verdicts": [{"id": ids[0], "verdict": "PASS", "reviewer": f"r{index}"}]}
                )
            )
        for proc in processes:
            self.assertEqual(proc.returncode, 0)

        _, status = self.ledger("status", "--session", started["session"])
        hunks = (
            Path(started["snapshot"]) / "ledger" / status["active_generation"] / "hunks.jsonl"
        )
        lines = [line for line in hunks.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 4)
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.RecordTest -v`
Expected: FAIL. `record` 서브커맨드가 없다.

- [ ] **Step 3: JSONL 입출력을 구현한다**

```python
HUNKS_NAME = "hunks.jsonl"
FINDINGS_NAME = "findings.jsonl"
REVIEWERS_NAME = "reviewers.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read append-only records, tolerating one torn trailing line.

    A crash during append can leave a partial last line. That must not
    invalidate every record written before it.
    """
    if not path.is_file():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records: list[dict[str, Any]] = []
    for position, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            if position == len(lines) - 1:
                break
            raise guard.GuardError(
                "원장 레코드가 손상되었습니다.",
                reason="ledger_corrupt",
                path=str(path),
                line=position + 1,
            )
    return records


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    payload = "".join(
        json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n" for record in records
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def active_generation_dir(ledger_dir: Path, data: dict[str, Any]) -> Path:
    name = data.get("active_generation") or ""
    if not name:
        raise guard.GuardError(
            "활성 세대가 없습니다. inventory를 먼저 실행하십시오.",
            reason="ledger_no_generation",
        )
    return ledger_dir / name


def inventory_ids(gen_dir: Path) -> set[str]:
    return {record["id"] for record in read_jsonl(gen_dir / INVENTORY_NAME)}
```

- [ ] **Step 4: `record` 명령을 구현한다**

```python
def cmd_record(args: argparse.Namespace) -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise guard.GuardError(
            "record 입력 JSON을 읽을 수 없습니다.", reason="ledger_bad_input"
        ) from exc
    if not isinstance(payload, dict):
        raise guard.GuardError(
            "record 입력은 JSON object여야 합니다.", reason="ledger_bad_input"
        )

    verdicts = payload.get("verdicts") or []
    findings = payload.get("findings") or []
    reviewers = payload.get("reviewers") or []

    _, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        gen_dir = active_generation_dir(ledger_dir, data)
        known = inventory_ids(gen_dir)
        finding_ids = {record.get("id") for record in read_jsonl(gen_dir / FINDINGS_NAME)}
        finding_ids.update(record.get("id") for record in findings)

        for verdict in verdicts:
            identifier = verdict.get("id")
            if identifier not in known:
                raise guard.GuardError(
                    f"inventory에 없는 id입니다: {identifier}",
                    reason="ledger_unknown_id",
                    id=identifier,
                )
            if verdict.get("verdict") not in VERDICTS:
                raise guard.GuardError(
                    f"허용되지 않는 판정입니다: {verdict.get('verdict')}",
                    reason="ledger_invalid_verdict",
                    id=identifier,
                )
            if verdict.get("verdict") == "FINDING":
                linked = verdict.get("finding_ids") or []
                missing = [value for value in linked if value not in finding_ids]
                if not linked or missing:
                    raise guard.GuardError(
                        "FINDING 판정에는 대응하는 finding 레코드가 필요합니다.",
                        reason="ledger_finding_missing",
                        id=identifier,
                        missing=missing,
                    )

        append_jsonl(gen_dir / FINDINGS_NAME, findings)
        append_jsonl(gen_dir / HUNKS_NAME, verdicts)
        if reviewers:
            existing = guard.read_json(gen_dir / REVIEWERS_NAME) or {}
            for reviewer in reviewers:
                existing[reviewer["name"]] = reviewer.get("status", "UNKNOWN")
            tmp = gen_dir / f"{REVIEWERS_NAME}.tmp"
            tmp.write_text(json.dumps(existing, ensure_ascii=True, indent=2), encoding="utf-8")
            os.replace(tmp, gen_dir / REVIEWERS_NAME)

        data["stage"] = "review"
        write_run(ledger_dir, data)

    guard.emit(
        {
            "ok": True,
            "recorded_verdicts": len(verdicts),
            "recorded_findings": len(findings),
            "recorded_reviewers": len(reviewers),
        }
    )
```

`build_parser()`에 추가한다.

```python
    record = sub.add_parser("record", help="Append verdicts, findings and reviewer status")
    record.add_argument("--session", required=True)
    record.add_argument("--token")
```

`main()`의 `handlers`에 `"record": cmd_record`를 추가한다.

- [ ] **Step 5: `status`가 손상 내성 경로를 거치게 한다**

`cmd_status`의 `read_run(ledger_dir)` 호출 뒤, `guard.emit` 앞에 추가한다.

```python
    generation = data.get("active_generation") or ""
    if generation:
        read_jsonl(ledger_dir / generation / HUNKS_NAME)
```

- [ ] **Step 6: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): 판정 적재와 inventory 대조 기반 반-위조 검증 추가"
```

---

### Task 5: advance — 세대 전이

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 2의 `generation_name`, `write_inventory`, `parse_diff_entries`, `untracked_record`, Task 3의 `range_scope_entries`
- Produces: `ledger.py advance --session S --fingerprint <hex>`, `live_scope_entries(ctx, scopes) -> list[dict]`

- [ ] **Step 1: 세대 전이 테스트를 작성한다**

```python
class AdvanceTest(LedgerTestCase):
    def started_with_inventory(self) -> tuple[dict, dict]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, built

    def test_advance_creates_new_generation_from_live_diff(self) -> None:
        started, first = self.started_with_inventory()
        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        _, advanced = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.assertTrue(advanced["ok"])
        self.assertEqual(advanced["iteration"], 2)
        self.assertNotEqual(advanced["generation"], first["generation"])
        self.assertTrue(advanced["generation"].startswith("gen-02-"))

    def test_previous_generation_stays_immutable(self) -> None:
        started, first = self.started_with_inventory()
        ledger_dir = Path(started["snapshot"]) / "ledger"
        original = (ledger_dir / first["generation"] / "inventory.jsonl").read_bytes()

        (self.tmp / "tracked.txt").write_text("base\nadded\nmore\n", encoding="utf-8")
        _, fingerprint = self.guard("fingerprint")
        self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", fingerprint["fingerprint"],
        )
        self.assertEqual(
            (ledger_dir / first["generation"] / "inventory.jsonl").read_bytes(), original
        )

    def test_advance_rejects_stale_fingerprint(self) -> None:
        started, _ = self.started_with_inventory()
        proc, refused = self.ledger(
            "advance", "--session", started["session"],
            "--fingerprint", "0" * 64, check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_fingerprint_mismatch")
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.AdvanceTest -v`
Expected: FAIL. `advance` 서브커맨드가 없다.

- [ ] **Step 3: `advance`를 구현한다**

```python
def live_scope_entries(ctx: dict[str, Path], scopes: list[str]) -> list[dict[str, Any]]:
    """Build the denominator from the live worktree, not the snapshot.

    The snapshot holds the pre-fix diff, so a post-fix generation must read
    current state instead.
    """
    entries: list[dict[str, Any]] = []
    for scope in scopes:
        if scope != "working":
            entries.extend(range_scope_entries(ctx, scope))
            continue
        entries.extend(
            parse_diff_entries(
                guard.run_git(
                    ["diff", "--cached", "--binary", "--full-index", "--no-ext-diff"],
                    cwd=ctx["root"],
                ),
                "staged",
            )
        )
        entries.extend(
            parse_diff_entries(
                guard.run_git(
                    ["diff", "--binary", "--full-index", "--no-ext-diff"],
                    cwd=ctx["root"],
                ),
                "working",
            )
        )
        entries.extend(untracked_record(path) for path in guard.list_untracked(ctx["root"]))
    return entries


def cmd_advance(args: argparse.Namespace) -> None:
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    current = guard.repository_fingerprint(ctx["root"])["fingerprint"]
    if args.fingerprint != current:
        raise guard.GuardError(
            "전달된 fingerprint가 현재 저장소 상태와 다릅니다.",
            reason="ledger_fingerprint_mismatch",
            expected=current,
            received=args.fingerprint,
        )
    with LedgerLock(ledger_dir):
        data = read_run(ledger_dir)
        data["iteration"] = int(data["iteration"]) + 1
        name = generation_name(data["iteration"], current[:8])
        gen_dir = ledger_dir / name
        gen_dir.mkdir(mode=0o700, exist_ok=True)

        entries = live_scope_entries(ctx, data["scopes"])
        write_inventory(gen_dir, entries)

        data["active_generation"] = name
        data["stage"] = "review"
        write_run(ledger_dir, data)

    guard.emit(
        {"ok": True, "generation": name, "iteration": data["iteration"], "total": len(entries)}
    )
```

`build_parser()`에 추가한다.

```python
    advance = sub.add_parser("advance", help="Open a new generation after a fix")
    advance.add_argument("--session", required=True)
    advance.add_argument("--token")
    advance.add_argument("--fingerprint", required=True)
```

`main()`의 `handlers`에 `"advance": cmd_advance`를 추가한다.

- [ ] **Step 4: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: PASS

- [ ] **Step 5: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): --fix 이후 세대 전이와 live diff 기반 분모 재생성 추가"
```

---

### Task 6: 커버리지 집계 — status 확장과 report

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py`
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 4의 `read_jsonl`
- Produces: `coverage(ctx, ledger_dir, data) -> dict`. 반환 키는 `complete`, `fingerprint_matches_current`, `generation`, `total`, `pending`, `pending_count`, `unknown`, `unknown_count`, `by_verdict`, `scopes`, `reviewers`다. **Task 7의 `ledger_gate`가 이 키 집합에 의존한다.** `ledger.py report --session S`.

- [ ] **Step 1: 집계 테스트를 작성한다**

```python
class CoverageTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, [entry["id"] for entry in built["entries"]]

    def test_status_reports_incomplete_coverage(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertFalse(status["complete"])
        self.assertGreater(status["pending_count"], 0)

    def test_status_reports_complete_coverage(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, status = self.ledger("status", "--session", started["session"])
        self.assertTrue(status["complete"])
        self.assertEqual(status["pending"], [])

    def test_unknown_verdict_blocks_completion(self) -> None:
        started, ids = self.prepared()
        verdicts = [{"id": identifier, "verdict": "PASS"} for identifier in ids[1:]]
        verdicts.append({"id": ids[0], "verdict": "UNKNOWN"})
        self.record(started["session"], {"verdicts": verdicts})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertFalse(status["complete"])
        self.assertEqual(status["unknown"], [ids[0]])

    def test_latest_verdict_wins_for_same_id(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "UNKNOWN"}]})
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, status = self.ledger("status", "--session", started["session"])
        self.assertEqual(status["unknown"], [])

    def test_report_emits_findings_and_counts(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {
                "verdicts": [{"id": ids[0], "verdict": "FINDING", "finding_ids": ["f-1"]}],
                "findings": [{"id": "f-1", "severity": "MAJOR", "file": "tracked.txt"}],
            },
        )
        _, report = self.ledger("report", "--session", started["session"])
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["findings"][0]["id"], "f-1")
        self.assertEqual(report["coverage"]["by_verdict"]["FINDING"], 1)
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.CoverageTest -v`
Expected: FAIL. `status`에 `complete` 키가 없고 `report` 서브커맨드가 없다.

- [ ] **Step 3: `coverage`를 구현한다**

```python
PENDING_SAMPLE_LIMIT = 20


def latest_verdicts(gen_dir: Path) -> dict[str, str]:
    """Collapse the append-only log so the last write for an id wins."""
    resolved: dict[str, str] = {}
    for record in read_jsonl(gen_dir / HUNKS_NAME):
        identifier = record.get("id")
        if isinstance(identifier, str):
            resolved[identifier] = record.get("verdict", "UNKNOWN")
    return resolved


def coverage(ctx: dict[str, Path], ledger_dir: Path, data: dict[str, Any]) -> dict[str, Any]:
    generation = data.get("active_generation") or ""
    if not generation:
        return {
            "complete": False,
            "fingerprint_matches_current": False,
            "generation": "",
            "total": 0,
            "pending": [],
            "pending_count": 0,
            "unknown": [],
            "unknown_count": 0,
            "by_verdict": {},
            "scopes": [],
            "reviewers": {},
        }

    gen_dir = ledger_dir / generation
    entries = read_jsonl(gen_dir / INVENTORY_NAME)
    resolved = latest_verdicts(gen_dir)

    by_verdict = {name: 0 for name in VERDICTS}
    pending: list[str] = []
    unknown: list[str] = []
    per_scope: dict[str, dict[str, int]] = {}

    for entry in entries:
        identifier = entry["id"]
        bucket = per_scope.setdefault(entry["source"], {"total": 0, "covered": 0})
        bucket["total"] += 1
        verdict = resolved.get(identifier)
        if verdict is None:
            pending.append(identifier)
            continue
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        if verdict == "UNKNOWN":
            unknown.append(identifier)
            continue
        bucket["covered"] += 1

    current = guard.repository_fingerprint(ctx["root"])["fingerprint"]
    expected = generation.rsplit("-", 1)[-1]

    return {
        "complete": not pending and not unknown,
        "fingerprint_matches_current": current.startswith(expected),
        "generation": generation,
        "total": len(entries),
        "pending": pending[:PENDING_SAMPLE_LIMIT],
        "pending_count": len(pending),
        "unknown": unknown[:PENDING_SAMPLE_LIMIT],
        "unknown_count": len(unknown),
        "by_verdict": by_verdict,
        "scopes": [
            {"source": source, **counts} for source, counts in sorted(per_scope.items())
        ],
        "reviewers": guard.read_json(gen_dir / REVIEWERS_NAME) or {},
    }
```

- [ ] **Step 4: `cmd_status`를 집계 기반으로 교체하고 `cmd_report`를 추가한다**

`cmd_status` 전체를 아래로 바꾼다. Task 4 Step 5에서 넣은 `read_jsonl` 호출은 `coverage`가 대신하므로 제거한다.

```python
def cmd_status(args: argparse.Namespace) -> None:
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    if not (ledger_dir / RUN_NAME).is_file():
        guard.emit({"ok": True, "exists": False})
    data = read_run(ledger_dir)
    guard.emit(
        {
            "ok": True,
            "exists": True,
            "stage": data["stage"],
            "iteration": data["iteration"],
            "active_generation": data["active_generation"],
            "scopes_declared": data["scopes"],
            **coverage(ctx, ledger_dir, data),
        }
    )


def cmd_report(args: argparse.Namespace) -> None:
    ctx, _, ledger_dir, _ = resolve_ledger(args.session, args.token)
    data = read_run(ledger_dir)
    summary = coverage(ctx, ledger_dir, data)
    generation = data.get("active_generation") or ""
    findings = read_jsonl(ledger_dir / generation / FINDINGS_NAME) if generation else []
    guard.emit(
        {
            "ok": True,
            "generation": generation,
            "iteration": data["iteration"],
            "coverage": summary,
            "findings": findings,
        }
    )
```

`build_parser()`에 추가한다.

```python
    report = sub.add_parser("report", help="Emit findings and coverage for the final report")
    report.add_argument("--session", required=True)
    report.add_argument("--token")
```

`main()`의 `handlers`에 `"report": cmd_report`를 추가한다.

- [ ] **Step 5: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger -v`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "feat(ledger): 커버리지 집계와 최종 보고용 report 추가"
```

---

### Task 7: guard 게이트 통합

미판정 hunk가 남은 채 `/cr`이 성공 종료하는 것을 여기서 막는다. 이 태스크가 문제의 본질을 제거한다.

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/guard.py` (`review_invariants` 뒤에 함수 추가, `cmd_verify_review`, `cmd_finish`, `build_parser`)
- Modify: `tests/test_ledger.py`

**Interfaces:**
- Consumes: Task 6의 `coverage`, Task 1의 `LEDGER_DIR_NAME`·`RUN_NAME`·`read_run`
- Produces: `guard.py verify-review --require-ledger [--allow-unledgered]`, `guard.py finish --require-ledger [--allow-unledgered]`

`ledger.py`가 `guard.py`를 import하므로 guard에서의 import는 **함수 안에서 지연 실행**한다. 모듈 최상단에 두면 순환 import가 된다.

- [ ] **Step 1: 게이트 테스트를 작성한다**

```python
class GateTest(LedgerTestCase):
    def prepared(self) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        self.ledger("init", "--session", started["session"], "--scope", "working")
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, [entry["id"] for entry in built["entries"]]

    def test_incomplete_ledger_blocks_verify_review(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")
        self.assertGreater(refused["pending_count"], 0)

    def test_complete_ledger_passes_verify_review(self) -> None:
        started, ids = self.prepared()
        self.record(
            started["session"],
            {"verdicts": [{"id": identifier, "verdict": "PASS"} for identifier in ids]},
        )
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger"]["complete"])

    def test_unknown_verdict_blocks_verify_review(self) -> None:
        started, ids = self.prepared()
        verdicts = [{"id": identifier, "verdict": "PASS"} for identifier in ids[1:]]
        verdicts.append({"id": ids[0], "verdict": "UNKNOWN"})
        self.record(started["session"], {"verdicts": verdicts})
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_unknown")

    def test_missing_ledger_blocks_verify_review(self) -> None:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        proc, refused = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_missing")

    def test_allow_unledgered_passes_with_bypass_marker(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        _, verified = self.guard(
            "verify-review", "--session", started["session"],
            "--source-read-only", "--require-ledger", "--allow-unledgered",
        )
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["ledger_bypassed"])
        self.assertGreater(verified["ledger"]["pending_count"], 0)

    def test_finish_enforces_the_same_gate(self) -> None:
        started, ids = self.prepared()
        self.record(started["session"], {"verdicts": [{"id": ids[0], "verdict": "PASS"}]})
        proc, refused = self.guard(
            "finish", "--session", started["session"],
            "--review-only", "--source-read-only", "--require-ledger", check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_incomplete")
        self.assertTrue(Path(started["snapshot"]).exists())
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `python3 -m unittest tests.test_ledger.GateTest -v`
Expected: FAIL. `--require-ledger`가 알 수 없는 인자라 argparse가 exit 2로 끝난다.

- [ ] **Step 3: guard에 원장 검사를 추가한다**

`guard.py`의 `review_invariants` 함수 정의 바로 뒤에 추가한다.

```python
def ledger_gate(
    ctx: dict[str, Path],
    snapshot: Path,
    *,
    allow_unledgered: bool,
) -> dict[str, Any]:
    """Compare the machine-owned denominator against recorded verdicts.

    Imported lazily: ledger.py imports guard.py, so a module-level import here
    would be circular.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger

    ledger_dir = snapshot / ledger.LEDGER_DIR_NAME
    if not (ledger_dir / ledger.RUN_NAME).is_file():
        if allow_unledgered:
            return {"complete": False, "reason": "ledger_missing", "pending_count": 0}
        raise GuardError(
            "리뷰 원장이 없어 커버리지를 확인할 수 없습니다.",
            reason="ledger_missing",
            ledger_dir=str(ledger_dir),
        )

    data = ledger.read_run(ledger_dir)
    summary = ledger.coverage(ctx, ledger_dir, data)

    if allow_unledgered:
        return summary
    if not summary["fingerprint_matches_current"]:
        raise GuardError(
            "원장의 활성 세대가 현재 저장소 상태와 다릅니다. advance가 누락되었습니다.",
            reason="ledger_stale",
            generation=summary["generation"],
        )
    if summary["unknown_count"]:
        raise GuardError(
            "UNKNOWN 판정이 남아 있어 완료할 수 없습니다.",
            reason="ledger_unknown",
            unknown_count=summary["unknown_count"],
            unknown=summary["unknown"],
        )
    if summary["pending_count"]:
        raise GuardError(
            "미판정 hunk가 남아 있어 완료할 수 없습니다.",
            reason="ledger_incomplete",
            pending_count=summary["pending_count"],
            pending=summary["pending"],
        )
    return summary
```

- [ ] **Step 4: `cmd_verify_review`에 연결한다**

`cmd_verify_review`의 `emit(result)` 바로 앞에 추가한다.

```python
    if args.require_ledger:
        summary = ledger_gate(ctx, snapshot, allow_unledgered=args.allow_unledgered)
        result["ledger"] = summary
        result["ledger_bypassed"] = bool(args.allow_unledgered) and not summary["complete"]
```

- [ ] **Step 5: `cmd_finish`에 연결한다**

`cmd_finish`의 `review_result` 블록 바로 뒤, `dirty = decode(...)` 앞에 추가한다. 스냅샷 삭제보다 앞이어야 차단 시 스냅샷이 보존된다.

```python
    ledger_result = None
    ledger_bypassed = False
    if args.require_ledger:
        ledger_result = ledger_gate(ctx, snapshot, allow_unledgered=args.allow_unledgered)
        ledger_bypassed = bool(args.allow_unledgered) and not ledger_result["complete"]
```

같은 함수의 `emit` payload 딕셔너리에 두 줄을 추가한다.

```python
            "ledger": ledger_result,
            "ledger_bypassed": ledger_bypassed,
```

- [ ] **Step 6: parser에 플래그를 추가한다**

`build_parser()`의 `verify_review` 파서에 추가한다.

```python
    verify_review.add_argument("--require-ledger", action="store_true")
    verify_review.add_argument("--allow-unledgered", action="store_true")
```

`finish` 파서에도 추가한다.

```python
    finish.add_argument("--require-ledger", action="store_true")
    finish.add_argument("--allow-unledgered", action="store_true")
```

- [ ] **Step 7: 테스트를 실행해 통과를 확인한다**

Run: `python3 -m unittest tests.test_ledger tests.test_guard -v`
Expected: PASS

- [ ] **Step 8: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/guard.py tests/test_ledger.py
git commit -m "feat(guard): verify-review와 finish에 원장 커버리지 게이트 추가"
```

---

### Task 8: 문서 계약 반영

스크립트가 있어도 SKILL.md가 호출하지 않으면 아무 일도 일어나지 않는다.

**Files:**
- Modify: `.claude/skills/cr/SKILL.md`
- Modify: `.claude/skills/_git-atomic-core/deep-review-protocol.md`
- Modify: `.claude/skills/_git-atomic-core/large-diff-review.md`
- Modify: `.claude/skills/_git-atomic-core/review-execution.md`
- Modify: `.claude/skills/_git-atomic-core/recovery.md`
- Modify: `.claude/skills/_git-atomic-core/reporting.md`

- [ ] **Step 1: `cr/SKILL.md`의 `allowed-tools`에 원장 스크립트를 추가한다**

`report_validator.py` 줄 아래에 추가한다.

```yaml
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" *)'
```

- [ ] **Step 2: `cr/SKILL.md`에 원장 초기화와 재개 절을 추가한다**

`## 1. Guard와 시작 불변식` 섹션 끝, `## 2. 변경 전체 스캔` 앞에 넣는다.

````markdown
## 1.5 리뷰 원장 초기화와 재개

Guard `begin` 직후 원장 상태를 먼저 확인한다.

```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" status \
  --session "$COMMITFORGE_SESSION_ID"
```

- `exists`가 `false`면 신규 실행이다. `init`으로 scope를 선언한 뒤 `inventory`로 분모를 만든다.
- `exists`가 `true`이고 `fingerprint_matches_current`가 `true`면 **처음부터 다시 리뷰하지 않는다.** `pending`에 남은 id만 이어서 검토한다. 컴팩트로 대화 기억을 잃었더라도 원장이 진행 상황의 정본이다.
- `fingerprint_matches_current`가 `false`면 원장과 저장소가 어긋난 상태다. 임의로 진행하지 말고 사용자에게 보고한다.

scope는 실제 리뷰 대상과 일치해야 한다. 기본은 `working`이며, `--base`·`--range`·`pr`·`today`·`3days`·`weekly`는 해당 커밋 범위를 함께 선언한다.

```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" init \
  --session "$COMMITFORGE_SESSION_ID" --scope working --scope "range:<A>..<B>"
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" inventory \
  --session "$COMMITFORGE_SESSION_ID"
```

`inventory`가 반환한 id 집합이 커버리지의 분모다. 이 목록을 직접 만들거나 수정하지 않는다.
````

- [ ] **Step 3: `cr/SKILL.md` §3에 기록 의무를 추가한다**

`- unreviewed hunk가 하나라도 있으면 완료로 처리하지 않는다.` 줄 뒤에 추가한다.

````markdown
- reviewer batch 결과를 받을 때마다 **즉시** 원장에 기록한다. 다음 batch를 시작하기 전에 기록한다.

```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" record \
  --session "$COMMITFORGE_SESSION_ID" <<'JSON'
{"verdicts": [{"id": "working:src/auth.py#3", "verdict": "PASS", "reviewer": "cca-line-reviewer"}],
 "findings": [], "reviewers": [{"name": "cca-line-reviewer", "status": "ACTIVE"}]}
JSON
```

- 기록 후에는 해당 판정을 컨텍스트에 유지하지 않아도 된다. 원장이 정본이다.
- 원장 기록은 lead만 수행한다. reviewer subagent와 Agent Team teammate는 기록하지 않는다.
- `inventory`에 없는 id는 거부된다. 판정 대상은 분모에서만 고른다.
````

- [ ] **Step 4: `cr/SKILL.md` §4에 세대 전이를 추가한다**

`4. 새 문제와 회귀가 없는지 검증한다.` 줄 뒤에 추가한다.

````markdown
5. 새 fingerprint로 원장 세대를 전이한다. 생략하면 종료 게이트가 `ledger_stale`로 차단한다.

```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" advance \
  --session "$COMMITFORGE_SESSION_ID" --fingerprint "<새 fingerprint>"
```
````

- [ ] **Step 5: `cr/SKILL.md` §6의 Guard 호출에 플래그를 추가한다**

`verify-review` 블록을 아래로 바꾼다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" verify-review \
  --session "<session>" \
  --source-read-only \
  --require-ledger
```

`finish` 블록을 아래로 바꾼다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" \
  --review-only \
  --source-read-only \
  --require-ledger
```

검증 항목 목록에 추가한다.

```markdown
- 원장의 모든 inventory id가 `PASS`·`FINDING`·`N_A` 중 하나를 가짐
```

섹션 끝에 문단을 추가한다.

```markdown
`--allow-unledgered`는 원장이 불완전해도 통과시키는 탈출구다. 사용자가 명시적으로 요청한 경우에만 쓰며, 사용했다면 `ledger_bypassed`, `pending_count`와 `pending` 목록을 최종 보고에 반드시 표시한다. 조용히 우회하지 않는다.
```

- [ ] **Step 6: `cr/SKILL.md` §7 보고 항목을 추가한다**

`- reviewer별 PASS/N/A/finding 수, unreviewed hunk 수` 줄 뒤에 추가한다.

```markdown
- 원장 커버리지: 총 inventory 수, 판정별 분포, 활성 세대와 iteration
- `--allow-unledgered`를 사용했다면 그 사실과 미판정 hunk 수·목록
```

- [ ] **Step 7: `deep-review-protocol.md` §1에 물리적 위치를 명시한다**

`모든 diff hunk를 빠짐없이 원장에 배정한다.`로 시작하는 문단 뒤에 추가한다.

```markdown
원장은 대화 기억이 아니라 디스크에 있다. 위치는 Guard 스냅샷 안의
`ledger/<활성 세대>/`이며 `ledger.py`로만 읽고 쓴다. 분모인 `inventory.jsonl`은
기계가 생성하므로 직접 만들거나 수정하지 않는다. 대화 컨텍스트가 압축되어도
원장은 남으며, 종료 게이트는 대화 기억이 아니라 이 파일을 검사한다.
```

- [ ] **Step 8: `large-diff-review.md`의 절차와 제한을 갱신한다**

`## 절차`의 6번과 7번을 아래로 바꾼다.

```markdown
6. lead aggregator가 finding stable ID, 반론, 중복을 통합한다. shard 하나가
   끝날 때마다 그 shard의 판정을 `ledger.py record`로 즉시 적재한다. lead는
   판정을 컨텍스트에 누적하지 않는다.
7. 전체 diff의 삭제 동작, wrapper/proxy, public contract를 다시 확인한다.
   미검토 hunk가 0인지는 기억이 아니라 `ledger.py status`의 `complete`와
   `pending`으로 확인한다.
```

`## 제한`의 마지막 줄 뒤에 추가한다.

```markdown
- 대형 diff에서 원장은 선택이 아니다. 컨텍스트가 압축되면 판정 기억이 먼저
  사라지고, 그 결과 미검토 hunk가 차단이 아니라 침묵 통과가 된다.
```

- [ ] **Step 9: `review-execution.md`에 writer 규칙을 추가한다**

`## 3. Finding 공통 스키마`의 `규칙:` 목록 끝에 추가한다.

```markdown
- 이 스키마가 곧 원장의 finding 레코드다. 별도 스키마를 만들지 않고
  `ledger.py record`의 `findings` 배열에 그대로 넣는다.
- 원장에 쓰는 주체는 lead뿐이다. teammate와 reviewer subagent는 결과를 lead에게
  반환하고, lead가 수신 즉시 적재한다.
- `cca-*` reviewer agent에 Bash를 부여하지 않는다. 읽기 전용 경계이자 원장의
  단일 writer를 보장하는 조건이다.
```

- [ ] **Step 10: `recovery.md`에 원장 구성을 추가한다**

`## 스냅샷 구성` 목록의 `- *.stat` 줄 뒤에 추가한다.

```markdown
- `ledger/`: 리뷰 원장. `run.json`과 세대별 `inventory.jsonl`·`hunks.jsonl`·
  `findings.jsonl`·`reviewers.json`으로 구성된다. 하위 디렉터리라서
  `audit-snapshot`의 파일 무결성 목록에는 포함되지 않는다.
```

같은 섹션 끝에 문단을 추가한다.

```markdown
`abort`와 `--keep-snapshot`은 원장을 함께 보존하므로, 차단된 실행이 어디까지
검토했는지 `ledger.py status`와 `report`로 사후 분석할 수 있다. `finish`는
스냅샷과 함께 원장을 삭제한다.
```

- [ ] **Step 11: `reporting.md`에 커버리지 보고를 추가한다**

리뷰 결과 보고 항목 목록에 추가한다.

```markdown
- 원장 커버리지 수치는 `ledger.py report`의 `coverage`에서 가져온다. 기억으로
  집계하지 않는다. `--format json`·`sarif` 산출물도 같은 출력에서 만든다.
```

- [ ] **Step 12: 문서 변경을 검증한다**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS. `tests/test_package.py`와 `tests/test_review_features.py`가 스킬 문서 구조를 검사하므로 문서 변경으로 깨지지 않는지 확인한다.

- [ ] **Step 13: 커밋한다**

```bash
git add .claude/skills/cr/SKILL.md .claude/skills/_git-atomic-core/deep-review-protocol.md \
  .claude/skills/_git-atomic-core/large-diff-review.md \
  .claude/skills/_git-atomic-core/review-execution.md \
  .claude/skills/_git-atomic-core/recovery.md \
  .claude/skills/_git-atomic-core/reporting.md
git commit -m "docs(cr): 원장 초기화·기록·세대 전이·게이트를 스킬 계약에 반영"
```

---

### Task 9: 릴리스 플러밍

새 파일이 추가되었으므로 패키지 메타데이터를 갱신하지 않으면 CI의 `release.py --check`와 `verify.py`가 실패한다.

**Files:**
- Modify: `CHANGELOG.md`, `VERSION`
- Modify: `MANIFEST.json`, `checksums.sha256` (스크립트가 생성)

- [ ] **Step 1: 현재 버전을 확인한다**

Run: `cat VERSION && head -20 CHANGELOG.md`
Expected: 버전 문자열과 기존 변경 이력 형식이 보인다. 다른 세션이 버전을 올렸을 수 있으므로 실제 값을 기준으로 다음 minor를 정한다.

- [ ] **Step 2: `VERSION`을 다음 minor로 올린다**

기능 추가이므로 minor를 올린다. Step 1에서 확인한 값이 `1.16.0`이면 `1.17.0`으로 한다.

- [ ] **Step 3: `CHANGELOG.md`에 항목을 추가한다**

기존 형식에 맞춰 최상단에 추가한다. 버전 번호는 Step 2에서 정한 값을 쓴다.

```markdown
## 1.17.0

### 추가

- `/cr`에 리뷰 원장을 도입했다. `ledger.py`가 Guard 스냅샷과 커밋 범위에서 hunk
  분모를 기계 생성하고, 판정·finding·reviewer 상태를 디스크에 적재한다.
- `guard.py verify-review`와 `finish`에 `--require-ledger`를 추가했다. 미판정
  hunk나 `UNKNOWN`이 남으면 완료를 차단한다. `--allow-unledgered`는 명시적
  탈출구이며 우회 사실이 출력에 남는다.

### 변경

- 대규모 diff 리뷰에서 컨텍스트 압축으로 변경 원장이 유실되어도 미검토 hunk가
  침묵 통과하지 않는다. 커버리지 판정 근거가 대화 기억에서 디스크로 옮겨졌다.
```

- [ ] **Step 4: 패키지 메타데이터를 재생성한다**

Run: `python3 release.py`
Expected: `MANIFEST.json`과 `checksums.sha256`이 갱신된다.

- [ ] **Step 5: 전체 검증을 실행한다**

Run: `python3 release.py --check && python3 verify.py && python3 -m unittest discover -s tests`
Expected: 모두 PASS

- [ ] **Step 6: 설치 스모크 테스트를 실행한다**

```bash
target="$(mktemp -d)"
./install.sh project "$target"
test -f "$target/.claude/skills/_git-atomic-core/scripts/ledger.py" && echo "ledger.py 설치 확인"
rm -rf "$target"
```

Expected: `ledger.py 설치 확인`이 출력된다. 출력되지 않으면 `install.py`의 파일 목록 수집 방식을 확인한다.

- [ ] **Step 7: 커밋한다**

```bash
git add VERSION CHANGELOG.md MANIFEST.json checksums.sha256
git commit -m "build(release): 리뷰 원장 도입 반영 manifest 및 체크섬 갱신"
```

---

## 자체 검토 결과

**스펙 커버리지.** §4(저장 위치)는 Task 1, §5.1~5.2(구조·엔트리)는 Task 1~2, §5.3(scope)은 Task 2~3, §5.4(세대)는 Task 5, §5.5(재개)는 Task 6과 Task 8 Step 2, §6.1~6.3(기록·반위조)은 Task 4, §6.4(guard 재사용)는 Task 1, §7(게이트)은 Task 7, §8.1~8.4(격리)는 Task 1의 소유권 바인딩, §8.5(lead 단독 writer)는 Task 8 Step 9, §8.6(심층 방어)은 Task 1의 `LedgerLock`과 Task 4의 `read_jsonl`, §9(문서)는 Task 8, §10(테스트)은 각 태스크에 분산 반영되었다.

**`/ccf` 공존 테스트를 별도로 두지 않은 이유.** 스펙 §8.4는 `guard.resolve_owned_review_context` 재사용으로 자동 충족된다. `/ccf` 스냅샷은 lock을 만들지 않으므로 이 경로가 항상 `owner_not_found`로 실패한다. Task 1의 `test_init_requires_active_lock`이 그 경로를 고정한다.

**타입 일관성.** `resolve_ledger`는 모든 태스크에서 4-튜플이다. `coverage()`의 반환 키(`complete`, `fingerprint_matches_current`, `generation`, `total`, `pending`, `pending_count`, `unknown`, `unknown_count`, `by_verdict`, `scopes`, `reviewers`)는 Task 6에서 정의하고 Task 7의 `ledger_gate`가 `pending_count`·`unknown_count`·`fingerprint_matches_current`·`generation`·`complete`를 소비한다. `allow_unledgered` 분기의 조기 반환에도 `complete`와 `pending_count`를 포함시켜 호출부가 키 부재로 실패하지 않게 했다. `LEDGER_DIR_NAME`·`RUN_NAME`·`read_run`·`coverage`는 Task 1·4·6에서 정의하고 Task 7이 `ledger.` 접두로 참조한다.
