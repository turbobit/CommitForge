# `/cr` 리뷰 원장(Review Ledger) 설계

- 작성일: 2026-09-12
- 상태: 승인됨 (구현 계획 대기)
- 범위: `/cr`에만 적용한다. 원장 스키마와 `ledger.py`는 `_git-atomic-core`에 공용으로 두어 `/cca`·`/cpr`가 나중에 그대로 붙일 수 있게 한다.

## 1. 배경과 문제

`deep-review-protocol.md` §1은 모든 diff hunk를 **변경 라인 원장**에 배정하라고 요구하고, §9의 완료 조건 1번은 "모든 hunk가 원장에 존재"다. `large-diff-review.md`는 "context 부족으로 읽지 못한 hunk는 `UNKNOWN`이며 성공을 차단한다"고 규정한다.

그런데 **이 원장에는 물리적 저장 위치가 없다.** 오직 모델 컨텍스트에만 존재한다. 여기서 두 가지가 동시에 발생한다.

1. **원장이 컴팩트를 유발한다.** shard mode threshold가 hunk 200개인데, hunk마다 7개 필드를 산문으로 기록하면 원장 자체가 수만 토큰이 된다. 컴팩터에게 이것은 반복적인 대량 텍스트이므로 우선 폐기 대상이 된다.
2. **누락이 차단되지 않고 침묵한다.** 컴팩트 이후 모델은 자신이 무엇을 잊었는지 알 수 없다. 잊힌 hunk는 `UNKNOWN`(차단)이 되지 못하고 **조용한 PASS**가 된다. §7의 "미검토 hunk 0을 다시 확인한다"조차 훼손된 기억을 대상으로 수행되므로 항상 통과한다.

즉 컴팩트가 차단 불변식을 통과 신호로 뒤집는다. 이것이 대규모 저장소 리뷰에서 관찰되는 누락의 원인이다.

## 2. 목표와 비목표

### 목표

- hunk 커버리지의 **분모를 모델이 아니라 스크립트가 소유**하게 한다.
- 원장·finding·reviewer 상태·재개 메타를 디스크에 적재해 컨텍스트 보유량을 줄인다.
- 미판정 hunk가 남은 채로 `/cr`이 성공 종료하는 것을 **기계적으로 차단**한다.
- 모델 프로바이더와 무관하게 동작한다. 준수도가 낮은 모델에서는 안전한 쪽(실패)으로 무너진다.

### 비목표

- `/cca`·`/cp`·`/cpr`에 대한 이번 적용. 구조만 공용으로 두고 적용은 후속 과제다.
- 컴팩트 자체를 막거나 제어하는 것. `/compact`·`autocompact`는 사용자 영역이며 스킬이 호출할 수 없다.
- 트랜스크립트 백업. 대규모 실행의 JSONL은 다시 읽으면 같은 오버플로를 재현하므로 복구 수단이 아니다.

## 3. 설계 원칙

> 모델이 기억하기를 기대하지 않는다. **증거가 디스크에 없으면 스크립트가 `finish`를 거부한다.**

"노트를 잘 남겨라" 같은 소프트 지시는 프로바이더별 준수도 편차에 노출된다. 하드 게이트는 `guard.py`가 집행하므로 Anthropic API·Bedrock·Vertex·Foundry·LLM 게이트웨이 어디서든 동일하게 작동한다.

## 4. 저장 위치와 생명주기

원장은 Guard 스냅샷 디렉터리 **안의 하위 디렉터리**에 둔다.

```
<git_dir>/claude-atomic-snapshots/<snapshot>/ledger/
```

이 위치를 선택한 근거는 다음 네 가지다.

