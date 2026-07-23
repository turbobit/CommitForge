# Changelog

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
