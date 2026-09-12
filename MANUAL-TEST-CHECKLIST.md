# 수동 End-to-End 시험 체크리스트

중요 저장소가 아닌 임시 저장소 또는 별도 worktree에서 수행합니다.

## 1. 설치 확인

```bash
claude --version
python3 verify.py
```

Claude Code에서 `/`를 입력해 다음이 보이는지 확인합니다.

- `ccr`
- `cc`
- `cr`
- `cca`
- `cpr`
- `cp`

custom reviewer가 보이지 않으면 Claude Code를 재시작합니다.

## 2. `/ccr` read-only 확인

서로 다른 의도의 작은 변경 두 개와 테스트 하나를 만듭니다.

```text
/ccr 테스트용 변경
```

확인:

- 2개 이상의 적절한 Atomic Commit 계획
- 파일/hunk와 분리 이유
- 한글 제목/본문 초안
- `git status`가 실행 전과 동일
- 실제 commit 없음

## 3. `/cc` 실행 확인

```text
/cc 테스트용 변경
```

확인:

- 소스 파일 내용은 바뀌지 않고 index/commit만 변경
- 의미별 여러 commit
- 각 제목이 `type(scope): 한글 제목`
- 구현과 직접 테스트가 논리적으로 함께 배치
- 마지막 `git status` clean
- snapshot 삭제와 lock 해제 보고
- push 없음

```bash
git log --oneline --decorate -10
git show --stat HEAD
```

## 4. `/cr` 기본 read-only 확인

새로운 작은 변경을 만든 뒤:

```text
/cr 테스트 변경
```

확인:

- 기본 10개 reviewer 또는 main fallback
- 근거가 있는 finding
- 소스 자동 수정 없음
- blocker가 없을 때 검증 후 종료
- reviewer finding이 과장되지 않음
- 모든 diff hunk가 PASS/FINDING/N/A로 판정
- 제거된 동작과 cross-file contract 검토
- 적용 가능한 Architecture/API/UX·A11y/Observability/Quality 결과
- 조건부 reviewer의 활성/N/A 근거
- Atomic Commit 계획과 메시지 초안 없음
- staged diff와 HEAD가 실행 전과 동일
- Guard `verify-review`와 `finish --review-only` 통과
- commit과 push 없음

## 5. `/cr --fix` 자동 수정 확인

의도적으로 명백하고 국소적인 회귀 테스트 누락 또는 null 경계 오류를 만든 테스트 저장소에서:

```text
/cr --fix 테스트 변경
```

확인:

- 문제를 실제 코드 근거로 검증
- 최소 범위 수정
- 기본 10개와 활성 조건부 관점 전체 재리뷰
- targeted test
- unrelated 리팩터링 없음
- Atomic Commit 계획·staging·commit·push 없음

## 6. `/cca` 전체 실행 확인

`/cr`로 검토한 변경에서:

```text
/cca 테스트 변경
```

확인:

- 심층 리뷰와 검증 후 Atomic Commit 계획 생성
- hunk/file 단위 staging과 의미별 commit
- 최종 통합 검증
- push 없음

## 7. 동시 실행 차단

같은 worktree의 두 Claude Code 세션에서 `/cc`를 거의 동시에 실행합니다.

확인:

- 첫 실행만 guard lock 획득
- 두 번째 실행은 Git 변경 없이 중단
- lock을 강제 삭제하지 않음

실제 병렬 개발은 별도 worktree에서 시험합니다.

## 8. 실패 복구

commit hook 실패를 재현하거나 작업을 중단합니다.

확인:

- 소유 lock 해제
- snapshot 보존 위치 보고
- `guard.py status`에서 snapshot 확인
- 다른 세션 snapshot 미삭제

## 9. `/cr today|3days|weekly`

오늘과 이번 주에 해당하는 여러 commit, 되돌림 commit, 새 미커밋 변경을 준비합니다.

```text
/cr today
/cr 3days --timezone Asia/Seoul
/cr weekly --all-authors
```

확인:

