# CommitForge 에디터 확장 설계

- 작성일: 2026-09-11
- 상태: 승인됨 (구현 계획 대기)
- 범위: 1단계(MVP)만 본 문서에서 확정한다. 2·3단계는 「후속 단계」에 경계만 기록한다.
- 대상 에디터: VS Code 확장 API(`engines.vscode`)로 만들며, 동일 VSIX가 Cursor에서도 동작한다. 본 문서에서 "확장"은 이 하나를 가리킨다.

## 1. 배경과 문제

CommitForge는 Claude Code용 Skills 패키지다. 사용자 진입점은 Claude Code 안의 슬래시 명령 9개(`/ccr`, `/cc`, `/cf`, `/cfr`, `/ccf`, `/cr`, `/cca`, `/cpr`, `/cp`)이고, 배포·관리 진입점은 `install.py`, `uninstall.py`, `verify.py`, 런타임 안전장치는 `guard.py`다. 모두 CLI다.

여기서 네 가지 마찰이 확인되었다.

1. **명령 실행이 번거롭다.** 명령 9개와 옵션(`/cca`만 31개)을 외워 타이핑해야 한다.
2. **설치·업그레이드 관리가 불투명하다.** 프로젝트마다 설치 여부와 버전을 확인할 방법이 사실상 없다.
3. **상태와 잠금이 보이지 않는다.** lock 보유 여부, Diff snapshot, 복구 필요 상태를 `guard.py status`로 직접 확인해야 한다.
4. **리뷰 결과를 활용하기 어렵다.** 터미널 텍스트로만 남아 문제 위치로 점프할 수 없다.

본 설계는 에디터 확장으로 1·2·3을 해결한다. 4는 3단계로 미룬다.

## 2. 목표와 비목표

### 목표 (1단계)

- 워크스페이스의 CommitForge 설치 상태를 항상 보이게 하고, 설치·업그레이드·검증·제거를 UI에서 실행한다.
- lock·snapshot·복구 상태를 상태바와 트리에 표시한다.
- 명령과 옵션을 UI로 조립해 Claude Code가 실행 중인 터미널로 전송한다.

### 비목표 (1단계에서 하지 않음)

- 헤드리스 실행(`claude -p`)
- SARIF → Problems 패널 연동
- 리뷰 결과 전용 패널, diff 점프
- 저장 시 자동 리뷰 등 자동 트리거
- Marketplace·OpenVSX 공개 배포

### 성공 기준

- 새 저장소에서 확장만으로 CommitForge를 설치하고 `/cr`을 실행하기까지 터미널 타이핑이 0회다.
- 설치된 버전과 번들 버전이 다를 때 확장이 그 사실과 두 버전 번호를 모두 표시한다.
- lock을 다른 세션이 쥐고 있을 때, 쓰기 명령을 전송하기 **전에** 경고한다.

## 3. 제약과 사전 조사 결과

설계를 좌우한 사실들이다. 모두 저장소 코드에서 직접 확인했다.

### 3.1 Claude Code 확장에는 프롬프트 주입 API가 없다

설치된 `anthropic.claude-code` 확장이 노출하는 명령은 패널 열기·포커스·diff 수락 수준이며, `extensionDependencies`나 공개 API가 없다. 외부 확장이 Claude Code 패널에 프롬프트를 넣을 공식 경로는 존재하지 않는다.

→ 명령 실행은 **통합 터미널 `sendText`** 로 한다.

### 3.2 `argument-hint`가 명령 카탈로그의 원천이다

각 `SKILL.md` frontmatter의 `argument-hint`에 전체 옵션 목록이 있고, 9개 명령 전부에서 문법이 일관된다.

