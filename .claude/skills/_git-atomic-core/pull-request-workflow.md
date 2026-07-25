# Pull Request preview·생성 공통 규칙

## 목차

1. 역할 경계
2. 입력과 base 결정
3. 로컬 PR context
4. `main`/`master` 자동 분기
5. PR 품질 검토
6. 제목과 본문
7. `/cpr` 종료
8. `/cp` push와 생성
9. 실패와 보고

## 1. 역할 경계

명령 호출 직후 시작 시각을 기록하고 최종 보고 직전에 종료 시각을 기록한다.
승인 대기·reviewer·검증·Guard 정리를 포함한 전체 경과 시간을 분으로 환산하며,
6초 미만은 `0.1분 미만`, 측정값을 잃으면 임의 추정 없이 사유를 표시한다.

| 명령 | 로컬 파일·Git | remote branch | Pull Request |
|---|---|---|---|
| `/cpr` | 읽기 전용 | 변경 안 함 | 생성·수정 안 함 |
| `/cp` | source/index/commit SHA 불변 | 검증된 branch를 일반 push | 새 PR 생성 |

- 두 명령 모두 source 수정, staging, commit, amend, rebase, squash, force push를 하지 않는다.
- `/cpr`은 PR readiness, review finding, 제목·본문·검증 초안까지만 보고한다.
- `/cp`는 `/cpr`과 같은 gate를 통과한 committed branch만 push하고 PR을 생성한다.
- 이미 열린 PR이 있으면 중복 생성하지 않고 기존 PR URL을 보고한다.
- `/cp`는 PR 생성 외 issue, release, deployment, merge, auto-merge를 수행하지 않는다.

## 2. 입력과 base 결정

지원 옵션:

- `--base <branch>`: PR 대상 branch
- `--remote <name>`: push remote, 기본 `origin`
- `--draft`: draft PR로 계획 또는 생성
- `--title <text>`: 검증 후 사용할 명시적 제목
- `--branch <name>`: `main`/`master` 자동 분기 시 사용할 명시적 head branch 이름
- `--no-verify`: 프로젝트 test/lint/build 생략 허용. diff·secret·Git·PR safety 검사는 유지
- `--strict`: 확인된 MINOR finding도 차단 대상으로 처리
- `--keep-snapshot`: 성공 후 Guard snapshot 보존

base:

1. `--base`가 있으면 Git branch 이름으로 검증한다.
2. 없으면 `gh repo view --json defaultBranchRef`로 저장소 기본 branch를 조회한다.
3. 조회 실패나 base가 모호하면 추측하지 말고 중단한다.
4. detached HEAD면 중단한다.
5. 현재 branch가 base와 같을 때는 `main` 또는 `master`에서만 아래 자동 분기 계약을 적용한다.
6. 그 외 branch가 base와 같으면 중단한다.
7. 자동 fetch와 checkout은 하지 않는다. base ref가 로컬에 없으면 안전한 fetch를 안내한다.

일반 문장은 PR의 배경·목적·제약으로 사용한다. 사용자 설명이 diff와 충돌하면 diff와 검증 결과를 우선하고 충돌을 보고한다.

## 3. 로컬 PR context

Guard `begin` 후 다음 계산기를 실행한다.

```bash
python3 "<absolute-CF_CORE>/scripts/pr_context.py" \
  --base "<base>" --remote "<remote>"
```

현재 branch와 base가 모두 `main` 또는 모두 `master`이면 `--allow-base-head`를 추가한다. 이때 최신 local remote-tracking base와 현재 `HEAD` 사이를 비교하며 결과의 `branch_needs_creation`은 `true`여야 한다.

반드시 확인:

- working tree와 index가 clean
- base와 head가 다르거나, 검증된 `main`/`master` 자동 분기 대상임
- `merge-base..HEAD` commit이 1개 이상
- commit range, 변경 파일, 추가·삭제 통계
- merge/rebase/cherry-pick/revert/bisect와 Git lock 없음
- submodule/LFS/generated/binary/migration/secret 위험

dirty 상태의 변경은 PR에 포함되지 않으므로 `/cp`를 차단한다. `/cpr`은 dirty 상태를 명확한 blocker로 보고할 수 있지만 PR 초안은 committed range만 근거로 작성한다.

## 4. `main`/`master` 자동 분기

현재 branch가 base인 `main` 또는 `master`이면 다음을 적용한다.