- today는 로컬 00:00, 3days는 이틀 전 00:00, weekly는 기본 월요일 00:00 경계
- 3days를 rolling 72시간으로 해석하지 않음
- timezone·UTC offset·정확한 시작/종료 시각
- commit별 원장과 branch net effect 분리
- revert·후속 correction·교차 commit finding 귀속
- working tree가 깨끗해도 기간 commit 리뷰
- HEAD·index 불변, Atomic 계획·commit·push 없음

## 10. `/cca today|3days|weekly`

테스트 브랜치에서 오늘 날짜의 기존 commit과 새 미커밋 변경을 준비합니다.

```text
/cca today 테스트 작업
/cca 3days --timezone Asia/Seoul 테스트 작업
/cca weekly --week-start sunday 테스트 작업
```

확인:

- 정확한 달력 경계와 현재 작성자의 기존 commit 표시
- weekly 날짜·domain별 집계와 반복 수정·미완료 위험
- 기존 commit은 amend/rebase/재생성하지 않음
- 미커밋 변경만 신규 Atomic Commit으로 생성
- 기존 기간 commit과 신규 commit을 구분해 보고
- working tree가 처음부터 clean이면 보고만 하고 commit 없음

## 11. `/cr release`와 `/cca release`

테스트 tag 이후 작은 변경을 준비합니다.

```text
/cr release --from <test-tag>
/cr release --target 1.9.0 --prepare --tag
/cca release --from <test-tag> --dry-run
/cca release --target 1.9.0 --prepare
```

확인:

- 지정 ref부터 HEAD까지의 범위 표시
- 앞의 세 read-only 호출은 HEAD·index·working tree와 tag refs 불변
- `/cr --prepare --tag`는 예상 변경 파일·commit·tag 대상만 보고
- major/minor/patch와 다음 tag 제안 및 자동 증가 근거
- 릴리스 노트 초안과 차단 요소
- `--prepare`에서만 version/CHANGELOG 갱신과 Atomic Commit
- `--tag` 없이는 tag를 만들지 않고 항상 push/publish/deploy 없음

## 12. `/cr emergency`와 `/cca emergency`

작은 hotfix와 직접 회귀 테스트를 준비합니다.

```text
/cr emergency --incident TEST-1 --severity sev3
/cca emergency --diagnose --base <known-good-ref>
/cca emergency --scope <hotfix-path> 장애 재현 설명
```

확인:

- 첫 두 호출은 source·HEAD·index 불변
- 장애 원인과 직접 관련된 최소 범위만 수정
- rollback/containment·관찰·복구 계획
- 무관한 formatting/refactor/dependency 변경 없음
- 직접 회귀 테스트 또는 명확한 수동 검증
- 배포 전후 확인 항목과 남은 위험 보고

## 13. `/cr learn`과 `/cca learn`

history가 있는 테스트 저장소에서 실행합니다.

```text
/cr learn --commits 20
/cca learn --preview --commits 20
/cca learn --commits 20
```

확인:

- 첫 두 호출은 파일과 Git 상태 불변
- 실제 `/cca learn`만 `.commitforge/profile.json`과 `.commitforge/profile.md` 생성 또는 갱신
- source/index/기존 commit 변경 없음
- 프로필 자동 stage/commit 없음
- 분석 범위·표본 수·확신도 표시
- 이후 `/ccr`, `/cc`, `/cr`, `/cca`가 프로필의 관련 선호를 참고

## 14. 심층 리뷰 Coverage Gate

테스트 저장소에 다음 변경을 준비합니다.

- 삭제된 validation 또는 fallback
- 인자를 누락하는 wrapper
- 기존 helper와 중복되는 새 구현
- UI focus/label 누락
- 실패 경로 telemetry 누락
- 언어별 lifecycle 또는 async API 오류

```text
/cr 심층 리뷰 시험
```

확인:

- 모든 hunk 원장과 미검토 0
- removed behavior와 wrapper/proxy 의미 보존 finding
- 기존 재사용 후보의 정확한 위치
- Architecture, Language/API, UX/A11y, Observability, Quality 결과
- 적용 불가능한 관점은 근거가 있는 N/A
- blocking finding이 있으면 실패로 보고
- commit 계획·staging·commit 없음

## 15. 조건부 Reviewer

각각 별도 테스트 변경으로 다음 trigger를 준비합니다.

