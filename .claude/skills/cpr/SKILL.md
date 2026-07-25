---
name: cpr
description: CommitForge의 Pull Request read-only 준비 명령이다. 현재 branch와 base 사이의 committed diff를 심층 리뷰하고 readiness, blocker, PR 제목·본문·검증 초안을 보고하지만 source, index, commit, remote branch와 PR은 변경하지 않는다. 사용자가 직접 /cpr로 요청할 때만 실행한다.
argument-hint: "[clean] [추가 맥락] [--team|--no-team] [--base <branch>] [--remote <name>] [--branch <name>] [--draft] [--title <text>] [--no-verify] [--strict] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: max
allowed-tools:
  - Read
  - Grep
  - Glob
  - Agent
  - SendMessage
  - TaskCreate
  - TaskGet
  - TaskList
  - TaskUpdate
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git merge-base *)
  - Bash(git show *)
  - Bash(git branch *)
  - Bash(git config *)
  - Bash(git remote *)
  - Bash(git rev-parse *)
  - Bash(git symbolic-ref *)
  - Bash(git ls-files *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git check-ref-format *)
  - Bash(git ls-remote *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
  - Bash(gh auth status *)
  - Bash(gh repo view *)
  - Bash(gh pr list *)
  - Bash(gh pr view *)
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/pr_context.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/baseline.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/agent_team_mode.py")'
---

# `/cpr` — Pull Request Preview

사용자 맥락:

```text
$ARGUMENTS
```

현재 branch가 PR로 제출 가능한지 검토하고, 실제 `/cp`가 생성할 PR을 완성된 형태로 미리 보고한다.

## Skill 경로 확정 (필수 Preflight)

`SKILL_DIR`는 **이 SKILL.md가 들어 있는 디렉터리의 절대경로**,
`<current-session-id>`는 현재 세션 ID다. shell 환경변수가 아니므로 실행 전에 실제 값으로
치환한다. 상위 skills 루트로 치환하면 `/..` 때문에 core 밖을 가리켜 모든 명령이 실패한다.

다른 어떤 명령보다 먼저 `CF_CORE`를 확정한다.

1. `CF_CORE = <이 SKILL.md의 디렉터리>/../_git-atomic-core`로 두고 `Read`로 `CF_CORE/README.md`를 읽어 확인한다.
2. 실패하면 `Glob`으로 `**/_git-atomic-core/scripts/guard.py`를 찾아 다시 정한다.
3. 이후 모든 `.claude/skills/_git-atomic-core`를 확정된 `CF_CORE` 절대경로로 바꾼다.

둘 다 실패하면 fail-closed다. core 미설치로 보고하고 즉시 종료하며, 경로 해석 실패를 이유로
Guard를 생략하거나 스캔·리뷰·검증·staging·commit을 대신 수행하지 않는다.

## `clean` 조기 종료

첫 번째 위치 인자가 정확히 `clean`이면
`.claude/skills/_git-atomic-core/lock-cleanup.md`만 읽어 잠금 정리를
실행하고 즉시 종료한다. Guard `begin`, PR 조회, 리뷰와 검증은 실행하지 않는다.

## 필수 규칙

작업 전에 다음을 읽는다.

1. `.claude/skills/_git-atomic-core/pull-request-workflow.md`
2. `.claude/skills/_git-atomic-core/safety-and-concurrency.md`
3. `.claude/skills/_git-atomic-core/deep-review-protocol.md`
4. `.claude/skills/_git-atomic-core/conditional-reviewers.md`
5. `.claude/skills/_git-atomic-core/review-execution.md`
6. `.claude/skills/_git-atomic-core/review-policy.md`
7. `.claude/skills/_git-atomic-core/validation-strategy.md`
8. `.claude/skills/_git-atomic-core/large-diff-review.md`

언어·프레임워크에 해당하는 `language-api-pitfalls.md` 섹션만 추가로 읽는다. 저장소의 PR template, `CLAUDE.md`, `AGENTS.md`, 기여 가이드, `.commitforge/review.yml`, `.commitforge/profile.md`, `.commitforge/profile.json` 학습 프로필도 적용한다.

## 절대 경계

- source, test, docs, config, untracked 파일을 생성·수정·삭제하지 않는다.
- staging, commit, branch 전환·생성, fetch, push를 하지 않는다. 현재가 `main`/`master`이면 생성할 branch 이름만 보고한다.
- PR 생성·수정·close·merge와 reviewer/label 지정도 하지 않는다.
- Atomic Commit 계획이나 commit 메시지 초안을 만들지 않는다.
- dirty 상태는 PR readiness blocker로 보고하되 working 변경을 PR 내용으로 가장하지 않는다.

## 실행

1. Guard `begin`으로 시작 상태를 보존한다. exit code가 0이 아니거나 `ok`가 `false`면
   fail-closed로 중단한다. exit code 126·127, `No such file or directory`,
   `command not found`, Python 미탐지도 같은 실패이며 Guard를 생략하고 리뷰를
   진행하지 않는다. `reason=guard_lock_conflict`이면 `stale_candidate`,
   `lock_owner_same_host`, `lock_owner_same_session`을 그대로 보고하고, 회수는
   `/cpr clean` 또는 `begin --reclaim-stale`로 사용자 승인을 받은 뒤에만 한다.
   `reason=git_external_lock`은 Git 자체 lock이 원인이다. `git_locks` 진단과
   `recovery.remove_hint`를 보고하고 `/cpr clean`을 안내한다. `clean`은 안전 조건을
   모두 통과한 stale lock만 제거하며 남은 lock은 강제로 삭제하지 않는다.
   Guard 실패 후 `git` 명령으로 우회해 리뷰를 진행하지 않는다.
2. `--base`가 없으면 GitHub 기본 branch를 읽는다.
3. `pr_context.py`로 local base/head/range/clean 상태를 계산한다. 현재가 base인 `main`/`master`이면 `--allow-base-head`로 remote tracking base 대비 ahead commit을 분석한다.
4. `--team`·`--no-team` 충돌을 검사한다. 옵션이 없고 환경이 활성화되어 있으면
   Team을 기본으로 하되 명백히 사소한 단일 영역 변경만 축소한다. Team이면
   core 3명이 domain/runtime shard, shared task와 peer messaging으로 committed
   range의 모든 hunk, contract와 최종 net effect를 교차검증한다. Testing·
   Reliability·UX·Migration·Requirements·Release·Domain trigger에 따라
   specialist를 추가한다. Team fallback에서는 기존 subagent를 사용한다.
5. 저장소 정의 검증을 실행한다. `--no-verify`여도 safety 검사는 유지한다.
6. PR template에 맞춘 제목·본문 초안을 작성한다.
7. readiness와 blocker를 결정한다.
8. `verify-review --source-read-only`와 `finish --review-only --source-read-only`로 불변 상태를 검증한다.
9. PR 초안과 결과를 한글로 보고한다.

## 보고

- `READY`, `CONDITIONAL`, `BLOCKED`
- base/head/merge-base와 committed range
- commit·파일·추가·삭제 통계
- 중요 finding과 blocker
- 실행·생략·실패한 검증
- 완성된 PR 제목과 본문
- `/cp`가 push할 remote/branch와 draft 여부
- 현재가 `main`/`master`이면 `/cp`가 생성할 충돌 없는 branch 이름과 선정 근거
- source/index/HEAD/remote/PR이 모두 불변임

완료되지 않은 검토를 성공으로 표현하지 않는다.
