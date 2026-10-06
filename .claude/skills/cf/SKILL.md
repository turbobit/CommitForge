---
name: cf
description: 아직 커밋되지 않은 모든 Git 변경을 의미 단위로 분리하지 않고 하나의 commit으로 빠르게 묶는다. Guard와 secret 차단 스캔은 유지하되 계획·hunk staging·프로젝트 검증은 생략한다. 결과는 Atomic Commit이 아니므로 사용자가 직접 /cf로 요청할 때만 사용한다.
argument-hint: "[clean] [추가 맥락] [--scope <경로...>] [--verify] [--no-verify] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: medium
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

# `/cf` — CommitForge Fast Commit 실행기

사용자 참고 맥락:

```text
$ARGUMENTS
```

이 명령은 **현재 변경을 편집하지 않고**, 아직 커밋되지 않은 모든 변경을 하나의 index로 합쳐 **단일 commit**을 만든다. 여러 의미 단위로 분리하지 않는다. 결과는 정의상 Atomic Commit이 아니며, 공유 히스토리에는 `/cc` 또는 `/cca`가 적합하다.

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

작업 전에 다음 파일을 읽고 적용한다.

1. `.claude/skills/_git-atomic-core/fast-commit-rules.md`
2. `.claude/skills/_git-atomic-core/commit-message-guide.md`
3. `.claude/skills/_git-atomic-core/safety-and-concurrency.md`
4. `.claude/skills/_git-atomic-core/reporting.md`
5. `--verify`가 있을 때만 `.claude/skills/_git-atomic-core/validation-strategy.md`

`atomic-commit-rules.md`는 읽지 않는다. `/cf`는 커밋을 분리하지 않으므로 그 규칙과 의도적으로 다르다.

규칙이 충돌하면 안전·작업 유실 방지 규칙을 최우선으로 한다.

저장소 루트에 `.commitforge/profile.json`과 `.commitforge/profile.md`가 있으면 읽고, 명시적 프로젝트 규칙 다음 우선순위로 메시지·scope 선호를 적용한다. 프로필의 커밋 분리 선호는 `/cf`에서 적용하지 않는다.

## 0. 인자 해석

- 일반 문장은 커밋 메시지 작성에 참고한다. `type(scope): 제목` 형태를 직접 주면 그것을 대표 제목으로 우선한다.
- `--scope <경로...>`가 있으면 지정 범위만 커밋한다. 범위 밖 변경은 그대로 유지한다.
- `--verify`가 있으면 commit 전에 프로젝트의 빠른 검증을 실행한다.
- `--no-verify`가 있으면 commit hook을 우회한다. 그래도 차단 스캔과 staged diff 확인은 생략하지 않는다.
- `--verify`와 `--no-verify`를 함께 주면 오류로 보고하고 종료한다.
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
- 진행 중 merge/rebase/cherry-pick/revert/bisect, Git lock, 다른 `/cf`·`/cc`·`/cca` lock이 있으면 중단한다.
- `reason=git_external_lock`은 Git 자체 lock이 원인이다. `git_locks`의
  `age_seconds`, `size`, `writer_pids`, `stale_candidate`와
  `recovery.remove_hint`를 그대로 보고하고 `/cf clean`을 안내한다. `clean`은
  안전 조건을 모두 통과한 stale lock만 제거하며 남은 lock은 강제로 삭제하지 않는다.
- Guard `begin` 실패 후 `git status`·`git diff`·`git log`로 변경을 스캔하거나
  `git -C <경로>`로 우회해 작업을 이어가지 않는다.
- `reason=guard_lock_conflict`이면 `stale_candidate`, `lock_owner_same_host`,
  `lock_owner_same_session`, `lock_age_seconds`를 그대로 보고한다. stale 후보여도
  스스로 회수하지 않는다. `/cf clean`은 사용자가 직접 입력해야 실행된다.
  `begin --reclaim-stale`은 사용자의 명시적 승인을 받은 뒤에만 실행한다.