- schema migration 또는 backfill
- dependency manifest와 lockfile
- retry/queue/failover 경로
- analytics 또는 개인정보 수집
- 명시적인 acceptance criteria와 구현

```text
/cr 조건부 reviewer 시험
```

확인:

- 관련 reviewer만 활성화
- 비관련 reviewer는 근거가 있는 N/A
- Requirements/Product는 명시적 기준이 없을 때 추측하지 않음
- 수정 후 trigger를 다시 판정하고 활성 reviewer를 재실행

## 16. Reviewer 실패와 Finding Schema

테스트 환경에서 선택 reviewer 하나를 사용할 수 없게 한 뒤 `/cr`을 실행합니다.

확인:

- main agent fallback 또는 `UNKNOWN`
- 필수/활성 관점이 UNKNOWN이면 성공 처리하지 않음
- finding에 stable ID, reviewer, fingerprint, severity, status, 위치, evidence, blocking 포함
- 중복 root cause가 하나의 owner finding으로 통합

## 17. Release 재현성

```bash
python3 release.py --check
python3 -m unittest tests.test_release -v
```

확인:

- metadata가 현재 source와 일치
- 서로 다른 임시 디렉터리에서 생성한 ZIP/TAR.GZ가 byte-identical

## 18. 비교 범위와 PR 리뷰

```text
/cr --base main
/cr --range HEAD~2..HEAD
/cr pr
```

확인:

- 실제 merge-base 또는 명시 범위를 보고
- PR 모드는 PR 번호·URL·base/head를 표시
- 과거 commit 범위는 소스 자동 수정 없음
- 모든 모드에서 Atomic 계획·staging·commit 없음

## 19. JSON·SARIF와 Baseline

```text
/cr --format json --output review.json
/cr --format sarif --output review.sarif
```

확인:

- 두 파일이 `report_validator.py` 검증 통과
- baseline의 이유·소유자·만료일이 모두 필요
- 만료된 baseline은 `STALE`
- CRITICAL·secret·인증 우회·데이터 손실 finding은 억제되지 않음

## 20. 대형 Diff와 Snapshot 감사

정책 기준을 낮춘 테스트 `.commitforge/review.yml`을 만들고 여러 domain의 변경을 준비합니다.

확인:

- domain/package shard별 결과와 최종 cross-file 집계
- 누락 문맥은 `UNKNOWN`
- snapshot metadata에 파일별 크기·SHA-256 존재
- snapshot 파일을 변조하면 `audit-snapshot`과 `finish`가 실패하고 snapshot이 보존됨

## 21. Claude Code Live Eval

```bash
python3 evals/run_evals.py --check
python3 evals/run_evals.py --live --scenario "python mutable default regression"
```

확인:

- 격리된 임시 저장소에서 기본 read-only `/cr` 실행
- 기대한 정확성 개념을 finding에서 탐지
- HEAD와 staged diff가 실행 전후 동일

## 22. Release 분석·준비·tag 경계

tag가 있는 임시 저장소에서:

```text
/cr release --from v1.8.0
/cca release --channel rc --target 2.0.0 --dry-run
```

확인:

- 두 실행 모두 HEAD·index·working tree 불변
- 기존 같은 channel tag 다음 prerelease 번호 자동 증가
- version/tag 계산 근거와 tag 충돌 검사
- 릴리스 노트·migration·배포 위험 보고
- commit, tag, push 없음

실행형 시험은 별도 test branch에서 수행합니다.

```text
/cca release --target 1.9.0 --prepare
```

확인:

- canonical version source와 CHANGELOG만 의도대로 갱신
- 검증된 Atomic Commit 생성
- `--tag`가 없으면 tag 없음
- push, GitHub Release, publish, deploy 없음

## 23. Emergency 진단·실행 경계

```text
/cr emergency --incident TEST-1 --severity sev3
/cr emergency --fix
/cca emergency --diagnose --base HEAD~1
```

확인:

- 증거·원인 후보·rollback/containment·검증 계획
- 세 실행 모두 source·HEAD·index 불변
- `/cr emergency --fix` 편집 Hook 차단

실행형 `/cca emergency`는 재현 가능한 작은 결함에서 최소 수정·직접 회귀 테스트·Atomic Commit만 생성하는지 확인합니다.

