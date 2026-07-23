# Shared Git Atomic Core

이 디렉터리는 CommitForge의 `/cc`, `/ccr`, `/cr`, `/cca`가 필요할 때 읽는 공통 지침과 안전 guard를 포함합니다.

`SKILL.md`가 없으므로 독립 slash command로 등록되지 않습니다.

- `atomic-commit-rules.md`: 분리·그룹화·순서
- `staging-strategy.md`: hunk/index 구성
- `commit-message-guide.md`: 한글 메시지
- `safety-and-concurrency.md`: 잠금·스냅샷·금지 명령
- `review-gates.md`: `/cr`·`/cca` 품질 gate
- `extended-modes.md`: `/cca today|release|emergency|learn` 동작과 프로젝트 프로필
- `deep-review-protocol.md`: line-by-line, removed behavior, cross-file, wrapper/proxy, UX·observability 검토
- `language-api-pitfalls.md`: 언어·프레임워크별 타입·lifecycle·API 함정
- `conditional-reviewers.md`: 데이터·공급망·복구·privacy·요구사항 reviewer trigger
- `review-execution.md`: 실행 budget, fallback, finding schema와 중복 제거
- `validation-strategy.md`: 테스트/빌드
- `project-profiles.md`: 언어·프레임워크
- `reporting.md`: 결과 형식
- `recovery.md`: 장애 복구
- `examples.md`: 사례
- `scripts/guard.py`: worktree별 lock, snapshot, fingerprint, cleanup
- `scripts/guard.sh`: macOS/Linux/WSL/Git Bash용 Python 3 launcher
- `scripts/reviewer_triggers.py`: 조건부 reviewer 최소 trigger 집합 계산
