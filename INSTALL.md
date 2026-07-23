# 설치 요약

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

대상 프로젝트에서 Claude Code를 실행하고 `/`를 입력해 `cc`, `ccr`, `cca`를 확인합니다.

```text
/ccr
/cc
/cca
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
/cca --no-fix 테스트 변경
```

`--no-fix`로 먼저 동작을 확인한 뒤 기본 `/cca`를 사용하는 방식이 안전합니다.
