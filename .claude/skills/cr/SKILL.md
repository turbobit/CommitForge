---
name: cr
description: CommitForge의 최고 강도 코드 리뷰 명령이다. 현재 변경이나 today/weekly/branch/range/PR 범위를 심층 리뷰하고 확정적 working-tree 문제만 수정·재리뷰·검증하며 Atomic Commit 계획, staging, commit, push는 하지 않는다. 사용자가 직접 /cr로 요청할 때만 실행한다.
argument-hint: "[today|weekly|pr] [추가 맥락] [--all-authors] [--week-start monday|sunday] [--timezone <IANA|±HH:MM>] [--base <ref>|--range <A..B>] [--scope <경로...>] [--format human|json|sarif] [--output <경로>] [--no-fix] [--no-verify] [--strict] [--iterations 1-5] [--keep-snapshot]"
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
  - Bash(git merge-base *)
  - Bash(git show *)
  - Bash(git branch *)
  - Bash(git config *)
  - Bash(git rev-parse *)
  - Bash(git ls-files *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
  - Bash(gh pr view *)
  - Bash(cmp *)
  - 'Bash(bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/reviewer_triggers.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/report_validator.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/baseline.py" *)'
  - 'Bash(python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/period_range.py" *)'
---

# `/cr` — CommitForge Review

사용자 참고 맥락:

```text
$ARGUMENTS
```

**ultrathink.** `/cca`의 심층 품질 파이프라인 중 리뷰·수정·재리뷰·검증만 수행한다.

결과 경계:

- 수행: 전체 diff 분석, 기본 10개 관점과 변경 유형별 조건부 전문 리뷰, 확정적 결함의 국소 수정, 재리뷰, 테스트·검증
- 금지: Atomic Commit 계획, commit 메시지 초안, `git add`, index 변경, `git commit`, push, amend, rebase, squash, history rewrite
- 종료 시 HEAD와 staging area는 시작 상태와 같아야 한다.
- 소스를 수정했다면 working tree에는 검증된 수정 결과가 남을 수 있다.

## 필수 지침 로드

작업 전에 다음 파일을 읽는다.

1. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/safety-and-concurrency.md`
2. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-gates.md`
3. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/validation-strategy.md`
4. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/project-profiles.md`
5. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`
6. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/deep-review-protocol.md`
7. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/conditional-reviewers.md`
8. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-execution.md`
9. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/review-policy.md`
10. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting-formats.md`
11. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/baseline-and-suppressions.md`
12. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/large-diff-review.md`
13. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/period-review-modes.md` — `today`·`weekly`에서만 읽는다.

변경 언어·프레임워크를 판별한 뒤 `language-api-pitfalls.md`에서 관련 섹션만 읽는다.

저장소 루트에 `.commitforge/profile.md`가 있으면 명시적 프로젝트 규칙 다음 우선순위로 적용한다.
`.commitforge/review.yml`이 있으면 `review-policy.md`에 따라 적용한다.

## 0. 인자와 수정 정책

- 일반 문장은 구현 의도와 리뷰 맥락으로 사용한다.
- 첫 번째 위치 인자가 `today` 또는 `weekly`이면 `period-review-modes.md`의 기간 범위와 review-only 정책을 적용한다.
- `--scope <경로...>`는 보고·수정 범위를 제한하지만 필수 의존성과 호출자는 분석한다.
- `--base <ref>`: `merge-base(<ref>, HEAD)..HEAD`와 현재 working change를 함께 리뷰한다.
- `--range <A>..<B>`: 명시한 committed diff를 리뷰한다. `B`가 HEAD가 아니면 자동으로 `--no-fix`다.
- 첫 인자가 `pr`이면 `gh pr view --json baseRefName,headRefName,number,url`로 현재 PR의 base를 읽어 `--base`처럼 처리한다. PR을 찾지 못하면 변경하지 말고 base를 요청한다.
- `--format human|json|sarif`과 `--output`은 `reporting-formats.md`를 따른다.
- `--all-authors`, `--week-start`, `--timezone`은 `today`·`weekly`에서만 적용한다.
- 기본은 현재 변경이 만든 확정적 CRITICAL/MAJOR 문제만 국소 수정한다.
- `--no-fix`는 모든 소스 수정을 금지한다.
- `--strict`는 확인된 MINOR도 해결하거나 명시적으로 차단한다.
- `--iterations N`은 리뷰-수정 반복 상한이며 기본 3, 최소 1, 최대 5다.
- `--no-verify`는 프로젝트 테스트·lint·build를 생략할 수 있지만 diff·secret·safety 검사는 유지한다.
- `--keep-snapshot`은 정상 종료 후에도 스냅샷을 보존한다.
- 새 dependency, 외부 서비스 변경, 데이터 파괴, 광범위한 재설계는 자동 수행하지 않는다.

## 1. Guard와 시작 불변식

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" begin \
  --session "${CLAUDE_SESSION_ID}"
```

`session`, `token`, `snapshot`, `fingerprint`, 시작 `HEAD`, staged fingerprint를 보관한다.

- Guard 실패, 진행 중 Git operation, Git lock, 동일 worktree의 `/cc`·`/cr`·`/cca`가 있으면 중단한다.
- 시작 staged diff는 사용자의 상태다. 수정하거나 비우지 않는다.
- 실패·차단 시 `abort`로 자신의 lock만 해제하고 snapshot은 보존한다.

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

`today`, `weekly`이면 `period_range.py`가 반환한 범위로 커밋 원장과 net effect를 수집한다. `--base`, `--range`, `pr`이면 `git merge-base`, `git diff <range>`, `git log <range>`로 해당 commit range를 별도 수집한다. 모든 committed 범위는 working tree hunk와 섞지 않고 원장에 표시한다.

변경 파일뿐 아니라 관련 호출부, 타입·인터페이스, 테스트, 설정, migration, generated source, 프로젝트 규칙을 읽는다. 모든 hunk를 `deep-review-protocol.md`의 변경 원장에 배정하고 삭제 라인과 wrapper/proxy/adapter를 별도 추적한다.

파일·hunk·changed line 수가 policy threshold를 넘으면 `large-diff-review.md`의 shard/aggregator 절차를 적용한다.

working change와 선택한 기간·commit range가 모두 비어 있을 때만 Guard `finish` 후 “검토 대상 없음”으로 종료한다.

## 3. 기본 10개 관점과 조건부 심층 리뷰

가능하면 동일 fingerprint를 기준으로 병렬 실행한다.

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
python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/reviewer_triggers.py" <changed-path...>
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

- CRITICAL/MAJOR: 차단하거나 안전하게 수정
- MINOR: scope와 위험에 따라 수정 또는 기록
- NOTE: 범위를 확대하지 않고 기록

자동 수정은 현재 변경이 만든 문제이고, 실패 시나리오와 검증법이 명확하며, 국소적이고 원래 의도를 보존할 때만 허용한다.

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
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" verify-review \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

검증 항목:

- `HEAD`가 동일함
- staged diff의 binary patch와 name/status가 동일함
- commit 수가 늘지 않음
- `/cr`이 설명하지 못하는 working tree 변화가 없음

정상 완료 시:

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>" \
  --review-only
```

`finish --review-only`가 같은 불변 조건을 다시 확인하므로 검증과 정리 사이의 변경도 차단한다. `--keep-snapshot`이면 해당 옵션을 추가한다.

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
- `today`·`weekly`이면 정확한 기간 경계, 작성자 조건, commit 원장, net effect와 finding 귀속

JSON/SARIF를 생성했다면 `report_validator.py` 검증 결과와 출력 경로를 포함한다.

완료되지 않은 작업을 성공으로 표현하지 않는다.
