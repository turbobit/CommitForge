---
name: cca
description: Git 변경 전체를 다각도로 리뷰하고 확정적 문제를 안전하게 보완한 뒤 검증하여, 최적 순서의 한글 Atomic Commit을 모두 생성하는 최고 강도 파이프라인이다. 사용자가 직접 /cca로 전체 자동화를 요청할 때만 실행한다.
argument-hint: "[추가 맥락] [--scope <경로...>] [--no-fix] [--no-verify] [--strict] [--iterations 1-5] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: max
allowed-tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Agent
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

# `/cca` — Ultimate Atomic Git Assistant

사용자 참고 맥락:

```text
$ARGUMENTS
```

**ultrathink.** 변경사항 전체를 근거 중심으로 분석하고, 리뷰 → 확정적 수정 → 재리뷰 → 검증 → Atomic Commit 계획 → 순차 commit → 최종 검증까지 한 번에 수행한다.

`/cca`는 push, amend, rebase, squash, force 작업을 하지 않는다.

## 필수 지침 로드

작업 전에 다음 파일을 읽는다.

1. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/atomic-commit-rules.md`
2. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/staging-strategy.md`
3. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/commit-message-guide.md`
4. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/safety-and-concurrency.md`
5. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-gates.md`
6. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/validation-strategy.md`
7. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/project-profiles.md`
8. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`

안전 규칙과 품질 gate가 다른 지침보다 우선한다.

## 0. 인자 해석

- 일반 문장은 구현 의도, 사용자 요구, commit 메시지 맥락으로 사용한다.
- `--scope <경로...>`: 지정 범위 중심으로 처리하되 필수 의존성은 분석한다.
- `--no-fix`: 소스 파일을 수정하지 않는다. blocking finding이 있으면 commit 전에 중단한다.
- 기본 모드: 근거가 확정적이고 국소적이며 원래 의도를 보존하는 CRITICAL/MAJOR 문제만 자동 수정한다.
- `--no-verify`: 프로젝트 테스트/검증과 hook 우회를 허용하지만 Git/secret/safety 검사는 유지한다.
- `--strict`: 확인된 MINOR도 가능한 범위에서 해소하거나 명시적으로 차단 판단한다.
- `--iterations N`: 리뷰-수정 반복 상한. 기본 3, 최소 1, 최대 5.
- `--keep-snapshot`: 성공 후 snapshot을 보존한다.
- 알 수 없는 옵션은 자연어 맥락으로 취급한다.
- 새 dependency 설치, 외부 서비스 변경, 데이터 파괴 작업은 인자로 명시돼도 별도 안전 판단 없이 수행하지 않는다.

## 1. Guard 및 원본 상태 보존

다음을 실행한다.

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" begin \
  --session "${CLAUDE_SESSION_ID}"
```

`session`, `token`, `snapshot`, `fingerprint`, 시작 `head`를 보관한다.

- `ok: false`면 즉시 중단한다.
- merge/rebase/cherry-pick/revert/bisect, Git lock, 동일 worktree의 다른 `/cc`·`/cca` 실행이 있으면 자동 해결하지 않는다.
- 이후 실패·중단 시 `abort`로 자신의 lock만 해제하고 원본 Diff snapshot은 보존한다.

## 2. 저장소·변경 전체 스캔

다음을 분리해 분석한다.

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git log -20 --pretty=format:'%h%x09%s'
```

읽어야 할 범위:

- 변경 파일 전체
- 관련 호출부·타입·인터페이스
- 직접/회귀 테스트
- manifest/lockfile/build/CI
- migration/schema/generated source
- 프로젝트 규칙(`CLAUDE.md`, `AGENTS.md`, 기여 가이드)
- 검증 명령 정의

분류:

- feat/fix/refactor/perf/test/docs/build/ci/style/chore
- staged/unstaged/untracked
- logical/formatting/generated
- API/schema/config breaking
- 위험 파일과 binary/submodule/LFS
- scope 밖 의존성

변경이 없으면 guard `finish`로 정리하고 종료한다.

