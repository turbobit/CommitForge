# Changelog

## 1.14.0 — 2026-07-26

- `/cca` 최초 리뷰와 수정 후 재리뷰를 read-only Agent Team core 3명과 조건부
  specialist로 실행하고, Team 종료 후에만 lead가 수정·검증·staging·commit
- 수정할 때마다 이전 결과를 무효화하고 fingerprint·trigger를 갱신한 새 Team으로
  전체 diff를 재리뷰하는 `--iterations` 반복 계약 유지
- `/cca` 반복 중 “종료 예약”을 받으면 현재 안전 경계에서 teammate를 회수하고
  Guard를 `abort`해 lock을 해제하며 snapshot을 보존하는 graceful stop 추가
- 최초 리뷰와 매 재리뷰 시작 시 현재 반복 횟수와 graceful stop 사용법 안내
- Windows에서 임시 경로의 표기·대소문자 정규화 차이로 lifecycle hook 보존 테스트가
  잘못 실패하던 문제 수정
- GitHub Actions의 중복 Ubuntu 검증 job과 중복 live eval step을 제거하고 기준
  검증 통과 후에만 세 portability job을 실행하며, 같은 ref의 이전 run은 자동 취소
- Dependabot GitHub Actions 갱신을 하나의 주간 그룹·PR로 제한해 중복 update
  workflow와 PR 검증 run을 축소

## 1.13.0 — 2026-07-26

- 설치 시 Claude Code `SessionStart`, `Stop`, `StopFailure`, `SessionEnd` lifecycle
  hook을 사용자 설정에 병합해 Guard owner를 실제 Claude `session_id`와 결합
- 정상 응답 종료, API 실패, `/clear`, `/exit`, `/resume`, 로그아웃에서 종료 세션과
  owner가 정확히 일치하는 현재 worktree 잠금만 자동 해제하고 Diff snapshot은 보존
- 수동·자동 `/compact`에서는 잠금을 유지하고 같은 session ID를 다시 바인딩해 진행 중
  리뷰·검증의 동시 실행 보호가 끊기지 않도록 처리
- 다른 세션의 잠금, 다른 저장소, 비정상 lock 내용은 자동 종료 정리가 건드리지 않는
  fail-closed `guard.py session-end` 경로와 회귀 테스트 추가
- 단기 Guard 프로세스 PID를 활성 세션으로 오인하지 않도록 owner 필드를
  `guard_pid`에서 의미가 명확한 `begin_pid`로 변경
- 프로젝트 설치는 `.claude/settings.local.json`, 전역 설치는
  `~/.claude/settings.json`을 사용하며 기존 사용자 설정·hook을 보존하고 제거 시
  CommitForge lifecycle hook만 제거
- macOS·Linux·Windows에서 셸이 만든 임의 세션 문자열 대신 설치 hook이 전달한
  `COMMITFORGE_SESSION_ID`만 사용하도록 모든 실행 계약과 복구 문서 갱신

## 1.12.1 — 2026-07-26

- `/cr`의 `PreToolUse` Write/Edit 훅이 셸에 존재하지 않는
  `${CLAUDE_SKILL_DIR}` 환경변수에 의존하지 않도록 설치 시 현재 Python과
  `cr_edit_gate.py`의 절대경로를 고정
- 모든 Skill frontmatter의 Guard·검토 보조 스크립트 권한 패턴도 설치 시 core
  절대경로로 고정하고, 모델용 경로·세션 표기는 셸 환경변수와 구분되는 명시적
  placeholder로 변경
- 검증기가 Skill frontmatter뿐 아니라 모든 Skill Markdown의 `${...}` 런타임
  변수형 placeholder를 거부하도록 보강해 같은 종류의 hook·permission·명령
  경로 회귀를 패키징 전에 차단
- 공백·작은따옴표가 포함된 설치 경로와 Windows 명령줄 quoting을 처리하고,
  `CLAUDE_SKILL_DIR`가 없는 환경에서 설치된 훅이 실제로 fail-closed 실행되는
  회귀 테스트 추가
- 프로젝트 검증 명령은 광범위하게 자동 승인하지 않는 안전 경계를 유지하되,
  실행 전 “allowed-tools 밖이라 거부될 수 있음” 같은 추측성 문구를 금지하고
  실제 permission 요청·거절·환경 실패가 발생했을 때만 정확히 보고
- 모든 명령의 성공·실패·중단 결과에 승인 대기, reviewer, 검증, Guard 정리를
  포함한 전체 소요 시간을 분 단위로 표시하고 JSON review report에도
  `timing.elapsed_minutes` 추가

## 1.12.0 — 2026-07-25

- `/ccr`, `/cc`, `/cr`, `/cca`, `/cpr`, `/cp`에 현재 Git worktree의
  CommitForge advisory lock만 명시적으로 해제하는 `clean` 조기 종료 명령 추가
- `clean`은 다른 저장소·worktree, working tree/index/commit과 보존된 Diff
  snapshot을 건드리지 않으며 잠금 없음 재실행은 성공한 no-op 처리
