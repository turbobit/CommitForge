# CommitForge

> Atomic Git Assistant for Claude Code

CommitForge는 Claude Code에서 변경 분석, 심층 코드 리뷰, Atomic Commit 계획과 안전한 커밋 실행을 제공하는 Skills 패키지입니다.

| 명령 | 역할 | Git 상태 변경 | 소스 수정 |
|---|---|---:|---:|
| `/ccr` | Atomic Commit 계획, 분리 기준, 순서, 한글 메시지 초안 | 없음 | 없음 |
| `/cc` | 현재 변경을 의미 단위로 나눠 여러 commit을 순차 생성 | staging/commit | 없음 |
| `/cr` | 기본 read-only 심층 리뷰, `--fix` 시 확정적 working 문제 수정·재리뷰 | 없음 | `--fix`만 |
| `/cca` | 기본 11개+조건부 전문 리뷰, 수정, 검증, Atomic Commit 전체 실행 | staging/commit | 필요 시 있음 |

`/cr`은 `today`, `weekly` 기간 리뷰를 제공하며 `/cca`는 `today`, `weekly`, `release`, `emergency`, `learn` 확장 모드를 제공합니다.

### 빠른 선택

| 원하는 결과 | 명령 |
|---|---|
| 변경을 커밋하지 않고 Atomic Commit 구성을 먼저 확인 | `/ccr` |
| 이미 만든 변경을 수정하지 않고 Atomic Commit으로 생성 | `/cc` |
| 코드를 바꾸지 않고 현재·기간·PR 변경을 심층 리뷰 | `/cr` |
| 리뷰에서 확인한 현재 working 문제만 고치고 커밋하지 않음 | `/cr --fix` |
| 리뷰·안전한 수정·검증·Atomic Commit을 한 번에 실행 | `/cca` |
| `/cca`에서 소스 수정 없이 blocker만 확인 | `/cca --no-fix` |

`/cr --fix`와 `/cca`의 자동 수정은 현재 working tree가 만든 확정적·국소적 문제로 제한됩니다. 기존 commit을 amend하거나 history를 재작성하지 않습니다.

커밋 메시지는 기본적으로 다음 형태를 사용합니다.

```text
type(scope): 한글 제목

- 변경 배경과 목적
- 핵심 동작 및 구현 변화
- 영향 범위와 호환성
- 실제 수행한 검증
```
<img width="546" height="378" alt="image" src="https://github.com/user-attachments/assets/d0c2c82b-27d5-4c5e-ba3e-6ceb1d32d7ab" />

## 왜 `.claude/skills`인가

현재 Claude Code에서는 Custom Commands가 Skills로 통합됐습니다. `.claude/commands/cc.md`도 계속 동작하지만, 권장 형식인 `.claude/skills/cc/SKILL.md`를 사용하면 지원 파일, invocation 통제, tool 사전 승인, subagent 구성을 함께 배포할 수 있습니다.

디렉터리 이름이 slash command가 됩니다.

```text
.claude/skills/cc/SKILL.md   → /cc
.claude/skills/ccr/SKILL.md  → /ccr
.claude/skills/cr/SKILL.md   → /cr
.claude/skills/cca/SKILL.md  → /cca
```

네 명령은 모두 `disable-model-invocation: true`이므로 사용자가 직접 입력할 때만 실행됩니다.

## 요구사항

- Git
- Python 3.9 이상
- 최신 Claude Code 권장
- `/cr`·`/cca`의 custom subagent를 새로 설치한 현재 세션에서 찾지 못하면 Claude Code를 한 번 재시작

Python은 lock, Diff snapshot, untracked 보존, fingerprint, 안전한 cleanup을 담당합니다. Python이 없거나 guard가 실패하면 `/cc`, `/cr`, `/cca`는 변경을 시작하지 않도록 설계했습니다.

기본 `/cr` 종료 시에는 Guard가 시작 snapshot과 현재 HEAD·branch·staged/unstaged binary diff, status, untracked content를 직접 비교합니다. 프롬프트 판단과 별개로 저장소 상태가 바뀌었다면 성공과 snapshot 삭제를 차단합니다. `--fix`를 명시한 실행에서도 HEAD·branch·staging 불변 조건은 유지합니다.