1. **무결성 감사와 충돌하지 않는다.** `capture_snapshot`의 `snapshot_files` 수집과 `audit_snapshot`의 대조는 모두 `path.is_file()`로 필터링하므로 하위 디렉터리를 무시한다. 봉인된 파일 목록을 건드리지 않는다.
2. **정리 생명주기를 물려받는다.** `finish`는 `shutil.rmtree(snapshot)`으로 재귀 삭제하므로 원장도 함께 정리된다. `abort`와 `--keep-snapshot`은 스냅샷을 보존하므로 원장도 남아 사후 분석이 가능하다.
3. **소유권을 물려받는다.** 스냅샷 marker의 `session`·`token`·`project_root`가 그대로 원장의 접근 제어가 된다.
4. **워킹트리를 오염시키지 않는다.** 저장소 안에 쓰면 `--source-read-only`의 `untracked_content_unchanged` 검사에 걸려 `/cr`이 자기 자신 때문에 실패한다.

## 5. 데이터 모델

### 5.1 디렉터리 구조

```
ledger/
  .lock/                           디렉터리 기반 배타 잠금 (mkdir 원자성)
  run.json                         실행 메타. 원자적 교체(write-temp-rename).
  gen-01-<fp8>/
    inventory.jsonl                기계 생성. 분모. 불변.
    hunks.jsonl                    판정. append-only.
    findings.jsonl                 finding 본문. append-only.
    reviewers.json                 reviewer별 상태.
  gen-02-<fp8>/
    ...
```

`<fp8>`은 `repository_fingerprint(root)["fingerprint"]`(sha256 hex)의 앞 8자다. 같은 함수는 `components`도 반환하지만 디렉터리 이름에는 최상위 `fingerprint`만 쓴다.

`run.json` 필드:

```json
{
  "session": "<claude session id>",
  "token": "<guard token>",
  "stage": "init|inventory|review|fix|verify|done",
  "iteration": 1,
  "active_generation": "gen-01-ab12cd34",
  "scopes": ["working", "range:abc123..def456"]
}
```

`stage`는 위 6개 값만 갖는다. append-only가 아닌 유일한 파일이므로 임시 파일에 쓴 뒤 `os.replace`로 교체해 부분 쓰기를 방지한다.

### 5.2 Inventory 엔트리

세대 안에서 diff는 고정이므로 위치 기반 id로 충분하다. 세대가 바뀌면 재생성하므로 세대 간 안정성은 요구하지 않는다.

```
id = <source>:<path>#<n>           예: working:src/auth.py#3
```

엔트리는 4종으로 나눈다. 이 구분이 없으면 커버리지가 거짓이 된다.

| kind | 대상 | 단위 |
|---|---|---|
| `hunk` | 일반 텍스트 `@@` hunk | hunk 1개 |
| `binary` | 바이너리 변경 | 파일 1개 (protocol §1의 수동 검토 표시 대상) |
| `meta` | mode·rename만 바뀌어 content hunk가 없는 변경 | 파일 1개 |
| `untracked` | untracked 파일 | 파일 1개 |

`untracked`는 `git diff`에 나타나지 않지만 SKILL.md §2가 `git ls-files --others`로 수집해 리뷰 대상에 포함시킨다. 스냅샷의 `untracked.z`가 목록을 갖고 있으므로 여기서 파생한다. `meta`를 빼면 chmod 변경이 원장에서 사라진다.

판정값은 4개뿐이다.

| verdict | 의미 | 게이트 |
|---|---|---|
| `PASS` | 검토했고 문제 없음 | terminal |
| `FINDING` | 검토했고 finding 발생 | terminal (finding 레코드 필수) |
| `N_A` | 근거 있는 비적용 | terminal |
| `UNKNOWN` | 검토하지 못함 | **차단** |

`UNKNOWN`은 `N_A`가 아니다. `review-execution.md` §2의 기존 구분을 그대로 따른다.

### 5.3 Scope

스냅샷은 working 상태만 담는다. 그러나 `--base`·`--range`·`pr`·`today`·`3days`·`weekly`는 커밋 범위를 리뷰한다. working hunk만 분모로 삼으면 기간·PR 리뷰에서 동일한 침묵 PASS가 재발한다.