| 형태 | 의미 |
|---|---|
| `[a\|b\|c]` | 첫 토큰 위치의 모드 (선택) |
| `[추가 맥락]` | 자유 텍스트 |
| `[--flag]` | 불리언 플래그 |
| `[--opt <값>]` | 값 필요, 자유 입력 |
| `[--opt a\|b\|c]` | 값 필요, 열거형 |
| `[--opt 20-500]` | 값 필요, 수치 범위 |
| `[--a\|--b]` | 배타 플래그 쌍 |

→ 명령·옵션 목록을 하드코딩하지 않고 파싱으로 생성한다.

### 3.3 `install.py`는 단순 복사가 아니다

- 9개 명령의 `SKILL.md`에서 `CORE_REFERENCE`(`.claude/skills/_git-atomic-core`)를 설치 절대경로로 치환한다.
- `/cr`의 edit gate hook 명령에 `sys.executable`과 gate 스크립트 절대경로를 박는다.
- `settings.local.json`(project) 또는 `settings.json`(global)에 SessionEnd lifecycle hook을 병합한다.
- 기존 파일은 `.claude/.commitforge-backups/<timestamp>/`에 백업한다.
- `--dry-run`을 지원한다.

→ 설치 로직을 TypeScript로 재구현하지 않고, **번들한 `install.py`를 그대로 실행**한다.

### 3.4 설치본에는 버전 표식이 없고, 일부 파일은 해시가 달라진다

`.claude/`로 들어가는 파일은 61개다.

| 분류 | 개수 | 설치 후 해시 |
|---|---:|---|
| `.claude/agents/*.md` | 16 | MANIFEST와 일치 |
| `.claude/skills/_git-atomic-core/**` | 36 | MANIFEST와 일치 |
| 명령별 `SKILL.md` | 9 | **재작성되어 불일치** |

또한 설치 시 버전을 기록하는 파일이 없다.

→ 해시 검증(52개) + 의미 검증(9개) + 신규 설치 마커를 조합한다. 마커는 `install.py`에 추가한다(§5.2).

### 3.5 리뷰 리포트는 이미 기계 판독 형식을 지원한다

`--format json|sarif --output <path>`, 스키마 `commitforge-review/v1`, 기본 위치 `.git/commitforge-reports/`, 검증기 `report_validator.py`가 이미 있다.

→ 2단계 Problems 패널 연동 시 본체 변경이 거의 필요 없다. 1단계에서는 사용하지 않는다.

### 3.6 셸 환경 의존성

사용자 환경에서 `claude`는 zsh 함수(`qlaudec`)다. `child_process.spawn`은 대화형 셸을 거치지 않으므로 이 래핑이 적용되지 않는다. 반면 터미널 `sendText`는 사용자의 대화형 셸을 그대로 거치므로 alias·함수·rc 설정이 살아 있다.

→ 1단계의 터미널 전송 방식은 이 문제의 영향을 받지 않는다. 2단계 헤드리스 실행에서 별도로 해결해야 한다.

## 4. 아키텍처

확장은 **상태를 소유하지 않는 얇은 어댑터**다. 진실의 원천은 세 곳이며 확장은 읽어서 그린다.

| 진실의 원천 | 제공 정보 | 접근 방법 |
|---|---|---|
| 번들 페이로드 `payload/` | 설치 가능한 버전, 92개 파일 해시 | VSIX 내 `MANIFEST.json` 읽기 |
| 워크스페이스 `.claude/` | 설치 여부·버전·무결성 | 파일 해시 대조 + 마커 |
| `guard.py status` | lock, snapshot, 복구 제안, git lock | 자식 프로세스 → JSON |

### 4.1 디렉터리 구조