## 설치

### 프로젝트에 설치

현재 저장소에만 `/cc`, `/ccr`, `/cr`, `/cca`를 제공합니다.

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

패키지의 `.claude` 내용을 대상 저장소의 `.claude`에 병합하면 됩니다.

전역 범위는 `~/.claude/skills`와 `~/.claude/agents`에 같은 구조로 복사합니다.

## 사용

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

어떤 모드에서도 `/cr`은 Atomic Commit 계획·메시지·staging·commit을 만들지 않습니다.

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
→ Git/정확성/line-by-line/보안/성능/테스트/architecture/API/UX·A11y/observability/품질 기본 리뷰
→ 변경 trigger에 맞는 데이터·공급망·복구·privacy·요구사항 전문 리뷰
→ finding 근거 검증
→ 확정적 CRITICAL/MAJOR 문제의 안전한 국소 수정
→ 재리뷰(최대 반복 횟수)
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

- 최대 4개 reviewer를 동시에 실행하고 나머지는 batch 처리
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

#### 오늘·이번 주 심층 리뷰

```text
/cr today
/cr weekly --all-authors
```

`/cr`은 오늘 또는 이번 주의 기존 commit과 현재 working tree를 함께 심층 리뷰합니다. 기간 commit은 읽기 전용이며 Atomic Commit 계획·staging·commit을 만들지 않습니다. working tree가 깨끗해도 기간 commit이 있으면 검토합니다.

#### 오늘 작업 전체 분석·커밋

```text
/cca today
/cca today 인증 처리 작업
```

호스트 로컬 달력의 오늘 00:00부터 현재까지 commit과 미커밋 변경을 함께 분석합니다. 커밋별 원장, 되돌림·후속 수정, 최종 net effect와 교차 commit 회귀를 검토합니다. 기존 commit은 재작성하지 않으며 현재 미커밋 변경만 `/cca` 파이프라인으로 commit합니다.

#### 이번 주 작업 전체 분석·커밋

```text
/cca weekly
/cca weekly --week-start sunday --all-authors
```

기본 월요일 00:00부터 현재까지를 날짜·domain·작성자별로 집계합니다. 반복 수정, revert, flaky test, 미완료 기능과 테스트·문서·migration·관측성 공백을 분석하고 현재 미커밋 변경만 commit합니다.

`today`는 최근 24시간, `weekly`는 최근 7일이 아닙니다. `--timezone <IANA|±HH:MM>`, `--week-start <monday|sunday>`, `--all-authors`로 명시적으로 범위를 조정할 수 있습니다.

#### 릴리스 준비

```text
/cca release
/cca release --from v1.1.0
```

최근 도달 가능한 tag 또는 `HEAD`의 조상으로 검증된 `--from` 기준 이후의 변경과 현재 작업을 검토합니다. 현재 변경을 commit한 뒤 권장 Semantic Version, 릴리스 노트 초안, migration·배포 주의사항을 보고합니다. tag, push, GitHub Release, publish, deploy는 수행하지 않습니다.

#### 긴급 수정

```text
/cca emergency 결제 승인 중복 처리
/cca emergency --scope src/payments test/payments
```

운영 장애나 hotfix를 가장 작은 안전 범위로 제한합니다. working tree가 깨끗해도 구체적인 장애 요청과 재현 가능한 근거가 있으면 최소 수정과 직접 회귀 테스트를 구현할 수 있습니다. 정확성·보안·데이터 무결성을 우선하며 무관한 리팩터링이나 의존성 변경을 포함하지 않습니다.

#### 프로젝트 스타일 학습

```text
/cca learn
/cca learn --commits 200
```

최근 non-merge commit을 분석해 `.commitforge/profile.md`에 제목·본문·scope·분리·검증 선호를 기록합니다. 이 모드는 소스나 Git index를 변경하거나 commit하지 않습니다. 이후 `/ccr`, `/cc`, `/cr`, `/cca`가 프로필을 프로젝트 명시 규칙 다음 우선순위로 참고합니다.

## 인자 규약

이 옵션들은 별도 shell parser가 아니라 Skill이 해석하는 명시적 프롬프트 규약입니다.