## 3. 병렬 전문 리뷰

가능하면 다음 custom subagent를 **동일한 현재 diff 기준으로 병렬 실행**한다.

1. `cca-git-reviewer`
2. `cca-correctness-reviewer`
3. `cca-security-reviewer`
4. `cca-performance-reviewer`
5. `cca-testing-reviewer`

각 agent에 사용자 맥락, scope, staged/unstaged 구분, “파일을 수정하지 말고 근거와 정확한 위치를 반환”하라는 조건을 전달한다.

- Agent가 설치되지 않았거나 실행할 수 없으면 main agent가 동일 관점을 직접 수행한다.
- reviewer가 반환한 내용을 사실로 가정하지 않는다.
- main agent가 각 finding을 코드와 diff로 재현·검증한다.
- 중복 finding은 하나로 통합한다.
- 범위 밖 기존 문제와 현재 변경이 만든 문제를 구분한다.
- secret 후보 값은 출력하지 않고 마스킹한다.

## 4. 품질 Gate와 수정 반복

`${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-gates.md`를 적용한다.

### 기본 Gate

- 확인된 CRITICAL: 반드시 차단 또는 안전하게 수정
- 확인된 MAJOR: 기본적으로 차단 또는 안전하게 수정
- MINOR: 현재 scope와 위험에 따라 수정/기록
- NOTE: scope를 확대하지 않고 기록

### 자동 수정 허용 범위

다음 조건을 모두 만족해야 한다.

- 현재 변경이 만든 문제
- 실패 시나리오가 명확함
- 수정이 국소적이고 원래 의도를 보존
- 새 dependency/외부 변경 불필요
- 직접 검증 가능
- 광범위한 설계 선택이 아님

수정할 수 있는 예:

- 누락된 null/boundary/error 처리
- 필수 호출부·타입 오류
- 명백한 secret 제거
- 직접 회귀 테스트
- 명백한 resource cleanup 또는 idempotency 오류
- hook/lint가 지적하는 국소 문제

자동 수정하지 않는 예:

- 요구가 불명확한 UX/업무 규칙
- 광범위한 리팩터링/재설계
- 취향 기반 개선
- 데이터 파괴 migration
- 범위 밖 기존 문제
- dependency 설치/업그레이드

`--no-fix`이면 소스 수정 없이 blocking 결과에서 중단한다.

### 반복

수정 후:

1. 전체 diff를 다시 읽는다.
2. guard fingerprint를 갱신한다.
3. 변경한 관점 reviewer와 Git reviewer를 다시 실행한다.
4. 기존 계획과 finding을 폐기하고 새 상태로 판단한다.

상한은 `--iterations`다. 상한까지 blocking finding이 남으면 commit하지 않고 snapshot을 보존한다.

## 5. 검증 전략 수립 및 실행

`${CLAUDE_SKILL_DIR}/../_git-atomic-core/validation-strategy.md`에 따라 저장소가 정의한 명령을 우선한다.

기본 순서:

1. changed-area의 가장 빠른 unit/regression test
2. 관련 lint/type check
3. 관련 build/check
4. 비용이 합리적이면 전체 test/build

제약:

- 임의로 의존성을 설치·업그레이드하지 않는다.
- 명령을 추측해 환경을 변경하지 않는다.
- 네트워크/credential/DB가 필요한 경우 환경 실패로 분리한다.
- 변경으로 인한 실패는 commit 전에 해결한다.
- 명백히 무관한 기존 실패만 근거와 함께 경고 처리할 수 있다.
- `--no-verify`여도 staged diff, whitespace, secret, safety 검사는 수행한다.

## 6. 최종 Atomic Commit 계획

리뷰와 수정이 끝난 **현재 diff**로 전체 commit dependency graph를 다시 만든다.

각 unit:

- 하나의 목적
- type/scope와 한글 제목
- 포함 file/hunk
- 직접 테스트/설정/문서
- 선행 의존성
- 예상 staging 방식
- targeted 검증
- Breaking Change/migration/deployment 영향

