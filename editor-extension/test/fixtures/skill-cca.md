---
name: cca
description: CommitForge의 최고 강도 Git 파이프라인이다. 모든 diff hunk와 제거 동작을 검토하고 정확성·보안·성능·architecture·언어 API·UX·접근성·observability·품질을 다중 reviewer로 검증한 뒤 안전하게 보완·테스트하여 한글 Atomic Commit을 생성한다. today/3days/weekly/release/emergency/learn 확장 모드도 제공하며 사용자가 직접 /cca로 요청할 때만 실행한다.
argument-hint: "[clean|today|3days|weekly|release|emergency|learn] [추가 맥락] [--team|--no-team] [--target <semver>] [--bump auto|major|minor|patch] [--channel stable|rc|beta|alpha] [--package <name>] [--tag-prefix <prefix>] [--from <ref>] [--prepare] [--tag] [--dry-run] [--incident <id>] [--severity sev1|sev2|sev3|sev4] [--diagnose] [--rollback-first] [--base <ref>] [--preview] [--since <ref>] [--branches <refs>] [--exclude-bots] [--commits 20-500] [--all-authors] [--week-start monday|sunday] [--timezone <IANA|±HH:MM>] [--scope <경로...>] [--format human|json|sarif] [--output <경로>] [--no-fix] [--no-verify] [--strict] [--iterations 1-5] [--keep-snapshot]"
---
본문
