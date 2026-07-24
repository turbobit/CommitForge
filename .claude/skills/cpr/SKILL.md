---
name: cpr
description: CommitForge의 Pull Request read-only 준비 명령이다. 현재 branch와 base 사이의 committed diff를 심층 리뷰하고 readiness, blocker, PR 제목·본문·검증 초안을 보고하지만 source, index, commit, remote branch와 PR은 변경하지 않는다. 사용자가 직접 /cpr로 요청할 때만 실행한다.
argument-hint: "[추가 맥락] [--base <branch>] [--remote <name>] [--branch <name>] [--draft] [--title <text>] [--no-verify] [--strict] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: max
allowed-tools:
  - Read
  - Grep
  - Glob
  - Agent
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
  - 'Bash(bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/pr_context.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/reviewer_triggers.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/baseline.py" *)'
---

# `/cpr` — Pull Request Preview

사용자 맥락:

```text
$ARGUMENTS
```

현재 branch가 PR로 제출 가능한지 검토하고, 실제 `/cp`가 생성할 PR을 완성된 형태로 미리 보고한다.

## 필수 규칙

작업 전에 다음을 읽는다.

1. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/pull-request-workflow.md`
2. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/safety-and-concurrency.md`
3. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/deep-review-protocol.md`
4. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/conditional-reviewers.md`
5. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-execution.md`
6. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-policy.md`
7. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/validation-strategy.md`
8. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/large-diff-review.md`

언어·프레임워크에 해당하는 `language-api-pitfalls.md` 섹션만 추가로 읽는다. 저장소의 PR template, `CLAUDE.md`, `AGENTS.md`, 기여 가이드, `.commitforge/review.yml`, `.commitforge/profile.md`, `.commitforge/profile.json` 학습 프로필도 적용한다.

## 절대 경계

- source, test, docs, config, untracked 파일을 생성·수정·삭제하지 않는다.
- staging, commit, branch 전환·생성, fetch, push를 하지 않는다. 현재가 `main`/`master`이면 생성할 branch 이름만 보고한다.
- PR 생성·수정·close·merge와 reviewer/label 지정도 하지 않는다.
- Atomic Commit 계획이나 commit 메시지 초안을 만들지 않는다.
- dirty 상태는 PR readiness blocker로 보고하되 working 변경을 PR 내용으로 가장하지 않는다.

## 실행

1. Guard `begin`으로 시작 상태를 보존한다.
2. `--base`가 없으면 GitHub 기본 branch를 읽는다.
3. `pr_context.py`로 local base/head/range/clean 상태를 계산한다. 현재가 base인 `main`/`master`이면 `--allow-base-head`로 remote tracking base 대비 ahead commit을 분석한다.
4. committed range의 모든 hunk와 최종 net effect를 심층 리뷰한다.
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
