# CommitForge `/cca` 확장 모드

## 목차

1. 공통 해석 규칙
2. `today`
3. `release`
4. `emergency`
5. `learn`
6. 프로젝트 프로필

## 1. 공통 해석 규칙

`/cca`의 첫 번째 위치 인자가 `today`, `release`, `emergency`, `learn` 중 하나면 확장 모드로 해석한다. 그 외에는 기본 `/cca` 흐름을 사용한다.

- 확장 모드 이름 뒤의 일반 문장은 작업 맥락으로 사용한다.
- 알 수 없는 모드처럼 보이는 단어는 자동 실행하지 말고 일반 맥락으로 취급한다.
- 어떤 모드도 기존 commit을 amend/rebase/reset/squash하지 않는다.
- 어떤 모드도 push, tag, GitHub Release 생성 또는 배포를 수행하지 않는다.
- `.commitforge/profile.md`가 있으면 저장소의 명시적 규칙과 충돌하지 않는 범위에서 메시지·분리·검증 선호에 적용한다.

## 2. `today`

호출 예:

```text
/cca today
/cca today 인증 처리 작업
/cca today --all-authors
```

목적:

- 현재 브랜치에서 오늘 수행한 작업과 현재 미커밋 변경을 하나의 작업 맥락으로 리뷰한다.
- 이미 생성된 commit은 분석·보고에만 사용한다.
- 현재 미커밋 변경만 기본 `/cca` 품질 파이프라인으로 수정·검증·commit한다.

오늘의 범위:

1. Claude Code를 실행하는 호스트의 로컬 시간대를 기준으로 자정 이후를 사용한다.
2. 사용자가 시간대 또는 날짜 경계를 명시하면 그 값을 우선하고 최종 보고에 기준을 표시한다.
3. 기본값은 `git config --get user.email`과 일치하는 작성자의 현재 브랜치 도달 가능 commit이다.
4. `--all-authors`이면 작성자 제한을 제거한다.
5. merge commit은 별도 표시하고 중복 통계가 생기지 않도록 diff 합산 기준을 명시한다.
6. 작성자 이메일이 없으면 임의 추정하지 말고 현재 브랜치의 오늘 commit 전체를 사용했다는 경고를 남긴다.

권장 조회:

```bash
git config --get user.email
git log --since=midnight --date=iso-local \
  --pretty=format:'%H%x09%an%x09%ae%x09%ad%x09%s'
```

실행:

1. 오늘 commit 목록과 시작 HEAD를 기록한다.
2. 각 commit의 목적·통계·검증 정보를 읽고 전체 작업 위험을 검토한다.
3. working tree가 깨끗하면 기존 commit을 재작성하지 않고 오늘 작업 보고만 반환한다.
4. 미커밋 변경이 있으면 기본 `/cca` Guard부터 Commit 실행까지 수행한다.
5. 최종 보고에는 기존 오늘 commit과 새 commit을 구분한다.

금지:

- 오늘 commit을 다시 commit하기
- 자동 squash/amend/rebase
- 날짜만으로 다른 branch의 도달 불가능 commit을 섞기
- 오늘 이전 commit을 암묵적으로 포함하기

## 3. `release`

호출 예:

```text
/cca release
/cca release 1.2.0 후보 점검
/cca release --from v1.1.0
```

목적:

- 릴리스 후보 범위와 현재 변경을 함께 검토한다.
- 현재 변경은 기본 `/cca` 흐름으로 안전하게 commit한다.
- 예상 Semantic Version 영향과 릴리스 노트 초안을 만든다.

범위 결정:

1. `--from <ref>`가 있으면 해당 ref의 유효성을 확인한다.
2. `<ref>`가 `HEAD`의 조상인지 확인한다. 조상이 아니면 임의 범위를 만들지 말고 중단해 다른 ref를 요청한다.
3. 유효한 조상이면 `<ref>..HEAD`를 사용한다.
4. `--from`이 없으면 현재 HEAD에서 도달 가능한 가장 최근 tag를 조회한다.
5. tag가 없으면 저장소 첫 commit부터 HEAD까지임을 명시한다.
6. 현재 미커밋 변경은 범위에 별도로 더한다.

권장 조회:

```bash
git describe --tags --abbrev=0
git merge-base --is-ancestor <from> HEAD
git log --first-parent --reverse --format='%H%x09%s' <from>..HEAD
git diff --stat <from>..HEAD
```

검토 항목:

- 사용자 가시 기능·수정·성능 변화
- Breaking Change, migration, 배포 순서
- 보안·데이터 호환성
- 문서·테스트·CHANGELOG 누락
- Conventional Commit type과 실제 diff를 근거로 한 major/minor/patch 제안

결과:

- 현재 변경이 있으면 Atomic Commit 생성
- 기준 ref와 최종 HEAD
- 권장 다음 버전과 근거
- 사용자 관점의 릴리스 노트 초안
- 차단 요소와 수동 배포 체크리스트

버전 파일, CHANGELOG, lockfile은 사용자가 명시적으로 갱신을 요청한 경우에만 수정한다. tag, push, GitHub Release, package publish, deploy는 수행하지 않는다.

