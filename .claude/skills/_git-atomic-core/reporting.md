# 결과 보고 형식

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

## 심층 리뷰
- reviewer별 PASS/N/A/finding 수
- 조건부 reviewer별 trigger와 활성/N/A 근거
- reviewer 실행·fallback·UNKNOWN 수와 중복 통합 수
- hunk coverage: 전체/PASS/FINDING/N/A/미검토
- 채택·기각한 finding과 근거

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

## `/cca`

추가로 포함:

- reviewer별 CRITICAL/MAJOR/MINOR 수
- 실제 채택·기각한 finding과 근거
- 자동 수정한 내용
- targeted/full 검증 결과
- 품질 gate 결과
- Breaking Change 여부
- 회귀·배포·migration 주의사항
- hunk coverage: 전체/PASS/FINDING/N/A/미검토 수
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
