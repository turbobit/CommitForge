# CommitForge 설치

Git과 Python 3.9 이상이 필요합니다. `/cpr`, `/cp`에는 GitHub CLI(`gh`)와 해당 저장소 인증도 필요합니다.

## 프로젝트 설치

```bash
./install.sh project /path/to/repo
```

```powershell
.\install.ps1 -Scope Project -Target C:\path\to\repo
```

## 전역 설치

```bash
./install.sh global
```

```powershell
.\install.ps1 -Scope Global
```

## 확인

대상 프로젝트에서 Claude Code를 실행하고 `/`를 입력해 `cc`, `ccr`, `cr`, `cca`, `cpr`, `cp`를 확인합니다.

```text
/ccr
/cc
/cr
/cr today
/cr 3days
/cr weekly
/cr release
/cr emergency
/cr learn
/cr --base main
/cr pr
/cca
/cca today
/cca 3days
/cca weekly
/cca release --dry-run
/cca emergency --diagnose
/cca learn --preview
/cpr --base main
/cp --base main --draft
```

새 `.claude/agents` 디렉터리를 실행 중 세션에서 처음 만들었다면 한 번 재시작하십시오.
설치기는 프로젝트 범위에서는 `.claude/settings.local.json`, 전역 범위에서는
`~/.claude/settings.json`에 CommitForge lifecycle hook만 병합합니다. 기존 설정과
다른 hook은 보존되며 제거 시에도 CommitForge hook만 제거됩니다.

실제 Claude 세션 ID 전달과 `/clear`·`/exit` 자동 잠금 정리는 새 세션부터 적용됩니다.
설치 또는 업데이트 뒤에는 실행 중인 Claude Code를 한 번 재시작하십시오. `/compact`는
세션 종료가 아니므로 잠금을 유지합니다.

## 권장 최초 시험

작은 테스트 브랜치 또는 별도 worktree에서:

```text
/ccr 테스트 변경 분석
```

계획을 확인한 뒤:

```text
/cc 테스트 변경
```

전체 리뷰 자동화는:

```text
/cr 테스트 변경
```

`/cr`은 기본 읽기 전용입니다. 검토 결과를 확인한 뒤 현재 미커밋 변경의 안전한 국소 수정을 원할 때만 `/cr --fix`를 사용합니다.

프로젝트별 리뷰 설정은 `examples/review.yml`을 `.commitforge/review.yml`로 복사해 조정할 수 있습니다. JSON·SARIF 결과가 필요하면 `/cr --format json|sarif --output <경로>`를 사용합니다.

PR 생성 전에는 `/cpr --base main`으로 제목·본문·readiness를 확인하고, 실제 branch push와 GitHub PR 생성은 `/cp --base main`을 실행합니다. 현재가 `main`/`master`이면 `/cpr`은 branch 이름만 제안하고 `/cp`가 검증 후 실제 branch를 만듭니다.