## 4. `emergency`

호출 예:

```text
/cca emergency 결제 승인 중복 처리
/cca emergency --scope src/payments test/payments
```

목적:

- 운영 장애 또는 긴급 hotfix를 최소 변경으로 검토·검증·commit한다.
- 속도보다 파괴적 회귀 방지를 우선하되 무관한 개선으로 범위를 넓히지 않는다.

규칙:

1. 사용자 설명과 `--scope`에서 실패 증상·영향 범위를 정한다.
2. 미커밋 변경이 있으면 그 diff를 hotfix 후보로 검토한다.
3. working tree가 깨끗해도 사용자가 구체적인 장애 수정을 명시했다면 Guard를 먼저 시작한 뒤 읽기 전용 진단을 수행할 수 있다.
4. clean 상태에서 원인이 코드로 재현되고 수정이 국소적·검증 가능할 때만 최소 hotfix와 직접 회귀 테스트를 구현한다. 이는 기본 Gate의 “현재 변경이 만든 문제” 조건에 대한 `emergency` 전용 예외다.
5. 원인이나 기대 동작이 불명확하면 코드를 추측해 변경하지 않고 중단한다.
6. scope가 없으면 diff와 관련 호출부에서 가장 작은 안전 범위를 추론하고 보고한다.
7. 보안·정확성·데이터 무결성·직접 회귀 테스트 관점을 우선한다.
8. 자동 수정은 장애 원인과 직접 관련된 확정적·국소 변경으로 제한한다.
9. formatting, 광범위한 refactor, 의존성 upgrade, 문서 정리는 별도 후속 작업으로 남긴다.
10. 가능한 가장 작은 재현/회귀 테스트와 필수 smoke 검증을 수행한다.
11. 서로 의존해 분리할 수 없는 hotfix는 하나의 commit으로 유지할 수 있다.

최종 보고에는 다음을 추가한다.

- 장애 증상과 근본 원인
- 완화 범위와 남은 위험
- 수행한 긴급 검증
- 배포 전후 수동 확인 항목
- 후속 정리 작업

검증을 생략하거나 실패한 상태를 긴급함만으로 성공 처리하지 않는다.

## 5. `learn`

호출 예:

```text
/cca learn
/cca learn --commits 200
```

목적:

- 저장소의 실제 commit history에서 메시지·scope·Atomic 분리·검증 문화를 학습한다.
- 결과를 `.commitforge/profile.md`에 저장해 이후 `/ccr`, `/cc`, `/cca`가 참고하게 한다.

입력 범위:

- 기본 최근 100개 non-merge commit
- `--commits N`: 20~500 범위
- 현재 브랜치의 도달 가능한 history만 사용
- commit 제목뿐 아니라 대표 commit의 stat/diff도 표본 검사

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

안전한 실행:

1. 다른 변경을 하기 전에 Guard `begin`을 호출하고 `session`, `token`, `snapshot`, 시작 fingerprint를 보관한다.
2. Git 작업 진행 상태 또는 동시 실행 lock이 있으면 변경 없이 중단한다.
3. 프로필을 쓰기 전에 `.commitforge/profile.md`를 제외한 staged diff, working diff, porcelain status를 snapshot 아래의 `learn-*-before` 파일에 저장한다.
4. 기존 source/index/commit을 변경하지 않는다.
5. `.commitforge/profile.md`만 새로 만들거나 갱신한다.
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
  ':(exclude).commitforge/profile.md' > "<snapshot>/learn-staged-before.diff"
git diff --binary --full-index -- . \
  ':(exclude).commitforge/profile.md' > "<snapshot>/learn-working-before.diff"
git status --porcelain=v2 -z --untracked-files=all -- . \
  ':(exclude).commitforge/profile.md' > "<snapshot>/learn-status-before.z"
# 프로필 작성 후 동일 명령의 출력은 각각 *-after 파일에 저장한다.
cmp -s "<snapshot>/learn-staged-before.diff" "<snapshot>/learn-staged-after.diff"
cmp -s "<snapshot>/learn-working-before.diff" "<snapshot>/learn-working-after.diff"
cmp -s "<snapshot>/learn-status-before.z" "<snapshot>/learn-status-after.z"
bash "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/guard.sh" finish \
  --session "<session>" --token "<token>" --snapshot "<snapshot>" --allow-dirty
```

`learn`은 소스 리뷰·수정·Atomic Commit 실행 모드가 아니다. 프로필 생성 결과와 변경된 파일 경로를 보고하고 종료한다.

## 6. 프로젝트 프로필

`/ccr`, `/cc`, `/cca`는 저장소 루트의 `.commitforge/profile.md`가 존재하면 읽는다.

우선순위:

1. 사용자의 현재 요청
2. 저장소의 `CLAUDE.md`, `AGENTS.md`, 기여 가이드와 lint/CI 규칙
3. `.commitforge/profile.md`
4. CommitForge 기본 규칙

프로필은 관찰된 선호를 보조할 뿐 안전 규칙, Atomic 독립성, 사실 기반 메시지, 검증 gate를 약화할 수 없다.