- snapshot 경고가 있으면 위험을 평가하고 결과에 기록한다.
- 이후 실패하거나 중단하면 반드시 `abort`로 **자신의 lock만 해제하고 snapshot은 보존**한다.
- 작업 중 working tree를 바꾸거나 HEAD를 되돌리는 명령(`git reset`, `git checkout`, `git restore --worktree`, `git stash`, `git clean`)을 실행하지 않는다. staging이 꼬여도 `git restore --staged -- <경로>`로 index만 되돌리고, 그래도 설명할 수 없으면 `abort`한다 (`safety-and-concurrency.md` 2.1절).

## 2. 대상 인벤토리

다음을 실행한다.

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git log -20 --pretty=format:'%h%x09%s'
```

확인할 것:

- 현재 branch/HEAD와 detached/unborn 여부
- staged / unstaged / untracked 각각의 파일 수
- rename/delete/submodule/LFS/binary
- 프로젝트별 commit convention과 최근 한글 메시지 스타일

**여기서 커밋 분리 계획을 세우지 않는다.** 파일별 의도 분류는 대표 type 선정과 메시지 본문 작성에 필요한 만큼만 수행하고, 의존성 그래프·순서·hunk 분할은 하지 않는다. 이 생략이 `/cf`가 빠른 이유다.

변경이 없으면 guard `finish`를 실행해 snapshot과 lock을 정리하고 "커밋할 변경 없음"을 보고한다.

## 3. 차단 스캔

`fast-commit-rules.md` 3절의 항목을 그대로 수행한다. secret/credential 후보, 자격 파일, 의도하지 않은 산출물 대량 유입, merge conflict marker, whitespace 오류, 진행 중 Git 작업을 확인한다.

```bash
git diff --check
git diff --cached --check
```

하나라도 걸리면 `git add`와 commit을 수행하지 않고 중단한다. secret 값 자체는 결과에 재출력하지 않고 파일과 줄 위치만 보고한다. 이 스캔은 `--verify`, `--no-verify`, `--scope` 어느 것으로도 끄지 않는다.

## 4. 단일 Unit staging

`--scope`가 없으면 남은 모든 변경이 하나의 unit이므로 다음을 사용한다.

```bash
git add -A --
```

`--scope`가 있으면 지정 경로만 명시해 stage한다.

```bash
git add -A -- <scope 경로...>
```

- working tree 파일을 수정하지 않는다. patch 파일이 필요하면 `snapshot` 디렉터리 아래에만 만든다.
- 이미 staged된 변경은 그대로 index에 남겨 함께 커밋한다. `/cf`는 index를 되돌리지 않는다.
- scope 밖 파일을 stage하지 않는다.

## 5. staged diff 확인

반드시 실행·검토한다.

```bash
git diff --cached --stat
git diff --cached --name-status
git diff --cached --summary
git diff --cached --check
git diff --cached
```

확인할 것:

- staged diff가 비어 있지 않음
- 계획 밖 경로(`--scope` 위반) 없음
- 3절 차단 항목이 staged diff에 없음
- 의도하지 않은 generated/lockfile/대용량 파일 유입 없음

문제가 있으면 commit하지 말고 중단한 뒤 현재 index 상태와 복구 방법을 보고한다.

## 6. 검증

`/cf`는 **기본적으로 프로젝트 검증을 실행하지 않는다**. 그리고 commit hook은 기본적으로 존중한다.

- `--verify`가 있을 때만 `validation-strategy.md`에 따라 저장소가 명시한 가장 관련성 높은 빠른 검증을 수행한다. 명령을 찾는 우선순위는 `CLAUDE.md` → manifest scripts → Make/Task/CI → README다.
- `--no-verify`가 있으면 `git commit --no-verify`로 hook을 우회한다.
- 새 의존성을 설치하거나 업그레이드하지 않는다. 네트워크가 필요한 작업을 임의로 실행하지 않는다.
- 변경으로 인한 검증 실패는 해결하지 말고 `/cf` 범위를 벗어난 것으로 보고 중단한다. `/cf`는 소스 코드를 수정하지 않는다.
- 기본 모드에서 검증을 생략했다는 사실을 최종 보고에 반드시 남긴다. 실행하지 않은 검증을 "시도함"으로 보고하지 않는다.

## 7. 한글 Commit 메시지 작성

`fast-commit-rules.md` 4·5절의 대표 type과 형식을 그대로 적용한다.

```text
type(scope): 한글 제목

