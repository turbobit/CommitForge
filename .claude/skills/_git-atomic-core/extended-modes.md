# CommitForge `/cr`·`/cca` 확장 모드

## 목차

1. 공통 해석 규칙
2. `today`·`3days`·`weekly`
3. `release`
4. `emergency`
5. `learn`
6. 프로젝트 프로필

## 1. 공통 해석 규칙

`/cr` 또는 `/cca`의 첫 번째 위치 인자가 `today`, `3days`, `weekly`, `release`, `emergency`, `learn` 중 하나면 확장 모드로 해석한다.

- 확장 모드 이름 뒤의 일반 문장은 작업 맥락으로 사용한다.
- 알 수 없는 모드처럼 보이는 단어는 자동 실행하지 말고 일반 맥락으로 취급한다.
- 어떤 모드도 기존 commit을 amend/rebase/reset/squash하지 않는다.
- 어떤 모드도 push, GitHub Release 생성, package publish 또는 deploy를 수행하지 않는다.
- `/cr release|emergency|learn`은 `--fix`가 있어도 항상 읽기 전용이다.
- `/cca release --dry-run`, `/cca emergency --diagnose`, `/cca learn --preview`도 읽기 전용이다.
- `.commitforge/profile.json`과 `.commitforge/profile.md`가 있으면 저장소의 명시적 규칙과 충돌하지 않는 범위에서 메시지·분리·검증 선호에 적용한다.

## 2. `today`·`3days`·`weekly`

세 모드는 `_git-atomic-core/period-review-modes.md`를 따른다.

```text
/cca today
/cca today --all-authors
/cca 3days
/cca 3days --timezone Asia/Seoul --all-authors
/cca weekly
/cca weekly --week-start sunday --all-authors
```

기간의 기존 commit은 강화된 이력·net-effect 리뷰와 보고에만 사용한다. 현재 미커밋 변경만 기본 `/cca` 품질 파이프라인으로 수정·검증·commit한다.

## 3. `release`

호출 예:

```text
/cr release --from v1.8.0
/cr release --channel rc --target 2.0.0-rc.1
/cca release --dry-run
/cca release --target 1.9.0 --prepare
/cca release --channel rc --target 2.0.0-rc.1 --prepare --tag
/cca release --package mobile --from mobile-v1.8.0 --bump minor
```

역할:

- `/cr release`: 릴리스 범위·현재 변경·버전·tag·릴리스 위험을 분석하고 보고만 한다.
- `/cr release --prepare --tag`: 실제 `/cca` 준비 흐름에서 변경할 파일·commit·로컬 annotated tag를 시뮬레이션해 보고하며 저장소는 변경하지 않는다.
- `/cca release`: 릴리스 후보를 리뷰·검증하며, 명시적 `--prepare`에서만 버전 파일과 CHANGELOG를 갱신해 Atomic Commit한다.
- `/cca release --tag`: 검증된 release commit에 로컬 annotated tag를 생성한다. push와 publish는 별도 작업이다.

옵션:

- `--from <ref>`: 릴리스 비교 기준. 반드시 유효하며 `HEAD`의 조상이어야 한다.
- `--target <semver>`: 정확한 목표 버전. `v` 접두사는 허용하되 결과 tag 규칙과 분리한다.
- `--bump auto|major|minor|patch`: 목표 버전 증가 방식. 기본 `auto`.
- `--channel stable|rc|beta|alpha`: 기본 `stable`. prerelease 번호는 같은 버전·channel의 기존 tag 다음 번호로 증가한다.
- `--package <name>`: monorepo package 범위. 기본 tag는 `<name>-v<version>`이다.
- `--tag-prefix <prefix>`: 저장소의 명시적 tag 접두사. `--package` 기본값보다 우선한다.
- `--prepare`: canonical version source와 CHANGELOG를 수정·검증·commit한다.
- `--tag`: `--prepare`와 함께만 허용하며 최종 HEAD에 로컬 annotated tag를 만든다.
- `--dry-run`: `/cca`에서도 모든 수정·stage·commit·tag를 금지하고 예상 결과만 보고한다.

위 `--prepare`·`--tag`의 실제 실행 의미는 `/cca`에만 적용한다. `/cr`에 같은 옵션을 전달하면 예상 변경 파일, commit 경계, tag 이름과 대상 commit만 보고한다.

범위 결정:

