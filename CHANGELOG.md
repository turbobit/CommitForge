# Changelog

## 1.2.0 — 2026-07-23

- 모든 diff hunk를 PASS/FINDING/N/A로 추적하는 엄격한 line-by-line 원장 추가
- 제거된 동작과 cross-file contract 회귀 검토 강화
- wrapper/proxy/adapter의 인자·반환·오류·취소·context 의미 보존 검사
- Architecture, Language/API, UX/Accessibility, Observability, Quality 전문 reviewer 추가
- 기존 구현 재사용·중복·복잡도·유지보수성 검토 추가
- JavaScript/TypeScript, React/Next.js, Dart/Flutter, Python, Go, Rust, JVM, Swift, C/C++, SQL, Infrastructure API 함정 카탈로그 추가
- 미검토 hunk가 있으면 commit을 차단하는 심층 Coverage Gate 추가
- `/cr` 심층 코드 리뷰 명령 추가: 리뷰·국소 수정·전면 재리뷰·검증만 수행하고 Atomic Commit 계획·staging·commit·push는 제외
- reviewer shell 권한 제거와 설치·제거 registry 일치 검증 강화

## 1.1.0 — 2026-07-23

- 프로젝트 이름과 사용자 문서를 CommitForge로 통일
- `/cca today`로 오늘의 기존 commit과 미커밋 변경 통합 분석
- `/cca release`로 tag 기준 릴리스 검토·버전 제안·릴리스 노트 초안 지원
- `/cca emergency`로 최소 범위 hotfix 리뷰·검증·commit 지원
- `/cca learn`으로 최근 history 기반 `.commitforge/profile.md` 생성
- `/ccr`, `/cc`, `/cca`에서 CommitForge 프로젝트 프로필 자동 반영
- 설치·제거 백업 디렉터리를 CommitForge 명칭으로 변경

## 1.0.0 — 2026-07-23

- 권장 Claude Code Skills 형식으로 `/cc`, `/ccr`, `/cca` 제공
- 한글 Conventional Commit 제목·상세 본문 규칙
- 파일 및 hunk 단위 Atomic Commit 분리
- commit dependency graph와 순차 실행
- worktree별 advisory lock
- staged/unstaged binary diff snapshot
- untracked manifest/hash/archive
- repository fingerprint를 통한 TOCTOU 감지
- 실패 시 snapshot 보존과 소유 lock만 해제
- Git, correctness, security, performance, testing 전문 subagent 5종
- `/cca` review-fix-review 검증 loop
- 언어·프레임워크별 기본 프로필
- macOS/Linux/Windows 설치 및 제거 스크립트
- guard 통합 테스트와 package verifier