이 커밋은 Atomic Commit이 아니다. 아래 의도가 함께 묶여 있다.

- feat: ...
- fix: ...

영향 범위와 호환성:
실제 수행한 검증:
```

- type/scope는 영문 소문자, 제목과 본문은 가능한 한글
- 제목은 가급적 72자 이내
- 섞인 의도를 하나도 빠뜨리지 않고 나열한다
- diff에 없는 사실이나 실행하지 않은 검증을 쓰지 않는다
- Breaking Change면 `!`와 `BREAKING CHANGE:` trailer를 사용한다

메시지는 stdin 또는 안전한 message file을 사용해 정확히 전달한다. `--amend`는 사용하지 않는다.

## 8. Commit 및 사후 검증

커밋 후:

```bash
git show --stat --oneline --decorate HEAD
git status --short --branch --untracked-files=all
```

기록:

- full/short hash
- 제목
- 묶인 의도 목록
- 파일 수와 통계
- 수행·생략한 검증

hook이 파일을 수정했거나 예상하지 않은 변경이 생겼으면 그 사실을 그대로 보고한다. 추가 커밋으로 덮지 않는다.

커밋 뒤 정리 전에 변경 보존을 확인한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" conserve \
  --session "$COMMITFORGE_SESSION_ID"
```

`conserve`는 시작 시점의 변경이 커밋되지 않은 채 사라졌는지(`lost`) 확인한다. `ok: false`·`reason=worktree_changes_lost`이면 더 이상 stage·commit하지 않고 아래 “변경 유실 감지” 절차를 따른다.

## 9. 완료 조건

기본 모드에서는 모든 미커밋 변경이 단일 커밋에 들어가고 working tree/index가 깨끗해야 한다.

`--scope` 모드에서는:

- scope 밖 변경이 시작 상태와 동일함을 fingerprint/diff로 검증한다.
- 동일함을 확신할 수 있을 때만 dirty cleanup을 허용한다.
- 확신할 수 없으면 snapshot을 보존한다.

## 10. Snapshot 정리

### 성공 + clean

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
- Guard `clean`, snapshot·lock 디렉터리 삭제, `git update-ref -d refs/commitforge/...`로 빠져나가지 않는다. `clean`은 사용자가 `/cf clean`을 직접 입력했을 때만 실행된다.
- 커밋 순서나 구성이 틀렸음을 알게 되어도 reset·rebase·cherry-pick으로 history를 고치지 않는다. 그때까지 만든 커밋과 문제를 보고하고 재구성은 사용자에게 맡긴다.

설치된 `worktree_gate.py` 훅은 Guard 잠금이 걸린 동안 허용 목록 밖의 git 명령(정적으로 해석할 수 없는 명령 포함), 다른 세션 이름의 Guard 명령, 사용자 입력 없는 `clean`, snapshot·recovery ref 삭제를 차단한다 (`safety-and-concurrency.md` 2.2절). 차단되면 다른 명령으로 우회하지 말고 이 절차를 따른다.

## 11. 최종 보고

`.claude/skills/_git-atomic-core/reporting.md`의 `/cf` 형식을 따라 한글로 보고한다.

반드시 포함:

- 생성 커밋 hash와 제목
- 묶인 의도 목록
- 파일 수와 통계
- 수행·생략한 검증
- 시작/최종 HEAD
- 남은 변경과 clean 여부
- snapshot 삭제/보존 위치
- 변경 보존 검사 결과 (`reporting.md` 공통 변경 보존 형식)
- lock 해제 여부
- push하지 않았음
- **이 커밋은 Atomic Commit이 아니다**는 경고와, 공유 히스토리에는 `/cc` 또는 `/cca`를 권장한다는 안내
- 실패했다면 현재 index 상태와 안전한 복구 지침

성공 여부를 과장하지 않는다.
