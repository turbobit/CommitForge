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

## 4. `/cr --no-fix` 확인

새로운 작은 변경을 만든 뒤:

```text
/cr --no-fix 테스트 변경
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

## 5. `/cr` 자동 수정 확인

의도적으로 명백하고 국소적인 회귀 테스트 누락 또는 null 경계 오류를 만든 테스트 저장소에서:

```text
/cr 테스트 변경
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

## 9. `/cca today`

테스트 브랜치에서 오늘 날짜의 기존 commit과 새 미커밋 변경을 준비합니다.

```text
/cca today 테스트 작업
```

확인:

- 로컬 자정 이후 현재 작성자의 기존 commit 표시
- 기존 commit은 amend/rebase/재생성하지 않음
- 미커밋 변경만 신규 Atomic Commit으로 생성
- 기존 오늘 commit과 신규 commit을 구분해 보고
- working tree가 처음부터 clean이면 보고만 하고 commit 없음

## 10. `/cca release`

테스트 tag 이후 작은 변경을 준비합니다.

```text
/cca release --from <test-tag>
```

확인:

- 지정 ref부터 HEAD까지의 범위 표시
- 현재 미커밋 변경만 commit
- major/minor/patch 제안과 근거
- 릴리스 노트 초안과 차단 요소
- tag, push, publish, deploy 없음

## 11. `/cca emergency`

작은 hotfix와 직접 회귀 테스트를 준비합니다.

```text
/cca emergency --scope <hotfix-path> 장애 재현 설명
```

확인:

- 장애 원인과 직접 관련된 최소 범위만 수정
- 무관한 formatting/refactor/dependency 변경 없음
- 직접 회귀 테스트 또는 명확한 수동 검증
- 배포 전후 확인 항목과 남은 위험 보고

## 12. `/cca learn`

history가 있는 테스트 저장소에서 실행합니다.

```text
/cca learn --commits 20
```

확인:

- `.commitforge/profile.md`만 생성 또는 갱신
- source/index/기존 commit 변경 없음
- 프로필 자동 stage/commit 없음
- 분석 범위·표본 수·확신도 표시
- 이후 `/ccr`, `/cc`, `/cr`, `/cca`가 프로필의 관련 선호를 참고

## 13. 심층 리뷰 Coverage Gate

테스트 저장소에 다음 변경을 준비합니다.

- 삭제된 validation 또는 fallback
- 인자를 누락하는 wrapper
- 기존 helper와 중복되는 새 구현
- UI focus/label 누락
- 실패 경로 telemetry 누락
- 언어별 lifecycle 또는 async API 오류

```text
/cr --no-fix 심층 리뷰 시험
```

확인:

- 모든 hunk 원장과 미검토 0
- removed behavior와 wrapper/proxy 의미 보존 finding
- 기존 재사용 후보의 정확한 위치
- Architecture, Language/API, UX/A11y, Observability, Quality 결과
- 적용 불가능한 관점은 근거가 있는 N/A
- blocking finding이 있으면 실패로 보고
- commit 계획·staging·commit 없음

## 14. 조건부 Reviewer

각각 별도 테스트 변경으로 다음 trigger를 준비합니다.

- schema migration 또는 backfill
- dependency manifest와 lockfile
- retry/queue/failover 경로
- analytics 또는 개인정보 수집
- 명시적인 acceptance criteria와 구현

```text
/cr --no-fix 조건부 reviewer 시험
```

확인:

- 관련 reviewer만 활성화
- 비관련 reviewer는 근거가 있는 N/A
- Requirements/Product는 명시적 기준이 없을 때 추측하지 않음
- 수정 후 trigger를 다시 판정하고 활성 reviewer를 재실행

## 15. Reviewer 실패와 Finding Schema

테스트 환경에서 선택 reviewer 하나를 사용할 수 없게 한 뒤 `/cr --no-fix`를 실행합니다.

확인:

- main agent fallback 또는 `UNKNOWN`
- 필수/활성 관점이 UNKNOWN이면 성공 처리하지 않음
- finding에 stable ID, reviewer, fingerprint, severity, status, 위치, evidence, blocking 포함
- 중복 root cause가 하나의 owner finding으로 통합

## 16. Release 재현성

```bash
python3 release.py --check
python3 -m unittest tests.test_release -v
```

확인:

- metadata가 현재 source와 일치
- 서로 다른 임시 디렉터리에서 생성한 ZIP/TAR.GZ가 byte-identical

## 17. 비교 범위와 PR 리뷰

```text
/cr --base main --no-fix
/cr --range HEAD~2..HEAD --no-fix
/cr pr --no-fix
```

확인:

- 실제 merge-base 또는 명시 범위를 보고
- PR 모드는 PR 번호·URL·base/head를 표시
- 과거 commit 범위는 소스 자동 수정 없음
- 모든 모드에서 Atomic 계획·staging·commit 없음

## 18. JSON·SARIF와 Baseline

```text
/cr --no-fix --format json --output review.json
/cr --no-fix --format sarif --output review.sarif
```

확인:

- 두 파일이 `report_validator.py` 검증 통과
- baseline의 이유·소유자·만료일이 모두 필요
- 만료된 baseline은 `STALE`
- CRITICAL·secret·인증 우회·데이터 손실 finding은 억제되지 않음

## 19. 대형 Diff와 Snapshot 감사

정책 기준을 낮춘 테스트 `.commitforge/review.yml`을 만들고 여러 domain의 변경을 준비합니다.

확인:

- domain/package shard별 결과와 최종 cross-file 집계
- 누락 문맥은 `UNKNOWN`
- snapshot metadata에 파일별 크기·SHA-256 존재
- snapshot 파일을 변조하면 `audit-snapshot`과 `finish`가 실패하고 snapshot이 보존됨

## 20. Claude Code Live Eval

```bash
python3 evals/run_evals.py --check
python3 evals/run_evals.py --live --scenario "python mutable default regression"
```

확인:

- 격리된 임시 저장소에서 `/cr --no-fix` 실행
- 기대한 정확성 개념을 finding에서 탐지
- HEAD와 staged diff가 실행 전후 동일
