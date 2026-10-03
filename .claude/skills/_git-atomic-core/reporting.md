# 결과 보고 형식

## 공통 실행 시간

명령 호출을 받은 직후 `RUN_STARTED_AT`을 기록하고, Guard 정리와 마지막 검증이
끝난 최종 보고 직전에 `RUN_FINISHED_AT`을 기록한다. 사용자 승인 대기와 reviewer,
검증, 정리 시간을 포함한 전체 경과 시간을 계산한다.

성공·실패·중단·부분 완료를 포함한 모든 human 결과의 `## 상태` 또는 마지막 요약에
`소요 시간: N.N분`을 반드시 포함한다. 6초 미만은 `소요 시간: 0.1분 미만`,
그 외에는 분으로 환산해 소수점 첫째 자리까지 표시한다. 시작 시각을 잃어 계산할
수 없으면 추측하지 말고 `소요 시간: 측정 불가 (사유)`로 표시한다. Guard의
`lock_age_seconds`를 실행 시간으로 대신 사용하지 않는다.

## 공통 판정

reviewer 파이프라인을 돌리는 `/cr`과 `/cca`는 세부 항목을 나열하기 전에 **한 줄
판정**을 먼저 쓴다. 게이트 조건 목록은 근거이지 결론이 아니다. 읽는 사람이 "이대로
진행해도 되는가"를 먼저 알 수 있어야 한다.

| 판정 | 조건 |
|---|---|
| `통과` | 확인된 CRITICAL·MAJOR가 0이고 필수·활성 reviewer의 `UNKNOWN`이 0이다 |
| `조건부 통과` | 차단 사유는 없으나 MINOR 또는 범위 밖으로 기록한 MAJOR가 남아 있다 |
| `차단` | 확인된 CRITICAL·MAJOR가 남았거나, `UNKNOWN` 관점·미검토 hunk가 있거나, 필수 검증이 실패했다 |

- 판정 뒤에 한 줄 근거를 붙인다. 예: `차단 — CRITICAL 1건(인증 우회), src/auth.py:42`
- 판정은 게이트 결과에서 유도한다. 기억이나 인상으로 매기지 않는다. `/cr`은
  `review-gates.md` §5의 완료 Gate, `/cca`는 §6의 Commit Gate가 근거다.
- 원장을 쓰는 `/cr`에서 미판정 hunk가 있거나 `--allow-unledgered`를 사용했으면
  `통과`로 쓰지 않는다.
- `/ccr`·`/cfr`·`/cpr`은 commit 계획·PR 미리보기이므로 이 판정 대신 각 형식의
  `차단 사유`와 `실행 전 차단 요소`를 사용한다.

## 공통 변경 보존

Guard `begin`을 쓰는 커밋 명령(`/cc`, `/ccf`, `/cf`, `/cca`)은 `## 종료` 또는 마지막
요약에 `finish`·`abort` 결과의 `conservation`을 적는다.

- 통과: `변경 보존: 확인됨 (시작 시 변경 경로 N개)`
- 검사 불가: `변경 보존: 검사 불가 (사유)` — `available: false`일 때
- 유실: `변경 보존: 유실 감지` 아래에 `lost` 경로(최대 20개와 총수),
  `head_rewound`, recovery ref, 복원 명령. 이 경우 결과를 성공으로 쓰지 않는다

## `/ccr`

```text
## 상태
- 브랜치 / HEAD
- staged / unstaged / untracked 요약
- 진행 중 Git 작업
- 분석 범위와 사용자 인자

## 권장 Atomic Commit 계획

### 1. type(scope): 한글 제목
목적:
의존성:
포함 파일/hunk:
제외 파일/hunk:
분리 이유:
본문 초안:
검증:
위험:

### 2. ...

## 교차 검토
- 과도하게 합쳐진 변경
- 과도하게 분리될 위험
- staged/unstaged 충돌
- generated/lockfile/migration
- secret/debug/TODO
- 사용자 판단이 필요한 항목

## 요약
- 예상 커밋 수
- 권장 순서
- 실행 전 차단 요소
```