다음을 방지한다.

- Feature/Fix/Refactor 혼합
- 파일별 기계적 분리
- 구현과 필수 테스트 과도 분리
- 포맷팅과 로직 혼합
- lockfile/generated 원인 없는 포함
- 중간 commit의 build/type 파손
- 여러 목적을 `및`으로 합친 제목

## 7. Commit 실행 루프

각 unit마다 다음을 수행한다.

### 7.1 TOCTOU 확인

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" fingerprint
git status --short --branch --untracked-files=all
```

자신의 수정·staging으로 설명되지 않는 변화면 재분석하거나 중단한다.

### 7.2 정확한 staging

- 명시적 path 또는 선택 hunk만 stage
- mixed file은 `git add -p` 또는 snapshot 아래의 검증된 patch 사용
- staged/unstaged 공존 파일에 무조건 `git add <file>` 금지
- `git add -A`/`.`는 단일 unit이라는 증거가 있을 때만 허용
- working tree를 staging 편의를 위해 편집하지 않음

### 7.3 staged diff 재리뷰

```bash
git diff --cached --stat
git diff --cached --name-status
git diff --cached --summary
git diff --cached --check
git diff --cached
```

main agent가 다음을 다시 확인한다.

- 정확히 하나의 목적
- 계획 밖 변경 없음
- 필수 변경 누락 없음
- reviewer에서 해결한 결함이 재발하지 않음
- secret/debug/임시 코드 없음
- 독립 적용·되돌림 가능
- 메시지 초안과 diff 일치

고위험 unit이면 관련 reviewer를 staged diff에 대해 한 번 더 실행한다.

### 7.4 Targeted 검증

가능한 빠른 검증을 commit 전에 실행한다. 실패하면 commit하지 않는다. hook을 존중한다.

### 7.5 Commit 메시지

```text
type(scope): 한글 제목

- 배경과 목적
- 핵심 동작/구현
- 영향·호환성·migration
- 실제 검증
```

- 과장/추측 금지
- 제목 가급적 72자 이내
- Breaking Change는 `!`와 trailer
- `--amend` 금지

### 7.6 Commit 후

```bash
git show --stat --oneline --decorate HEAD
git status --short --branch --untracked-files=all
```

hash, 제목, 목적, 통계, 검증을 기록한다. hook/도구가 새로운 파일을 수정했다면 남은 계획을 전부 재생성한다.

## 8. 최종 통합 검증

마지막 commit 후 가능한 범위에서:

- 전체 또는 대표 test
- type check/lint
- build/check
- migration/generated consistency
- `git status`
- 생성된 commit 순서와 dependency
- 각 commit의 title/body/stats

검증 실패가 현재 변경과 관련되면 성공 처리하지 않는다. 이미 생성한 commit을 자동 amend/reset하지 않는다. snapshot을 보존하고 현재 상태를 정확히 보고한다.

## 9. Snapshot 및 Lock 종료

### 완전 성공 + clean

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

`--keep-snapshot`이면 해당 옵션을 추가한다.

### 검증된 scope 성공 + 범위 밖 dirty 유지

범위 밖 변경이 시작 상태와 정확히 같음을 검증한 경우에만 `--allow-dirty`를 사용한다. 불확실하면 snapshot을 보존한다.

### 실패·중단·부분 완료

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" abort \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

snapshot은 삭제하지 않는다.

## 10. 최종 보고

`${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`의 `/cca` 형식으로 한글 보고한다.

포함:

- reviewer별 finding 수와 Gate 결과
- 검증 후 채택/기각한 중요 finding
- 자동 수정한 내용
- 실행한/생략한 검증
- 순서별 commit hash·제목·목적·통계
- 시작 HEAD → 최종 HEAD
- Breaking Change/migration/deployment 주의
- 남은 변경과 clean 여부
- snapshot 삭제 또는 보존 경로
- lock 해제 여부
- push하지 않았음
- 실패 시 이미 만든 commit과 안전한 복구 방법

완료되지 않은 작업을 성공으로 표현하지 않는다.
