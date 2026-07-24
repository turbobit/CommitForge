# Shared Git Atomic Core

이 디렉터리는 CommitForge의 `/cc`, `/ccr`, `/cr`, `/cca`가 필요할 때 읽는 공통 지침과 안전 guard를 포함합니다.

`SKILL.md`가 없으므로 독립 slash command로 등록되지 않습니다.

- `atomic-commit-rules.md`: 분리·그룹화·순서
- `staging-strategy.md`: hunk/index 구성
- `commit-message-guide.md`: 한글 메시지
- `safety-and-concurrency.md`: 잠금·스냅샷·금지 명령
- `review-gates.md`: `/cr`·`/cca` 품질 gate
- `extended-modes.md`: `/cca today|3days|weekly|release|emergency|learn` 분기와 프로젝트 프로필
- `period-review-modes.md`: `/cr`·`/cca`의 강화된 today·3days·weekly 범위·원장·net-effect 리뷰
- `deep-review-protocol.md`: line-by-line, removed behavior, cross-file, wrapper/proxy, UX·observability 검토
- `language-api-pitfalls.md`: 언어·프레임워크별 타입·lifecycle·API 함정
- `conditional-reviewers.md`: 데이터·공급망·복구·privacy·요구사항 reviewer trigger
- `review-execution.md`: 실행 budget, fallback, finding schema와 중복 제거
- `review-policy.md`: `.commitforge/review.yml` 프로젝트별 reviewer·출력·대형 diff 정책
- `reporting-formats.md`: human·JSON·SARIF 보고서 계약과 검증
- `baseline-and-suppressions.md`: 기한·소유자가 있는 제한적 finding 기준선
- `large-diff-review.md`: 대형 변경의 도메인 분할과 cross-file 집계
- `validation-strategy.md`: 테스트/빌드
- `project-profiles.md`: 언어·프레임워크
- `reporting.md`: 결과 형식
- `recovery.md`: 장애 복구
- `examples.md`: 사례
- `scripts/guard.py`: worktree별 lock, snapshot, 무결성 감사, fingerprint, cleanup
- `scripts/guard.sh`: macOS/Linux/WSL/Git Bash용 Python 3 launcher
- `scripts/reviewer_triggers.py`: 조건부 reviewer 최소 trigger 집합 계산
- `scripts/report_validator.py`: JSON·SARIF 결과 계약 검증
- `scripts/baseline.py`: review baseline 구조·만료 검증
- `scripts/period_range.py`: today·3days·weekly 로컬 달력 경계 계산