1. `--from`이 있으면 ref와 조상 관계를 검증하고 `<from>..HEAD`를 사용한다.
2. 없으면 package/tag prefix와 일치하며 HEAD에서 도달 가능한 최신 tag를 사용한다.
3. tag가 없으면 저장소 첫 commit부터 HEAD까지임을 명시한다.
4. committed range와 현재 미커밋 변경은 별도 원장으로 유지한다.
5. `--package`에서는 package 경로, canonical version source, tag namespace가 모두 식별돼야 한다. 모호하면 `--prepare`를 차단한다.

```bash
git describe --tags --abbrev=0
git merge-base --is-ancestor <from> HEAD
git log --first-parent --reverse --format='%H%x09%s' <from>..HEAD
git diff --stat <from>..HEAD
```

버전·tag 계산:

1. diff와 검증된 breaking/feature/fix 근거로 `auto`를 `major`, `minor`, `patch` 중 하나로 확정한다.
2. 호환 불가능한 API·schema·동작 변경은 major, 하위 호환 기능은 minor, fix·perf·docs·build만 있으면 patch를 제안한다.
3. 근거가 충돌하거나 버전 정책이 SemVer가 아니면 추측하지 말고 `--target` 또는 명시적 `--bump`를 요구한다.
4. 모델이 tag 문자열을 직접 조합하지 않는다. 다음 계산기의 JSON 결과를 사용한다.

```bash
python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/release_version.py" \
  --bump <major|minor|patch> \
  [--target <semver>] [--channel <stable|rc|beta|alpha>] \
  [--package <name>] [--tag-prefix <prefix>]
```

예:

- 최신 `v1.8.0`, `--bump minor` → `v1.9.0`
- 기존 `v2.0.0-rc.1`, `v2.0.0-rc.2`, 목표 `2.0.0`, channel `rc` → `v2.0.0-rc.3`
- package `mobile`, 최신 `mobile-v1.8.0`, patch → `mobile-v1.8.1`
- 계산된 tag가 이미 있으면 중단한다.

검토:

- 사용자 가시 기능·수정·성능 변화
- Breaking Change, migration, 배포 순서
- 보안·데이터 호환성
- 문서·테스트·CHANGELOG 누락
- Conventional Commit type과 실제 diff를 근거로 한 major/minor/patch 제안

`/cca release --prepare`:

1. Guard와 전체 `/cca` review gate를 통과한다.
2. 저장소가 이미 사용하는 canonical version source만 수정한다. 후보가 여러 개면 추측하지 않는다.
3. CHANGELOG의 대상 버전·날짜·사용자 관점 변경·breaking/migration을 갱신한다.
4. 생성물·lockfile은 프로젝트 명령이 요구할 때만 갱신한다.
5. version/CHANGELOG와 직접 필요한 변경을 검증 가능한 Atomic Commit으로 만든다.
6. `--tag`가 있으면 working tree clean, final verification 성공, tag 미존재를 다시 확인한 후 `git tag -a <tag> -m "Release <version>" HEAD`를 실행한다.
7. tag object와 대상 HEAD를 검증한다. 이후 실패해도 tag를 임의 삭제하지 않고 상태를 보고한다.
8. remote push, GitHub Release, publish, deploy는 하지 않는다.

`/cr release`와 `--dry-run` 보고:

- 기준 ref, 분석 HEAD, package와 범위
- 계산된 다음 version/tag와 bump 근거
- channel과 prerelease 증가 근거
- 릴리스 노트 초안, 차단 요소, 배포 전후 체크리스트
- 수정·commit·tag·push를 하지 않았음

## 4. `emergency`

호출 예:

```text
/cr emergency --incident INC-142 --severity sev1
/cca emergency --diagnose
/cca emergency --rollback-first --incident INC-142
/cca emergency --base v1.8.0 --scope src/payment
```

역할:

- `/cr emergency`: 장애 증거·영향·원인 후보·완화책·검증 계획을 읽기 전용으로 보고한다.
- `/cca emergency --diagnose`: `/cr emergency`와 같은 읽기 전용 진단이며 commit하지 않는다.
- `/cca emergency`: 재현 가능한 원인만 최소 수정·회귀 검증·Atomic Commit한다.

옵션:

