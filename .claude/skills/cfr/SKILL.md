---
name: cfr
description: /cf가 만들 단일 묶음 커밋을 읽기 전용으로 미리 보여준다. 대상 파일, 대표 type, 한글 메시지 초안, secret·conflict 차단 사유와 권장 후속 명령을 제시하며 실제 staging과 commit은 수행하지 않는다. 사용자가 직접 /cfr로 요청할 때만 사용한다.
argument-hint: "[clean] [추가 맥락] [--scope <경로...>] [--verify] [--compact]"
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
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" *)'
---

# `/cfr` — CommitForge Fast Commit 미리보기

사용자 참고 맥락:

```text
$ARGUMENTS
```

**읽기 전용 명령이다.** `/cf`와 동일한 판단을 수행하지만 **실제 staging과 commit은 수행하지 않는다.** Git index, working tree, branch, stash, commit, 파일 내용을 변경하지 않으며 테스트·빌드처럼 산출물을 만들 수 있는 명령도 실행하지 않는다.

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
Guard를 생략하거나 스캔을 대신 수행하지 않는다.

## `clean` 조기 종료

첫 번째 위치 인자가 정확히 `clean`이면
`.claude/skills/_git-atomic-core/lock-cleanup.md`만 읽어 잠금 정리를
실행하고 즉시 종료한다. 일반 상태 분석은 하지 않는다.

## 필수 지침 로드

다음을 읽는다.

1. `.claude/skills/_git-atomic-core/fast-commit-rules.md`
2. `.claude/skills/_git-atomic-core/commit-message-guide.md`
3. `.claude/skills/_git-atomic-core/safety-and-concurrency.md`
4. `.claude/skills/_git-atomic-core/reporting.md`

`atomic-commit-rules.md`는 읽지 않는다. Atomic Commit 계획이 필요하면 `/ccr`을 안내한다.

저장소 루트에 `.commitforge/profile.json`과 `.commitforge/profile.md`가 있으면 읽고, 명시적 프로젝트 규칙 다음 우선순위로 메시지·scope 선호를 적용한다.

## 0. 인자 해석

- 일반 문장은 메시지 초안 작성에 참고한다. `type(scope): 제목` 형태를 직접 주면 그것을 대표 제목으로 우선한다.
- `--scope <경로...>`가 있으면 해당 범위만 대상으로 본다.
- `--verify`가 있으면 `/cf --verify`가 실행할 검증 명령을 **식별해 제시만** 한다. 실제로 실행하지 않는다.
- `--compact`가 있으면 본문 초안은 핵심 bullet만 제시한다.
- 알 수 없는 인자는 자연어 맥락으로 취급한다.

## 1. 저장소 Guard 시작

다음을 실행한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" begin \
  --session "$COMMITFORGE_SESSION_ID"
```

- `ok: false`이면 분석을 수행하지 않고 원인을 보고한다.
- Guard 명령이 아예 실행되지 못한 경우도 같은 실패다. exit code 126·127,
  `No such file or directory`, `command not found`, Python 미탐지, permission
  거부가 여기에 해당한다. Guard를 생략하고 진행하지 않는다. Preflight로 `CF_CORE`를
  다시 확정해 한 번만 재시도하고, 그래도 실패하면 종료한다. 이는 fail-closed다.
- `reason=git_external_lock`이면 `git_locks`의 `age_seconds`, `size`,
  `writer_pids`, `stale_candidate`와 `recovery.remove_hint`를 그대로 보고하고
  `/cfr clean`을 안내한다.
- `reason=guard_lock_conflict`이면 `stale_candidate`, `lock_owner_same_host`,
  `lock_owner_same_session`, `lock_age_seconds`를 그대로 보고한다. stale 후보여도
  스스로 회수하지 않고 `/cfr clean` 또는 `begin --reclaim-stale`을 안내한 뒤
  사용자 승인을 받아 실행한다.
- 분석이 끝나면 `finish`로 lock을 해제한다. 실패·중단이면 `abort`로 자신의 lock만 해제하고 snapshot은 보존한다.

## 2. 대상 인벤토리

다음을 실행한다.

```bash
git status --short --branch --untracked-files=all
git rev-parse --show-toplevel
git branch --show-current
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git log -20 --pretty=format:'%h%x09%s'
```

명시할 것:

- branch와 HEAD
- staged / unstaged / untracked 파일 수와 목록
- rename/delete/submodule/binary
- 분석 시점 이후 working tree가 바뀌면 초안이 무효화될 수 있음

변경이 없으면 초안을 만들지 말고 "커밋할 변경 없음"을 보고한다.

## 3. 차단 스캔

`fast-commit-rules.md` 3절 항목을 index 변경 없이 수행한다.

```bash
git diff --check
git diff --cached --check
```

secret/credential 후보, 자격 파일, 의도하지 않은 산출물 대량 유입, merge conflict marker, 진행 중 Git 작업을 확인한다. 발견한 항목은 `/cf` 실행 시 **차단 사유**로 명확히 표시한다. secret 값 자체는 재출력하지 않고 파일과 줄 위치만 보고한다.

## 4. 대표 type과 메시지 초안

`fast-commit-rules.md` 4·5절을 적용한다.

- 파일·hunk별 의도를 분류하고 각 의도의 비중을 밝힌다.
- 우선순위에 따라 선정한 대표 type과 **그 근거**를 제시한다.
- scope 후보(공통 상위 경로)와 생략 판단 근거를 제시한다.
- 다음 형식의 전체 메시지 초안을 제시한다.

```text
type(scope): 한글 제목

이 커밋은 Atomic Commit이 아니다. 아래 의도가 함께 묶여 있다.

- feat: ...
- fix: ...

영향 범위와 호환성:
실제 수행한 검증:
```

`실제 수행한 검증:` 줄은 `/cf`가 실행 후 채울 자리이므로, 초안에서는 예상 검증만 표시하고 수행했다고 쓰지 않는다.

## 5. 교차 검토

다음을 비판적으로 짚는다.

- 섞인 의도가 너무 많아 `/cf`보다 `/cc`가 적합한가? (서로 무관한 3개 이상의 의도, 또는 revert 단위가 명확히 갈리는 변경)
- 대표 type이 실제 지배적 변경을 가리는가?
- Breaking Change나 migration이 섞여 단일 커밋으로 묶으면 위험한가?
- `--scope`로 범위를 좁히는 편이 나은가?

## 6. 최종 요약

`.claude/skills/_git-atomic-core/reporting.md`의 `/cfr` 형식을 따라 한글로 보고한다.

반드시 포함:

- 대상 파일 수와 예상 통계
- 대표 type 선정 근거
- 메시지 초안
- 차단 사유와 해결 방법
- `--verify` 시 실행될 검증 명령(식별만)
- 권장 후속 명령: 그대로 진행하면 `/cf`, 의미 단위로 나누려면 `/cc` 또는 `/ccr`
- **이 커밋은 Atomic Commit이 아니다**는 경고
- lock 해제 여부
- **실제 Git 상태를 변경하지 않았음**

`/cfr` 결과를 파일에 저장하거나 staging/commit하지 않는다.