1. remote tracking base보다 앞선 commit이 1개 이상이어야 한다. 미커밋 변경만 있거나 ahead commit이 없으면 차단한다.
2. PR의 주목적과 commit range를 근거로 branch 이름을 만든다.
3. 기본 형식은 `<type>/<ascii-kebab-slug>`이며 `type`은 `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore` 중 하나다.
4. slug는 의미를 보존하는 짧은 영문 소문자이며 전체 이름은 가급적 50자 이내로 한다.
5. `--branch`가 있으면 `git check-ref-format --branch`와 diff 의미 일치 여부를 검증한다.
   현재가 `main`/`master`가 아니라면 `--branch`를 branch rename 용도로 사용하지 않고 중단한다.
6. local 또는 remote에 같은 이름이 있으면 덮어쓰지 않는다. 자동 이름에는 `-2`, `-3` 순번을 붙여 충돌 없는 이름을 선택한다.
7. `/cpr`은 branch를 만들거나 전환하지 않고 제안 이름과 선정 근거만 보고한다.
8. `/cp`는 모든 review gate를 통과한 뒤 현재 `HEAD`에서 `git switch -c "<validated-branch>"`로 branch를 만든다. commit 객체와 source/index는 바뀌지 않아야 한다.
9. branch 생성 후 context와 Guard 불변 조건을 다시 확인한 다음 새 branch를 push한다.
10. branch 생성 후 실패하면 자동으로 `main`/`master`로 돌아가거나 branch를 삭제하지 않는다. 현재 branch와 안전한 재시도 방법을 보고한다.

## 5. PR 품질 검토

`merge-base..HEAD`의 모든 commit과 net diff를 읽는다.

```bash
git log --reverse --stat <range>
git diff --name-status <range>
git diff --check <range>
git diff <range>
```

검토 범위:

- line-by-line correctness와 제거된 동작
- cross-file contract, wrapper/proxy 의미 보존
- security, privacy, secret, permission
- performance, memory, concurrency, resource lifecycle
- architecture, reuse, duplication, maintainability
- language/API 함정과 type safety
- test, migration, docs, UX/A11y, observability
- commit별 중간 상태보다 PR 최종 net effect
- base 최신 상태와의 conflict 가능성

`review-policy.md`, `deep-review-protocol.md`, `conditional-reviewers.md`, `review-execution.md`, `large-diff-review.md`를 적용한다. reviewer는 읽기 전용이며 main agent가 finding을 재검증한다.

기본 reviewer는 Correctness, Line-by-line, Security, Performance, Testing, Architecture, Language/API, UX/A11y, Observability, Quality다. 변경 trigger에 따라 Data/Migration, Dependency/Supply Chain, Reliability/Recovery, Privacy/Governance, Requirements/Product를 추가한다. Git Atomicity reviewer는 PR commit range의 분리·순서·중간 상태가 review 가능성을 해치는지 평가하되 commit 재계획이나 history rewrite를 수행하지 않는다.

Gate:

- CRITICAL/MAJOR, secret, 데이터 손실, 인증 우회, 미검토 hunk, 필수 reviewer `UNKNOWN`: 차단
- `--strict`이면 확인된 MINOR도 차단
- 프로젝트 검증 실패가 변경과 관련되면 차단
- 환경 때문에 필수 검증을 못 했으면 readiness를 `CONDITIONAL` 또는 `BLOCKED`로 정확히 표시

두 명령 모두 finding을 자동 수정하지 않는다. 수정이 필요하면 `/cr --fix`, `/cca` 또는 수동 작업 후 다시 실행하도록 안내한다.

## 6. 제목과 본문

저장소의 PR template와 기여 가이드를 먼저 읽는다.

제목:

- 사용자가 `--title`을 주면 diff와 일치하는지 검증
- 없으면 PR 전체의 주목적을 한글로 작성
- 가능하면 `type(scope): 한글 제목`
- 하나의 주목적, 가급적 72자 이내
- 과장, 구현 세부 나열, 검증되지 않은 효과 금지

본문은 template를 보존하며 최소 다음 내용을 포함한다.

```markdown
## 요약

## 주요 변경

## 검증

## 영향과 위험

## Breaking Change / Migration

## 체크리스트
```

- 실제 diff와 commit에서 확인한 내용만 작성
- 실행한 검증과 실행하지 못한 검증을 분리
- 사용자 영향, 호환성, migration, 배포·rollback, 관측 항목 기록
- issue 번호는 사용자가 제공하거나 commit에서 명확히 확인된 경우에만 연결
- secret, 개인정보, 내부 credential·운영 데이터는 본문에 복제하지 않음

## 7. `/cpr` 종료

