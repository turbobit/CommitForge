# CommitForge 설치

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

대상 프로젝트에서 Claude Code를 실행하고 `/`를 입력해 `cc`, `ccr`, `cr`, `cca`를 확인합니다.

```text
/ccr
/cc
/cr
/cr --base main --no-fix
/cr pr --no-fix
/cca
/cca today
/cca release
/cca emergency
/cca learn
```

새 `.claude/agents` 디렉터리를 실행 중 세션에서 처음 만들었다면 한 번 재시작하십시오.

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
/cr --no-fix 테스트 변경
```

`/cr --no-fix`로 읽기 전용 심층 리뷰를 확인한 뒤 `/cr` 또는 `/cca`를 사용하는 방식이 안전합니다.

프로젝트별 리뷰 설정은 `examples/review.yml`을 `.commitforge/review.yml`로 복사해 조정할 수 있습니다. JSON·SARIF 결과가 필요하면 `/cr --format json|sarif --output <경로>`를 사용합니다.