- `--incident <id>`: 사용자가 제공한 incident 식별자. commit 본문과 보고서에 값 그대로 기록한다.
- `--severity sev1|sev2|sev3|sev4`: 사용자가 확인한 심각도. 없으면 추정값을 사실처럼 쓰지 않는다.
- `--diagnose`: 수정·stage·commit을 금지한다.
- `--rollback-first`: 기존 feature flag, 설정, 호환 가능한 revert 경로를 코드 수정 전에 우선 평가한다. 파괴적 reset이나 자동 deploy를 뜻하지 않는다.
- `--base <ref>`: 정상 기준 후보. ref 유효성과 현재 변경과의 관련성을 검증한다.
- `--scope <경로...>`: hotfix 실행 범위. 필수 호출부·테스트·운영 설정은 읽는다.

규칙:

1. 사용자 설명과 `--scope`에서 실패 증상·영향 범위를 정한다.
2. 미커밋 변경이 있으면 그 diff를 hotfix 후보로 검토한다.
3. 시간선, 최근 변경, 증상, 재현, 로그·metric·trace 증거를 구분하고 관찰되지 않은 사실을 만들지 않는다.
4. `--rollback-first`면 안전한 feature flag/config/호환 rollback과 blast radius를 먼저 평가한다. history rewrite, 자동 `git revert`, 배포는 하지 않는다.
5. working tree가 깨끗해도 사용자가 구체적인 장애 수정을 명시했다면 Guard를 먼저 시작한 뒤 읽기 전용 진단을 수행할 수 있다.
6. clean 상태에서 원인이 코드로 재현되고 수정이 국소적·검증 가능할 때만 최소 hotfix와 직접 회귀 테스트를 구현한다.
7. 원인이나 기대 동작이 불명확하면 코드를 추측해 변경하지 않고 중단한다.
8. 보안·정확성·데이터 무결성·동시성·복구 가능성·직접 회귀 테스트를 우선한다.
9. schema/data 파괴, dependency upgrade, 광범위한 refactor, 운영 외부 변경은 자동 수행하지 않는다.
10. 가장 작은 재현/회귀 테스트, 관련 lint/type check, 필수 smoke 검증을 수행한다.
11. 검증 실패를 긴급함으로 우회하지 않는다. hook·서명·secret 검사를 우회하지 않는다.
12. 서로 의존해 분리할 수 없는 hotfix는 하나의 commit으로 유지할 수 있다.

최종 보고에는 다음을 추가한다.

- 장애 증상과 근본 원인
- incident ID, 확인된 severity, 시간선과 증거
- rollback/containment 후보와 선택 근거
- 완화 범위와 남은 위험
- 수행한 긴급 검증
- 배포 전후 수동 확인 항목
- rollback 조건과 관찰할 metric·log·trace
- 후속 정리 작업

검증을 생략하거나 실패한 상태를 긴급함만으로 성공 처리하지 않는다.

## 5. `learn`

호출 예:

```text
/cr learn --since v1.5.0 --exclude-bots
/cr learn --branches main,develop --package mobile
/cca learn --preview
/cca learn --since v1.5.0 --branches main,develop --exclude-bots
/cca learn --package mobile --commits 200
```

목적:

- 저장소의 실제 commit history에서 메시지·scope·Atomic 분리·검증 문화를 근거와 확신도와 함께 추출한다.
- `/cr learn`과 `/cca learn --preview`는 프로필 후보만 보고한다.
- 실제 `/cca learn`만 `.commitforge/profile.json`과 `.commitforge/profile.md`를 갱신한다.

입력 범위:

- 기본 최근 100개 non-merge commit
- `--commits N`: 20~500 범위
- `--since <ref>`: ref 이후만 분석하며 각 분석 branch와의 관계를 검증한다.
- `--branches <a,b,...>`: checkout하지 않고 명시한 branch의 도달 가능한 history를 분석한다.
- `--exclude-bots`: 이름·email·일반 bot 패턴으로 확인되는 자동화 작성자를 제외하고 제외 수를 보고한다.
- `--package <name>`: package 경로가 확인된 commit과 cross-package 의존 commit을 구분한다.
- 기본은 현재 브랜치의 도달 가능한 history만 사용
- commit 제목뿐 아니라 대표 commit의 stat/diff도 표본 검사
- 최신 commit에 편향되지 않도록 type/scope/package/기간별로 표본을 계층화하고 merge commit은 제외한다.

프로필에 포함:

- 분석한 ref, commit 수, 생성 시각
- 주로 사용하는 type/scope
- 제목 언어·길이·시제·구두점
- 본문 형식과 상세도
- 구현/테스트/문서 결합 관행
- rename/refactor/formatting 분리 관행
- package/domain별 scope
- 자주 사용하는 검증 명령의 근거
- 명시적 프로젝트 규칙과의 충돌 시 우선순위
- 확신도와 표본 부족 경고
- 각 규칙의 evidence commit과 반례