## 24. Learn preview·프로필 저장 경계

```text
/cr learn --exclude-bots
/cca learn --preview --branches main
```

확인:

- profile 후보·근거 commit·반례·확신도 보고
- 파일 생성과 Git 상태 변경 없음

실제 `/cca learn` 실행 후 `.commitforge/profile.json`과 `.commitforge/profile.md`만 변경되고 자동 stage/commit되지 않는지 확인합니다.

## 25. `/cpr` Pull Request 미리보기

base보다 1개 이상 앞선 clean test branch에서:

```text
/cpr --base main
/cpr --base main --draft
```

확인:

- committed range의 모든 hunk와 net effect 리뷰
- readiness가 `READY`, `CONDITIONAL`, `BLOCKED` 중 하나
- PR 제목·본문·검증·위험 완성 초안
- 기존 동일-head PR이 있으면 URL 보고
- source·index·HEAD·branch·remote·PR 모두 불변
- dirty working tree는 blocker

`main` 또는 `master`가 remote tracking base보다 앞선 임시 저장소에서도 실행합니다.

확인:

- 의미에 맞는 `type/ascii-kebab-slug` branch 이름 제안
- branch를 실제 생성하거나 전환하지 않음
- ahead commit이 0개면 차단

## 26. `/cp` Pull Request 생성

쓰기 가능한 별도 GitHub test repository의 clean branch에서:

```text
/cp --base main --draft
```

확인:

- review gate 통과 전 push 없음
- force 없는 현재 branch push
- draft PR 하나 생성 후 number·URL·base·head·title 재검증
- 같은 명령을 다시 실행하면 중복 PR 대신 기존 URL 보고
- source·index·HEAD commit 불변
- merge·close·auto-merge·label·reviewer·deploy 없음

`main`/`master`가 remote보다 앞선 별도 test repository에서도 실행합니다.

확인:

- review 이후에만 충돌 없는 branch 생성
- 새 branch의 commit SHA가 시작 HEAD와 동일
- 새 branch를 push해 PR 생성
- 실패 시 branch 자동 삭제·원래 branch 자동 복귀 없음
- `--branch <name>`의 잘못된 ref 형식과 기존 local/remote 이름 충돌 차단

## 27. 에디터 확장

`editor-extension/`을 VS Code 또는 Cursor로 열고 F5(Extension Development
Host)로 새 창을 띄워 확인합니다. 터미널 전송과 GUI 상호작용은 자동 검증이
어려운 부분입니다.

CommitForge가 설치되지 않은 임시 git 저장소를 새 창에서 엽니다.

확인:

- 활동 표시줄에 CommitForge($(git-commit)) 아이콘이 보이고 클릭하면 사이드바에
  `상태` 트리 뷰가 열린다
- 상태바가 `$(alert) CommitForge 미설치`를 보여준다
- 트리의 `설치` 노드 아래 `project`가 미설치(회색 원 아이콘)로 표시된다
- 상태바 클릭 시 같은 트리 뷰로 포커스가 이동한다 (`commitforge.focusView`)

명령 팔레트에서 `CommitForge: 설치` → `project` 선택으로 설치합니다.

확인:

- dry-run 내용이 Output 채널에 먼저 나오고, 확인 모달에서 승인해야 실제로
  설치된다
- 설치 후 상태바가 `$(check) CommitForge v<번들버전>`으로 바뀐다
- `.claude/.commitforge-install.json`이 생성되고 `version`이 루트 `VERSION`과
  같다
- 상태바에 마우스를 올리면 tooltip에 `project: ...`, `global: ...`,
  `번들 버전: v...`, `Python: ...` 네 줄이 보인다
- 트리에서 `project` 행을 클릭(트리 항목 자체, 버튼 아님)해도 QuickPick 없이
  바로 그 행의 scope로 동작하고, 명령 팔레트에서 인자 없이
  `CommitForge: 설치`를 직접 실행하면 여전히 범위를 QuickPick으로 묻는다
  (회귀 확인)

`.claude/.commitforge-install.json`의 `version`만 손으로 다른 값으로 바꾸고
(해시는 그대로) `CommitForge: 상태 새로고침`을 실행합니다.

확인:

- 상태바 배지는 번들 버전 그대로 유지되고, tooltip에 "설치 마커: v..." 경고
  줄이 추가된다 (해시가 일치하면 마커가 낡아도 `정상`으로 판정)

트리의 인라인 버튼을 확인합니다.

확인:

- 미설치 행에는 `[설치]`($(cloud-download)) 버튼 하나만 보이고, 클릭 시
  QuickPick 없이 바로 그 행의 scope로 dry-run 확인 모달이 뜬다
- 설치 완료 후에는 같은 행에 `[검증]`($(check)) `[제거]`($(trash)) 버튼만
  남고 설치 버튼은 사라진다
- 번들 버전을 바꿔 `version-mismatch` 상태를 재현하면 `[업그레이드]`
  ($(arrow-up)) 버튼이, `.claude/`를 손상시켜 `misconfigured`/`corrupt`
  상태를 재현하면 `[재설치]`($(sync)) 버튼이 뜨고 tooltip도 각각
  "CommitForge: 업그레이드"/"CommitForge: 재설치"로 다르게 보인다
- 명령 팔레트에서 "CommitForge"를 검색하면 "설치"만 보이고 "업그레이드"·
  "재설치"는 보이지 않는다
- `CommitForge: 설치 검증` 실행 시 `verify.py`가 아니라 이 확장의 재판정
  결과가 Output에 출력된다(파일시스템 변화 없이)
- `CommitForge: 제거` 실행 → dry-run 확인 → 승인 후 상태바가 미설치로
  돌아가고 `.claude/.commitforge-install.json` 마커가 사라진다
- 스냅샷이 하나도 없을 때는 `스냅샷` 행에 인라인 버튼이 보이지 않는다.
  `/cca` 등을 한 번 실행해 스냅샷이 생긴 뒤에는 $(folder-opened) 버튼이
  나타나고 클릭 시 OS 파일 탐색기가 `.git/claude-atomic-snapshots`로 열린다
- Git 저장소가 아닌 폴더를 열면 잠금·스냅샷 노드 자체가 트리에 보이지 않는다

트리 항목을 **우클릭**해 메뉴를 확인합니다(지금까지는 인라인 버튼만
확인했습니다 — 우클릭 메뉴는 F5로만 확인할 수 있고 자동 테스트 대상이
아닙니다).

확인:

- 미설치 `project`/`global` 행을 우클릭하면 `CommitForge: 설치`가 (인라인
  버튼과 별개로) 메뉴에도 뜬다
- 설치 완료된 행을 우클릭하면 `CommitForge: 설치 검증`·`CommitForge: 제거`가
  뜬다. `version-mismatch`/`misconfigured`/`corrupt` 상태를 재현해 같은 행을
  우클릭하면 각각 `CommitForge: 업그레이드`/`CommitForge: 재설치`가 대신
  뜬다(인라인 버튼과 같은 상태별 규칙을 그대로 따른다)
- `잠금` 그룹 행을 우클릭하면 `CommitForge: lock 해제(clean)`이 뜬다(잠금
  보유 여부와 무관하게 항상 보인다)
- `스냅샷` 그룹 행을 우클릭하면 `CommitForge: 스냅샷 폴더 열기`가 뜬다(스냅샷이
  하나도 없으면 항목 자체가 없다)

Source Control 패널의 CommitForge 버튼을 확인합니다. 이 워크스페이스가 git
저장소여야 나타납니다.

확인:

- 사이드바를 Source Control 뷰(활동 표시줄의 분기 아이콘)로 바꾸면 제목 줄에
  $(search) 아이콘과 $(git-commit) 아이콘 두 개가 보인다(마우스를 올리면
  각각 "CommitForge: 리뷰 실행 (/cr)", "CommitForge: 순차 커밋 실행 (/cc)")
- 제목 줄의 "..." (넘침) 메뉴를 열면 **CommitForge**라는 하위 메뉴가 있고,
  그 안에 `/ccf`·`/cf`·`/cca`·`CommitForge: 명령 실행` 네 항목이 순서대로
  있다