- `/cr` source-read-only, `/ccr`, `/cpr`에 환경·변경 규모·domain·고위험
  trigger 기반 선택적·적응형 Agent Team 모드와 `--team`·`--no-team` 추가
- 읽기 전용 대상은 Agent Teams 환경 활성 시 Team-first를 기본으로 변경하고,
  모든 대상 명령을 core 3명으로 단순화. 파일 2개·80 changed lines 이하의
  저위험 단일 domain만 Team 생략
- 대형 변경을 파일 수로 균등 분할하지 않고 package/domain/runtime shard와
  core 3명·조건부 specialist 관점을 겹쳐 배정하며 lead aggregator가 contract와
  hunk coverage 통합
- 대형 diff 시작 공지에 실제 초과 값·적용 threshold와 core 3명+specialist
  구조를 분리해 표시하고, 계산하지 않은 hunk 수나 임의 threshold 보고를 금지
- 문서 전용이 아닌 행위 변경은 Testing/Independent Verification을 필수
  specialist로 활성화하고 Reliability, UX, Migration, Requirements, Release,
  Domain/Framework는 의미 trigger로 조건부 추가
- `/cr --fix`, `/cc`, `/cca`, `/cp`는 기존 custom subagent + lead 단독 변경
  구조를 유지하고 Team 환경이 꺼졌거나 coordination 실패 시 subagent fallback
- Agent Team을 명령별 core 역할과 조건부 specialist로 구성하고 shared task와
  peer messaging을 통해 cross-file contract와 finding을 교차검증하도록 실행 계약 보강
- OWASP Top 10:2025·ASVS 5.0, WCAG 2.2, NIST SSDF와 OpenTelemetry 최신 관점을
  반영해 공급망·artifact integrity/provenance, exceptional conditions,
  compatibility, observability/alerting, 접근성·migration/rollback 검토 강화
- Agent Teams 환경변수는 정확히 `1`일 때만 활성으로 판정하며 CommitForge가
  사용자 환경을 설정·변경하지 않는다는 경계 추가
- 모든 명령 본문 첫 섹션에 `${CLAUDE_SKILL_DIR}` 해석 규칙과 `CF_CORE` 확정
  Preflight를 추가해 skills 루트로 잘못 치환된 경로가 만드는 실행 실패 차단
- Guard 실행 자체가 실패한 경우(exit code 126·127, `command not found`,
  Python 미탐지)도 fail-closed 사유로 명시해 Guard 생략 후 진행을 금지
- Guard owner에 `hostname`을 기록하고 `begin`·`status` 결과에 `stale_candidate`,
  `lock_owner_same_host`, `lock_owner_same_session`, `stale_after_seconds` 보고
- 같은 호스트의 오래된 잠금이나 동일 세션 재진입만 회수하는
  `begin --reclaim-stale [--stale-after <초>]` 추가. 기존 owner의 snapshot은 보존하고
  다른 호스트·신선한 잠금·비정상 잠금 내용은 `reclaim_refused_reason`으로 거부
- 잠금 충돌 결과의 `recovery`에 `clean_hint`, `clean_argv`, `reclaim_hint`를 추가해
  복구 경로를 명시
- Git 자체 lock(`index.lock` 등) 차단을 `reason=git_external_lock`으로 분리하고 각
  lock의 `size`, `age_seconds`, `writer_pids`, `stale_candidate` 진단 보고. 크기 0,
  5분 경과, 쓰기 프로세스 없음을 모두 만족할 때만 stale 후보로 표시하며 읽기 전용
  핸들은 사용 중으로 보지 않음
- 명시적 `clean`은 알려진 Git lock(`index.lock`, `HEAD.lock`,
  `packed-refs.lock`, `config.lock`)이 5분 이상·0바이트·writer 없음·진행 중 Git
  operation 없음·검사 중 identity 불변을 모두 만족할 때만 제거
- macOS `lsof` 접근 모드, Linux `/proc` fd flags, Windows Win32 share-mode로
  writer를 판별하고 Finder·Spotlight·Explorer·인덱서의 읽기 전용 핸들은 제외.
  판별 불능은 자동 제거하지 않는 fail-closed 상태로 처리
- `clean`이 제거한 Git lock과 안전 조건 미충족으로 남긴 Git lock을 각각
  `git_locks_removed`, `git_lock_cleanup`, `git_locks`로 보고
- Guard `begin` 실패 후 `git status`·`git diff`·`git log` 또는 `git -C <경로>`로
  우회해 작업을 이어가는 것을 모든 명령에서 명시적으로 금지
- `verify-review`·`finish`가 session과 일치하는 현재 worktree owner token과
  유일한 snapshot을 자동 해석하도록 보강해 장시간 리뷰 후 인자 유실·basename
  오사용·존재하지 않는 `snapshot-path` 추측을 제거. 명시적 오입력은 계속 거부

## 1.10.1 — 2026-07-25