```
editor-extension/
  package.json              contributes: 명령·뷰·상태바·설정
  scripts/sync-payload.mjs  빌드 시 페이로드 복사
  payload/                  빌드 산출물 (gitignore)
  src/
    core/                   VS Code 비의존, 단위 테스트 대상
      payload.ts            번들 버전·MANIFEST 로딩
      detect.ts             설치 상태 판정
      guard.ts              guard.py status 실행·파싱
      catalog.ts            SKILL.md → 명령·옵션 카탈로그
      composer.ts           선택 조합 → 명령 문자열
      python.ts             Python 인터프리터 탐색
    vscode/                 얇은 UI 층
      statusBar.ts treeView.ts quickPick.ts terminal.ts installer.ts
    extension.ts            activate 배선
  test/
    fixtures/               실제 SKILL.md·guard 출력 샘플
```

### 4.2 불변 제약

이 네 가지는 구현 중 협상 대상이 아니다.

1. **확장은 `.claude/` 아래에 쓰지 않는다.** 모든 쓰기는 번들된 `install.py`/`uninstall.py`가 한다. 확장의 파일 작업은 읽기와 해시 계산뿐이다. 이를 지켜야 확장 설치와 CLI 설치가 영원히 동일하다.
2. **명령·옵션을 하드코딩하지 않는다.** `catalog.ts`가 `SKILL.md`에서 생성한다.
3. **`guard.py clean`을 확장이 직접 호출하지 않는다.** `/cr clean`을 터미널로 보낸다. 직접 호출하면 실행 중인 Claude Code 세션이 모르는 사이 lock이 사라진다.
4. **폴링하지 않는다.** 이벤트 기반으로만 갱신한다(§7.1).

### 4.3 활성화

`onStartupFinished`로 활성화한다. 상태바가 워크스페이스를 연 직후부터 보여야 하고, 미설치 상태를 알리는 것 자체가 기능이기 때문이다. 활성화 직후 수행하는 작업은 설치 판정 1회와 `guard.py status` 1회로 제한한다. git 저장소가 아니면 후자를 건너뛴다.

## 5. 설치 상태 감지

### 5.1 판정 절차

1. `.claude/.commitforge-install.json` 마커를 읽는다(있으면 버전·scope·core_path 확보).
2. 52개 무수정 파일을 번들 `MANIFEST.json`과 sha256 대조한다.
3. 9개 `SKILL.md`는 해시 대신 **의미 검증**을 한다: 치환된 core 경로가 이 설치의 `_git-atomic-core`를 가리키는가.
4. hook 등록을 확인한다: `settings.local.json`(project) / `settings.json`(global)에 `session_lifecycle.py` handler가 있는가.

**마커와 해시의 우선순위를 명시한다.** 해시 대조가 판정의 근거이고, 마커는 표시용 정보다. 둘이 어긋나면 해시를 따른다. 구체적으로:

- 마커 없음 + 해시 일치 → `정상`. 버전은 번들 버전으로 표시한다. 마커 도입 이전 버전으로 설치된 정상 케이스다.
- 마커 없음 + 해시 불일치 → `버전 다름`. 설치 버전은 "알 수 없음"으로 표시한다.
- 마커 있음 + 해시 불일치 → `버전 다름`. 마커의 버전과 번들 버전을 함께 표시한다.
- 마커 있음 + 해시 일치 + 마커 버전 ≠ 번들 버전 → `정상`으로 판정하되 Output에 경고를 남긴다. 마커가 낡았거나 손으로 편집된 경우다.

3번을 해시가 아닌 의미로 검증하는 이유는 실제 고장 모드를 정확히 짚기 위해서다. `.claude/`를 git에 커밋한 저장소를 다른 머신에서 클론하면 경로가 남의 머신을 가리켜 skill이 조용히 깨진다. 해시 대조는 이를 "버전 다름"으로 오인하지만 의미 검증은 "설정 불완전"으로 정확히 분류한다.

### 5.2 설치 마커 (`install.py` 변경)

설치 시 `.claude/.commitforge-install.json`을 기록하고, `uninstall.py`가 제거한다.

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

요구사항:

- `--dry-run`에서는 기록하지 않고 예정 경로만 출력한다.
- `version`은 저장소 루트 `VERSION`에서 읽는다.
- 마커 추가에 따라 `MANIFEST.json`과 `checksums.sha256`을 재생성한다.
- CLI 단독 사용자에게도 이득이므로 확장과 무관하게 유지 가치가 있다.

### 5.3 판정 결과

| 상태 | 조건 | 배지 | 제안 행동 |
|---|---|---|---|
| 미설치 | `.claude/skills/cr` 없음 | 회색 | 설치 |
| 정상 | 61개 존재 · 해시 일치 · 경로 일치 · hook 등록 | 초록 `v1.15.0` | — |
| 버전 다름 | 해시 불일치 (마커 있으면 두 버전 표시) | 노랑 | 업그레이드 |
| 설정 불완전 | 파일은 있으나 경로가 타 설치를 가리킴, 또는 hook 미등록 | 노랑 | 재설치 |
| 손상 | 파일 누락 또는 일부만 불일치 | 빨강 | 재설치 + 상세 목록 |

project와 global 두 범위를 모두 검사해 트리에 나란히 표시한다. 어느 쪽이 명령을 제공하는지 혼동되는 것이 흔한 문제이기 때문이다.

## 6. 명령 실행

### 6.1 조립기

`catalog.ts`가 §3.2 문법을 파싱해 타입화된 모델을 만든다. 미설치 상태에서는 번들 페이로드의 `SKILL.md`를 읽는다.

`/cca`의 옵션 31개는 모드별로 관련성이 갈리지만(`--target`·`--bump`·`--channel`·`--prepare`·`--tag`는 `release` 전용, `--incident`·`--severity`·`--diagnose`·`--rollback-first`는 `emergency` 전용, `--since`·`--branches`·`--exclude-bots`·`--commits`·`--all-authors`·`--week-start`·`--timezone`은 기간 모드 전용) `argument-hint`는 이 조건부 관계를 담지 않는다.

따라서 확장에 **모드→옵션 그룹 힌트 표**를 둔다. 단 이 표는 **정렬과 그룹 헤더에만 사용하고 필터로 사용하지 않는다.** 힌트에 없는 옵션은 "기타" 그룹에 그대로 나타난다. 결과적으로 CommitForge에 새 옵션이 추가돼도 UI에서 숨겨지지 않으며, 힌트 표가 낡으면 정렬만 어색해질 뿐 기능은 유지된다.

### 6.2 흐름

흔한 경우가 두 번의 입력으로 끝나야 한다. 대부분의 사용은 옵션 없는 `/cr`, `/cca`이다.

```
CommitForge: 명령 실행
┌──────────────────────────────────────────────┐
│ /cr    심층 코드 리뷰 (읽기 전용)         ⚙  │  Enter = 즉시 전송
│ /cca   리뷰·수정·검증·commit 전체 실행    ⚙  │  ⚙ = 옵션 지정
│ /cc    의미 단위별 순차 commit            ⚙  │
│ ⋯                                            │
│ ── 최근 ──                                   │
│ /cca today --no-fix                          │
└──────────────────────────────────────────────┘
```

`⚙` 경로: 모드 선택 → 옵션 다중 선택 → 값 입력(열거형은 QuickPick, 자유 입력은 InputBox) → 미리보기 확인 → 전송.

명령 설명은 `SKILL.md`의 `description` 첫 문장을 사용한다. 최근 실행 목록은 워크스페이스 상태에 최대 5개 저장한다.

### 6.3 터미널 전송 정책

`sendText`는 키 입력을 흉내낼 뿐이므로, 받는 쪽이 Claude Code REPL이 아니면 셸에 `/cr`이 입력되어 엉뚱한 에러가 난다.