따라서 inventory는 scope별로 생성한다.

- `working` — 스냅샷의 `staged.diff`·`working.diff`·`untracked.z`에서 파생
- `range:<A>..<B>` — `ledger.py`가 `git diff <A>..<B>`를 직접 실행해 파생

**구현된 규칙(§7과 일치).** 게이트는 scope별 비어있지 않음이 아니라 **활성 세대
inventory 전체가 비어 있지 않음**을 요구한다. 총 개수가 0이면
`ledger_empty_inventory`로 차단한다. scope별 검사를 택하지 않은 이유는 두
가지다. 첫째, 선언은 됐지만 실제로 아무것도 바뀌지 않은 scope(깨끗한 working
tree와 함께 선언된 `working`)가 정상적으로 존재하며 이를 실패로 만들면 `/cr pr`
같은 흔한 실행이 항상 차단된다. 둘째, 침묵 PASS를 만드는 조건은 "분모가 0"이지
"어떤 scope가 0"이 아니다.

선언되지 않은 scope는 분모에 들어가지 않으므로 게이트에도 보이지 않는다.
따라서 SKILL.md는 §2에서 범위를 계산한 직후 `init`으로 그 scope를 선언하고
`inventory`를 실행하도록 순서를 고정한다. `init`은 파괴적이지 않고 scope를
합집합으로 더하며, 분모를 넓히면 활성 세대를 해제해 다음 `inventory`가 다시
만들게 한다.

### 5.4 세대 전이

`--fix`로 fingerprint가 바뀌면 `ledger.py advance`가 새 세대를 만든다. 기존 정책인 "수정 후 이전 reviewer 결과를 모두 무효화한다"가 그대로 구현된다.

- 이전 세대는 불변 이력이 된다. 별도 `STALE` 마킹 로직이 필요 없다. 활성 세대가 아니면 이력이다.
- **2세대 이후의 inventory는 스냅샷이 아니라 live `git diff`에서 만든다.** 스냅샷은 수정 전 원본이므로 수정 후의 분모가 될 수 없다. 이는 `advance`뿐 아니라 `iteration > 1`에서 실행되는 `inventory` 재실행에도 동일하게 적용된다.
- **이미 만들어진 세대의 분모는 다른 내용으로 대체되지 않는다.** 같은 id 집합이 다시 나오면 멱등이고, 다르면 `ledger_inventory_conflict`로 거부한다. 분모를 옮기는 수단은 `advance`(수정 후)와 `init`의 scope 추가(활성 세대 해제 후 재생성)뿐이다.
- 활성 세대의 fingerprint가 현재 저장소 fingerprint와 다르면 게이트는 실패한다. `advance` 없이 수정이 일어났다는 뜻이다.

### 5.5 재개 계약

컴팩트 이후 모델이 자신의 진행 상황을 되찾는 경로다. Guard `begin` 직후 SKILL.md가 `ledger.py status`를 호출한다.

커버리지는 세대 전체에 대해 평평하게 집계하고, scope는 그 안의 내역으로 둔다.
`by_verdict`를 scope마다 복제하면 게이트가 읽는 값이 두 곳에 생겨 갈라진다.
`reviewers`는 상태별 개수가 아니라 **이름 → 상태** 맵이다. 어떤 reviewer가
`UNKNOWN`인지 알아야 재개할 수 있고, 개수만으로는 알 수 없다.

```json
{
  "ok": true,
  "exists": true,
  "stage": "review",
  "iteration": 1,
  "active_generation": "gen-01-ab12cd34",
  "scopes_declared": ["working"],
  "complete": false,
  "fingerprint_matches_current": true,
  "generation": "gen-01-ab12cd34",
  "total": 214,
  "pending": ["working:src/auth.py#8", "..."],
  "pending_count": 77,
  "unknown": [],
  "unknown_count": 0,
  "by_verdict": {"PASS": 120, "FINDING": 17, "N_A": 0, "UNKNOWN": 0},
  "scopes": [{"source": "working", "total": 214, "covered": 137}],
  "reviewers": {"cca-security-reviewer": "ACTIVE", "cca-ux-accessibility-reviewer": "N_A"}
}
```

