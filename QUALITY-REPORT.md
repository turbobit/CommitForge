# 품질 검증 보고서

## 완료한 자동 검증

- Python 파일 syntax compile
- Skill/Agent YAML frontmatter parser 검증
- `SKILL.md` 각각 500줄 미만 확인
- 필수 파일 존재 확인
- skeleton/TODO placeholder 검색
- 설치 → 재설치 backup → 제거 backup 통합 시험
- 공백이 포함된 경로에서 guard launcher 및 설치 시험
- guard 통합 테스트 3개
- CommitForge 브랜딩·버전·확장 모드 정적 검증
- 심층 리뷰 reference와 전문 reviewer 6종 연결 검증
- `/cr`의 11개 관점 리뷰와 Atomic 계획·staging·commit 금지 검증
- 설치·제거 agent registry와 실제 파일 목록 일치 검증
- 모든 reviewer의 shell 실행 권한 부재 검증

### Guard 통합 테스트

1. 같은 worktree에서 두 번째 `/cc`·`/cr`·`/cca` lock 차단
2. staged/unstaged Diff와 untracked archive snapshot 생성
3. repository fingerprint 변경 감지
4. 실패 시 snapshot 보존 + 소유 lock 해제
5. 성공 시 snapshot 삭제 + lock 해제
6. merge 등 진행 중 Git operation에서 시작 차단
7. 서로 다른 linked worktree의 독립 lock/snapshot

### 확장 모드 검증

- `/cca today`, `release`, `emergency`, `learn` 분기 존재
- 확장 모드 공통 규칙 파일 설치 대상 포함
- `learn` 프로필을 `/ccr`, `/cc`, `/cr`, `/cca`가 참조
- README·MANIFEST·VERSION의 CommitForge 브랜딩과 버전 일치

### 심층 리뷰 검증

- Line-by-line hunk 원장과 미검토 차단 규칙
- Removed behavior, cross-file, wrapper/proxy 프로토콜
- Architecture, Language/API, UX/A11y, Observability, Quality reviewer 설치 대상 포함
- 11개 언어·플랫폼 카탈로그 섹션 확인

## 검증하지 못한 항목

이 패키지 생성 환경에는 실제 Claude Code CLI 세션이 연결되어 있지 않아 `/cc`, `/ccr`, `/cr`, `/cca`를 Claude Code UI에서 end-to-end 호출하는 시험은 수행하지 못했습니다.

대신 현재 공식 Skills/Subagent frontmatter 형식에 맞춰 작성하고, YAML과 로컬 Git guard/installer 동작을 검증했습니다. 설치 후 작은 테스트 저장소 또는 별도 worktree에서 `MANUAL-TEST-CHECKLIST.md` 순서로 최초 시험하는 것을 권장합니다.