- $(search) 아이콘을 클릭하면 QuickPick에서 `/cr`을 고른 것과 동일하게
  동작한다: `commitforge.confirmBeforeSend`가 켜져 있으면 "터미널로 보냅니다:
  /cr" 확인 모달이 뜨고, 승인해야 실제로 전송된다
- 다른 세션(또는 다른 창)이 lock을 쥔 상태에서 $(git-commit)(`/cc`) 아이콘을
  클릭하면, 확인 모달보다 **먼저** "다른 세션이 lock을 보유 중입니다: session
  ... · N분 경과 · 호스트" 경고가 뜬다("그래도 보내기"/"clean 실행" 선택지도
  QuickPick 경로와 동일하다) — 옵션 없는 단축 버튼이라고 이 경고를 건너뛰지
  않는다
- git 저장소가 아닌 폴더를 열면 Source Control 뷰 제목 줄에 CommitForge
  아이콘·메뉴가 아예 보이지 않는다
- `.claude/`를 지워 CommitForge가 미설치인 상태에서 $(search) 아이콘을
  누르면(카탈로그가 비어 있으므로) "명령을 카탈로그에서 찾지 못했습니다"
  경고가 뜨고, 아무것도 터미널로 전송되지 않는다

`잠금`·`스냅샷` 자식 항목의 **값 복사**를 확인합니다. 다른 창에서 `/cc` 등으로
lock을 잡아 두거나 `/cca` 등을 실행해 스냅샷을 하나 이상 만들어 둡니다.

확인:

- `잠금` 아래 `session ...` 행을 우클릭 → **값 복사**를 실행하면 클립보드에
  전체 세션 ID가 들어가고("복사했습니다: ..." 알림이 뜬다), 붙여넣기로
  확인하면 라벨에 잘려 보이던 부분까지 포함한 전체 값이다
- `이 호스트`(또는 `다른 호스트`) 행을 우클릭 → **값 복사**를 실행하면
  클립보드에 실제 호스트명이 들어간다
- `N 경과` 행은 우클릭해도 값 복사 메뉴 자체가 보이지 않는다(복사할 값이
  없다)
- `스냅샷` 아래 각 스냅샷 행을 우클릭하면 **폴더 열기**·**경로 복사** 두
  항목이 보인다. **폴더 열기**는 행을 클릭했을 때와 동일하게 OS 파일
  탐색기를 그 스냅샷 폴더로 연다. **경로 복사**는 클립보드에 그 스냅샷의
  전체 절대 경로를 담는다

명령 실행 흐름을 확인합니다.

확인:

- `CommitForge: 명령 실행` → `/cr` 선택(Enter) → 확인 모달 → 첫 전송이면
  터미널을 한 번 물어보고, 선택한 터미널에서 `claude`가 뜬 뒤 `/cr`이
  입력되고 Enter까지 눌린다 — 팔레트 선택부터 전송까지 두 번의 입력(명령
  선택 + 확인)으로 끝난다
- 두 번째 전송부터는 터미널을 다시 묻지 않는다. 그 터미널을 닫은 뒤 다시
  실행하면 닫혔음을 감지해 새로 묻거나 만든다
- `/cca`의 톱니(⚙) 버튼 → `release` 모드를 고르면 `--target`·`--bump`·
  `--channel` 등이 "release 관련" 그룹 헤더 아래 먼저 오고, 힌트 표에 없는
  옵션도 "기타" 그룹에 그대로 남아 있다(숨겨지지 않는다)
- `--commits`에 `5`를 넣으면 "20-500 범위여야 합니다" 오류가 뜨고 전송되지
  않는다. `100`처럼 범위 안 값은 정상 조립된다
- **옵션 값 InputBox에 개행이 붙여넣기로 들어갈 수 있는가**: 값 입력창에
  여러 줄 텍스트를 붙여넣었을 때, 실제로 개행이 들어가면 "값에 개행을 넣을
  수 없습니다" 오류로 전송이 막히고 조용히 깨진 값이 전송되지 않는다
- **홑따옴표가 든 옵션 값으로 `/cr --fix`를 보냈을 때 편집이 거부되지
  않는가**: 예를 들어 자유 맥락이나 옵션 값에 `o'brien`처럼 홑따옴표가 든
  값을 넣어 `--fix`와 함께 전송했을 때, `cr_edit_gate.py`의 edit gate가
  read-only 오류로 편집을 거부하지 않고 정상적으로 `--fix`를 인식한다
