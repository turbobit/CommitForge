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
