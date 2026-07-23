# CommitForge

> Atomic Git Assistant for Claude Code

CommitForge는 Claude Code에서 변경 분석, Atomic Commit 계획, 다각도 리뷰와 안전한 커밋 실행을 제공하는 Skills 패키지입니다.

| 명령 | 역할 | Git 상태 변경 | 소스 수정 |
|---|---|---:|---:|
| `/ccr` | Atomic Commit 계획, 분리 기준, 순서, 한글 메시지 초안 | 없음 | 없음 |
| `/cc` | 현재 변경을 의미 단위로 나눠 여러 commit을 순차 생성 | staging/commit | 없음 |
| `/cca` | 병렬 다각도 리뷰, 확정적 수정, 검증, Atomic Commit 전체 실행 | staging/commit | 필요 시 있음 |

커밋 메시지는 기본적으로 다음 형태를 사용합니다.

```text
type(scope): 한글 제목

- 변경 배경과 목적
- 핵심 동작 및 구현 변화
- 영향 범위와 호환성
- 실제 수행한 검증
```

## 왜 `.claude/skills`인가

현재 Claude Code에서는 Custom Commands가 Skills로 통합됐습니다. `.claude/commands/cc.md`도 계속 동작하지만, 권장 형식인 `.claude/skills/cc/SKILL.md`를 사용하면 지원 파일, invocation 통제, tool 사전 승인, subagent 구성을 함께 배포할 수 있습니다.

디렉터리 이름이 slash command가 됩니다.

```text
.claude/skills/cc/SKILL.md   → /cc
.claude/skills/ccr/SKILL.md  → /ccr
.claude/skills/cca/SKILL.md  → /cca
```

세 명령은 모두 `disable-model-invocation: true`이므로 사용자가 직접 입력할 때만 실행됩니다.

## 요구사항

- Git
- Python 3.9 이상
- 최신 Claude Code 권장
- `/cca`의 custom subagent를 새로 설치한 현재 세션에서 찾지 못하면 Claude Code를 한 번 재시작

Python은 lock, Diff snapshot, untracked 보존, fingerprint, 안전한 cleanup을 담당합니다. Python이 없거나 guard가 실패하면 `/cc`와 `/cca`는 Git 변경을 시작하지 않도록 설계했습니다.

## 설치

### 프로젝트에 설치

현재 저장소에만 `/cc`, `/ccr`, `/cca`를 제공합니다.

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

### 수동 설치

프로젝트 범위:

```text
<repo>/.claude/
├── skills/
│   ├── cc/
│   ├── ccr/
│   ├── cca/
│   └── _git-atomic-core/
└── agents/
    ├── cca-git-reviewer.md
    ├── cca-correctness-reviewer.md
    ├── cca-security-reviewer.md
    ├── cca-performance-reviewer.md
    └── cca-testing-reviewer.md
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
→ Git/정확성/보안/성능/테스트 병렬 리뷰
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

## 인자 규약

이 옵션들은 별도 shell parser가 아니라 Skill이 해석하는 명시적 프롬프트 규약입니다.

| 옵션 | 적용 | 의미 |
|---|---|---|
| `--scope <경로...>` | 전체 | 지정 범위 중심으로 분석/커밋 |
| `--compact` | `/ccr` | 메시지 본문 초안을 간결하게 출력 |
| `--no-fix` | `/cca` | 소스 수정 금지; blocker에서 중단 |
| `--no-verify` | `/cc`, `/cca` | 프로젝트 검증 및 hook 우회 허용 |
| `--strict` | `/cca` | 확인된 MINOR도 엄격하게 처리 |
| `--iterations 1-5` | `/cca` | 리뷰-수정 반복 상한, 기본 3 |
| `--keep-snapshot` | `/cc`, `/cca` | 성공 후에도 Diff snapshot 보존 |

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

`/cc`와 `/cca`는 worktree별 advisory lock을 사용합니다. 같은 worktree에서 두 번째 실행은 중단됩니다.

다만 이 lock은 다른 IDE, terminal, Git GUI를 강제로 막지 못합니다. 실행 중 다른 세션이 파일이나 index를 바꾸면 fingerprint 불일치로 재분석 또는 중단합니다.

### 여러 세션 권장 방식

각 Claude Code 세션을 별도 Git worktree에서 실행합니다.

```bash
git worktree add ../repo-feature-a -b feature/a
git worktree add ../repo-feature-b -b feature/b
```

각 worktree는 별도 index와 guard lock을 갖습니다.

## 작업 전 Diff 보존

`/cc`와 `/cca` 시작 시 실제 worktree의 Git directory 아래에 세션 전용 snapshot을 만듭니다.

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

모든 의도된 commit과 검증이 성공하면 자기 snapshot만 삭제합니다.

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

Skill frontmatter는 invocation turn 동안 필요한 Git 조회·staging·commit 및 guard 실행을 사전 승인합니다. 테스트, 빌드, package manager 등 프로젝트별 명령은 넓게 사전 승인하지 않았기 때문에 사용자의 Claude Code permission 설정에 따라 승인을 요청할 수 있습니다.

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

## 한계

- Atomicity는 코드 의미에 대한 모델 판단을 포함하므로 최종 `git log`와 각 diff 검토가 여전히 중요합니다.
- 같은 worktree를 수정하는 비협조적 외부 프로세스까지 완전히 차단하지 못합니다.
- 매우 큰 diff, 복잡한 generated source, binary, 초기 unborn branch의 부분 staging은 자동 분리가 제한될 수 있습니다.
- 프로젝트 테스트 환경이 준비되지 않으면 일부 검증을 수행할 수 없으며 결과에 명시합니다.
- `/cca` reviewer는 finding을 제안하며 main agent가 근거를 재검증하도록 설계했지만, 자동 리뷰가 인간의 도메인 검토를 완전히 대체하지는 않습니다.

## 파일 구조

```text
.claude/
├── skills/
│   ├── cc/SKILL.md
│   ├── ccr/SKILL.md
│   ├── cca/SKILL.md
│   └── _git-atomic-core/
│       ├── atomic-commit-rules.md
│       ├── staging-strategy.md
│       ├── commit-message-guide.md
│       ├── safety-and-concurrency.md
│       ├── review-gates.md
│       ├── validation-strategy.md
│       ├── project-profiles.md
│       ├── reporting.md
│       ├── recovery.md
│       ├── examples.md
│       └── scripts/guard.py
└── agents/
    ├── cca-git-reviewer.md
    ├── cca-correctness-reviewer.md
    ├── cca-security-reviewer.md
    ├── cca-performance-reviewer.md
    └── cca-testing-reviewer.md
```