실제 Git 상태를 변경하지 않았음을 마지막에 명시한다.

## `/cr`

```text
## 상태
- 시작/종료 HEAD와 staging 불변 여부
- working tree 변경 요약
- 분석 범위와 사용자 인자

## 판정
- `통과` | `조건부 통과` | `차단` 중 하나와 한 줄 근거

## 심층 리뷰
- reviewer별 PASS/N/A/finding 수
- 조건부 reviewer별 trigger와 활성/N/A 근거
- reviewer 실행·fallback·UNKNOWN 수와 중복 통합 수
- hunk coverage: 전체/PASS/FINDING/N_A/미검토
- 격리 검증: `ISOLATED`·`SELF`·`UNVERIFIED` finding 수와 `REJECTED` 수.
  `ledger.py report`의 `verification`에서 가져온다. `SELF`·`UNVERIFIED`가 있으면
  그 이유도 적는다.
- 도달성: `이론`·`성립불가`로 기각한 수와 `확인불가`로 비차단 강등한 수.
  `review-execution.md` §3.6의 판정 결과다. 강등분은 심각도를 유지하므로
  미해결 MAJOR와 **별도 줄**로 적고 무엇을 확인하지 못했는지 밝힌다.
- 채택·기각한 finding과 근거
- 원장 커버리지 수치는 `ledger.py report`의 `coverage`에서 가져온다. 기억으로
  집계하지 않는다. `--format json`·`sarif` 산출물도 같은 출력에서 만든다.
- `ledger.py report`는 **Guard `finish` 이전에** 실행해 출력을 보관한다.
  `finish`는 lock을 해제하고 snapshot을 삭제하므로 그 뒤에 실행하면
  `owner_not_found`로 실패한다. `finish` 결과에는 커버리지 요약만 있고
  `findings`가 없어 JSON/SARIF를 만들 수 없다. 보고문 자체는 `finish`가 성공한
  뒤 이 보관된 출력으로 작성한다.
- hunk 판정값은 `PASS`·`FINDING`·`N_A`다. 원장은 `N/A`를 `ledger_invalid_verdict`로
  거부한다. reviewer 적용 여부를 뜻하는 산문의 `N/A`와 혼동하지 않는다.

## 수정 및 검증
- 자동 수정 내용과 남은 blocker
- 실행·생략·실패한 테스트/lint/type/build

## 종료
- snapshot 삭제/보존
- lock 해제
- Atomic Commit 계획·staging·commit·push를 하지 않았음
```

## `/cc`

각 생성 커밋:

```text
1. <short-hash> type(scope): 한글 제목
   - 목적
   - 파일 수 / +추가 / -삭제
   - 수행한 검증
```

마지막:

- 생성 커밋 수
- 시작 HEAD → 최종 HEAD
- 남은 변경
- snapshot 삭제 여부
- lock 해제 여부
- 생략/실패한 검증
- push하지 않았음

## `/cf`

```text
## 상태
- 브랜치 / 시작 HEAD → 최종 HEAD
- 대상 범위와 사용자 인자

## 생성 커밋
<short-hash> type(scope): 한글 제목
- 묶인 의도: feat ..., fix ..., docs ...
- 파일 수 / +추가 / -삭제

## 검증
- 수행한 검증 또는 "기본 모드로 프로젝트 검증 생략"
- commit hook 존중 / 우회 여부

## 종료
- 남은 변경과 clean 여부
- snapshot 삭제/보존 위치
- lock 해제 여부
- push하지 않았음
```

마지막에 반드시 다음을 명시한다.

- 이 커밋은 Atomic Commit이 아니며 여러 의도가 묶여 있다
- 공유 branch·release 히스토리에는 `/cc` 또는 `/cca`를 권장한다

차단 스캔에 걸려 중단했으면 `## 오류/중단` 형식을 따르고, 현재 index 상태와
`git restore --staged` 복구 방법을 함께 제시한다.

## `/cfr`

