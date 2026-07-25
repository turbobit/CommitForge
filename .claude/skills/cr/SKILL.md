---
name: cr
description: CommitForge의 최고 강도 코드 리뷰 명령이다. 현재 변경이나 기간·release·emergency·learn·branch·range·PR 범위를 기본 읽기 전용으로 심층 리뷰하며, 일반 리뷰에서 사용자가 --fix를 명시한 경우에만 확정적 working-tree 문제를 수정한다. release·emergency·learn은 항상 읽기 전용이고 Atomic Commit 계획, staging, commit, tag, push는 하지 않는다.
argument-hint: "[clean|today|3days|weekly|release|emergency|learn|pr] [추가 맥락] [--fix] [--team|--no-team] [--target <semver>] [--bump auto|major|minor|patch] [--channel stable|rc|beta|alpha] [--package <name>] [--from <ref>] [--incident <id>] [--severity sev1|sev2|sev3|sev4] [--diagnose] [--rollback-first] [--since <ref>] [--branches <refs>] [--exclude-bots] [--commits 20-500] [--all-authors] [--week-start monday|sunday] [--timezone <IANA|±HH:MM>] [--base <ref>|--range <A..B>] [--scope <경로...>] [--format human|json|sarif] [--output <경로>] [--no-verify] [--strict] [--iterations 1-5] [--keep-snapshot]"
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
  - Bash(git describe *)
  - Bash(git tag --list *)
  - Bash(git rev-parse *)
  - Bash(git ls-files *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
  - Bash(gh pr view *)
  - Bash(cmp *)
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/report_validator.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/baseline.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/period_range.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/release_version.py" *)'
  - 'Bash(python3 ".claude/skills/_git-atomic-core/scripts/agent_team_mode.py")'
hooks:
  PreToolUse:
    - matcher: "Edit|Write|NotebookEdit"
      hooks:
        - type: command
          command: 'python3 ".claude/skills/_git-atomic-core/scripts/cr_edit_gate.py"'
---

# `/cr` — CommitForge Review

사용자 참고 맥락:

```text
$ARGUMENTS
```

**ultrathink.** `/cca`의 심층 품질 파이프라인 중 리뷰·수정·재리뷰·검증만 수행한다.

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
실행하고 즉시 종료한다. 수정 권한 Gate, Guard `begin`, 리뷰와 검증은 실행하지
않는다.

## 수정 권한 Gate

`$ARGUMENTS`에 독립된 옵션 token `--fix`가 정확히 존재하는지 먼저 판정한다.

- 없으면 `SOURCE_EDIT_ALLOWED=false`다. `Edit`·`Write`로 source, test, config, docs 또는 untracked 파일을 생성·수정·삭제하지 않는다.
- 있으면 `SOURCE_EDIT_ALLOWED=true`지만 현재 working hunk가 만든 확정적·국소 문제만 수정할 수 있다.
- 첫 번째 위치 인자가 `release`, `emergency`, `learn`이면 `SOURCE_EDIT_ALLOWED=false`로 고정한다. 이 모드의 `--fix`는 오류로 보고하며 편집 권한을 열지 않는다.
- 자연어의 “고쳐”, `fix`, `수정`은 `--fix`를 대신하지 않는다.
- report output은 Guard 불변식 검증과 `finish`가 성공한 뒤 마지막에 생성한다.

결과 경계:

- 기본 수행: 전체 diff 분석, 기본 10개 관점과 변경 유형별 조건부 전문 리뷰, 테스트·검증
- `--fix` 수행: 현재 working tree가 만든 확정적 결함의 국소 수정과 전면 재리뷰
- 금지: Atomic Commit 계획, commit 메시지 초안, `git add`, index 변경, `git commit`, push, amend, rebase, squash, history rewrite
- 종료 시 HEAD와 staging area는 시작 상태와 같아야 한다.
- `--fix`를 명시해 소스를 수정했다면 working tree에는 검증된 수정 결과가 남을 수 있다.

## 필수 지침 로드

작업 전에 다음 파일을 읽는다.

1. `.claude/skills/_git-atomic-core/safety-and-concurrency.md`
2. `.claude/skills/_git-atomic-core/review-gates.md`
3. `.claude/skills/_git-atomic-core/validation-strategy.md`
4. `.claude/skills/_git-atomic-core/project-profiles.md`
5. `.claude/skills/_git-atomic-core/reporting.md`
6. `.claude/skills/_git-atomic-core/deep-review-protocol.md`
7. `.claude/skills/_git-atomic-core/conditional-reviewers.md`
8. `.claude/skills/_git-atomic-core/review-execution.md`
9. `.claude/skills/_git-atomic-core/review-policy.md`
10. `.claude/skills/_git-atomic-core/reporting-formats.md`
11. `.claude/skills/_git-atomic-core/baseline-and-suppressions.md`
12. `.claude/skills/_git-atomic-core/large-diff-review.md`
13. `.claude/skills/_git-atomic-core/period-review-modes.md` — `today`·`3days`·`weekly`에서만 읽는다.
14. `.claude/skills/_git-atomic-core/extended-modes.md` — `release`·`emergency`·`learn`에서만 읽는다.

변경 언어·프레임워크를 판별한 뒤 `language-api-pitfalls.md`에서 관련 섹션만 읽는다.

저장소 루트에 `.commitforge/profile.json`과 `.commitforge/profile.md`가 있으면 명시적 프로젝트 규칙 다음 우선순위로 적용한다.
`.commitforge/review.yml`이 있으면 `review-policy.md`에 따라 적용한다.

## 0. 인자와 수정 정책

- 일반 문장은 구현 의도와 리뷰 맥락으로 사용한다.
- 첫 번째 위치 인자가 `today`, `3days`, `weekly` 중 하나면 `period-review-modes.md`의 기간 범위와 review-only 정책을 적용한다.
- 첫 번째 위치 인자가 `release`, `emergency`, `learn`이면 `extended-modes.md`의 해당 read-only 흐름을 적용한다. Atomic Commit 계획이나 메시지 초안을 만들지 않는다.
- `release`: `--from`, `--target`, `--bump`, `--channel`, `--package`, `--tag-prefix`를 검증해 릴리스 위험·다음 version/tag·릴리스 노트를 제안한다. `--prepare --tag`가 있으면 `/cca`가 바꿀 version/CHANGELOG, 만들 commit과 로컬 annotated tag를 시뮬레이션해 보고하되 실행하지 않는다. `--fix`도 실행하지 않는다.
- `emergency`: incident·severity·base·scope 증거를 바탕으로 원인 후보, rollback/containment, 최소 수정·검증 계획만 제안한다. `--diagnose` 유무와 관계없이 소스를 고치지 않는다.
- `learn`: `--since`, `--branches`, `--exclude-bots`, `--package`, `--commits` 범위에서 profile 후보와 근거·확신도만 보여주며 프로필 파일을 쓰지 않는다.
- `--scope <경로...>`는 보고·수정 범위를 제한하지만 필수 의존성과 호출자는 분석한다.
- `--team`은 Agent Team을 강제 선호하고 `--no-team`은 끈다. 둘을 함께 쓰면 오류다.
  옵션이 없고 환경이 활성화되어 있으면 Agent Team이 기본이며, 명백히 사소한
  단일 영역 변경만 `review-execution.md` 기준으로 축소한다.
- Agent Team은 source-read-only 실행에서만 허용한다. 일반 리뷰의 `--fix`에서는
  `--team`이 있어도 기존 subagent로 fallback하고 이유를 보고한다.
- `--base <ref>`: `merge-base(<ref>, HEAD)..HEAD`와 현재 working change를 함께 리뷰한다.
- `--range <A>..<B>`: 명시한 committed diff를 리뷰한다. `B`가 HEAD가 아니면 `--fix`를 허용하지 않는다.
- 첫 인자가 `pr`이면 `gh pr view --json baseRefName,headRefName,number,url`로 현재 PR의 base를 읽어 `--base`처럼 처리한다. PR을 찾지 못하면 변경하지 말고 base를 요청한다.
- `--format human|json|sarif`과 `--output`은 `reporting-formats.md`를 따른다.
- `--all-authors`, `--timezone`은 `today`·`3days`·`weekly`에서 적용하고, `--week-start`는 `weekly`에서만 적용한다.
- 기본은 모든 소스 수정을 금지하는 읽기 전용 리뷰다.
- `--fix`를 명시한 경우에만 현재 working hunk가 만든 확정적·국소적 CRITICAL/MAJOR 문제를 수정할 수 있다.
- `--fix`가 없으면 blocker를 보고하고 소스는 그대로 둔다.
- 과거 commit·기간·PR 범위의 문제만으로 새 corrective change를 만들지 않는다.
- `--strict`는 확인된 MINOR도 해결하거나 명시적으로 차단한다.
- `--iterations N`은 리뷰-수정 반복 상한이며 기본 3, 최소 1, 최대 5다.
- `--no-verify`는 프로젝트 테스트·lint·build를 생략할 수 있지만 diff·secret·safety 검사는 유지한다.
- `--keep-snapshot`은 정상 종료 후에도 스냅샷을 보존한다.
- 새 dependency, 외부 서비스 변경, 데이터 파괴, 광범위한 재설계는 자동 수행하지 않는다.

## 1. Guard와 시작 불변식

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" begin \
  --session "<current-session-id>"
```

`session`, `token`, `snapshot`, `fingerprint`, 시작 `HEAD`, staged fingerprint를 보관한다.

- Guard `begin`의 exit code가 0이 아니거나 결과의 `ok`가 `false`면 즉시
  fail-closed로 중단한다. 변경 스캔, reviewer, 테스트, fingerprint, `abort`를
  포함한 후속 명령을 실행하지 않는다. 이 경우 현재 세션은 lock을 획득하지
  않았으므로 다른 owner의 lock을 해제하지 않는다.
- Guard 명령이 아예 실행되지 못한 경우도 같은 실패다. exit code 126·127,
  `No such file or directory`, `command not found`, Python 미탐지, permission
  거부가 여기에 해당한다. “스크립트가 없으니 Guard를 생략한다”, “미설치라
  건너뛴다”는 판단은 금지한다. Preflight로 `CF_CORE`를 다시 확정해 한 번만
  재시도하고, 그래도 실패하면 리뷰를 시작하지 않고 종료한다.
- `reason=guard_lock_conflict`이면 결과의 `project_root`, `git_dir`,
  `lock_scope`, `lock_owner`, `lock_owner_snapshots`, `recovery`를 그대로
  보고해 다른 저장소의 잠금과 혼동하지 않도록 한다. `abort` 성공 결과를
  실제로 받기 전에는 잠금이 해제됐다고 보고하거나 `begin`을 재시도하지 않는다.
  잠금 경과 시간은 Guard의 `lock_age_seconds`만 사용하고 직접 계산하지 않는다.
  복구 명령을 안내하거나 사용자가 해제를 요청하면 `recovery.cwd`에서
  `recovery.abort_argv`를 인자 단위 그대로 사용하며 명령을 재작성하지 않는다.
- 잠금 충돌 보고에는 Guard가 준 `stale_candidate`, `lock_owner_same_host`,
  `lock_owner_same_session`, `stale_after_seconds`도 포함한다. `stale_candidate`가
  `true`여도 스스로 회수하지 않는다. 사용자에게 `/cr clean` 또는
  `begin --reclaim-stale`을 선택지로 제시하고 명시적 승인을 받은 뒤에만 실행한다.
  `lock_owner_same_host`가 `false`면 `--reclaim-stale`을 권하지 않는다.
- `reason=git_external_lock`이면 Git 자체 lock 때문에 차단된 것이며 CommitForge
  잠금 문제가 아니다. Guard가 준 `git_locks`의 `path`, `age_seconds`, `size`,
  `writer_pids`, `stale_candidate`와 `recovery.remove_hint`를 그대로 보고하고
  `/cr clean`을 안내한다. `clean`은 안전 조건을 모두 통과한 stale lock만 제거하며,
  writer 판별 불능·활성 writer·진행 중 Git operation·변경된 lock은 보존한다.
  `stale_candidate`가 `false`면 진행 중인 작업이 끝나기를 기다리게 한다.
- Guard 실패, 진행 중 Git operation, Git lock, 동일 worktree의
  `/cc`·`/cr`·`/cca`·`/cpr`·`/cp`가 있으면 중단한다.
- Guard `begin`이 실패한 뒤 `git status`, `git diff`, `git log`를 대신 실행해
  변경을 스캔하지 않는다. `git -C <경로>`로 다른 작업 디렉터리를 우회해 리뷰를
  이어가는 것도 금지한다. 실패 원인을 보고하고 종료하는 것이 유일한 다음 동작이다.
- 시작 staged diff는 사용자의 상태다. 수정하거나 비우지 않는다.
- Guard를 성공적으로 획득한 뒤 실패·차단된 경우에만 `abort`로 자신의 lock만
  해제하고 snapshot은 보존한다.

## 2. 변경 전체 스캔

다음을 분리해 읽는다.

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git log -20 --pretty=format:'%h%x09%s'
```

`today`, `3days`, `weekly`이면 `period_range.py`가 반환한 범위로 커밋 원장과 net effect를 수집한다. `release`, `emergency`, `learn`이면 `extended-modes.md`의 범위·증거를 수집한다. `--base`, `--range`, `pr`이면 `git merge-base`, `git diff <range>`, `git log <range>`로 해당 commit range를 별도 수집한다. 모든 committed 범위는 working tree hunk와 섞지 않고 원장에 표시한다.

변경 파일뿐 아니라 관련 호출부, 타입·인터페이스, 테스트, 설정, migration, generated source, 프로젝트 규칙을 읽는다. 모든 hunk를 `deep-review-protocol.md`의 변경 원장에 배정하고 삭제 라인과 wrapper/proxy/adapter를 별도 추적한다.

파일·hunk·changed line 수가 policy threshold를 넘으면 `large-diff-review.md`의
shard/aggregator 절차를 적용한다. 시작 공지에는 실제로 초과한 값과 적용
threshold, `Agent Team core 3명 + 조건부 specialist` 구조를 함께 표시하며,
shard 수를 teammate 수처럼 표현하거나 계산하지 않은 hunk 수를 추정하지 않는다.

working change와 선택한 기간·commit range가 모두 비어 있을 때만 Guard `finish` 후 “검토 대상 없음”으로 종료한다.

## 3. 기본 10개 관점과 조건부 심층 리뷰

동일 fingerprint를 기준으로 `review-execution.md`의 구조 선택을 먼저 적용한다.
Agent Team이면 core 3명이 domain/runtime shard, shared task와 peer messaging으로
교차검증하고 Testing·Reliability·UX·Migration·Requirements·Release·Domain
trigger에 따라 specialist를 추가한다. 그 밖에는 기존 custom subagent를 병렬
실행한다.

1. `cca-correctness-reviewer`
2. `cca-line-reviewer`
3. `cca-security-reviewer`
4. `cca-performance-reviewer`
5. `cca-testing-reviewer`
6. `cca-architecture-reviewer`
7. `cca-language-api-reviewer`
8. `cca-ux-accessibility-reviewer`
9. `cca-observability-reviewer`
10. `cca-quality-reviewer`

Git/Atomicity reviewer는 Atomic Commit 계획 전용이므로 `/cr`에서 실행하지 않는다.

`conditional-reviewers.md`의 trigger를 판정해 Data/Migration, Dependency/Supply Chain, Reliability/Recovery, Privacy/Governance, Requirements/Product reviewer를 필요한 경우에만 추가한다. 비활성 조건도 `N/A`와 근거를 남긴다.

변경 경로를 다음 도구에 전달해 조건부 reviewer의 최소 활성 집합을 얻는다.

```bash
python3 ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py" <changed-path...>
```

이 결과는 하한선이다. 실제 코드 의미에서 추가 trigger가 확인되면 reviewer를 더 활성화한다. `review-execution.md`의 최대 동시 실행 수, fallback, `UNKNOWN` 차단과 finding schema를 적용한다.

baseline이 있으면 `baseline.py`로 먼저 검증하고 `baseline-and-suppressions.md`에 따라 finding 상태만 `BASELINED`로 표시한다. finding 자체를 삭제하지 않는다.

- `cca-data-migration-reviewer`
- `cca-dependency-supply-chain-reviewer`
- `cca-reliability-recovery-reviewer`
- `cca-privacy-governance-reviewer`
- `cca-requirements-product-reviewer`

각 agent에 `review-only` 모드, 사용자 맥락, branch/HEAD, status, staged·unstaged·untracked diff, 관련 log, scope를 제공한다. Agent는 shell과 파일 수정을 하지 않고 근거·정확한 위치·심각도·실패 시나리오를 반환하며 Atomic Commit 계획이나 메시지 후보를 만들지 않는다.

- 설치되지 않은 agent 관점은 main agent가 직접 수행한다.
- 적용 불가능한 관점도 `N/A`와 근거를 남긴다.
- main agent가 모든 finding을 실제 코드와 diff로 재검증한다.
- 모든 hunk와 삭제 동작이 `PASS`, `FINDING`, `N/A` 중 하나여야 한다.
- unreviewed hunk가 하나라도 있으면 완료로 처리하지 않는다.

## 4. Gate, 수정, 전면 재리뷰

`review-gates.md`를 적용한다.

- CRITICAL/MAJOR: 기본은 차단·보고하고, `--fix`일 때만 허용 범위 안에서 안전하게 수정
- MINOR: scope와 위험에 따라 수정 또는 기록
- NOTE: 범위를 확대하지 않고 기록

자동 수정은 `--fix`가 명시됐고 현재 working hunk가 만든 문제이며, 실패 시나리오와 검증법이 명확하고 국소적이며 원래 의도를 보존할 때만 허용한다.

수정 후에는:

1. 전체 diff와 fingerprint를 다시 수집한다.
2. 이전 기본·활성 조건부 reviewer 결과를 모두 무효화한다.
3. trigger를 다시 판정하고 새 상태로 기본 10개와 활성 조건부 reviewer를 전부 다시 실행한다.
4. 새 문제와 회귀가 없는지 검증한다.

반복 상한까지 blocker가 남으면 실패로 종료하며 snapshot을 보존한다.

## 5. 검증

저장소가 정의한 명령을 우선해 다음 순서로 실행한다.

1. changed-area unit/regression test
2. 관련 lint/type check
3. 관련 build/check
4. 비용이 합리적이면 전체 test/build

의존성을 임의로 설치·업그레이드하지 않는다. 환경 실패와 변경 실패를 구분하며, 변경으로 인한 실패는 해결되지 않으면 완료로 처리하지 않는다.

## 6. 종료 불변식과 Guard 정리

종료 직전에 다음을 실행해 Guard가 시작 snapshot과 직접 비교하게 한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" verify-review \
  --session "<session>" \
  --source-read-only
```

기본 `/cr`은 반드시 `--source-read-only`를 사용한다. 일반 리뷰에서 사용자가 `--fix`를 명시한 경우에만 이 flag를 생략한다. `release`·`emergency`·`learn`은 `--fix`가 있어도 반드시 `--source-read-only`를 사용한다.
Guard는 현재 worktree에서 session과 일치하는 owner token과 유일한 snapshot을
직접 해석한다. `snapshot-path` 같은 문서화되지 않은 하위 명령을 만들거나,
basename을 `--snapshot`으로 넘기거나, 종료 단계에서 `begin`을 다시 호출하지
않는다. 명시적 `--token`·`--snapshot`은 진단상 정확한 원본 값을 그대로 재사용할
때만 전달한다.

검증 항목:

- `HEAD`가 동일함
- staged diff의 binary patch와 name/status가 동일함
- commit 수가 늘지 않음
- `/cr`이 설명하지 못하는 working tree 변화가 없음

정상 완료 시:

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" \
  --review-only \
  --source-read-only
```

기본 `/cr`은 `finish`에도 반드시 `--source-read-only`를 사용하고, 일반 리뷰의 `--fix`일 때만 생략한다. `release`·`emergency`·`learn`은 항상 `--source-read-only`를 유지한다. `finish --review-only`가 같은 불변 조건을 다시 확인하므로 검증과 정리 사이의 변경도 차단한다. `--keep-snapshot`이면 해당 옵션을 추가한다.

불변식 위반, 검증 실패, unresolved blocker이면 `abort`로 lock만 해제하고 snapshot을 보존한다.

## 7. 최종 보고

한글로 다음을 보고한다.

- 시작/종료 HEAD와 staging 불변 여부
- reviewer별 PASS/N/A/finding 수, unreviewed hunk 수
- 채택·기각한 중요 finding과 근거
- 자동 수정 내용과 남은 blocker
- 실행·생략·실패한 검증
- 현재 working tree 상태
- snapshot 삭제/보존과 lock 해제
- Atomic Commit 계획, staging, commit, push를 하지 않았음
- `--fix` 요청 여부와 실제 수정 파일
- `today`·`3days`·`weekly`이면 정확한 기간 경계, 작성자 조건, commit 원장, net effect와 finding 귀속
- `release`이면 기준 ref, package, 권장 version/tag, 자동 증가 근거, 릴리스 노트와 차단 요소
- `emergency`이면 incident/severity, 증거·원인 후보, rollback/containment, 검증·관찰 계획
- `learn`이면 분석 refs·표본·제외 조건, profile 후보, 근거·확신도·반례

JSON/SARIF를 생성했다면 `report_validator.py` 검증 결과와 출력 경로를 포함한다.

완료되지 않은 작업을 성공으로 표현하지 않는다.