- 확장은 **자기가 만든 터미널만 신뢰한다.** `CommitForge`라는 이름의 터미널을 만들고 거기서 `claude`를 실행한다.
- 사용자가 이미 다른 터미널에서 claude를 쓰고 있는 경우는 감지할 수 없다. 첫 전송 시 **대상 터미널을 한 번 묻고**(열린 터미널 목록 + 새로 만들기) 선택을 워크스페이스 세션 동안 기억한다.
- 전송 직전 **미리보기 확인**을 거친다.
- 자유 텍스트 입력의 개행은 제거한다. `sendText`에서 개행은 Enter이므로 명령이 절반만 전송될 수 있다.

### 6.4 lock 충돌 사전 경고

쓰기 명령(`/cc`, `/cf`, `/ccf`, `/cca`, `/cp`) 전송 전에 `guard.py status`를 읽는다. 다른 세션이 lock을 보유 중이면 전송을 멈추고 소유자·경과 시간·호스트를 제시하며 `clean` 실행을 제안한다. 명령을 보낸 뒤 Claude가 거부하는 것보다 보내기 전에 아는 편이 낫다.

## 7. 상태 UI

### 7.1 갱신 시점

폴링하지 않는다. 다음 네 시점에만 `guard.py status`를 실행한다.

- 창 포커스 복귀 (`window.onDidChangeWindowState`)
- 명령 전송 직후
- 수동 새로고침
- `FileSystemWatcher` 이벤트: `.git/claude-atomic.lock`, `.git/claude-atomic-snapshots`, `.claude/**`

유휴 시 비용이 0이면서 사실상 실시간이다.

### 7.2 상태바

```
$(check)   CommitForge v1.15.0      정상, lock 없음
$(lock)    CommitForge · 12분        내 세션이 lock 보유
$(warning) CommitForge · 다른 세션   타 세션 lock
$(alert)   CommitForge 미설치        워크스페이스 미설치
```

클릭하면 트리 뷰를 연다.

### 7.3 트리 뷰

```
CommitForge
├─ 설치        ● project v1.15.0 정상
│              ○ global  미설치
│              [설치] [업그레이드] [검증] [제거]
├─ 잠금        보유자 없음
│              (보유 시) session abc123 · 12분 · 이 호스트
│              [해제(clean)]
├─ 스냅샷      2개 · .git/claude-atomic-snapshots/
│              [Finder에서 열기]
└─ 경고        git index.lock 존재 (4분)
               rebase-merge 진행 중
```

데이터는 `guard.py status`의 `claude_atomic_lock`, `lock_age_seconds`, `lock_owner_same_host`, `snapshots`, `recovery`, `operations`, `git_locks`를 그대로 매핑한다.

### 7.4 설치·제거 실행

터미널 전송이 아니라 자식 프로세스로 실행한다. Claude가 아니라 Python이 하는 일이고, 결과를 파싱해 트리를 갱신해야 하기 때문이다.

- 실행 전 `--dry-run`을 먼저 돌려 변경 예정 내용을 보여주고 확인을 받는다.
- 출력은 `CommitForge` Output 채널에 그대로 흘린다.
- 완료 후 설치 상태를 재판정한다.

버튼별 동작은 다음과 같다. **트리의 `[검증]`은 `verify.py`를 실행하지 않는다.** `verify.py`는 CommitForge *소스 패키지*를 검사하는 도구이고, 여기서 필요한 것은 *설치본* 검사이므로 목적이 다르다.

| 버튼 | 실행 |
|---|---|
| 설치 | `install.py --scope <범위> --target <경로>` (dry-run 후 확인) |
| 업그레이드 | 설치와 동일한 명령. `install.py`가 백업 후 덮어쓴다 |
| 검증 | §5.1 판정을 전체 재실행하고 불일치 파일 목록을 Output에 출력 |
| 제거 | `uninstall.py --scope <범위> --target <경로>` (dry-run 후 확인) |

## 8. 실패 처리

확장은 실패해도 죽지 않고 기능을 하나씩 끈다. 모든 실패 메시지는 "무엇이 없는지 + 다음에 무엇을 할지"로 번역한다.

