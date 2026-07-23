---
name: cc
description: 현재 Git 변경사항 전체를 분석하고 의미·기능별로 분리해 한글 제목과 상세한 한글 본문의 여러 Atomic Commit을 순차 생성한다. 사용자가 직접 /cc로 커밋 실행을 요청할 때만 사용한다.
argument-hint: "[추가 맥락] [--scope <경로...>] [--no-verify] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: high
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
  - Bash(git apply --cached *)
  - Bash(git apply --check *)
  - Bash(git commit *)
  - Bash(git diff-tree *)
  - 'Bash(bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" *)'
---

# `/cc` — CommitForge Atomic Commit 실행기

사용자 참고 맥락:

```text
$ARGUMENTS
```

이 명령은 **현재 변경을 편집하지 않고**, staging과 commit만 수행해 여러 개의 의미 단위 커밋을 만든다. 하나의 커밋으로 합치는 것이 목표가 아니다. 모든 의도된 변경이 소진될 때까지 반복한다.

## 필수 지침 로드

작업 전에 다음 파일을 읽고 적용한다.

1. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/atomic-commit-rules.md`
2. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/staging-strategy.md`
3. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/commit-message-guide.md`
4. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/safety-and-concurrency.md`
5. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/project-profiles.md`
6. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`

규칙이 충돌하면 안전·작업 유실 방지 규칙을 최우선으로 한다.

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
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" begin \
  --session "${CLAUDE_SESSION_ID}"
```

JSON 결과의 `session`, `token`, `snapshot`, `fingerprint`, `head`를 작업 완료까지 보관한다.

- `ok: false`이면 어떤 Git 변경도 수행하지 않고 원인을 보고한다.
- 진행 중 merge/rebase/cherry-pick/revert/bisect, Git lock, 다른 `/cc`·`/cca` lock이 있으면 중단한다.
- snapshot 경고가 있으면 위험을 평가하고 결과에 기록한다.
- 이후 실패하거나 중단하면 반드시 `abort`로 **자신의 lock만 해제하고 snapshot은 보존**한다.

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
- rename/delete/submodule/LFS/binary
- debug code, 임시 로그, TODO/FIXME
- secret/credential 가능성
- formatting-only와 논리 변경 혼합
- 프로젝트별 commit convention과 최근 한글 메시지 스타일

변경이 없으면 guard `finish`를 실행해 snapshot과 lock을 정리하고 “커밋할 변경 없음”을 보고한다.

## 3. 전체 Atomic Commit 계획

커밋을 시작하기 전에 남은 모든 변경을 다음 구조로 내부 계획한다.

- 순서
- type/scope
- 한글 제목 초안
- 목적
- 포함 file/hunk
- 제외 file/hunk
- 선행 커밋 의존성
- 구현과 함께 묶을 테스트/설정/문서
- 검증 명령
- Breaking Change 여부

원칙:

- 기능, 수정, 리팩터링, 성능, 테스트-only, 문서, build/CI, style을 독립 의도별로 분리한다.
- 구현과 직접 회귀 테스트처럼 분리 시 중간 상태가 깨지는 변경은 함께 둔다.
- rename-only와 로직 변경은 가능한 분리한다.
- 커밋 개수를 최소화하지 않되, 기술적 단계만으로 과도하게 쪼개지 않는다.
- 각 커밋이 독립 적용·되돌림·이해가 가능해야 한다.
- 이미 staged인 변경은 사용자의 의도 신호로 존중하되, 비원자적이면 snapshot 확보 후 index만 안전하게 재구성할 수 있다.

## 4. Commit 반복 루프

남은 의도된 변경이 있는 동안 아래를 반복한다.

### 4.1 상태 재검사

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" fingerprint
git status --short --branch --untracked-files=all
```

마지막으로 예상한 상태와 설명되지 않는 차이가 있으면 외부 세션 변경으로 간주해 전체 diff를 다시 분석한다. 안전하게 설명할 수 없으면 중단한다.

### 4.2 하나의 Atomic Unit만 stage

- 파일 전체가 해당 unit이면 `git add -- <명시적 경로>`를 사용한다.
- 한 파일에 여러 의도가 섞이면 `git add -p` 또는 검증된 선택 patch를 사용한다.
- staged/unstaged가 같은 파일이면 `git add <file>`로 덮어쓰지 않는다.
- patch 파일이 필요하면 반드시 `snapshot` 디렉터리 아래에만 만들고 working tree 파일은 수정하지 않는다.
- `git add -A`, `git add .`는 남은 모든 변경이 단일 unit이라는 근거가 있을 때만 허용한다.
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
- 정확히 하나의 목적
- 계획 밖 file/hunk 없음
- 필요한 호출부·타입·테스트 누락 없음
- secret/debug/임시 파일 없음
- 의도하지 않은 generated/lockfile 변화 없음
- 독립 cherry-pick/revert 가능
- 가능한 범위에서 중간 빌드 상태 성립

문제가 있으면 commit하지 말고 staging을 다시 구성한다.

### 4.4 검증

`--no-verify`가 없으면 저장소가 명시한 가장 관련성 높은 빠른 검증을 수행한다. 명령을 찾는 우선순위는 `CLAUDE.md` → manifest scripts → Make/Task/CI → README다.

- 새 의존성을 설치하거나 업그레이드하지 않는다.
- 네트워크가 필요한 작업을 임의로 실행하지 않는다.
- 변경으로 인한 실패는 해결하지 말고 `/cc` 범위를 벗어난 것으로 보고 중단한다. `/cc`는 소스 코드를 수정하지 않는다.
- 기존/환경 실패는 근거를 구분해 기록한다.
- commit hook은 기본적으로 존중한다.

### 4.5 한글 Commit 메시지 작성

형식:

```text
type(scope): 한글 제목

- 변경 목적과 배경
- 핵심 동작·구현 변화
- 영향 범위와 호환성
- 실제 수행한 검증
```

- type/scope는 영문 소문자, 제목과 본문은 가능한 한글
- 제목은 가급적 72자 이내
- diff에 없는 사실이나 실행하지 않은 검증을 쓰지 않는다
- Breaking Change면 `!`와 `BREAKING CHANGE:` trailer를 사용한다
- 여러 목적을 `및`으로 억지로 합치지 않는다

메시지는 stdin 또는 안전한 message file을 사용해 정확히 전달한다. `--amend`는 사용하지 않는다.

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
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

`--keep-snapshot`이면 `--keep-snapshot`을 추가한다.

### 검증된 scope 성공 + 의도된 dirty 유지

범위 밖 변경이 정확히 보존됐음을 검증한 경우에만 `--allow-dirty`를 추가한다.

### 실패·중단·불확실

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" abort \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

snapshot을 삭제하지 않는다.

## 7. 최종 보고

`${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`의 `/cc` 형식을 따라 한글로 보고한다.

반드시 포함:

- 순서별 hash와 제목
- 각 커밋의 목적과 핵심 변경
- 검증 결과
- 시작/최종 HEAD
- 남은 변경과 clean 여부
- snapshot 삭제/보존 위치
- lock 해제 여부
- push하지 않았음
- 실패했다면 이미 생성된 커밋과 안전한 복구 지침

성공 여부를 과장하지 않는다.