- Guard 잠금 충돌 결과에 `project_root`, `git_dir`, `lock_scope`, owner를 구조화해 다른 저장소의 잠금과 구분
- 잠금 범위가 실제 worktree Git directory이며 같은 부모 아래 독립 저장소는 서로 차단하지 않는다는 계약 명시
- 독립 저장소 동시 실행과 같은 저장소 하위 폴더 중복 차단 회귀 테스트 추가
- 중간 종료로 남은 stale lock을 현재 세션에서도 확인 후 안전하게 `abort`할 수 있도록 복구 지침 보강
- `abort --session --token`이 일치하는 owner snapshot을 자동 선택하도록 복구 API 개선
- 잠금 충돌과 status 결과에 `lock_owner_snapshots`와 구조화된 recovery 정보 추가
- 실제 `abort` 성공 결과 전에는 잠금 해제를 단정하거나 `begin`을 재시도하지 않는 `/cr` 계약 추가
- Guard가 `lock_age_seconds`와 실행 가능한 `recovery.abort_argv`를 반환해 시간대 오산·깨진 명령 방지
- `/cr` Guard begin 실패 후 변경 스캔·reviewer·테스트를 실행하지 않는 fail-closed 시작 Gate 강화
- `/cpr`, `/cp`를 포함하도록 Guard 중복 실행 오류 메시지 갱신

## 1.10.0 — 2026-07-24

- `/cpr` read-only Pull Request 미리보기 명령 추가
- `/cp` 심층 검토·검증 후 일반 branch push와 GitHub Pull Request 생성 명령 추가
- 동일 head의 열린 PR 중복 생성, non-fast-forward, stale tracking ref, dirty tree와 blocking finding 차단
- 현재가 `main`/`master`이면 변경 의미에 맞는 충돌 없는 branch 이름을 `/cpr`에서 제안하고 `/cp`에서 실제 생성
- 자동 분기 시 예상 branch 변경만 허용하고 HEAD commit·source·index 불변을 Guard로 검증
- PR 옵션·안전 경계·설치·수동 검증·파일 구조 문서 보강

## 1.9.2 — 2026-07-24

- README 첫 화면을 명령 선택·release 안전 경계·30초 시작 중심으로 재배치
- 주요 문서 섹션으로 바로 이동할 수 있는 탐색 링크 추가
- `/cr` 읽기 전용 분석과 `/cca` 실행형 확장 모드를 한 표로 비교
- 설치·명령 사용법·옵션·Atomic 메시지·권한 섹션의 제목과 설명 순서 정돈
- remote push 금지와 `/cca release --prepare --tag`의 로컬 tag 예외를 안전 섹션에서 재강조
- README 핵심 정보 순서와 시인성 요소를 정적 테스트로 고정

## 1.9.1 — 2026-07-24

- README 상단에 release tag 실행 경계를 눈에 띄는 안내로 추가
- `/cca release --prepare --tag`만 로컬 annotated tag를 실제 생성한다고 명시
- `/cr release --prepare --tag`는 예상 version/CHANGELOG·commit·tag를 읽기 전용으로 시뮬레이션한다고 명시
- 두 흐름 모두 remote tag push, GitHub Release, publish, deploy를 수행하지 않는 경계 재강조

## 1.9.0 — 2026-07-24

- `/cr release`, `/cr emergency`, `/cr learn` 읽기 전용 분석 모드 추가
- 세 `/cr` 확장 모드에서 `--fix`가 있어도 Edit·Write Hook이 차단되도록 실행 경계 강화
- `/cca release`에 `--target`, `--bump`, `--channel`, `--package`, `--tag-prefix`, `--from`, `--dry-run`, `--prepare`, `--tag` 계약 추가
- 기존 tag를 기준으로 stable/rc/beta/alpha와 monorepo package tag 번호를 결정론적으로 자동 증가하는 계산기 추가
- `/cca release --prepare --tag`에서만 검증된 최종 HEAD에 로컬 annotated tag를 생성하고 push·publish·deploy는 분리
- emergency 모드에 incident·severity·diagnose·rollback-first·base·scope 기반 진단, 완화, 최소 hotfix, 관찰·복구 절차 추가
- learn 모드에 preview·since·branches·exclude-bots·package 범위와 근거·반례·확신도를 가진 JSON/Markdown 프로필 추가
- README, 설치 안내, 수동 시험 체크리스트와 품질 보고서에 실행형 `/cca`와 읽기 전용 `/cr`의 차이를 보강

## 1.8.0 — 2026-07-24

- `/cr 3days`, `/cca 3days` 최근 3개 달력일 리뷰·커밋 모드 추가
- `3days`를 선택 시간대의 이틀 전 00:00부터 현재까지로 정의하고 rolling 72시간과 구분
- 기간 경계 계산기와 고정 시각 회귀 테스트에 `3days` 추가
- reviewer 기본 동시 실행을 6개로 확대하고 고위험·대형 diff는 환경 상한 안에서 최대 8개까지 사용
- rate-limit, agent 시작 실패, 반복 timeout 발생 시 후속 batch를 3~4개로 자동 축소
- README, 설치 안내, 수동 체크리스트와 품질 보고서에 새 기간 모드와 적응형 병렬 정책 반영

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