`profile.json`은 machine-readable 원본이며 다음을 포함한다.

- `schema: commitforge-profile/v1`
- 생성 시각, refs, since, package, 표본 수와 제외 수
- category/value/confidence/evidence commit을 가진 규칙
- 충돌, 반례, 표본 부족 경고

`profile.md`는 같은 근거의 사람이 읽는 요약이다. commit 메시지에 적힌 검증 명령만으로 실제 프로젝트 명령이라고 단정하지 않고 CI·manifest·script 정의에서 교차 검증한다. secret·email 등 민감한 원문은 프로필에 복제하지 않는다.

안전한 실행:

1. 다른 변경을 하기 전에 Guard `begin`을 호출하고 `session`, `token`, `snapshot`, 시작 fingerprint를 보관한다.
2. Git 작업 진행 상태 또는 동시 실행 lock이 있으면 변경 없이 중단한다.
3. 프로필을 쓰기 전에 `.commitforge/profile.md`와 `.commitforge/profile.json`을 제외한 staged diff, working diff, porcelain status를 snapshot 아래의 `learn-*-before` 파일에 저장한다.
4. 기존 source/index/commit을 변경하지 않는다.
5. `.commitforge/profile.md`와 `.commitforge/profile.json`만 새로 만들거나 갱신한다.
6. 기존 프로필이 있으면 내용을 읽고 근거가 달라진 부분만 갱신한다.
7. 프로필 파일을 자동 stage/commit하지 않는다.
8. 작성 직후 같은 세 출력을 `learn-*-after` 파일에 저장하고 각각 `cmp -s`로 byte 비교한다.
9. 하나라도 다르면 프로필 외 상태가 바뀐 것이다. Guard `abort`로 lock을 해제하고 snapshot을 보존한다.
10. 세 비교가 모두 같고 `git status`에서 추가 변화가 프로필뿐이면 Guard `finish --allow-dirty`로 snapshot을 제거하고 lock을 해제한다. `--keep-snapshot`이면 snapshot만 보존한다.

Guard 명령:

```bash
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" begin \
  --session "${CLAUDE_SESSION_ID}"
git diff --cached --binary --full-index -- . \
  ':(exclude).commitforge/profile.md' \
  ':(exclude).commitforge/profile.json' > "<snapshot>/learn-staged-before.diff"
git diff --binary --full-index -- . \
  ':(exclude).commitforge/profile.md' \
  ':(exclude).commitforge/profile.json' > "<snapshot>/learn-working-before.diff"
git status --porcelain=v2 -z --untracked-files=all -- . \
  ':(exclude).commitforge/profile.md' \
  ':(exclude).commitforge/profile.json' > "<snapshot>/learn-status-before.z"
# 프로필 작성 후 동일 명령의 출력은 각각 *-after 파일에 저장한다.
cmp -s "<snapshot>/learn-staged-before.diff" "<snapshot>/learn-staged-after.diff"
cmp -s "<snapshot>/learn-working-before.diff" "<snapshot>/learn-working-after.diff"
cmp -s "<snapshot>/learn-status-before.z" "<snapshot>/learn-status-after.z"
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" --token "<token>" --snapshot "<snapshot>" --allow-dirty
```

`learn`은 소스 리뷰·수정·Atomic Commit 실행 모드가 아니다. `--preview` 또는 `/cr`에서는 Guard `finish --review-only --source-read-only`로 종료하고 파일을 만들지 않는다. 실제 `/cca learn`은 프로필 생성 결과와 변경된 파일 경로를 보고한다.

## 6. 프로젝트 프로필

`/ccr`, `/cc`, `/cr`, `/cca`는 저장소 루트의 `.commitforge/profile.json`과 `.commitforge/profile.md`가 존재하면 읽는다.

우선순위:

1. 사용자의 현재 요청
2. 저장소의 `CLAUDE.md`, `AGENTS.md`, 기여 가이드와 lint/CI 규칙
3. `.commitforge/profile.json`과 `.commitforge/profile.md`
4. CommitForge 기본 규칙

프로필은 관찰된 선호를 보조할 뿐 안전 규칙, Atomic 독립성, 사실 기반 메시지, 검증 gate를 약화할 수 없다.