- **다른 세션이 lock을 쥔 상태에서 쓰기 명령이 전송 전에 경고하는가**: 다른
  세션(또는 다른 창)에서 `/cc` 등으로 lock을 잡은 채 이 창에서 `/cca`를
  고르면, 터미널로 보내기 **전에** "다른 세션이 lock을 보유 중입니다: session
  ... · N분 경과 · 호스트" 경고가 뜬다. "clean 실행"을 고르면 `/cr clean`이
  전송되고, "그래도 보내기"를 고르면 원래 명령이 그대로 전송된다
- 트리 `잠금` 행의 `[해제(clean)]` 버튼을 클릭하면 확인 모달 이후 `/cr
  clean`이 전송되고, 최근 실행 목록에는 남지 않는다
- 최근 실행 목록에 직전 명령이 남고, 팔레트를 다시 열면 "최근" 구분선 아래
  보인다

이벤트 기반 갱신(폴링 없음)을 확인합니다. **이 워크트리처럼 git worktree로
연 워크스페이스에서 확인하는 것이 특히 중요합니다** — 일반 저장소와 `.git`
경로 구조가 달라 감시 대상 계산이 어긋나기 쉽습니다.

확인:

- git worktree로 연 워크스페이스에서 lock을 잡았다 풀었을 때(`/cc` 등 실행
  중·후), 수동 새로고침 없이도 트리의 `잠금` 항목이 자동으로 갱신된다
- 다른 앱으로 전환했다가 에디터로 돌아오면(창 포커스 복귀) 상태바·트리가
  자동 갱신된다
- 워크스페이스 밖 터미널에서 `.claude/` 아래 파일을 수정·삭제하면 트리의
  설치 상태가 자동 갱신된다
- 확장을 비활성화(창 닫기·reload)해도 오류 없이 정리되고, 다음 세션에서
  watcher가 중복 등록되지 않는다

예외 상황을 확인합니다.

확인:

- `commitforge.pythonPath`에 잘못된 경로를 넣어도 확장이 죽지 않고, 설치·
  상태 판정만 비활성화되며 명령 전송(터미널로 보내기)은 계속 동작한다
- `commitforge.statusBar.enabled`를 `false`로 설정하고 새로고침하면 상태바가
  숨는다
- 다중 루트 워크스페이스를 열면 사용할 폴더를 한 번 QuickPick으로 묻고,
  창을 다시 열면 다시 묻지 않는다
- guard.py의 **stderr 실패**를 재현한다. 파일을 옮기거나 지우면 안 된다 —
  `state.ts`는 `exists(guardScript)`가 거짓이면 guard 실행 자체를 건너뛰어
  `guard = null, guardError = null`이 되고, 잠금·스냅샷 노드가 경고 한 줄
  없이 그냥 사라진다(파일이 없으면 해시 대조 대상에서도 빠져 설치 상태가
  `손상`으로 뒤집힌다). 대신 파일 내용은 그대로 두고 **읽기 권한만** 잠깐
  제거해 Python이 파일을 열지 못하게 한다(해시는 파일 바이트만 보므로 설치
  상태는 영향받지 않고, `access()`는 존재 여부만 확인하므로 guard 실행
  자체는 그대로 시도된다):
  1. `chmod 000 .claude/skills/_git-atomic-core/scripts/guard.py`
     (global scope로 테스트 중이면 해당 설치 경로의 같은 파일)
  2. `CommitForge: 상태 새로고침`을 실행한다
  3. 확인: 트리의 `잠금`·`스냅샷` 노드에 마지막으로 성공한 정보가
     `(오래된 값)` 표시와 회색 아이콘으로 남아 있다
  4. 확인: Output 채널(`CommitForge`)에 `Permission denied`가 포함된
     stderr가 찍힌다(spec §8, guardErrorLog.ts)
  5. 확인: `설치` 섹션의 상태는 여전히 `정상`이다(파일 내용을 건드리지
     않았으므로 해시 대조는 깨지지 않는다)
  6. 끝나면 반드시 권한을 복구한다: `chmod 644 .claude/skills/_git-atomic-core/scripts/guard.py`