| 상황 | 동작 |
|---|---|
| 워크스페이스가 git 저장소 아님 | 잠금·스냅샷 그룹 숨김, 설치 기능 유지 |
| Python 없음 | 설치·상태 비활성 + `commitforge.pythonPath` 안내. 명령 전송은 계속 동작 |
| `guard.py status` 실패 | 마지막 성공 상태를 회색 표시 + stderr를 Output에 |
| 다중 루트 워크스페이스 | 폴더 선택 QuickPick, 선택 기억 |
| `settings.local.json` 손상 | `install.py`가 이미 거부한다. 그 메시지를 그대로 노출 |
| 번들 페이로드 누락 | 빌드 실패로 간주, 활성화 시 오류 알림 |

## 9. 설정 항목

| 키 | 기본값 | 설명 |
|---|---|---|
| `commitforge.pythonPath` | 자동 탐색 | Python 인터프리터 경로 |
| `commitforge.terminal.name` | `CommitForge` | 확장이 만드는 터미널 이름 |
| `commitforge.terminal.launchCommand` | `claude` | 새 터미널에서 실행할 명령 |
| `commitforge.statusBar.enabled` | `true` | 상태바 표시 여부 |
| `commitforge.confirmBeforeSend` | `true` | 전송 전 미리보기 확인 |

## 10. 테스트 전략

`src/core/`에 집중한다. VS Code 비의존 순수 함수이므로 `vitest`로 빠르게 실행한다.

| 대상 | 검증 내용 |
|---|---|
| `catalog.ts` | 9개 `SKILL.md`의 실제 `argument-hint` 픽스처 파싱. 문법 변경 시 즉시 실패 |
| `detect.ts` | 임시 디렉터리에 다섯 상태(미설치·정상·버전 다름·설정 불완전·손상) 구성 후 판정 |
| `composer.ts` | 선택 조합 → 명령 문자열. 배타 옵션(`--team\|--no-team`)과 개행 제거 필수 |
| `guard.ts` | `guard.py status` 실제 출력 샘플 파싱 |
| `python.ts` | 탐색 실패·설정 우선순위 |

E2E는 `@vscode/test-electron`으로 활성화·트리 렌더·명령 등록만 얕게 확인한다. 터미널 전송은 자동 검증이 어려우므로 `MANUAL-TEST-CHECKLIST.md`에 항목을 추가한다.

`install.py` 마커 추가(§5.2)는 기존 pytest 스위트에 테스트를 더한다.

## 11. 패키징과 배포

- `scripts/sync-payload.mjs`가 빌드 시 `.claude/`, `install.py`, `uninstall.py`, `MANIFEST.json`, `VERSION`을 `payload/`로 복사한다.
- `payload/`는 gitignore에 추가한다. 커밋된 사본이 본체와 어긋나는 사고를 원천 차단한다.
- `editor-extension/node_modules/`도 gitignore에 추가한다. 현재 `.gitignore`에 `node_modules/` 항목이 없다.
- 확장 버전은 루트 `VERSION`을 그대로 따른다. 확장 v1.15.0은 CommitForge v1.15.0을 담는다.
- 배포는 로컬 `.vsix`부터 시작한다. Marketplace·OpenVSX 공개는 이후 별도 판단한다.
- `release.py`와 `.github/workflows/verify.yml`에 확장 빌드·테스트를 통합할지는 구현 계획에서 결정한다. MVP는 수동 빌드로 충분하다.

## 12. 후속 단계

| 단계 | 내용 | 선행 조건 |
|---|---|---|
| 2 | 헤드리스 `/cr --format sarif` 실행 → Problems 패널 연동 | `claude` 실제 바이너리 탐색(§3.6), lock 충돌 정책, 권한 모드 결정 |
| 3 | 리뷰 결과 전용 패널, diff 점프, 결과 이력 | 2단계 |

각 단계는 별도 spec과 구현 계획을 갖는다.
