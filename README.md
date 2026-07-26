# CommitForge

> Atomic Git Assistant for Claude Code

CommitForge는 Claude Code에서 **코드 리뷰 → 안전한 수정 → 검증 → Atomic Commit → Pull Request**를 일관된 규칙으로 실행하는 Skills 패키지입니다. 커밋과 PR 제목·본문은 기본적으로 한국어를 사용합니다.

## 한눈에 보기

| 명령 | 핵심 역할 | 소스 수정 | Git 변경 |
|---|---|---:|---:|
| `/ccr` | Atomic Commit 계획·순서·메시지 초안 | 안 함 | 안 함 |
| `/cc` | 현재 변경을 의미 단위별로 순차 commit | 안 함 | staging·commit |
| `/cr` | line-by-line 심층 코드 리뷰 | 기본 안 함, 일반 모드의 `--fix`만 허용 | 안 함 |
| `/cca` | 리뷰·국소 수정·검증·Atomic Commit 전체 실행 | 필요 시 | staging·commit |
| `/cpr` | committed branch의 PR 리뷰·제목·본문 미리보기 | 안 함 | 안 함 |
| `/cp` | PR gate 통과 후 branch push·GitHub PR 생성 | 안 함 | branch 생성 가능·일반 push·PR 생성 |

### 무엇을 실행해야 하나요?

| 원하는 결과 | 명령 |
|---|---|
| 계획만 먼저 확인 | `/ccr` |
| 변경된 소스를 건드리지 않고 commit | `/cc` |
| 현재 변경·branch·PR을 읽기 전용으로 심층 리뷰 | `/cr` |
| 리뷰에서 확인한 현재 문제만 고치고 commit하지 않음 | `/cr --fix` |
| 리뷰부터 수정·검증·commit까지 한 번에 실행 | `/cca` |
| `/cca`에서 자동 수정 없이 blocker만 확인 | `/cca --no-fix` |
| 기간 작업 분석 | `/cr today`, `/cr 3days`, `/cr weekly` |
| 기간 분석 후 현재 미커밋 변경까지 commit | `/cca today`, `/cca 3days`, `/cca weekly` |
| release·장애·학습 결과만 미리 확인 | `/cr release`, `/cr emergency`, `/cr learn` |
| release 준비·hotfix·프로필 저장을 실제 실행 | `/cca release`, `/cca emergency`, `/cca learn` |
| PR 생성 전 결과와 blocker만 확인 | `/cpr --base main` |
| 검증된 현재 branch로 GitHub PR 생성 | `/cp --base main` |
| 현재 프로젝트에 남은 CommitForge 잠금 해제 | `/cr clean` 등 모든 명령의 `clean` |

> [!IMPORTANT]
> **Release tag 실행 경계**
>
> - `/cca release --prepare --tag`만 최종 clean HEAD에 **로컬 annotated tag를 실제 생성**합니다.
> - `/cr release --prepare --tag`는 version·CHANGELOG·commit·tag 결과를 **읽기 전용으로 시뮬레이션**할 뿐 아무것도 변경하지 않습니다.
> - `/cr release`만으로도 권장 version/tag를 확인할 수 있습니다.
> - 두 명령 모두 remote tag push, GitHub Release, package publish, deploy는 수행하지 않습니다.

`/cr --fix`와 `/cca`의 자동 수정은 현재 working tree가 만든 확정적·국소적 문제로 제한됩니다. 기존 commit을 amend하거나 history를 재작성하지 않습니다.

<p align="center">
  <img width="546" height="378" alt="CommitForge 실행 결과 예시" src="https://github.com/user-attachments/assets/d0c2c82b-27d5-4c5e-ba3e-6ceb1d32d7ab">
</p>

## 30초 빠른 시작

현재 저장소에 설치:

```bash
./install.sh project
```

Claude Code를 열고 목적에 맞는 명령을 실행합니다.

```text
/cr    # 읽기 전용 심층 리뷰
/ccr   # Atomic Commit 계획
/cc    # 계획·staging·commit
/cca   # 리뷰·수정·검증·commit 전체 실행
/cpr   # Pull Request 읽기 전용 미리보기
/cp    # branch push와 Pull Request 실제 생성
```