`pending`·`unknown`은 상위 20개 표본이며 정확한 수는 `pending_count`·
`unknown_count`에 있다.

재개 규칙:

- `exists: false`이면 신규 실행이다. `init` → `inventory`로 진행한다.
- `exists: true`이고 `fingerprint_matches_current: true`이면 **처음부터 다시 하지 않는다.** `stage`와 `pending_sample`을 근거로 미판정 id만 이어서 검토한다.
- `fingerprint_matches_current: false`이면 원장과 저장소가 어긋난 상태다. 임의로 진행하지 않고 사용자에게 보고한다. read-only `/cr`에서는 외부 변경을, `--fix` 실행에서는 `advance` 누락을 뜻한다.

`begin`이 새 token으로 새 스냅샷을 만들면 원장도 새로 시작된다. 따라서 재개는 같은 `/cr` 실행이 컴팩트를 겪은 경우를 대상으로 하며, `abort`로 보존된 이전 실행의 원장은 사후 분석 자료로만 쓴다.

## 6. 기록 경로

### 6.1 Write 도구를 쓸 수 없다

`cr_edit_gate.py`는 `PreToolUse`에서 `Edit|Write|NotebookEdit`를 **경로와 무관하게** 차단한다. `--fix`가 없는 기본 `/cr`에서 모델은 Write 도구로 원장을 기록할 수 없다.

이 게이트에 경로 예외를 추가하지 않는다. 경로 허용목록은 traversal·symlink 우회 표면을 만들고, 현재의 "전부 거부"라는 단순함이 이 게이트의 안전성이다. 대신 전용 스크립트를 통해 기록한다.

### 6.2 `ledger.py` 인터페이스

```bash
ledger.py init      --session S --scope working [--scope range:<A>..<B>]
                    # 재실행 시 scope를 합집합으로 더하고 진행 상황을 보존한다
ledger.py inventory --session S
ledger.py record    --session S          # stdin JSON
ledger.py status    --session S
ledger.py advance   --session S --fingerprint <new>
ledger.py report    --session S
```

모든 명령은 guard의 `resolve_owned_review_context`와 동일한 규칙으로 token·snapshot을 해석하고, guard의 `emit()` JSON 형식으로 출력한다. 변경 계열 명령은 `flock` 획득 후 실행한다.

`record`는 배치를 받는다. hunk 200개를 호출 200번으로 쪼개지 않기 위함이다.

```json
{
  "verdicts":  [{"id": "working:src/auth.py#3", "verdict": "PASS", "reviewer": "cca-correctness-reviewer"}],
  "findings":  [],
  "reviewers": [{"name": "cca-security-reviewer", "status": "ACTIVE"}]
}
```

`findings[]` 원소는 `review-execution.md` §3의 finding 스키마를 그대로 쓴다. 원장은 그 스키마의 저장소이며 새 스키마를 만들지 않는다. 세 배열 모두 선택이므로 판정만, finding만, reviewer 상태만 보낼 수도 있다.

### 6.3 반-위조 속성

`verdicts[].id`가 inventory에 존재하지 않으면 거부한다. 분모는 기계가 만들고 id는 대조되므로 **"전부 검토했다"고 주장해 게이트를 통과할 방법이 없다.** `verdict: FINDING`은 대응하는 finding 레코드를 요구한다.

### 6.4 guard.py 재사용

