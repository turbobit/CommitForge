---
name: cp
description: CommitForge의 안전한 Pull Request 생성 명령이다. 현재 clean branch와 base 사이의 committed diff를 심층 리뷰·검증하고 fast-forward 가능한 일반 push를 수행한 뒤 GitHub Pull Request를 실제 생성한다. source, index, commit history는 바꾸지 않으며 사용자가 직접 /cp로 요청할 때만 실행한다.
argument-hint: "[clean] [추가 맥락] [--base <branch>] [--remote <name>] [--branch <name>] [--draft] [--title <text>] [--no-verify] [--strict] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: max
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Agent
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git merge-base *)
  - Bash(git show *)
  - Bash(git branch *)
  - Bash(git switch *)
  - Bash(git config *)
  - Bash(git remote *)
  - Bash(git rev-parse *)
  - Bash(git symbolic-ref *)
  - Bash(git ls-files *)
  - Bash(git ls-remote *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git check-ref-format *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
  - Bash(git push *)
  - Bash(gh auth status *)
  - Bash(gh repo view *)
  - Bash(gh pr list *)
  - Bash(gh pr create *)
  - Bash(gh pr view *)
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/pr_context.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/baseline.py" *)'
---

# `/cp` — Create Pull Request

사용자 맥락:

```text
$ARGUMENTS
```

`/cpr`과 같은 PR readiness 검토를 통과한 현재 committed branch를 push하고 실제 GitHub PR을 생성한다.

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
Guard를 생략하거나 스캔·리뷰·검증·staging·commit을 대신 수행하지 않는다.

## `clean` 조기 종료

첫 번째 위치 인자가 정확히 `clean`이면
`.claude/skills/_git-atomic-core/lock-cleanup.md`만 읽어 잠금 정리를
실행하고 즉시 종료한다. Guard `begin`, branch 변경, push와 PR 생성은 실행하지
않는다.

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

언어·프레임워크에 해당하는 `language-api-pitfalls.md` 섹션만 추가로 읽는다. 저장소 PR template, 프로젝트 규칙, `.commitforge/profile.md`, `.commitforge/profile.json` 학습 프로필을 순서대로 적용한다.

## 절대 경계

- source, index, commit SHA와 commit history를 수정하지 않는다. `main`/`master` 자동 분기에 필요한 branch 생성·전환만 예외다.
- dirty working tree, detached HEAD, ahead commit 0개, blocking finding에서는 push하지 않는다.
- 일반 fast-forward push만 허용하고 force 계열은 금지한다.
- 기존 PR을 자동 수정하거나 중복 생성하지 않는다.
- PR을 merge, close, ready 전환하거나 auto-merge하지 않는다.
- `Write`는 Guard snapshot 내부의 임시 PR 본문에만 사용한다.

## 실행

1. Guard `begin`으로 시작 상태를 보존한다. exit code가 0이 아니거나 `ok`가 `false`면
   fail-closed로 중단한다. exit code 126·127, `No such file or directory`,
   `command not found`, Python 미탐지도 같은 실패이며 Guard를 생략하고 push나 PR
   생성을 진행하지 않는다. `reason=guard_lock_conflict`이면 `stale_candidate`,
   `lock_owner_same_host`, `lock_owner_same_session`을 그대로 보고하고, 회수는
   `/cp clean` 또는 `begin --reclaim-stale`로 사용자 승인을 받은 뒤에만 한다.
   `reason=git_external_lock`은 Git 자체 lock이 원인이다. `git_locks` 진단과
   `recovery.remove_hint`를 보고하고 `/cp clean`을 안내한다. `clean`은 안전 조건을
   모두 통과한 stale lock만 제거하며 남은 lock은 강제로 삭제하지 않는다.
   Guard 실패 후 `git` 명령으로 우회해 push나 PR 생성을 진행하지 않는다.
2. base를 확정하고 `pr_context.py`로 clean branch와 committed range를 계산한다. 현재가 base인 `main`/`master`이면 `--allow-base-head`를 사용한다.
3. 모든 hunk와 net effect를 심층 리뷰하고 프로젝트 검증을 수행한다.
4. blocker가 없을 때 PR template 기반 제목·본문을 확정한다.
5. 현재가 `main`/`master`이면 의미에 맞는 충돌 없는 branch 이름을 검증하고 현재 commit에서 새 branch를 만든다.
6. 열린 동일-head PR을 조회한다. 있으면 새 PR을 만들지 않고 기존 URL을 보고한다.
7. `ls-remote` SHA와 최신 local tracking ref가 일치하는지 확인한 뒤 fast-forward 가능성을 검증한다. tracking ref가 없거나 stale이면 자동 fetch하지 않고 차단한다.
8. 현재 HEAD를 검증된 동일 이름 remote branch로 force 없이 push한다.
9. remote SHA가 현재 HEAD인지 확인한다.
10. snapshot 내부 PR 본문 파일로 `gh pr create`를 실행한다. `--draft`를 정확히 반영한다.
11. 생성된 PR number·URL·base·head·draft·title을 다시 조회한다.
12. source/index/commit SHA 불변을 확인한다. 자동 분기하지 않았다면 Guard의 source-read-only 절차를 사용하고, 자동 분기했다면 `--expected-branch "<validated-branch>"`로 허용된 branch 이름 변경만 검증한다.

## 부분 실패

- push 후 PR 생성 실패 시 remote branch를 삭제하거나 되돌리지 않는다.
- PR 생성 후 로컬 불변 검증 실패 시 PR을 close하지 않는다.
- 자동 branch 생성 후 실패하면 원래 branch로 자동 복귀하거나 생성 branch를 삭제하지 않는다.
- 이미 수행된 remote 결과와 안전한 재시도 방법을 정확히 보고한다.

## 보고

- readiness와 품질 gate
- base/head/merge-base와 commit·diff 통계
- push remote/branch/SHA
- PR number·URL·title·draft
- 검증 결과와 남은 위험
- source/index/HEAD 불변 여부
- snapshot과 lock 상태
- force push, merge, deploy를 하지 않았음
