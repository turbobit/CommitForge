# Changelog

## 1.7.1 — 2026-07-24

- README 옵션 표의 `|` 구분자가 열로 잘못 해석되는 Markdown 렌더링 오류 수정
- 공통 리뷰, today·weekly 기간, `/cca` 확장 모드 옵션을 적용 범위별로 재구성
- `--output` 보고서 생성 시점과 저장소 내부 출력의 미커밋 처리 명시
- 빠른 명령 선택표, 재설치 기반 업그레이드 절차, 기간 옵션 기본값과 예시 추가
- 기본 `/cr`의 작업 트리 불변 검증 범위와 Permission Hook 설명 최신화
- README 파일 구조에 `/cr` Skill과 `cr_edit_gate.py` 누락 보완

## 1.7.0 — 2026-07-24

- `/cr`의 기본 동작을 소스 수정 없는 read-only 리뷰로 변경
- 현재 working hunk의 확정적·국소 문제 수정은 `--fix`를 명시한 경우에만 허용
- `/cr today`, `weekly`, `--base`, `--range`, `pr`도 같은 opt-in 수정 정책 적용
- committed range finding만으로 corrective working change를 자동 생성하지 않는 경계 강화
- Skill 범위 PreToolUse Hook이 기본 `/cr`의 Edit·Write·NotebookEdit 호출을 실행 전에 차단
- `/cca`는 기존 기본 수정 정책과 `--no-fix` 옵션 유지
- Live eval에서 별도 `--no-fix` 없이 `/cr`의 HEAD·index·working tree 불변 검증

## 1.6.0 — 2026-07-24

- `/cr today`, `/cr weekly` 기간 심층 리뷰 모드 추가
- `/cca today`를 커밋 원장·net effect·revert·후속 수정·교차 커밋 finding 귀속으로 강화
- `/cca weekly`에 날짜·domain·작성자 집계와 반복 수정·미완료 위험 분석 추가
- today는 로컬 달력 자정, weekly는 기본 월요일 자정으로 명확히 정의
- `--all-authors`, `--week-start monday|sunday`, `--timezone <IANA|±HH:MM>` 기간 옵션 추가
- 기존 기간 commit은 불변으로 유지하고 `/cr`은 Atomic 계획 없이, `/cca`는 미커밋 변경만 commit하도록 경계 강화
- Python 3.9 호환 기간 경계 계산기와 고정 시각 회귀 테스트 추가
- clean working tree의 오늘 커밋을 검토하는 실제 Claude Code E2E 평가 추가

## 1.5.0 — 2026-07-23

- `/cr --base`, `--range`, `pr`로 branch·commit range·GitHub PR 심층 리뷰 지원
- `.commitforge/review.yml` 기반 프로젝트별 reviewer·대형 diff·출력·baseline 정책 추가
- `commitforge-review/v1` JSON과 SARIF 2.1.0 보고서 및 계약 validator 추가
- 소유자·사유·만료일·fingerprint 기반 finding baseline과 고위험 억제 금지 규칙 추가
- 대형 diff의 domain shard, cross-file contract 집계, 문맥 부족 `UNKNOWN` 차단 추가
- snapshot 파일별 크기·SHA-256 inventory와 삭제 전 무결성 감사 추가
- 실제 Claude Code `/cr --no-fix` opt-in 평가 harness와 회귀 scenario 추가
- Ubuntu Python 3.9/3.13, macOS, Windows CI matrix 추가
- LF checkout과 UTF-8 Python 출력을 고정해 Windows 검증의 재현성 확보
- GitHub Actions를 전체 commit SHA로 고정하고 Dependabot 업데이트 설정 추가

## 1.4.0 — 2026-07-23

- Guard `verify-review`와 `finish --review-only`로 `/cr`의 HEAD·branch·staged diff 불변 조건을 프로그램 수준에서 강제
- 조건부 reviewer 최소 활성 집합을 계산하는 보수적 trigger 도구와 golden fixture 평가 추가
- finding stable ID, fingerprint, severity, status, evidence, blocking 공통 schema 추가
- reviewer 최대 병렬 수, 필수 관점, fallback과 `UNKNOWN` 차단 정책 추가
- Node.js 24 기반 GitHub Actions에서 metadata·test·syntax·checksum·installer를 자동 검증
- `release.py`로 manifest·checksum 검증과 재현 가능한 ZIP/TAR.GZ 생성 지원

## 1.3.0 — 2026-07-23

- `/cr`에서 Atomic Commit 전용 Git reviewer와 staging plan Gate를 제거해 순수 review-only 경계 보장
- `/cr` 종료 Gate에 HEAD·staged diff 불변과 Commit 계획·메시지·staging 금지 조건 추가
- Testing reviewer가 `review-only` 모드에서 Atomic Commit 배치 제안을 생략하도록 분기
- Data/Migration, Dependency/Supply Chain, Reliability/Recovery 전문 reviewer 추가
- Privacy/Governance, Requirements/Product 전문 reviewer를 명시적 trigger 기반으로 추가
- 조건부 reviewer 활성화·N/A 근거·수정 후 trigger 재평가 규칙 추가

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