`ledger.py`는 소유권 판정 로직을 **재구현하지 않고 `guard.py`를 import해 재사용한다.**

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard
```

`guard.py`는 모든 실행 코드가 `if __name__ == "__main__"` 아래에 있어 import 부작용이 없다. 재사용 대상은 `repo_context`, `safe_session`, `resolve_owned_review_context`, `owned_snapshots`, `validate_snapshot`, `repository_fingerprint`, `read_json`, `emit`, `GuardError`다.

특히 `resolve_owned_review_context`는 worktree lock의 owner에서 token을 해석하고 `owned_snapshots`로 스냅샷을 좁힌다. `/ccf`는 lock 없이 스냅샷만 만들어 token이 다르므로 이 경로에서 자동으로 배제된다. §8.4의 요구가 재사용만으로 충족된다.

보안 관련 판정을 복제하면 두 구현이 갈라질 때 조용히 약한 쪽이 뚫린다. 복제하지 않는 것이 이 결정의 핵심이다.

## 7. 게이트

게이트는 **원장의 존재로 무장한다.** `<snapshot>/ledger/run.json`이 있으면
`verify-review`와 `finish`가 flag와 무관하게 검사한다. 플래그 옵트인은 §3의
원칙("모델이 기억하기를 기대하지 않는다")과 모순된다. 게이트를 켜는 지시가
컴팩터가 먹는 바로 그 SKILL.md에 있기 때문이다. `/cpr`·`/cca`는 원장을 만들지
않으므로 존재 기반 무장에서도 영향을 받지 않으며, 이는 플래그 방식이 주던 격리와
동일하다.

`--require-ledger`는 "원장이 아예 없으면 **추가로** 실패한다"는 의미로 남는다.

| 조건 | 결과 |
|---|---|
| 원장 없음 | `--require-ledger`면 실패 `ledger_missing`, 아니면 검사 없음 |
| 활성 세대 없음 (`inventory` 미실행) | 실패 `ledger_no_generation` |
| 활성 세대 fingerprint ≠ 현재 | 실패 `ledger_stale` |
| 활성 세대의 live inventory 개수 ≠ `run.json`에 기록된 개수 | 실패 `ledger_inventory_mismatch` |
| 활성 세대 inventory 개수 = 0 | 실패 `ledger_empty_inventory` |
| `UNKNOWN` 존재 | 실패 `ledger_unknown` |
| 미판정 id 존재 | 실패 `ledger_incomplete` (개수·샘플 포함) |
| 전부 terminal | 통과 + 커버리지 수치 |

순서가 중요하다. 잘린 inventory(개수 0, 기록된 개수 2)는
`ledger_inventory_mismatch`이지 `ledger_empty_inventory`가 아니다. 후자는 분모가
실제로 비어 있게 만들어진 경우, 즉 리뷰 대상 scope가 선언되지 않은 경우다.

`ledger.py`의 거부 사유도 함께 둔다.

| 조건 | 결과 |
|---|---|
| 활성 세대에 이미 다른 id 집합의 inventory가 있음 | 실패 `ledger_inventory_conflict` |
| `run.json`이 있으나 파싱 불가 | 실패 `ledger_corrupt` |

`finish --review-only`도 동일 검사를 다시 수행한다. 기존 불변식이 `verify-review`와 `finish`에서 두 번 검사되는 패턴과 같다.

**탈출구.** `--allow-unledgered`를 명시하면 통과하되 `ledger_bypassed: true`, `pending_count`, `pending`을 출력한다. SKILL.md는 이 값들을 최종 보고에 강제 표시하도록 규정한다. 조용히 우회할 수 없다.

## 8. 동시성과 격리

### 8.1 같은 worktree, 다른 세션

Guard advisory lock이 이미 차단한다. SKILL.md §1이 동일 worktree의 `/cc`·`/cr`·`/cca`·`/cpr`·`/cp` 동시 실행을 중단시킨다. 원장은 lock을 획득한 세션의 스냅샷 안에 있으므로 추가 방어가 필요 없다.

### 8.2 다른 worktree

`repo_context`가 `--git-dir`를 사용하고(linked worktree면 `.git/worktrees/<name>`), lock과 snapshot이 모두 `git_dir` 아래에 있다. lock·snapshot·ledger가 worktree별로 자연 격리된다.

### 8.3 다른 프로젝트, 다른 폴더

스크립트에 전역 상태가 없다. `Path.home()`·`~/.claude`·`expanduser`·`/tmp`·`tempfile` 사용이 0건이며, 모든 경로가 `repo_context(Path.cwd())`에서 파생된다. `persist_session`도 전역이 아니라 세션별 `CLAUDE_ENV_FILE`에 기록한다. 서로 다른 프로젝트는 구조적으로 간섭하지 않는다.

같은 Claude 세션이 여러 프로젝트를 오가는 경우에도 `owned_snapshots`가 `project_root`를 대조하고 `session-end`가 worktree·git_dir 불일치를 거부한다. 원장은 session+token+project_root 3중 바인딩으로 이를 물려받는다.

### 8.4 `/ccf`와의 공존

`/ccf`는 lock 없이 스냅샷만 만든다. 따라서 `/cr` 실행 중 같은 worktree에 다른 스냅샷이 존재할 수 있다.

**`ledger.py`는 스냅샷을 "가장 최신" 또는 "유일한 것"으로 선택해서는 안 된다.** `owned_snapshots()`와 동일하게 session+token+project_root 3중 일치로 바인딩하고, 복수 매치면 `owner_snapshot_ambiguous`로 실패한다.

### 8.5 서브에이전트와 Agent Team

**lead 단독 writer**로 한다. 기존 정책과 일치한다. `review-execution.md`는 "teammate는 source, index, snapshot, lock을 변경하거나 Guard를 실행하지 않는다. Guard의 획득·검증·종료는 lead만 수행한다"고 규정한다.

구조적으로도 이미 막혀 있다. `cca-*.md`는 `tools: Read, Grep, Glob`만 가지므로 Bash가 없어 `ledger.py`를 호출할 수 없다. Agent Team은 이 정의를 teammate type으로 재사용하므로 제약을 물려받는다.

**불변조건: `cca-*` 에이전트에 Bash를 부여하지 않는다.**

teammate 결과는 lead가 수신 즉시 기록한다. 컨텍스트 절약은 전달이 아니라 **보유**에서 나온다. 현재는 최종 보고까지 모든 결과를 컨텍스트에 유지해야 하지만, 원장이 있으면 기록 후 버릴 수 있다. shard mode에서 lead 컨텍스트가 shard 수에 비례해 누적되지 않는 것이 이 설계의 핵심 이득이다.

### 8.6 심층 방어

정책에만 의존하지 않는다.

1. **디렉터리 잠금** — 모든 변경 계열 명령이 `ledger/.lock`을 `mkdir`로 생성해 배타 잠금을 얻는다. 병렬 호출에서도 append가 섞이지 않는다.

   `fcntl.flock`은 POSIX 전용이라 쓰지 않는다. CI 매트릭스에 `windows-latest`가 포함되며, `guard.py`의 `acquire_lock`도 같은 이유로 `lock_dir.mkdir(mode=0o700)`의 원자성을 쓴다. 동일 패턴을 따른다.
2. **호출마다 소유권 검증** — session+token이 스냅샷 marker와 불일치하면 거부한다.
3. **부분 쓰기 내성** — 레코드 1건을 개행 포함 단일 `write()`로 append하고, 리더는 파싱 불가한 **마지막 줄 1개만** 허용해 경고 후 무시한다. 크래시로 잘린 줄이 원장 전체를 무효화하지 않는다.

## 9. 문서·계약 변경

| 파일 | 변경 |
|---|---|
| `skills/cr/SKILL.md` | `allowed-tools`에 `ledger.py` 추가. §1.5 `status`→`init --scope working`→(§2에서 범위 계산)→`init --scope range:<A>..<B>`→`inventory` 순서 고정, §3 batch 수신 즉시 `record`, §4 `--fix` 후 `guard.sh fingerprint`로 얻은 값으로 `advance`, §6 `finish` 이전에 `ledger.py report` 수집, §7 커버리지 수치와 bypass 강제 표시 |
| `deep-review-protocol.md` §1 | 원장의 물리적 위치와 기록 명령 명시 |
| `large-diff-review.md` | shard 종료 직후 `record`. §7의 미검토 hunk 확인을 `ledger.py status` 결과로 대체 |
| `review-execution.md` | §3 finding 스키마가 원장 레코드임을 명시. lead 단독 writer 규칙과 cca-* Bash 미부여 불변조건 추가 |
| `recovery.md` | ledger 구성, `abort`·`--keep-snapshot` 시 보존, 사후 분석 절차 |
| `reporting.md`, `reporting-formats.md` | 보고에 커버리지 수치 포함. JSON/SARIF를 `ledger.py report`에서 생성 |
| `CHANGELOG.md`, `VERSION` | 릴리스 기록 |
| `MANIFEST.json`, `checksums.sha256` | `python3 release.py`로 재생성. CI의 `release.py --check`가 강제한다 |

## 10. 테스트 전략

기존 `tests/` 스타일을 따른다. `unittest`, 임시 git 저장소, subprocess 호출, JSON 출력 파싱.

`tests/test_ledger.py` 신설:

- **inventory** — `hunk`·`binary`·`meta`(chmod)·`untracked` 4종이 각각 잡히는지. `range` scope가 커밋 범위를 잡는지.
- **반-위조** — inventory에 없는 id 거부. `FINDING`인데 finding 레코드가 없으면 거부.
- **내구성** — 배치 append. 잘린 마지막 줄 내성. `advance` 후 이전 세대 불변.
- **게이트** — 미판정 시 실패. 전부 terminal이면 통과. `advance` 누락 시 `ledger_stale`. `--allow-unledgered` 시 통과와 bypass 플래그.
- **동시성** — 같은 원장에 두 프로세스가 동시에 `record`할 때 flock으로 직렬화되고 레코드 유실이 없는지.
- **격리** — 서로 다른 저장소에서 동시 실행 시 무간섭. `/ccf` 스냅샷이 공존할 때 올바른 스냅샷에 바인딩.

`tests/test_guard.py`에 회귀 추가:

- `ledger/` 하위 디렉터리가 존재해도 `audit_snapshot`이 통과하고 `finish`가 정상 삭제하는지. **이 설계 전체가 "디렉터리는 감사 대상이 아니다"에 의존하므로 반드시 고정한다.**

구현은 TDD로 진행한다.

## 11. 결정 기록

| 결정 | 선택 | 근거 |
|---|---|---|
| 활성 조건 | 항상 활성 | 코드 경로가 하나라 단순하고 일관됨 |
| 강제 강도 | 하드 차단 + 명시적 탈출구 | 침묵 PASS를 즉시 제거하되 비상구를 남김 |
| 적용 범위 | `/cr` 먼저, 구조는 공용 | 검증이 확실하고 `/cca`·`/cpr`가 나중에 붙일 수 있음 |
| 원장 내용 | hunk + finding + reviewer + 재개 메타 | 재개와 리포트 재구성까지 확보 |
| 커밋 범위 | scope별 inventory에 포함 | 제외하면 기간·PR 리뷰에 동일 버그가 잔존 |
| 저장 구조 | 세대 디렉터리 | 기존 무효화 정책과 1:1 대응, STALE 로직 불필요 |
| 저장 위치 | `<snapshot>/ledger/` | 감사·정리·소유권을 그대로 물려받고 워킹트리를 오염시키지 않음 |
| 기록 수단 | 전용 스크립트 | Write 도구가 게이트로 차단됨. 보안 게이트에 예외를 뚫지 않음 |
