---
name: ccf
description: 현재 Git 변경사항 전체를 분석하고 의미·기능별로 분리해 여러 개의 commit을 순차 생성한다. /cc와 같은 Guard lock·snapshot·fingerprint 재검사·의존성 계획·프로젝트 검증을 모두 유지하고, hunk 단위 분리만 하지 않고 파일 단위로만 분리한다. 사용자가 직접 /ccf로 요청할 때만 사용한다.
argument-hint: "[clean] [추가 맥락] [--scope <경로...>] [--no-verify] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git show *)
  - Bash(git branch *)
  - Bash(git rev-parse *)
  - Bash(git ls-files *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
  - Bash(git add *)
  - Bash(git restore --staged *)
  - Bash(git commit *)
  - Bash(git diff-tree *)
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" *)'
---

# `/ccf` — CommitForge 파일 단위 의미 분리 커밋

사용자 참고 맥락:

```text
$ARGUMENTS
```

`/ccf`는 `/cc`와 **같은 절차와 같은 안전장치**로 현재 변경을 의미별로 분리해 여러 개의 commit을 만든다. 차이는 단 하나, **hunk 단위로 분리하지 않는다.** 분리는 파일 단위로만 하고, `git add -p`와 선택 patch(`git apply --cached`)를 쓰지 않는다.

hunk 분리는 `/cc`에서 가장 실패하기 쉬운 단계다. patch context 불일치, staged·unstaged가 겹친 파일의 index 재구성, 새 파일 부분 staging에서 오류가 날 수 있다. `/ccf`는 이 단계를 없애 staging을 항상 `git add -- <파일>`로 단순하게 유지한다.

| | `/cc` | `/ccf` |
|---|---|---|
| 커밋 수 | 의미 단위 여러 개 | 의미 단위 여러 개 |
| 분리 단위 | 파일 + hunk | **파일만** |
| worktree lock | 획득 | 획득 |
| Diff snapshot | 생성·정리 | 생성·정리 |
| fingerprint 재검사 | 커밋마다 | 커밋마다 |
| 의존성 계획 | 함 | 함 |
| 프로젝트 검증 | 기본 실행 | 기본 실행 |
| secret·conflict 차단 | 함 | 함 |

한 파일에 여러 의도가 섞여 있으면 그 파일은 가장 지배적인 의도의 커밋에 통째로 들어가므로 결과가 **완전한 Atomic Commit이 아닐 수 있다.** 섞인 파일이 많거나 공유·release 히스토리라면 `/cc` 또는 `/cca`를 사용한다.

## Skill 경로 확정 (필수 Preflight)

`SKILL_DIR`는 **이 SKILL.md가 들어 있는 디렉터리의 절대경로**다.
설치된 `SessionStart` 훅이 실제 Claude 세션 ID를 `COMMITFORGE_SESSION_ID`에
설정한다. 값이 비어 있으면 기존 세션이므로 Claude Code를 재시작한 뒤 다시 실행한다.
임의 세션 문자열을 만들거나 다른 ID로 대체하지 않는다. 상위 skills 루트로
치환하면 `/..` 때문에 core 밖을 가리켜 모든 명령이 실패한다.

다른 어떤 명령보다 먼저 `CF_CORE`를 확정한다.

1. `CF_CORE = <이 SKILL.md의 디렉터리>/../_git-atomic-core`로 두고 `Read`로 `CF_CORE/README.md`를 읽어 확인한다.
2. 실패하면 `Glob`으로 `**/_git-atomic-core/scripts/guard.py`를 찾아 다시 정한다.
3. 이후 모든 `.claude/skills/_git-atomic-core`를 확정된 `CF_CORE` 절대경로로 바꾼다.

둘 다 실패하면 fail-closed다. core 미설치로 보고하고 즉시 종료하며, 경로 해석 실패를 이유로
Guard를 생략하거나 스캔·검증·staging·commit을 대신 수행하지 않는다.

## `clean` 조기 종료

첫 번째 위치 인자가 정확히 `clean`이면
`.claude/skills/_git-atomic-core/lock-cleanup.md`만 읽어 잠금 정리를
실행하고 즉시 종료한다. Guard `begin`, staging과 commit은 실행하지 않는다.

## 필수 지침 로드

작업 전에 다음 파일을 읽고 적용한다. `/cc`와 같다.

1. `.claude/skills/_git-atomic-core/atomic-commit-rules.md`
2. `.claude/skills/_git-atomic-core/staging-strategy.md`
3. `.claude/skills/_git-atomic-core/commit-message-guide.md`
4. `.claude/skills/_git-atomic-core/safety-and-concurrency.md`
5. `.claude/skills/_git-atomic-core/project-profiles.md`
6. `.claude/skills/_git-atomic-core/reporting.md`

`staging-strategy.md`의 4절(한 파일에 여러 의도), 5절의 선택 patch 재구성, 6절(새 파일 부분 staging)은 **적용하지 않는다.** 이 명령에서는 아래 "파일 단위 분리 규칙"이 그 절들을 대신한다. 나머지 규칙이 충돌하면 안전·작업 유실 방지 규칙을 최우선으로 한다.

저장소 루트에 `.commitforge/profile.json`과 `.commitforge/profile.md`가 있으면 읽고, 명시적 프로젝트 규칙 다음 우선순위로 메시지·scope·분리 선호를 적용한다.

## 파일 단위 분리 규칙

- 각 파일은 **정확히 하나의 커밋에만** 속한다. 파일 단위로만 분리한다.
- `git add -p`, `git add -N` 후 patch 적용, `git apply --cached`, 선택 patch 파일 생성을 하지 않는다.
- 한 파일에 여러 의도가 섞이면 **가장 지배적인 의도**의 커밋에 파일 전체를 넣는다. 지배적 의도는 변경 줄 수가 아니라 그 파일이 존재하는 이유(동작 변경 > 리팩터링 > 포맷팅)로 판단한다.
- 섞인 파일을 넣은 커밋은 본문과 최종 보고에 함께 들어간 다른 의도를 적는다.
- 섞인 파일이 다른 커밋의 선행 조건을 담고 있으면(예: 리팩터링으로 추가한 helper를 다른 파일의 기능이 사용) 의존 순서가 깨지지 않도록 **두 커밋을 합치거나 그 파일의 커밋을 앞에 둔다.** 중간 커밋의 빌드 성립이 hunk 분리보다 우선한다.
- 같은 파일에 staged와 unstaged가 공존하면 둘 다 같은 커밋에 속하므로 `git add -- <파일>`로 파일 전체를 stage한다. 이것이 `/cc`와 다른 유일한 staging 동작이며, 최종 보고에 그 파일을 적는다.
- 이미 staged인 변경은 사용자의 의도 신호로 참고하되, 파일 단위 계획과 어긋나면 snapshot 확보 후 `git restore --staged -- <경로>`로 index만 재구성한다.

## 0. 인자 해석

- 일반 문장은 변경 의도와 커밋 메시지 작성에 참고한다.
- `--scope <경로...>`가 있으면 지정 범위만 커밋한다. 범위 밖 변경은 그대로 유지한다.
- `--no-verify`가 있을 때만 프로젝트 검증과 commit hook 우회를 허용한다. 그래도 staged diff, secret, Git safety 검사는 생략하지 않는다.
- `--keep-snapshot`이 있으면 성공 후에도 snapshot을 보존하되 lock은 해제한다.
- 알 수 없는 인자는 자연어 맥락으로 취급한다.
- push, amend, rebase, squash는 이 skill의 범위가 아니다.

## 1. 저장소 Guard 시작

다음을 실행한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" begin \
  --session "$COMMITFORGE_SESSION_ID"
```

JSON 결과의 `snapshot`, `fingerprint`, `head`, `recovery_ref`, `recovery_copy`를 작업 완료까지 보관한다.
이후 `conserve`·`finish`·`abort`에는 `--session "$COMMITFORGE_SESSION_ID"`만 넘긴다. Guard가 세션으로 현재 lock owner의 snapshot을 고르고, 옮겨 적은 `--token`은 무시한다(`token_ignored`). token을 다시 입력하지 않는다.

- `ok: false`이면 어떤 Git 변경도 수행하지 않고 원인을 보고한다.
- Guard 명령이 아예 실행되지 못한 경우도 같은 실패다. exit code 126·127,
  `No such file or directory`, `command not found`, Python 미탐지, permission
  거부가 여기에 해당한다. Guard를 생략하고 진행하지 않는다. Preflight로 `CF_CORE`를
  다시 확정해 한 번만 재시도하고, 그래도 실패하면 종료한다.
- 진행 중 merge/rebase/cherry-pick/revert/bisect, Git lock, 다른 CommitForge 명령의 lock이 있으면 중단한다.
- `reason=git_external_lock`은 Git 자체 lock이 원인이다. `git_locks`의
  `age_seconds`, `size`, `writer_pids`, `stale_candidate`와
  `recovery.remove_hint`를 그대로 보고하고 `/ccf clean`을 안내한다. `clean`은
  안전 조건을 모두 통과한 stale lock만 제거하며 남은 lock은 강제로 삭제하지 않는다.
- Guard `begin` 실패 후 `git status`·`git diff`·`git log`로 변경을 스캔하거나
  `git -C <경로>`로 우회해 작업을 이어가지 않는다.
- `reason=guard_lock_conflict`이면 `stale_candidate`, `lock_owner_same_host`,
  `lock_owner_same_session`, `lock_age_seconds`를 그대로 보고한다. stale 후보여도
  스스로 회수하지 않는다. `/ccf clean`은 사용자가 직접 입력해야 실행된다.
  `begin --reclaim-stale`은 사용자의 명시적 승인을 받은 뒤에만 실행한다.
- snapshot 경고가 있으면 위험을 평가하고 결과에 기록한다.
- 이후 실패하거나 중단하면 반드시 `abort`로 **자신의 lock만 해제하고 snapshot은 보존**한다.
- 작업 중 working tree를 바꾸거나 HEAD를 되돌리는 명령(`git reset`, `git checkout`, `git restore --worktree`, `git stash`, `git clean`)을 실행하지 않는다. staging이 꼬여도 `git restore --staged -- <경로>`로 index만 되돌리고, 그래도 설명할 수 없으면 `abort`한다 (`safety-and-concurrency.md` 2.1절).

## 2. 전체 변경 인벤토리

다음을 분리해서 확인한다.

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
```

필요한 관련 파일, 호출부, 타입, 테스트, migration, manifest, lockfile, generated source를 읽어 변경 의도를 확인한다. 파일명만 보고 분류하지 않는다.

추가 확인:

- 현재 branch/HEAD와 detached/unborn 여부
- staged와 unstaged가 같은 파일에 공존하는지
- 한 파일 안에 여러 의도가 섞였는지 (섞인 파일 목록을 따로 기록)
- rename/delete/submodule/LFS/binary
- debug code, 임시 로그, TODO/FIXME
- secret/credential 가능성, 자격 파일(`.env`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`)
- merge conflict marker(`<<<<<<<`, `=======`, `>>>>>>>`)
- 프로젝트별 commit convention과 최근 한글 메시지 스타일

secret·자격 파일·merge conflict marker를 발견하면 어떤 커밋도 만들지 않고 중단해 `abort`한다. secret 값 자체는 재출력하지 않고 파일과 줄 위치만 보고한다.

변경이 없으면 guard `finish`를 실행해 snapshot과 lock을 정리하고 “커밋할 변경 없음”을 보고한다.

## 3. 전체 커밋 계획

커밋을 시작하기 전에 남은 모든 변경을 다음 구조로 내부 계획한다.

- 순서
- type/scope
- 한글 제목 초안
- 목적
- 포함 파일
- 함께 들어가는 다른 의도 (섞인 파일이 있을 때)
- 선행 커밋 의존성
- 구현과 함께 묶을 테스트/설정/문서
- 검증 명령
- Breaking Change 여부

원칙:

- 기능, 수정, 리팩터링, 성능, 테스트-only, 문서, build/CI, style을 독립 의도별로 분리한다.
- 구현과 직접 회귀 테스트처럼 분리 시 중간 상태가 깨지는 변경은 함께 둔다.
- lockfile·generated 파일은 그것을 유발한 커밋에 함께 둔다.
- rename-only 파일과 로직 변경 파일은 가능한 분리한다. 같은 파일에서 rename과 수정이 함께 일어났으면 한 커밋에 둔다.
- 커밋 개수를 최소화하지 않되, 기술적 단계만으로 과도하게 쪼개지 않는다. 그룹이 하나뿐이면 커밋도 하나다.
- 각 커밋이 독립 적용·되돌림·이해가 가능해야 한다.
- 모든 파일이 정확히 한 커밋에 배정됐는지 확인한다.

## 4. Commit 반복 루프

남은 의도된 변경이 있는 동안 아래를 반복한다.

### 4.1 상태 재검사

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" fingerprint
git status --short --branch --untracked-files=all
```

마지막으로 예상한 상태와 설명되지 않는 차이가 있으면 외부 세션 변경으로 간주해 전체 diff를 다시 분석한다. 안전하게 설명할 수 없으면 중단한다.

이어서 변경 보존을 확인한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" conserve \
  --session "$COMMITFORGE_SESSION_ID"
```

`conserve`는 시작 시점의 변경이 커밋되지 않은 채 사라졌는지(`lost`) 확인한다. `ok: false`·`reason=worktree_changes_lost`이면 더 이상 stage·commit하지 않고 아래 “변경 유실 감지” 절차를 따른다.

### 4.2 하나의 커밋 단위만 stage

- `git add -- <명시적 경로...>`로 이 커밋에 배정된 파일 전체를 stage한다.
- 삭제와 rename은 관련 old/new 경로를 명시한다.
- `git add -p`, `git apply --cached`, 선택 patch를 사용하지 않는다.
- `git add -A`, `git add .`는 남은 모든 변경이 단일 커밋이라는 근거가 있을 때만 허용한다.
- scope 밖 파일을 stage하지 않는다.

### 4.3 staged diff 품질 검사

반드시 실행·검토한다.

```bash
git diff --cached --stat
git diff --cached --name-status
git diff --cached --summary
git diff --cached --check
git diff --cached
```

다음을 확인한다.

- staged diff가 비어 있지 않음
- staged 파일 목록이 계획의 포함 파일과 정확히 일치
- 계획 밖 파일 없음
- 필요한 호출부·타입·테스트 누락 없음
- secret/debug/임시 파일, merge conflict marker 없음
- 의도하지 않은 generated/lockfile 변화 없음
- 독립 cherry-pick/revert 가능
- 가능한 범위에서 중간 빌드 상태 성립

문제가 있으면 commit하지 말고 `git restore --staged -- <경로>`로 index만 되돌린 뒤 staging을 다시 구성한다. working tree 파일은 수정하지 않는다.

### 4.4 검증

`--no-verify`가 없으면 저장소가 명시한 가장 관련성 높은 빠른 검증을 수행한다. 명령을 찾는 우선순위는 `CLAUDE.md` → manifest scripts → Make/Task/CI → README다.

- 새 의존성을 설치하거나 업그레이드하지 않는다.
- 네트워크가 필요한 작업을 임의로 실행하지 않는다.
- 변경으로 인한 실패는 해결하지 말고 `/ccf` 범위를 벗어난 것으로 보고 중단한다. `/ccf`는 소스 코드를 수정하지 않는다.
- 기존/환경 실패는 근거를 구분해 기록한다.
- commit hook은 기본적으로 존중한다.

### 4.5 한글 Commit 메시지 작성

형식:

```text
type(scope): 한글 제목

- 변경 목적과 배경
- 핵심 동작·구현 변화
- 영향 범위와 호환성
- (해당하면) 파일 단위 분리 때문에 함께 들어간 다른 의도와 그 파일
- 실제 수행한 검증
```

- type/scope는 영문 소문자, 제목과 본문은 가능한 한글
- 제목은 가급적 72자 이내이며, 지배적 의도를 기준으로 쓴다
- diff에 없는 사실이나 실행하지 않은 검증을 쓰지 않는다
- Breaking Change면 `!`와 `BREAKING CHANGE:` trailer를 사용한다
- 여러 목적을 `및`으로 억지로 합치지 않는다

메시지는 stdin 또는 안전한 message file을 사용해 정확히 전달한다. `--amend`는 사용하지 않는다. `--no-verify`가 있으면 `git commit --no-verify`를 사용한다.

### 4.6 Commit 및 사후 검증

커밋 후:

```bash
git show --stat --oneline --decorate HEAD
git status --short --branch --untracked-files=all
```

기록:

- full/short hash
- 제목
- 목적
- 파일 수와 통계
- 함께 들어간 다른 의도
- 수행한 검증

hook이 파일을 수정했거나 예상하지 않은 변경이 생겼으면 이전 계획을 폐기하고 남은 diff를 처음부터 재분석한다.

## 5. 완료 조건

기본 모드에서는 모든 의도된 변경이 커밋되고 working tree/index가 깨끗해야 한다.

`--scope` 모드에서는:

- scope 밖 변경이 시작 상태와 동일함을 fingerprint/diff로 검증한다.
- 동일함을 확신할 수 있을 때만 dirty cleanup을 허용한다.
- 확신할 수 없으면 snapshot을 보존한다.

최종 상태, 시작 HEAD, 최종 HEAD, 생성 커밋 목록을 확인한다.

## 6. Snapshot 정리

### 전체 성공 + clean

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" finish \
  --session "$COMMITFORGE_SESSION_ID"
```

`--keep-snapshot`이면 `--keep-snapshot`을 추가한다.

### 검증된 scope 성공 + 의도된 dirty 유지

범위 밖 변경이 정확히 보존됐음을 검증한 경우에만 `--allow-dirty`를 추가한다.

### 실패·중단·불확실

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" abort \
  --session "$COMMITFORGE_SESSION_ID"
```

snapshot을 삭제하지 않는다.

### 변경 유실 감지 (`reason=worktree_changes_lost`)

`conserve` 또는 `finish`가 이 사유로 실패하면 working tree가 깨끗해 보여도 **성공이 아니다.**

1. 더 이상 stage·commit하지 않는다. reset·checkout·stash로 "정리"하지 않는다.
2. `abort`로 lock만 해제한다. snapshot과 recovery ref는 남는다.
3. `conservation.lost` 경로, `head_rewound`, `recovery_ref`, `recovery_copy`를 그대로 보고하고 복원 명령(`restore_hint`, ref가 사라졌으면 `restore_copy_hint`)을 안내한다. 복원은 사용자 승인 없이 실행하지 않는다.

`finish`를 다른 옵션으로 다시 실행해 이 검사를 우회하지 않는다.

### Guard 명령 실패 (그 밖의 모든 `ok: false`)

`conserve`·`finish`·`abort`가 다른 사유로 실패하면 보존 검사가 끝나지 않은 것이다. 성공으로 보지 않는다.

- `reason=lock_not_owned`는 이 실행의 잠금이 다른 세션이나 `clean`으로 풀렸다는 뜻이다. 결과에 함께 온 `conservation.lost`, `recovery_ref`, `recovery_copy`, `snapshot`을 그대로 보고하고 멈춘다. 잠금을 다시 잡거나 다른 세션의 잠금을 풀지 않는다.

- 더 이상 stage·commit하지 않고 `abort --session`을 한 번 실행한다. 그것도 실패하면 오류를 그대로 보고하고 멈춘다.
- Guard `clean`, snapshot·lock 디렉터리 삭제, `git update-ref -d refs/commitforge/...`로 빠져나가지 않는다. `clean`은 사용자가 `/ccf clean`을 직접 입력했을 때만 실행된다.
- 커밋 순서나 구성이 틀렸음을 알게 되어도 reset·rebase·cherry-pick으로 history를 고치지 않는다. 그때까지 만든 커밋과 문제를 보고하고 재구성은 사용자에게 맡긴다.

설치된 `worktree_gate.py` 훅은 Guard 잠금이 걸린 동안 허용 목록 밖의 git 명령(정적으로 해석할 수 없는 명령 포함), 다른 세션 이름의 Guard 명령, 사용자 입력 없는 `clean`, snapshot·recovery ref 삭제를 차단한다 (`safety-and-concurrency.md` 2.2절). 차단되면 다른 명령으로 우회하지 말고 이 절차를 따른다.

## 7. 최종 보고

`.claude/skills/_git-atomic-core/reporting.md`의 `/ccf` 형식을 따라 한글로 보고한다.

반드시 포함:

- 순서별 hash와 제목
- 각 커밋의 목적과 핵심 변경
- 파일 단위 분리 때문에 의도가 섞인 커밋과 그 파일 (없으면 "없음")
- staged·unstaged를 합쳐 stage한 파일
- 검증 결과
- 시작/최종 HEAD
- 남은 변경과 clean 여부
- snapshot 삭제/보존 위치
- 변경 보존 검사 결과 (`reporting.md` 공통 변경 보존 형식)
- lock 해제 여부
- push하지 않았음
- 실패했다면 이미 생성된 커밋과 안전한 복구 지침

의도가 섞인 커밋이 있으면 결과가 **완전한 Atomic Commit이 아닐 수 있다**는 점과, 필요하면 `/cc`로 hunk 단위 분리를 할 수 있다는 점을 알린다.

성공 여부를 과장하지 않는다.
