# 품질 검증 보고서

## 완료한 자동 검증

- `/cr` 기본 read-only와 명시적 `--fix` opt-in 수정 계약 검증
- `/cpr` 완전 read-only PR 미리보기와 `/cp` 일반 push·PR 생성 경계 검증
- `main`/`master`에서 제안 branch와 실제 자동 branch 생성을 분리하고 Guard의 예상 branch 불변식 검증
- PR context의 merge-base·commit range·dirty·ahead commit 회귀 검증
- `/cr` frontmatter의 `--fix`와 `/cca --no-fix` 독립 정책 검증
- 기본 `/cr` 편집 도구 호출을 Skill 범위 PreToolUse Hook으로 실행 전 차단
- Live eval의 HEAD·index·working diff·status 불변 검증
- `/cr`·`/cca` today/3days/weekly 공통 기간 규칙과 명령 연결 검증
- `/cr release`·`emergency`·`learn`의 강제 read-only 계약과 `--fix` 편집 Hook 차단 검증
- `/cca release`의 SemVer·stable/rc/beta/alpha·package tag 자동 증가 계산기 회귀 검증
- `/cca release --prepare/--tag`, emergency diagnose/실행, learn preview/프로필 저장 경계 검증
- README 상단과 release 옵션 표의 `/cr` tag 시뮬레이션·`/cca` 실제 tag 생성 경계 검증
- README 명령 선택·빠른 시작·탐색·설치·사용·옵션 순서와 확장 모드 비교표 검증
- today·3days·weekly 월요일·weekly 일요일 고정 시각 경계 회귀 검증
- 기간 commit 불변, `/cr` Atomic 계획 금지, `/cca` working-only commit 경계 검증
- Python 파일 syntax compile
- Skill/Agent YAML frontmatter parser 검증
- `SKILL.md` 각각 500줄 미만 확인
- 필수 파일 존재 확인
- skeleton/TODO placeholder 검색
- 설치 → 재설치 backup → 제거 backup 통합 시험
- 공백이 포함된 경로에서 guard launcher 및 설치 시험
- guard 통합 테스트 6개
- CommitForge 브랜딩·버전·확장 모드 정적 검증
- 심층 리뷰 reference와 전문 reviewer 6종 연결 검증
- `/cr`의 기본 10개 리뷰와 Atomic 계획·staging·commit 금지 검증
- `/cca` 기본 11개와 조건부 전문 reviewer 5종 trigger 연결 검증
- 설치·제거 agent registry와 실제 파일 목록 일치 검증
- 모든 reviewer의 shell 실행 권한 부재 검증
- `/cr` HEAD·branch·staged diff 불변의 Guard 강제 검증
- 조건부 reviewer trigger golden fixture 검증
- finding 공통 schema와 reviewer fallback·UNKNOWN 정책 검증
- deterministic release metadata와 ZIP/TAR.GZ 재현성 검증
- GitHub Actions 검증 workflow 포함
- Ubuntu Python 3.9/3.13, macOS, Windows CI matrix와 SHA 고정 Action 검증
- `.gitattributes` LF 정책과 CI `PYTHONUTF8`로 운영체제별 metadata·한글 출력 일관성 검증
- JSON·SARIF report validator 및 baseline schema·만료 검증
- `/cr --base`, `--range`, PR 비교 모드 계약 검증
- 대형 diff shard/cross-file 집계 규칙 연결 검증
- snapshot inventory SHA-256 감사와 변조 차단 검증
- 실제 Claude Code 평가 scenario 계약 검증
- 실제 Claude Code CLI + Sonnet으로 Python mutable-default 회귀 기본 read-only `/cr` E2E 통과
- 실제 Claude Code CLI + Sonnet으로 clean working tree의 기본 read-only `/cr today` 기간 커밋 회귀 E2E 통과

### Guard 통합 테스트

1. 같은 worktree에서 두 번째 `/cc`·`/cr`·`/cca`·`/cpr`·`/cp` lock 차단
2. staged/unstaged Diff와 untracked archive snapshot 생성
3. repository fingerprint 변경 감지
4. 실패 시 snapshot 보존 + 소유 lock 해제
5. 성공 시 snapshot 삭제 + lock 해제
6. merge 등 진행 중 Git operation에서 시작 차단
7. 서로 다른 linked worktree의 독립 lock/snapshot
8. `/cr` working tree 수정 허용 + HEAD·branch·index 불변 확인
9. `/cr` index 변경 시 verify와 finish 모두 차단
10. snapshot 파일 변조 시 `audit-snapshot`과 `finish` 차단
11. `main`/`master` 시작 시 지정한 새 branch 하나만 허용하고 HEAD·source·index 불변 확인

### 확장 모드 검증

- `/cca today`, `3days`, `weekly`, `release`, `emergency`, `learn` 분기 존재
- `/cr today`, `3days`, `weekly`, `release`, `emergency`, `learn` read-only 분기 존재
- today는 최근 24시간, 3days는 최근 72시간, weekly는 최근 7일로 해석하지 않는 달력 경계 확인
- commit 원장·net effect·revert·교차 commit finding 귀속 규칙 확인
- 확장 모드 공통 규칙 파일 설치 대상 포함
- `learn`의 JSON·Markdown 프로필을 `/ccr`, `/cc`, `/cr`, `/cca`가 참조
- README·MANIFEST·VERSION의 CommitForge 브랜딩과 버전 일치

### 심층 리뷰 검증

- Line-by-line hunk 원장과 미검토 차단 규칙
- Removed behavior, cross-file, wrapper/proxy 프로토콜
- Architecture, Language/API, UX/A11y, Observability, Quality reviewer 설치 대상 포함
- Data/Migration, Dependency/Supply Chain, Reliability/Recovery, Privacy/Governance, Requirements/Product 조건부 reviewer 포함
- `/cr` Gate에서 staging plan 조건이 제거되고 HEAD/index 불변 조건이 적용되는지 확인
- 11개 언어·플랫폼 카탈로그 섹션 확인

## 선택적 실제 모델 평가

`evals/run_evals.py`는 격리된 임시 Git 저장소에 CommitForge를 설치하고 실제 Claude Code CLI로 기본 read-only `/cr`을 호출하는 opt-in 평가를 제공합니다. CI에서는 비용과 인증 의존성을 피하기 위해 scenario·trigger 계약만 검증합니다.

Claude Code 계정·권한·모델 변화가 결과에 영향을 줄 수 있으므로 live 결과는 고정적인 단위 테스트가 아니라 보조 품질 신호로 취급합니다. 중요한 저장소에서는 별도 worktree에서 수동 체크리스트도 함께 수행하십시오.

이번 릴리스에서는 `python mutable default regression`과 `today committed regression` 시나리오를 Sonnet으로 실행했습니다. 일반 working diff와 clean working tree의 오늘 커밋 모두에서 상태 공유 회귀를 탐지하고 HEAD·index 불변 조건을 지키는 것을 확인했습니다. destructive migration 시나리오는 계약 검증까지만 수행했습니다.