`/cpr`은 다음을 완료한 뒤 Guard를 `verify-review --source-read-only`, `finish --review-only --source-read-only`로 종료한다.

두 명령에는 현재 session을 전달하고, Guard가 같은 worktree의 owner token과
유일한 snapshot을 자동 해석하게 한다. `snapshot-path` 같은 문서화되지 않은
하위 명령, snapshot basename, 종료 단계의 `begin` 재호출을 사용하지 않는다.
명시적 token/snapshot을 전달해야 한다면 `begin` 결과의 원본 값을 그대로 쓴다.

- readiness: `READY`, `CONDITIONAL`, `BLOCKED`
- base/head/merge-base와 commit 원장
- review finding과 해결해야 할 blocker
- 실행·생략·실패한 검증
- PR 제목·본문 완성 초안
- `/cp` 실행 시 push될 remote/branch와 생성될 draft 상태
- `main`/`master`라면 생성될 제안 branch 이름과 선정 근거
- source/index/HEAD/remote/PR을 변경하지 않았음

## 8. `/cp` push와 생성

PR 생성 직전에 전체 context와 HEAD를 다시 계산한다. 처음 검토한 fingerprint와 다르면 전면 재검토한다.

1. `gh auth status`와 repository 접근을 확인한다.
2. `main`/`master` 자동 분기 대상이면 검증된 branch를 만들고 context를 다시 계산한다.
3. 같은 head branch의 열린 PR을 조회한다. 있으면 중복 생성하지 않는다.
4. `git ls-remote --heads`로 remote branch SHA를 확인한다.
5. remote branch가 이미 있으면 다음을 모두 만족해야 한다.
   - 로컬 `refs/remotes/<remote>/<branch>`가 존재한다.
   - 그 tracking ref SHA가 `ls-remote`에서 읽은 SHA와 같다.
   - remote SHA가 현재 `HEAD`의 조상이다.
6. tracking ref가 없거나 stale이면 자동 fetch하지 않고, 사용자가 fetch한 뒤 다시 실행하도록 차단한다.
7. remote head가 현재 HEAD의 조상이 아니면 non-fast-forward 위험으로 차단한다.
8. 다음 형태의 일반 push만 허용한다.

```bash
git push "<remote>" "HEAD:refs/heads/<validated-branch>"
```

9. push 후 `git ls-remote --heads`로 remote branch SHA가 현재 HEAD와 같은지 확인한다.
10. Guard snapshot 내부에 최종 PR 본문 파일을 만들고 다음 형태로 생성한다.

```bash
gh pr create \
  --base "<base>" \
  --head "<validated-branch>" \
  --title "<title>" \
  --body-file "<snapshot>/pull-request.md"
```

`--draft`가 있으면 `gh pr create`에 `--draft`를 추가한다.

11. 생성 직후 `gh pr view`로 number, URL, base, head, draft, title을 검증한다.
12. source/index/commit SHA 불변을 Guard로 확인하고 정리한다. 자동 분기한 경우 `verify-review --source-read-only --expected-branch "<validated-branch>"`와 동일한 `finish` 옵션을 사용해 허용된 branch 이름 변경만 입증한다.

base remote-tracking ref도 `ls-remote`의 실제 base SHA와 일치해야 한다. 다르면 PR 범위 자체가 stale하므로 `/cpr`과 `/cp` 모두 자동 fetch 없이 차단한다.

금지:

- `--force`, `--force-with-lease`
- remote branch 삭제
- 기존 PR 본문·title의 자동 수정
- reviewer/label/milestone 자동 지정
- PR merge, close, ready 전환, auto-merge

## 9. 실패와 보고

- push 전에 실패: remote 변경 없음, snapshot 보존, lock 해제
- push 성공 후 PR 생성 실패: remote branch를 삭제하거나 되돌리지 않음. pushed SHA와 안전한 재시도 방법 보고
- PR 생성 후 Guard 검증 실패: PR을 자동 close하지 않음. PR URL과 로컬 외부 변경을 함께 보고
- 자동 branch 생성 후 실패: 원래 branch로 자동 복귀하거나 생성 branch를 삭제하지 않음
- 기존 PR 발견: 기존 number/URL을 보고하고 새 PR을 만들지 않음

최종 보고:

- readiness와 gate
- base/head/merge-base, commit·파일·라인 통계
- PR title과 URL/number/draft
- pushed remote branch와 SHA
- 검증 결과와 남은 위험
- snapshot/lock 상태
- 소요 시간(분)
- 수행하지 않은 source 수정·commit·force push·merge·deploy
