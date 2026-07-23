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
- JSON·SARIF report validator 및 baseline schema·만료 검증
- `/cr --base`, `--range`, PR 비교 모드 계약 검증
- 대형 diff shard/cross-file 집계 규칙 연결 검증
- snapshot inventory SHA-256 감사와 변조 차단 검증
- 실제 Claude Code 평가 scenario 계약 검증
- 실제 Claude Code CLI + Sonnet으로 Python mutable-default 회귀 `/cr --no-fix` E2E 통과

### Guard 통합 테스트

1. 같은 worktree에서 두 번째 `/cc`·`/cr`·`/cca` lock 차단
2. staged/unstaged Diff와 untracked archive snapshot 생성
3. repository fingerprint 변경 감지
4. 실패 시 snapshot 보존 + 소유 lock 해제
5. 성공 시 snapshot 삭제 + lock 해제
6. merge 등 진행 중 Git operation에서 시작 차단
7. 서로 다른 linked worktree의 독립 lock/snapshot
8. `/cr` working tree 수정 허용 + HEAD·branch·index 불변 확인
9. `/cr` index 변경 시 verify와 finish 모두 차단
10. snapshot 파일 변조 시 `audit-snapshot`과 `finish` 차단

### 확장 모드 검증

- `/cca today`, `release`, `emergency`, `learn` 분기 존재
- 확장 모드 공통 규칙 파일 설치 대상 포함
- `learn` 프로필을 `/ccr`, `/cc`, `/cr`, `/cca`가 참조
- README·MANIFEST·VERSION의 CommitForge 브랜딩과 버전 일치

### 심층 리뷰 검증

- Line-by-line hunk 원장과 미검토 차단 규칙
- Removed behavior, cross-file, wrapper/proxy 프로토콜
- Architecture, Language/API, UX/A11y, Observability, Quality reviewer 설치 대상 포함
- Data/Migration, Dependency/Supply Chain, Reliability/Recovery, Privacy/Governance, Requirements/Product 조건부 reviewer 포함
- `/cr` Gate에서 staging plan 조건이 제거되고 HEAD/index 불변 조건이 적용되는지 확인
- 11개 언어·플랫폼 카탈로그 섹션 확인

## 선택적 실제 모델 평가

`evals/run_evals.py`는 격리된 임시 Git 저장소에 CommitForge를 설치하고 실제 Claude Code CLI로 `/cr --no-fix`를 호출하는 opt-in 평가를 제공합니다. CI에서는 비용과 인증 의존성을 피하기 위해 scenario·trigger 계약만 검증합니다.

Claude Code 계정·권한·모델 변화가 결과에 영향을 줄 수 있으므로 live 결과는 고정적인 단위 테스트가 아니라 보조 품질 신호로 취급합니다. 중요한 저장소에서는 별도 worktree에서 수동 체크리스트도 함께 수행하십시오.

이번 릴리스에서는 `python mutable default regression` 시나리오를 Sonnet으로 실행해 기대한 상태 공유 회귀를 탐지하고 HEAD·index 불변 조건을 지키는 것을 확인했습니다. destructive migration 시나리오는 계약 검증까지만 수행했습니다.