```text
## 상태
- 브랜치 / HEAD
- staged / unstaged / untracked 요약
- 대상 범위와 사용자 인자

## 예상 단일 커밋
type(scope): 한글 제목
대표 type 근거:
scope 근거:
대상 파일 / 예상 통계:
묶이는 의도:
메시지 초안:

## 차단 사유
- secret / 자격 파일 / 산출물 유입 / conflict marker / 진행 중 Git 작업
- 각 항목의 해결 방법

## 교차 검토
- `/cf`보다 `/cc`가 적합한 근거가 있는가
- Breaking Change·migration 위험
- `--scope` 축소 권장 여부

## 요약
- 권장 후속 명령 (`/cf`, `/cc`, `/ccr`)
- `--verify` 시 실행될 검증 명령 (식별만)
- lock 해제 여부
```

이 커밋이 Atomic Commit이 아니라는 점과 실제 Git 상태를 변경하지 않았음을
마지막에 명시한다.

## `/ccf`

`/cc` 형식을 그대로 따르고 다음을 추가한다.

```text
## 섞인 의도
- 파일 단위 분리 때문에 두 개 이상의 의도가 함께 들어간 커밋, 그 파일과 내용
- 없으면 "없음"

## 합쳐 stage한 파일
- staged·unstaged가 공존해 `git add -- <file>`로 합친 파일
- 없으면 "없음"
```

섞인 의도가 있으면 결과가 완전한 Atomic Commit이 아닐 수 있고, 필요하면 `/cc`로
hunk 단위 분리를 할 수 있음을 마지막에 명시한다.

## `/cca`

추가로 포함:

- reviewer별 CRITICAL/MAJOR/MINOR 수
- 실제 채택·기각한 finding과 근거
- 자동 수정한 내용
- targeted/full 검증 결과
- 품질 gate 결과
- Breaking Change 여부
- 회귀·배포·migration 주의사항
- hunk coverage: 전체/PASS/FINDING/N_A/미검토 수
- 격리 검증: `ISOLATED`·`SELF`·`UNVERIFIED` finding 수와 `REJECTED` 수.
  `SELF`·`UNVERIFIED`가 있으면 그 이유도 적는다.
- 도달성: `이론`·`성립불가` 기각 수와 `확인불가` 비차단 강등 수. 강등분은
  심각도를 유지하므로 미해결 MAJOR와 별도 줄로 적는다
- Architecture, Language/API, UX/A11y, Observability, Quality reviewer 결과
- 조건부 Data/Migration, Dependency/Supply Chain, Reliability/Recovery, Privacy/Governance, Requirements/Product 결과
- reviewer 실행·fallback·UNKNOWN 수와 finding fingerprint
- 제거된 동작·wrapper/proxy·cross-file 검증 결과

### 확장 모드 추가 항목

- `today`: 정확한 시간대·자정 경계·작성자 조건, commit 원장, net effect, 새 commit, 오늘 전체 통계
- `3days`: 정확한 시간대·3개 달력일 경계·작성자 조건, commit 원장, net effect, 새 commit, 전체 통계
- `weekly`: 주 시작·기간·작성자 조건, 날짜·domain별 집계, net effect, 반복 수정·미완료 위험, 새 commit
- `release`: 기준 ref, package, 분석 범위, 권장 Semantic Version/tag와 자동 증가 근거, channel, 릴리스 노트, 차단 요소, prepare/commit/local tag 여부
- `emergency`: incident ID·확인된 severity·증거·근본 원인·rollback/containment·최소 완화 범위·긴급 검증·관찰 지표·배포 전후 확인·후속 작업
- `learn`: 분석 refs·since/package·표본/제외 commit 수·프로필 경로 또는 preview·규칙별 확신도·반례·프로필 외 파일을 변경하지 않았음

## 오류/중단

절대로 성공처럼 보고하지 않는다.

필수:

- 중단 단계
- 원인
- 이미 생성된 커밋
- 현재 staged/unstaged 상태
- 보존된 snapshot 경로
- lock 해제 여부
- 안전한 복구 지침

민감정보는 마스킹한다.
