# JSON·SARIF 보고

기본은 한글 human 보고다. `--format json|sarif` 또는 review policy가 지정되면 machine-readable 결과를 추가한다.

## JSON

```json
{
  "schema": "commitforge-review/v1",
  "mode": "cr",
  "fingerprint": "...",
  "range": {"kind": "working|base|range|pr", "value": "..."},
  "summary": {"critical": 0, "major": 0, "minor": 0, "note": 0},
  "reviewers": [],
  "findings": [],
  "coverage": {"total_hunks": 0, "unreviewed_hunks": 0},
  "invariants": {"head": true, "branch": true, "index": true}
}
```

`findings`는 `review-execution.md` 공통 schema를 사용한다. `status`는 `OPEN`, `FIXED`, `REJECTED`, `N_A`, `UNKNOWN`, `BASELINED`, `STALE` 중 하나다.

## SARIF

- SARIF `2.1.0`
- `$schema`: `https://json.schemastore.org/sarif-2.1.0.json`
- tool driver name: `CommitForge`
- finding ID를 `ruleId`로 사용
- severity mapping: CRITICAL/MAJOR=`error`, MINOR=`warning`, NOTE=`note`
- repository 상대 URI와 1-based line 사용
- secret·개인정보·전체 source line을 message에 포함하지 않음

## 출력 위치

- `--output <path>`가 있으면 해당 파일에 기록한다.
- 경로가 없으면 응답의 fenced JSON으로 반환한다.
- 저장소 안 파일을 생성했다면 `/cr` working change로 명시한다.
- `/cca` 보고서는 Atomic Commit 대상에서 제외하며 commit 실행이 끝난 뒤 생성한다. 저장소 내부 경로를 명시했다면 결과 파일은 미커밋 상태로 남기고 보고한다.
- `.git/commitforge-reports/`를 기본 임시 위치로 사용할 수 있다.
- 생성 후 `report_validator.py`로 검증한다.