`설치` 그룹 행(project·global 중 하나만 있으면 된다는 결론)을 확인합니다.
global에는 CommitForge를 설치하고(`CommitForge: 설치` → `global`), 이
워크스페이스의 `.claude/`는 지우거나 아예 만들지 않은 상태로 엽니다.

확인:

- `설치` 그룹 행의 description이 `global 사용 중`으로 보인다(project가
  미설치라도 "할 일이 남았다"는 인상을 주지 않는다)
- `project` 행은 회색(흐린) 아이콘으로 표시되고 description에 `없어도 됨`이
  붙는다 — 하지만 `[설치]` 버튼은 여전히 눌러 project에 따로 설치할 수 있다
- `project`·`global` 행에 마우스를 올리면 tooltip에 각각 "이 저장소에서만"/
  "모든 프로젝트에서"가 보인다
- project에도 설치하면(`CommitForge: 설치` → `project`) 그룹 행이
  `project 사용 중`으로 바뀌고, 이번엔 `global` 행에 `없어도 됨`이 붙는다
- 둘 다 제거하면 그룹 행이 `설치 필요`로 바뀌고 두 행 모두 색이 정상으로
  돌아온다(둘 다일 때는 "없어도 됨" 단서가 붙지 않는다 — 실제로 할 일이다)

global만 설치한 뒤(project는 미설치 상태로 둔 채) 일부러 손상시켰을 때
`설치` 그룹 행이 그 사실을 드러내는지 확인합니다(리뷰 재현: primary가
`missing`이 아니라는 것만으로 "사용 중"이라 말하던 버그).

- `CommitForge: 설치` → `global`로 설치한다
- global 설치본의 `.claude/agents/` 아래 아무 파일 하나(예:
  `cca-architecture-reviewer.md`)의 내용을 한 줄 고쳐 저장한다(해시 대조가
  깨져 `손상` 판정을 유도한다)
- `CommitForge: 상태 새로고침`을 실행한다

확인:

- `설치` 그룹 행의 description이 `global 사용 중`이 **아니라**
  `global 손상 · 확인 필요`처럼 문제를 드러내고, 아이콘이 경고로 바뀐다
- `project` 행(여전히 미설치)에는 `없어도 됨`이 **붙지 않는다** — 반대쪽인
  global이 실제로는 손상돼 있어 명령이 동작하지 않을 수 있기 때문이다
- 상태바 tooltip/배지가 보여주는 상태(`$(warning) CommitForge 손상`)와
  트리의 판정이 서로 모순되지 않는다
- 고친 파일을 원래 내용으로 되돌리고 상태 새로고침하면 그룹 행이 다시
  `global 사용 중`으로 돌아온다

`잠금`·`스냅샷` 자식 항목의 tooltip과 클릭 동작을 확인합니다. 한 창에서
`/cc` 등으로 lock을 잡아 두고(또는 다른 창에서) 이 워크스페이스를 봅니다.

확인:

- `잠금` 아래 `session ...` 행에 마우스를 올리면 tooltip에 잘리지 않은
  전체 세션 ID가 보인다
- `N 경과` 행의 tooltip에 실제 잠금 생성 시각(ISO 문자열)이 보인다
- `이 호스트` 행의 tooltip에 이 컴퓨터의 호스트명이 보인다. 다른 머신에서
  잡은 lock을 보는 상황을 재현하면(어렵다면 코드로 `lockOwnerSameHost:
  false`를 임시로 강제해 확인) `다른 호스트` 행이 되고 tooltip에 그
  호스트명과 "여기서 해제(clean)하면 안 됩니다" 경고가 함께 보인다
- `/cca` 등을 실행해 스냅샷을 하나 이상 만든 뒤, `스냅샷` 아래 각 행의
  라벨이 전체 경로가 아니라 디렉터리 이름(짧은 식별자)으로 보인다
- 그 스냅샷 행을 **클릭**하면(버튼이 아니라 행 자체) OS 파일 탐색기가 그
  스냅샷 폴더로 바로 열린다(그룹 행의 $(folder-opened) 버튼은 전체
  스냅샷 폴더를 여는 것과 별개로 계속 동작해야 한다)