### 공통·리뷰 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--scope <경로...>` | 전체 | 지정 범위 중심으로 분석/커밋 |
| `--compact` | `/ccr` | 메시지 본문 초안을 간결하게 출력 |
| `--fix` | `/cr` | 현재 working hunk의 확정적·국소 문제 수정 허용 |
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

### Today·Weekly 기간 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--all-authors` | `/cr today`, `/cr weekly`, `/cca today`, `/cca weekly` | 기본 Git 사용자 이메일 제한을 제거하고 모든 작성자의 기간 commit 포함 |
| `--week-start <monday\|sunday>` | `/cr weekly`, `/cca weekly` | 주간 시작 요일 선택; 기본값은 `monday` |
| `--timezone <IANA\|±HH:MM>` | `/cr today`, `/cr weekly`, `/cca today`, `/cca weekly` | 기간 경계 계산 시간대 지정; 기본값은 호스트 로컬 시간대 |

```text
/cr today --timezone Asia/Seoul
/cr weekly --all-authors --week-start sunday
/cca today --timezone +09:00
/cca weekly --all-authors --week-start monday
```

`today`는 선택한 시간대의 오늘 00:00부터 현재까지이며 최근 24시간이 아닙니다. `weekly`는 선택한 시작 요일의 00:00부터 현재까지이며 최근 7일이 아닙니다.

### `/cca` 확장 모드 옵션

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--from <ref>` | `/cca release` | 릴리스 분석 시작 ref 지정; 생략하면 HEAD에서 도달 가능한 최근 tag 사용 |
| `--commits 20-500` | `/cca learn` | 학습할 최근 non-merge commit 수 |

`--no-verify`여도 staged diff 직접 검토, whitespace, secret, 저장소 안전 검사는 생략하지 않습니다.

## Atomic Commit 기준

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

### 같은 worktree

`/cc`, `/cr`, `/cca`는 worktree별 advisory lock을 사용합니다. 같은 worktree에서 두 번째 실행은 중단됩니다.

다만 이 lock은 다른 IDE, terminal, Git GUI를 강제로 막지 못합니다. 실행 중 다른 세션이 파일이나 index를 바꾸면 fingerprint 불일치로 재분석 또는 중단합니다.

### 여러 세션 권장 방식

각 Claude Code 세션을 별도 Git worktree에서 실행합니다.

```bash
git worktree add ../repo-feature-a -b feature/a
git worktree add ../repo-feature-b -b feature/b
```

각 worktree는 별도 index와 guard lock을 갖습니다.

## 작업 전 Diff 보존

`/cc`, `/cr`, `/cca` 시작 시 실제 worktree의 Git directory 아래에 세션 전용 snapshot을 만듭니다.

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

비정상 종료 후 stale lock이 있으면 현재 작업 세션이 끝났는지 확인하고 `status`에 표시된 동일 session/token/snapshot으로 `guard.py abort`를 실행합니다. lock 디렉터리를 무조건 삭제하지 마십시오.

## 안전상 하지 않는 작업

- push
- amend
- rebase/squash/history rewrite
- force push
- hard reset
- clean
- stash 삭제
- branch 강제 삭제
- Git lock 강제 삭제
- dependency 자동 설치/업그레이드
- 외부 서비스/인프라 변경

commit hook과 서명 설정을 기본적으로 존중합니다.

## Permission

Skill frontmatter는 invocation turn 동안 각 명령에 필요한 Git 조회·staging·commit 및 Guard 실행만 사전 승인합니다. 기본 `/cr`은 Skill 범위의 `PreToolUse` Hook이 편집 도구를 차단하며, 독립된 `--fix` 옵션이 있을 때만 편집 권한 평가를 통과합니다. 테스트, 빌드, package manager 등 프로젝트별 명령은 넓게 사전 승인하지 않았기 때문에 사용자의 Claude Code permission 설정에 따라 승인을 요청할 수 있습니다.

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
│       ├── reporting.md
│       ├── recovery.md
│       ├── examples.md
│       └── scripts/
│           ├── cr_edit_gate.py
│           ├── guard.py
│           ├── reviewer_triggers.py
│           ├── report_validator.py
│           ├── baseline.py
│           └── period_range.py
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