Windows PowerShell에서는 `.\install.ps1 -Scope Project`를 사용합니다. 전체 설치 방식은 [설치](#설치)를 참고하십시오.

## 문서 바로가기

- [설치](#설치)
- [명령 사용법](#명령-사용법)
- [심층 리뷰와 reviewer](#심층-리뷰-범위)
- [확장 모드: 기간·release·emergency·learn](#확장-모드)
- [Pull Request 미리보기와 생성](#pull-request-미리보기와-생성)
- [옵션 참조](#옵션-참조)
- [Atomic Commit 기준](#atomic-commit-기준)
- [동시 세션·Diff 보존·복구](#동시-세션-안전성)
- [안전 경계와 권한](#안전상-하지-않는-작업)
- [검증·제거·개발](#검증)

## 설치

### 요구사항

- Git
- Python 3.9 이상
- 최신 Claude Code 권장
- `/cpr`, `/cp` 사용 시 GitHub CLI(`gh`)와 GitHub 인증

Python은 lock, Diff snapshot, untracked 보존, fingerprint와 안전한 cleanup을 담당합니다. Python이 없거나 Guard가 실패하면 `/cc`, `/cr`, `/cca`, `/cpr`, `/cp`는 시작하지 않습니다.

### 프로젝트 설치

현재 저장소에만 `/cc`, `/ccr`, `/cr`, `/cca`, `/cpr`, `/cp`를 제공합니다.

macOS / Linux / WSL / Git Bash:

```bash
./install.sh project /path/to/repository
```

현재 디렉터리가 대상 저장소라면:

```bash
./install.sh project
```

Windows PowerShell:

```powershell
.\install.ps1 -Scope Project -Target C:\path\to\repository
```

### 전역 설치

모든 프로젝트에서 사용합니다.

macOS / Linux / WSL / Git Bash:

```bash
./install.sh global
```

Windows PowerShell:

```powershell
.\install.ps1 -Scope Global
```

기존 같은 이름의 skill/agent는 삭제하지 않고 `.claude/.commitforge-backups/<timestamp>/` 아래에 먼저 백업합니다. 이전 버전의 `.cca-backups`도 제거하지 않습니다. 심볼릭 링크 대상은 자동 교체하지 않습니다.

### 업그레이드

CommitForge 저장소를 갱신한 뒤 기존 설치와 같은 범위로 설치 명령을 다시 실행합니다.

```bash
git pull
./install.sh project /path/to/repository
# 또는
./install.sh global
```

Windows에서는 `install.ps1`의 `Project` 또는 `Global` 범위를 다시 사용합니다. 설치 프로그램은 기존 파일을 먼저 백업합니다. 실행 중인 Claude Code가 새 Skill Hook이나 agent를 찾지 못하면 세션을 한 번 재시작합니다.

### 수동 설치

프로젝트 범위:

```text
<repo>/.claude/
├── skills/
│   ├── cc/
│   ├── ccr/
│   ├── cr/
│   ├── cca/
│   ├── cpr/
│   ├── cp/
│   └── _git-atomic-core/
└── agents/
    ├── cca-git-reviewer.md
    ├── cca-correctness-reviewer.md
    ├── cca-line-reviewer.md
    ├── cca-security-reviewer.md
    ├── cca-performance-reviewer.md
    ├── cca-testing-reviewer.md
    ├── cca-architecture-reviewer.md
    ├── cca-language-api-reviewer.md
    ├── cca-ux-accessibility-reviewer.md
    ├── cca-observability-reviewer.md
    ├── cca-quality-reviewer.md
    ├── cca-data-migration-reviewer.md
    ├── cca-dependency-supply-chain-reviewer.md
    ├── cca-reliability-recovery-reviewer.md
    ├── cca-privacy-governance-reviewer.md
    └── cca-requirements-product-reviewer.md
```

패키지의 `.claude` 내용을 대상 저장소의 `.claude`에 병합하면 됩니다. 다만 `/cr`
Write 훅과 Skill 권한 패턴은 설치 위치의 절대경로를 사용해야 하므로, 가능하면 위
설치 프로그램을 사용하십시오. 수동 복사 시 각 `SKILL.md`의
`.claude/skills/_git-atomic-core` 경로를 대상 core의 절대경로로 바꾸고,
`cr/SKILL.md`의 `cr_edit_gate.py` 명령도 절대경로로 바꿔야 합니다.

전역 범위는 `~/.claude/skills`와 `~/.claude/agents`에 같은 구조로 복사합니다.

### 설치 후 확인

대상 저장소에서 Claude Code를 다시 열고 `/`를 입력해 `ccr`, `cc`, `cr`, `cca`, `cpr`, `cp`가 표시되는지 확인합니다. 새 `.claude/agents` 디렉터리를 현재 세션에서 처음 만들었다면 Claude Code를 한 번 재시작하십시오.

## 명령 사용법

### 계획만 검토

```text
/ccr
```

```text
/ccr 로그인 세션 갱신과 캐시 변경
```

```text
/ccr --scope lib/auth test/auth 인증 갱신 변경
```

`/ccr`은 staging, commit, 파일 수정, 테스트/빌드를 수행하지 않습니다.
Agent Teams 환경이 활성화되면 `/ccr`은 3개 teammate를 고정 기본으로 사용해
commit 경계와 의존 순서를 교차검증합니다. multi-domain이어도 인원을 늘리지 않고
domain shard와 cross-file dependency task를 세 owner에게 나눕니다. 명백히
사소한 단일 영역 변경과 Team fallback만 기존 subagent 또는 main agent 분석을
사용합니다.

### 여러 Atomic Commit 생성

```text
/cc
```

```text
/cc 이메일 본문 prefetch와 모델 변경
```

```text
/cc --scope lib/email test/email 이메일 로딩 최적화
```

`/cc`는 소스 코드를 수정하지 않습니다. 현재 변경을 분석하고 index만 구성하여 여러 commit을 만듭니다. 검증 실패나 코드 문제를 발견하면 수정하지 않고 중단하여 snapshot을 보존합니다.

### 심층 코드 리뷰만 실행

```text
/cr
```

```text
/cr --fix 인증 및 세션 처리 변경
```

`/cr`은 기본적으로 소스를 수정하지 않는 읽기 전용 심층 리뷰입니다. Commit 계획 전용 Git/Atomicity reviewer를 제외한 기본 10개 관점과 조건부 전문 reviewer로 검토하고 테스트·검증합니다. 현재 미커밋 변경에서 발견한 확정적·국소적 문제를 수정하려면 `/cr --fix`처럼 명시해야 합니다. 어느 경우에도 Atomic Commit 계획, 메시지 초안, staging, commit, push는 만들지 않습니다.

읽기 전용 `/cr`, `/cpr`, `/ccr`과 `/cca`의 read-only 리뷰 단계는 Claude Code
Agent Teams 환경이 활성화돼
있으면 core 3명을 기본으로 사용합니다. 파일 2개 이하·80 changed lines 이하인
단일 domain이며 고위험 trigger와 cross-file contract가 없는 경우에만 Team을
생략할 수 있습니다. `--team`이면 사소한 변경도 core 3명으로
실행하고 `--no-team`이면 subagent를 사용합니다. 환경이
꺼져 있거나 coordination을 사용할 수 없으면 기존 subagent로 안전하게
fallback합니다. Team 생성은 Claude Code가 요구하는 승인을 거치며, 승인하지
않아도 subagent 리뷰는 계속됩니다. CommitForge는
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`를 설정하거나 변경하지 않습니다.
`/cca`는 Team 결과를 모두 집계하고 종료한 뒤 lead만 수정하며, fingerprint가
바뀌면 새 read-only Team으로 전체 diff를 재리뷰합니다. `/cr --fix`, `/cc`,
`/cp`는 기존 subagent 구조를 유지합니다. 모든 실행형 단계에서 실제 변경은
lead만 수행합니다.

`/cca` 반복 중 “종료 예약” 또는 “현재 반복 후 종료”를 보내면 현재 read-only
Team과 이미 시작한 국소 수정의 재리뷰까지만 안전하게 마칩니다. 새 반복·수정·
commit은 시작하지 않고 Team을 종료한 뒤 Guard lock을 해제하며 snapshot을
보존합니다. 최초 리뷰와 매 재리뷰 시작 시 현재 반복 횟수와 이 종료 방법을
안내합니다.

`/cr`·`/cpr`의 core 3명은 Correctness/State/Concurrency,
Security/Privacy/Supply Chain/Integrity, Architecture/API/Compatibility를
담당합니다. 실행 행위가 바뀌면 Testing/Independent Verification을 필수로
추가하고, trigger에 따라 Reliability/Observability, UX/Accessibility,
Data/Migration, Requirements/Product, Release/Deployment, Domain/Framework
specialist를 활성화합니다.

기본 모드에서는 Skill 범위의 `PreToolUse` Hook이 `Edit`, `Write`, `NotebookEdit`를 실행 전에 차단합니다. 따라서 프롬프트 준수에만 의존하지 않으며, 자연어로 “수정해 줘”라고 적는 것은 권한을 열지 않습니다. 독립된 `--fix` 옵션만 편집 권한 평가를 통과시킵니다.

기본 working tree 외에도 비교 대상을 지정할 수 있습니다.

```text
/cr --base main
/cr --range v1.4.0..HEAD
/cr pr
```

- `--base <ref>`: merge-base부터 현재 HEAD까지의 commit과 현재 변경을 함께 검토
- `--range <A..B>`: 명시한 commit 범위를 검토하며 `B`가 HEAD가 아니면 자동 수정 금지
- `pr`: GitHub CLI로 현재 PR의 base/head를 확인해 PR 범위를 검토

`/cr release`, `/cr emergency`, `/cr learn`은 `--fix`를 붙여도 편집 Hook이 권한을 열지 않는 강제 read-only 모드입니다. 어떤 모드에서도 `/cr`은 Atomic Commit 계획·메시지·staging·commit·tag를 만들지 않습니다.

### 전체 파이프라인

```text
/cca
```

```text
/cca 인증 및 세션 처리 변경
```

```text
/cca --strict --iterations 4 결제 취소 처리
```

`/cca`는 다음 순서로 실행됩니다.

```text
Guard + 원본 Diff 보존
→ 변경 전체 분석
→ read-only Agent Team core 3명으로 전체 diff 기본 리뷰
→ 변경 trigger에 맞는 데이터·공급망·복구·privacy·요구사항 전문 리뷰
→ finding 근거 검증·Team 종료
→ 확정적 CRITICAL/MAJOR 문제의 안전한 국소 수정
→ fingerprint 갱신·새 read-only Team 재리뷰(최대 반복 횟수)
→ targeted 검증
→ Commit Dependency Graph
→ hunk/file 단위 staging
→ 한글 Atomic Commit 순차 생성
→ 최종 통합 검증
→ snapshot 정리 및 결과 보고
```

요구가 불명확한 설계 변경, 광범위한 리팩터링, 새 의존성 설치, 데이터 파괴 migration은 자동 수정하지 않습니다.

### 심층 리뷰 범위

`/cr`과 `/cca`는 모든 diff hunk를 변경 원장에 배정하고 `PASS`, `FINDING`, `N/A`로 판정합니다. 미검토 hunk가 있으면 성공 처리하지 않습니다.

추가 검토 영역:

- 제거된 guard·fallback·cleanup·API 동작
- cross-file 정의·구현·호출자·테스트 contract
- wrapper/proxy/adapter의 인자·반환·오류·취소·context 보존
- 기존 구현 재사용과 의미 중복
- architecture·domain·dependency·데이터 소유권
- UX 상태와 keyboard·focus·screen reader 접근성
- log·metric·trace·alert·correlation·cardinality
- 복잡도·책임·dead code·유지보수성
- 언어·프레임워크별 타입·lifecycle·async·serialization API 함정

변경 의미에 따라 다음 reviewer만 조건부로 추가합니다.

| 조건부 관점 | 활성화 예 |
|---|---|
| Data/Migration | schema, migration, ORM, index, backfill, 저장 형식 |
| Dependency/Supply Chain | manifest, lockfile, registry, CI 권한, container image |
| Reliability/Recovery | queue, job, retry, failover, distributed lock, graceful shutdown |
| Privacy/Governance | 개인정보, analytics, consent, retention, export/deletion |
| Requirements/Product | 비교 가능한 ticket, ADR, acceptance criteria, API 명세가 제공됨 |

활성화하지 않은 관점도 생략 사실과 근거를 `N/A`로 남깁니다. 명시적인 요구나 privacy 정책이 없으면 제품 의도나 법률 준수를 추측하지 않습니다.

### Reviewer 실행 신뢰성

- 읽기 전용 `/cr`·`/cpr`·`/ccr`과 `/cca`의 read-only 리뷰 단계는 core 3명
  Team이 기본이며, 명백히 사소한 단일 영역 변경만 생략
- `/cca`는 Team을 완전히 종료한 뒤 lead만 수정하고, 수정된 fingerprint마다
  새 Team으로 전체 diff를 재리뷰
- 대형 diff는 파일 수 균등 분할 대신 package/domain/runtime shard와 위험
  관점을 겹쳐 배정하고 lead aggregator가 contract graph와 hunk coverage 통합
- Testing은 문서 전용 변경 외에는 필수 specialist로 활성화하고 Reliability·UX·
  Migration·Requirements·Release·Domain specialist는 의미 trigger로 추가
- 모든 specialist를 `ACTIVE`, 근거 있는 `N/A`, `UNKNOWN`으로 기록하고
  `UNKNOWN` 필수 관점은 성공을 차단
- Team 역할은 correctness/state, security/privacy/supply-chain/integrity,
  architecture/API/compatibility, performance/reliability/observability,
  testing/UX/WCAG 2.2/requirements/migration 관점으로 교차검증
- 기본 6개 reviewer를 병렬 실행하고 고위험·대형 diff는 환경 상한 안에서 최대 8개까지 확대
- rate-limit·agent 시작 실패·반복 timeout 시 다음 batch를 3~4개로 자동 축소
- Line·Correctness·Security와 활성 조건부 reviewer는 필수
- agent 실패·timeout 시 main agent가 같은 관점으로 fallback
- 완료하지 못한 관점은 `UNKNOWN`이며 `/cr` 성공과 `/cca` commit을 차단
- finding은 stable ID, diff fingerprint, severity, status, evidence, failure scenario, validation으로 정규화
- 같은 root cause는 직접 owner reviewer 하나로 통합

### 프로젝트별 리뷰 정책

저장소의 `.commitforge/review.yml`에서 reviewer, 대형 diff 기준, 보고서 형식과 baseline 위치를 조정할 수 있습니다. 시작 예시는 [examples/review.yml](examples/review.yml)입니다.

정책은 필수 안전 관점을 약화할 수 없습니다. Line·Correctness·Security reviewer와 변경 trigger로 활성화된 조건부 reviewer는 비활성화할 수 없고, 미검토 영역은 `UNKNOWN`으로 차단됩니다.

### JSON·SARIF 보고서

```text
/cr --format json --output review.json
/cr --base main --format sarif --output review.sarif
/cca --format json --output .git/commitforge-reports/cca.json
```

JSON은 `commitforge-review/v1`, SARIF는 2.1.0 계약을 사용합니다. 생성된 결과는 `report_validator.py`로 구조를 검증합니다.

`--output`을 생략하면 machine-readable 결과를 응답의 fenced block으로 반환합니다. 저장소 내부에 출력한 보고서는 `/cca`의 Atomic Commit 대상에 포함하지 않으며 최종 상태에 미커밋 파일로 명시합니다.

### Baseline과 억제

기존 finding은 `.commitforge/review-baseline.json`에 stable ID, fingerprint, 이유, 소유자, 만료일을 기록해 `BASELINED`로 분리할 수 있습니다. CRITICAL, secret, 인증 우회, 데이터 손실 위험은 baseline으로 억제할 수 없습니다. 시작 예시는 [examples/review-baseline.json](examples/review-baseline.json)입니다.

### 대형 Diff

기본적으로 40개 파일, 200개 hunk 또는 3,000 변경 라인 중 하나를 넘으면 대형 diff 모드가 활성화됩니다. 변경을 domain/package 단위로 나눠 리뷰하되 마지막 cross-file 집계가 공유 contract, migration, 권한, 호출 관계를 다시 연결합니다. 문맥 부족은 통과가 아니라 `UNKNOWN`입니다.

### 확장 모드

| 모드 | `/cr` — 읽기 전용 분석 | `/cca` — 실행 |
|---|---|---|
| `today` | 오늘 commit과 현재 변경 리뷰 | 오늘 이력 분석 + 현재 변경 commit |
| `3days` | 최근 3개 달력일 리뷰 | 3개 달력일 분석 + 현재 변경 commit |
| `weekly` | 이번 주 리뷰 | 주간 분석 + 현재 변경 commit |
| `release` | version/tag·릴리스 위험 또는 준비 작업 시뮬레이션 | 명시적 `--prepare`·`--tag` 실행 |
| `emergency` | 장애 원인·rollback·검증 계획 | 최소 hotfix·회귀 검증·commit |
| `learn` | 프로젝트 스타일 프로필 미리보기 | JSON·Markdown 프로필 저장 |

#### 오늘·최근 3개 달력일·이번 주 심층 리뷰

```text
/cr today
/cr 3days
/cr weekly --all-authors
```

`/cr`은 오늘, 최근 3개 달력일 또는 이번 주의 기존 commit과 현재 working tree를 함께 심층 리뷰합니다. 기간 commit은 읽기 전용이며 Atomic Commit 계획·staging·commit을 만들지 않습니다. working tree가 깨끗해도 기간 commit이 있으면 검토합니다.

#### 오늘 작업 전체 분석·커밋

```text
/cca today
/cca today 인증 처리 작업
```

호스트 로컬 달력의 오늘 00:00부터 현재까지 commit과 미커밋 변경을 함께 분석합니다. 커밋별 원장, 되돌림·후속 수정, 최종 net effect와 교차 commit 회귀를 검토합니다. 기존 commit은 재작성하지 않으며 현재 미커밋 변경만 `/cca` 파이프라인으로 commit합니다.

#### 최근 3개 달력일 분석·커밋

```text
/cca 3days
/cca 3days --timezone Asia/Seoul --all-authors
```

선택 시간대에서 오늘과 직전 2개 날짜를 포함해 이틀 전 00:00부터 현재까지 분석합니다. 정확한 최근 72시간이 아닙니다. 기존 기간 commit은 재작성하지 않고 현재 미커밋 변경만 `/cca` 파이프라인으로 commit합니다.

#### 이번 주 작업 전체 분석·커밋

```text
/cca weekly
/cca weekly --week-start sunday --all-authors
```

기본 월요일 00:00부터 현재까지를 날짜·domain·작성자별로 집계합니다. 반복 수정, revert, flaky test, 미완료 기능과 테스트·문서·migration·관측성 공백을 분석하고 현재 미커밋 변경만 commit합니다.

`today`는 최근 24시간, `3days`는 최근 72시간, `weekly`는 최근 7일이 아닙니다. `--timezone <IANA|±HH:MM>`, `--week-start <monday|sunday>`, `--all-authors`로 명시적으로 범위를 조정할 수 있습니다.

#### 릴리스 분석과 준비

```text
/cr release --from v1.8.0
/cr release --channel rc --target 2.0.0-rc.1
/cr release --target 1.9.0 --prepare --tag
/cca release --dry-run
/cca release --target 1.9.0 --prepare
/cca release --channel rc --target 2.0.0-rc.1 --prepare --tag
/cca release --package mobile --from mobile-v1.8.0 --bump minor
```

`/cr release`는 최근 도달 가능한 tag 또는 검증된 `--from` 이후의 변경을 읽기 전용으로 분석해 다음 version/tag, 릴리스 노트, migration·배포 위험을 제안합니다. `/cr release --prepare --tag`는 `/cca`가 실제 실행할 version/CHANGELOG 변경, commit, 로컬 annotated tag를 시뮬레이션해 보고하지만 아무것도 생성하지 않습니다. `/cca release`도 기본은 분석만 하며, `--prepare`를 명시해야 저장소의 기존 canonical version source와 CHANGELOG를 갱신하고 검증된 Atomic Commit을 만듭니다.

tag는 문자열을 추측하지 않고 전용 계산기가 SemVer와 기존 tag를 기준으로 결정합니다. `stable`, `rc`, `beta`, `alpha`, monorepo package prefix를 지원하며 같은 prerelease channel은 `rc.1 → rc.2`처럼 자동 증가합니다. `--tag`는 `--prepare`와 함께만 허용되고 최종 clean HEAD에 로컬 annotated tag를 만듭니다. tag push, GitHub Release, package publish, deploy는 수행하지 않습니다.

#### 긴급 진단과 수정

```text
/cr emergency --incident INC-142 --severity sev1
/cca emergency --diagnose
/cca emergency --rollback-first --incident INC-142
/cca emergency --base v1.8.0 --scope src/payments test/payments
```

`/cr emergency`와 `/cca emergency --diagnose`는 증거·시간선·영향·원인 후보·rollback/containment·검증·관찰 계획만 보고합니다. 실행형 `/cca emergency`는 working tree가 깨끗해도 구체적인 장애가 재현되고 수정이 국소적일 때 최소 hotfix와 직접 회귀 테스트를 구현해 Atomic Commit합니다.

`--rollback-first`는 feature flag, 설정, 호환 가능한 복구 경로를 코드 수정보다 먼저 검토한다는 뜻입니다. 파괴적 reset, 자동 revert, 배포를 의미하지 않습니다. 정확성·보안·데이터 무결성·동시성·복구 가능성을 우선하며, 검증 실패를 긴급함으로 우회하지 않습니다.

#### 프로젝트 스타일 미리보기와 학습

```text
/cr learn --since v1.5.0 --exclude-bots
/cr learn --branches main,develop --package mobile
/cca learn --preview
/cca learn --since v1.5.0 --branches main,develop --exclude-bots
/cca learn --package mobile --commits 200
```

`/cr learn`과 `/cca learn --preview`는 최근 non-merge commit을 branch·기간·package·type별로 표본화해 제목·본문·scope·분리·검증 선호, 근거 commit, 반례, 확신도를 보여주지만 파일을 만들지 않습니다. 실제 `/cca learn`만 machine-readable `.commitforge/profile.json`과 사람이 읽는 `.commitforge/profile.md`를 갱신합니다.

bot 제외 수, 분석 refs, 표본 부족과 규칙 충돌을 함께 기록하며, commit 메시지의 검증 명령은 CI·manifest·script 정의로 교차 검증합니다. 프로필은 자동 stage/commit하지 않고 이후 `/ccr`, `/cc`, `/cr`, `/cca`가 프로젝트 명시 규칙 다음 우선순위로 참고합니다.

### Pull Request 미리보기와 생성

```text
/cpr --base main
/cpr --base main --draft
/cp --base main
/cp --base main --draft
```

| 명령 | 결과 | 원격 변경 |
|---|---|---|
| `/cpr` | committed diff 심층 리뷰, readiness, blocker, PR 제목·본문 완성 초안 | 없음 |
| `/cp` | 같은 gate 통과 후 현재 branch를 일반 push하고 GitHub PR 생성 | branch push와 새 PR 하나 |

두 명령은 clean working tree와 commit이 존재하는 branch만 대상으로 합니다. 소스 수정, staging, commit, amend, rebase, force push, PR merge·close·auto-merge는 하지 않습니다. 같은 head의 열린 PR이 이미 있으면 새 PR을 중복 생성하지 않고 기존 URL을 보고합니다.

현재가 base인 `main` 또는 `master`이면 다음처럼 동작합니다.

- `/cpr`: committed diff의 주목적에 맞는 `feat/...`, `fix/...` 등의 충돌 없는 branch 이름만 제안하며 branch를 만들지 않습니다.
- `/cp`: remote tracking base보다 앞선 commit을 리뷰한 뒤 같은 규칙으로 branch를 실제 생성하고 그 branch를 push해 PR을 만듭니다.
- 미커밋 변경만 있거나 ahead commit이 없으면 두 명령 모두 차단됩니다. 먼저 `/cca` 또는 `/cc`로 commit한 뒤 다시 실행하십시오.
- `--branch <name>`으로 head 이름을 명시할 수 있습니다. 형식·충돌·diff 의미를 검증하며 기존 local/remote branch를 덮어쓰지 않습니다.
- 자동 branch 생성 뒤 push나 PR 생성이 실패하면 branch를 자동 삭제하거나 `main`/`master`로 복귀하지 않고 현재 상태와 재시도 방법을 보고합니다.

`/cp`는 GitHub CLI 인증과 저장소 쓰기 권한이 필요합니다. remote branch가 이미 있으면 최신 local tracking ref와 실제 remote SHA가 일치하고 fast-forward 가능한 경우에만 일반 push합니다. 자동 fetch는 하지 않습니다.

## 옵션 참조

이 옵션들은 별도 shell parser가 아니라 Skill이 해석하는 명시적 프롬프트 규약입니다.

### 공통·리뷰 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--scope <경로...>` | 전체 | 지정 범위 중심으로 분석/커밋 |
| `--compact` | `/ccr` | 메시지 본문 초안을 간결하게 출력 |
| `--team` | `/cr`, `/ccr`, `/cpr`, `/cca` | 환경이 활성화된 경우 read-only 리뷰 단계에서 Agent Team 강제 선호 |
| `--no-team` | `/cr`, `/ccr`, `/cpr`, `/cca` | Agent Team을 끄고 기존 subagent 사용 |
| `--fix` | `/cr` 일반 리뷰 | 현재 working hunk의 확정적·국소 문제 수정 허용; `release`·`emergency`·`learn`에서는 거부 |
| `--no-fix` | `/cca` | 소스 수정 금지; blocker에서 중단 |
| `--no-verify` | `/cc`, `/cr`, `/cca` | 프로젝트 검증 생략 허용; `/cc`, `/cca`는 hook 우회도 허용 |
| `--strict` | `/cr`, `/cca` | 확인된 MINOR도 엄격하게 처리 |
| `--iterations 1-5` | `/cr`, `/cca` | 리뷰-수정 반복 상한, 기본 3 |
| `--keep-snapshot` | `/cc`, `/cr`, `/cca` | 성공 후에도 Diff snapshot 보존 |
| `--base <ref>` | `/cr` | merge-base부터 HEAD 및 현재 변경 검토 |
| `--range <A..B>` | `/cr` | 명시한 commit 범위 검토 |
| `pr` | `/cr` | 현재 GitHub PR의 base/head 범위 검토 |
| `--format <human\|json\|sarif>` | `/cr`, `/cca` | 보고서 형식 선택; 기본값은 `human` |
| `--output <path>` | `/cr`, `/cca` | `--format json` 또는 `--format sarif` 보고서를 파일로 저장 |

`--output`으로 저장소 내부 경로를 지정하면 보고서 파일은 commit 대상에서 제외되고 미커밋 상태로 남습니다. `/cr`은 Guard 불변식 검증과 종료 후, `/cca`는 commit 실행 종료 후 보고서를 생성합니다.

### Today·3days·Weekly 기간 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--all-authors` | `/cr today`, `/cr 3days`, `/cr weekly`, `/cca today`, `/cca 3days`, `/cca weekly` | 기본 Git 사용자 이메일 제한을 제거하고 모든 작성자의 기간 commit 포함 |
| `--week-start <monday\|sunday>` | `/cr weekly`, `/cca weekly` | 주간 시작 요일 선택; 기본값은 `monday` |
| `--timezone <IANA\|±HH:MM>` | `/cr today`, `/cr 3days`, `/cr weekly`, `/cca today`, `/cca 3days`, `/cca weekly` | 기간 경계 계산 시간대 지정; 기본값은 호스트 로컬 시간대 |

```text
/cr today --timezone Asia/Seoul
/cr 3days --all-authors --timezone Asia/Seoul
/cr weekly --all-authors --week-start sunday
/cca today --timezone +09:00
/cca 3days --timezone +09:00
/cca weekly --all-authors --week-start monday
```

`today`는 선택한 시간대의 오늘 00:00부터 현재까지이며 최근 24시간이 아닙니다. `3days`는 이틀 전 00:00부터 현재까지인 3개 달력일이며 최근 72시간이 아닙니다. `weekly`는 선택한 시작 요일의 00:00부터 현재까지이며 최근 7일이 아닙니다.

### Release 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--from <ref>` | `/cr release`, `/cca release` | 릴리스 분석 시작 ref; 생략하면 namespace와 일치하는 최근 도달 가능 tag |
| `--target <semver>` | `/cr release`, `/cca release` | 정확한 목표 SemVer |
| `--bump <auto\|major\|minor\|patch>` | `/cr release`, `/cca release` | 버전 증가 방식; 기본 `auto` |
| `--channel <stable\|rc\|beta\|alpha>` | `/cr release`, `/cca release` | 안정/사전 릴리스 channel과 순번 자동 증가 |
| `--package <name>` | `/cr release`, `/cca release` | monorepo package 범위와 기본 `<name>-v` tag namespace |
| `--tag-prefix <prefix>` | `/cr release`, `/cca release` | 명시적 tag 접두사 |
| `--dry-run` | `/cca release` | 수정·commit·tag 없이 예상 결과만 보고 |
| `--prepare` | `/cr release` | 실제 변경 없이 version/CHANGELOG 준비 계획을 시뮬레이션해 보고 |
| `--tag` | `/cr release --prepare` | 실제 생성 없이 예상 로컬 annotated tag와 대상 commit을 보고 |
| `--prepare` | `/cca release` | version source·CHANGELOG 갱신, 검증, Atomic Commit |
| `--tag` | `/cca release --prepare` | 최종 HEAD에 로컬 annotated tag를 실제 생성; push하지 않음 |

### Emergency 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--incident <id>` | `/cr emergency`, `/cca emergency` | incident 식별자 기록 |
| `--severity <sev1\|sev2\|sev3\|sev4>` | `/cr emergency`, `/cca emergency` | 사용자가 확인한 심각도 |
| `--diagnose` | `/cca emergency` | 수정·stage·commit 없는 진단 |
| `--rollback-first` | `/cr emergency`, `/cca emergency` | 안전한 rollback/containment 경로 우선 평가 |
| `--base <ref>` | `/cr emergency`, `/cca emergency` | 정상 동작 비교 기준 후보 |
| `--scope <경로...>` | `/cr emergency`, `/cca emergency` | hotfix 중심 범위 |

### Learn 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--preview` | `/cca learn` | 프로필 파일을 쓰지 않고 후보만 보고 |
| `--since <ref>` | `/cr learn`, `/cca learn` | 지정 ref 이후 history 분석 |
| `--branches <a,b,...>` | `/cr learn`, `/cca learn` | checkout 없이 여러 branch 분석 |
| `--exclude-bots` | `/cr learn`, `/cca learn` | 확인 가능한 bot 작성자 제외 및 제외 수 보고 |
| `--package <name>` | `/cr learn`, `/cca learn` | monorepo package 관련 표본 중심 분석 |
| `--commits 20-500` | `/cr learn`, `/cca learn` | 분석할 non-merge commit 수 |

`--no-verify`여도 staged diff 직접 검토, whitespace, secret, 저장소 안전 검사는 생략하지 않습니다.

### Pull Request 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--base <branch>` | `/cpr`, `/cp` | PR 대상 branch; 생략하면 GitHub 기본 branch |
| `--remote <name>` | `/cpr`, `/cp` | 조회·push remote; 기본값 `origin` |
| `--branch <name>` | `/cpr`, `/cp` | `main`/`master` 자동 분기의 head 이름 제안 또는 실제 생성 |
| `--draft` | `/cpr`, `/cp` | draft PR 미리보기 또는 실제 draft 생성 |
| `--title <text>` | `/cpr`, `/cp` | diff와 일치 여부를 검증할 명시적 PR 제목 |
| `--no-verify` | `/cpr`, `/cp` | 프로젝트 test/lint/build 생략; diff·secret·Git 안전 검사는 유지 |
| `--strict` | `/cpr`, `/cp` | 확인된 MINOR finding도 차단 |
| `--keep-snapshot` | `/cpr`, `/cp` | 성공 후 Guard snapshot 보존 |

## Atomic Commit 기준

기본 메시지 형식:

```text
type(scope): 한글 제목

- 변경 배경과 목적
- 핵심 동작 및 구현 변화
- 영향 범위와 호환성
- 실제 수행한 검증
```

이 패키지는 다음을 함께 유지합니다.

- 구현 + 직접 회귀 테스트
- API + 필수 호출부
- 타입/스키마 + 최소 구현
- migration + 소비 코드
- manifest + 같은 의존성의 lockfile
- UI + 필수 스타일

다음은 가능한 분리합니다.

- rename/move + 로직
- 리팩터링 + 기능
- 버그 수정 + 독립 기능
- formatting + 로직
- dependency 업그레이드 + 무관한 코드
- 독립 package/domain 변경

파일 수가 많아도 하나의 의도면 한 commit일 수 있고, 파일 하나라도 여러 의도면 hunk 단위로 나눌 수 있습니다.

## 동시 세션 안전성

### 세션 종료 자동 정리

설치기는 Claude Code의 실제 `session_id`를 Guard owner와 결합하는 lifecycle hook을
등록합니다. 정상 응답 종료, API 실패, `/clear`, `/exit`, `/resume`, 로그아웃에서
종료 세션이 소유한 현재 worktree 잠금만 자동 해제하고 Diff snapshot은 보존합니다.
다른 세션이나 다른 저장소의 잠금은 해제하지 않습니다.

`/compact`와 자동 context compaction은 같은 세션이 계속 실행되는 동작이므로 잠금을
유지합니다. compaction 뒤 같은 session ID가 다시 전달됩니다. 강제 종료·전원 손실처럼
Claude가 종료 hook을 전달할 수 없는 경우에는 아래의 stale 회수 또는 `clean`을 사용합니다.

### 현재 프로젝트 잠금 정리

모든 명령에서 첫 번째 인자로 `clean`을 사용할 수 있습니다.

```text
/cr clean
/cc clean
/ccr clean
/cca clean
/cpr clean
/cp clean
```

현재 디렉터리가 속한 Git worktree의 CommitForge advisory lock을 해제합니다.
다른 저장소·worktree, 작업 파일·index·commit은 건드리지 않으며 Diff snapshot도
보존합니다. 실행 중인 기존 세션의 lock까지 해제할 수 있으므로 그 세션이 끝났거나
중단됐음을 확인한 뒤 사용하십시오.

### Git 자체 lock으로 차단된 경우

`index.lock` 같은 Git 자체 lock이 있으면 `begin`은
`reason=git_external_lock`으로 중단하고 각 lock의 경로, 크기, 경과 시간,
쓰기 중인 프로세스 PID, stale 후보 여부를 보고합니다. 이때 해당 명령의
`clean`을 다시 실행하면 안전 판정을 통과한 stale Git lock도 정리합니다.

정상적인 index 연산은 1초 이내에 끝나므로, 5분(기본값) 이상 지났고 크기가 0이며
쓰기 중인 프로세스가 없을 때만 stale 후보로 표시합니다. macOS의 Finder·Spotlight,
Windows의 Explorer·인덱서 등 읽기 전용 핸들은 writer로 보지 않습니다.

`clean`은 알려진 Git lock 네 종류(`index.lock`, `HEAD.lock`,
`packed-refs.lock`, `config.lock`)에 한해 stale 조건, 진행 중 Git operation 없음,
symbolic link 아님, 재검사 중 파일 identity 불변을 모두 확인한 뒤 제거합니다.
macOS는 `lsof`, Linux는 `/proc`, Windows는 Win32 share-mode를 사용합니다.
writer 판별이 불가능하거나 상태가 바뀌면 삭제하지 않고 남은 경로와 사유를
보고합니다. `begin`, `status`, `--reclaim-stale`은 Git lock을 삭제하지 않습니다.

### 오래된 잠금 회수

잠금 충돌 결과에는 `stale_candidate`, `lock_age_seconds`, `lock_owner_same_host`,
`lock_owner_same_session`이 함께 보고됩니다. `stale_candidate: true`는 잠금이
임계값(기본 1시간)보다 오래됐다는 뜻일 뿐 원래 세션이 죽었다는 증거가 아니므로
자동으로 회수하지 않습니다.

원래 실행이 끝났음을 확인했다면 `clean` 대신 회수를 요청할 수 있습니다.

```bash
python3 ~/.claude/skills/_git-atomic-core/scripts/guard.py begin \
  --session "$COMMITFORGE_SESSION_ID" --reclaim-stale
```

같은 호스트의 오래된 잠금이거나 동일 세션 재진입일 때만 해제 후 재획득하며,
기존 owner의 snapshot은 그대로 보존합니다. 다른 호스트의 잠금, 아직 신선한
잠금, 예상치 못한 잠금 내용은 `reclaim_refused_reason`으로 거부됩니다. 임계값은
`--stale-after <초>`로 조정합니다.

`clean`은 조건 없이 해제만 하고 종료하며, `--reclaim-stale`은 안전 조건을
만족할 때만 해제하고 곧바로 작업을 이어갑니다.

### 같은 worktree

`/cc`, `/cr`, `/cca`, `/cpr`, `/cp`는 worktree별 advisory lock을 사용합니다. 같은 worktree에서 두 번째 실행은 중단됩니다.

다만 이 lock은 다른 IDE, terminal, Git GUI를 강제로 막지 못합니다. 실행 중 다른 세션이 파일이나 index를 바꾸면 fingerprint 불일치로 재분석 또는 중단합니다.

### 여러 세션 권장 방식

각 Claude Code 세션을 별도 Git worktree에서 실행합니다.

```bash
git worktree add ../repo-feature-a -b feature/a
git worktree add ../repo-feature-b -b feature/b
```

각 worktree는 별도 index와 guard lock을 갖습니다.

## 작업 전 Diff 보존

`/cc`, `/cr`, `/cca`, `/cpr`, `/cp` 시작 시 실제 worktree의 Git directory 아래에 세션 전용 snapshot을 만듭니다.

```text
<git-dir>/claude-atomic-snapshots/<timestamp-session-random>/
```

포함:

- staged binary diff
- unstaged binary diff
- status와 HEAD/branch
- untracked 파일 목록·해시
- 기본 256 MiB 이내 untracked archive
- repository fingerprint
- 세션 소유 token
- snapshot 파일별 크기와 SHA-256 inventory

모든 의도된 commit과 검증이 성공하면 Guard가 snapshot inventory를 다시 감사한 뒤 자기 snapshot만 삭제합니다. 손상·누락·변조가 감지되면 삭제와 성공 처리를 차단합니다.

실패, 중단, 불확실한 dirty 상태면 lock만 해제하고 snapshot은 보존합니다.

## 장애 복구

상태 확인:

프로젝트 설치:

```bash
python3 .claude/skills/_git-atomic-core/scripts/guard.py status
```

전역 설치:

```bash
python3 ~/.claude/skills/_git-atomic-core/scripts/guard.py status
```

상세 복구 방법은 `_git-atomic-core/recovery.md`를 참고하십시오.

잠금은 명령 이름이나 상위 개발 폴더가 아니라 현재 worktree의 실제 Git
directory를 기준으로 분리됩니다. 같은 부모 폴더 아래의 서로 다른 Git
저장소는 서로 차단하지 않습니다.

비정상 종료 후 stale lock이 있으면 `status`의 `project_root`, `git_dir`,
session/token과 `lock_owner_snapshots`를 확인하십시오. 생성 시각만으로 stale이라고 단정하지
말고 원래 작업 세션이 끝났는지 확인한 뒤, 원래 세션에 돌아갈 수 없으면 현재
세션에서 동일한 owner session/token으로 `guard.py abort`를 실행할 수 있습니다.
일치하는 snapshot이 하나면 Guard가 자동 선택합니다. lock 디렉터리를 무조건
삭제하지 마십시오.

## 안전상 하지 않는 작업

- remote commit/tag push (`/cp`의 검증된 현재 branch 일반 push만 예외)
- amend
- rebase/squash/history rewrite
- force push
- hard reset
- `git clean`
- stash 삭제
- branch 강제 삭제
- Git lock 강제 삭제
- dependency 자동 설치/업그레이드
- 외부 서비스/인프라 변경

`/cp`의 force 없는 검증된 branch push와 새 PR 생성, `/cca release --prepare --tag`의 검증된 로컬 annotated tag 생성만 예외입니다. `/cp`도 tag push, merge, auto-merge, deploy는 하지 않습니다. commit hook과 서명 설정은 기본적으로 존중합니다.

## 권한과 실행 통제

Skill frontmatter는 invocation turn 동안 각 명령에 필요한 Git 조회·staging·commit 및 Guard 실행만 사전 승인합니다. 기본 `/cr`은 Skill 범위의 `PreToolUse` Hook이 편집 도구를 차단하며, 일반 리뷰에서 독립된 `--fix` 옵션이 있을 때만 편집 권한 평가를 통과합니다. `release`·`emergency`·`learn`은 `--fix`가 있어도 차단됩니다. 테스트, 빌드, package manager 등 프로젝트별 명령은 넓게 사전 승인하지 않았기 때문에 사용자의 Claude Code permission 설정에 따라 승인을 요청할 수 있습니다. CommitForge는 실행 전에 거부 가능성을 추측해 알리지 않고, 실제 permission 요청이나 실패가 발생했을 때만 정확한 명령과 미검증 범위를 표시합니다.

모든 최종 결과에는 명령 시작부터 검증·Guard 정리까지의 전체 소요 시간을 분
단위로 포함합니다. 6초 미만은 `0.1분 미만`, 그 외에는 소수점 첫째 자리까지
표시하며 측정값을 잃은 경우에는 임의로 추정하지 않습니다.

저장소에 포함된 Skill은 workspace trust를 승인하기 전에 내용을 검토하십시오.

## 검증

패키지 정적 검사:

```bash
python3 verify.py
```

guard 통합 테스트:

```bash
python3 -m unittest -v tests/test_guard.py
```

## 제거

macOS / Linux:

```bash
./uninstall.sh project /path/to/repository
./uninstall.sh global
```

Windows PowerShell:

```powershell
.\uninstall.ps1 -Scope Project -Target C:\path\to\repository
.\uninstall.ps1 -Scope Global
```

알려진 skill/agent만 제거하고 `.claude/.commitforge-uninstall-backups/<timestamp>/`에 사본을 남깁니다.

## 개발·릴리스 검증

현재 metadata 확인:

```bash
python3 release.py --check
```

manifest와 checksum 갱신:

```bash
python3 release.py
```

재현 가능한 ZIP/TAR.GZ 생성:

```bash
python3 release.py --check --archives-dir dist
```

GitHub Actions는 push와 pull request마다 release metadata, 전체 테스트, Python syntax, SHA-256, 설치·재설치·제거를 검증합니다. Ubuntu Python 3.9/3.13, macOS, Windows portability matrix도 실행하며 외부 Action은 전체 commit SHA로 고정합니다. Dependabot이 Action 업데이트를 주기적으로 제안합니다.

실제 Claude Code 모델 판단은 로컬 opt-in 평가로 확인할 수 있습니다.

```bash
python3 evals/run_evals.py --check
python3 evals/run_evals.py --live --scenario "python mutable default regression"
```

Live 평가는 기본적으로 scenario마다 Sonnet과 최대 5달러 상한을 사용합니다. `--command` 또는 `COMMITFORGE_EVAL_COMMAND`로 모델·권한·비용 정책을 명시적으로 바꿀 수 있습니다.

## 한계

- Atomicity는 코드 의미에 대한 모델 판단을 포함하므로 최종 `git log`와 각 diff 검토가 여전히 중요합니다.
- 같은 worktree를 수정하는 비협조적 외부 프로세스까지 완전히 차단하지 못합니다.
- 매우 큰 diff는 자동 분할하지만 복잡한 generated source, binary, 초기 unborn branch의 부분 staging은 여전히 제한될 수 있습니다.
- 프로젝트 테스트 환경이 준비되지 않으면 일부 검증을 수행할 수 없으며 결과에 명시합니다.
- `/cr`·`/cca` reviewer는 finding을 제안하며 main agent가 근거를 재검증하도록 설계했지만, 자동 리뷰가 인간의 도메인 검토를 완전히 대체하지는 않습니다.

## 파일 구조

```text
.claude/
├── skills/
│   ├── cc/SKILL.md
│   ├── ccr/SKILL.md
│   ├── cr/SKILL.md
│   ├── cca/SKILL.md
│   ├── cpr/SKILL.md
│   ├── cp/SKILL.md
│   └── _git-atomic-core/
│       ├── atomic-commit-rules.md
│       ├── staging-strategy.md
│       ├── commit-message-guide.md
│       ├── safety-and-concurrency.md
│       ├── review-gates.md
│       ├── validation-strategy.md
│       ├── project-profiles.md
│       ├── extended-modes.md
│       ├── period-review-modes.md
│       ├── deep-review-protocol.md
│       ├── language-api-pitfalls.md
│       ├── review-policy.md
│       ├── reporting-formats.md
│       ├── baseline-and-suppressions.md
│       ├── large-diff-review.md
│       ├── pull-request-workflow.md
│       ├── reporting.md
│       ├── recovery.md
│       ├── examples.md
│       └── scripts/
│           ├── cr_edit_gate.py
│           ├── guard.py
│           ├── reviewer_triggers.py
│           ├── report_validator.py
│           ├── baseline.py
│           ├── period_range.py
│           ├── pr_context.py
│           └── release_version.py
└── agents/
    ├── cca-git-reviewer.md
    ├── cca-correctness-reviewer.md
    ├── cca-line-reviewer.md
    ├── cca-security-reviewer.md
    ├── cca-performance-reviewer.md
    ├── cca-testing-reviewer.md
    ├── cca-architecture-reviewer.md
    ├── cca-language-api-reviewer.md
    ├── cca-ux-accessibility-reviewer.md
    ├── cca-observability-reviewer.md
    ├── cca-quality-reviewer.md
    ├── cca-data-migration-reviewer.md
    ├── cca-dependency-supply-chain-reviewer.md
    ├── cca-reliability-recovery-reviewer.md
    ├── cca-privacy-governance-reviewer.md
    └── cca-requirements-product-reviewer.md
```
