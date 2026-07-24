# Reviewer 실행·결과 규약

## 1. 실행 단계

1. 동일 fingerprint에서 변경 경로와 의미를 triage한다.
2. `/cr` 기본 10개 또는 `/cca` 기본 11개 reviewer를 준비한다.
3. `reviewer_triggers.py` 결과를 조건부 reviewer의 **최소 활성 집합**으로 사용한다.
4. 코드 의미에서 추가 trigger가 확인되면 reviewer를 더 활성화한다. 스크립트가 비활성이라고 판정해도 의미 근거가 있으면 생략하지 않는다.
5. 기본 동시 실행 목표는 6개 agent다. 현재 Claude Code의 유효 concurrency 상한이 더 낮으면 그 값을 따른다.
6. 고위험 또는 대형 diff이고 독립 reviewer가 충분하면 최대 8개까지 병렬 실행한다. 환경 상한을 초과하지 않는다.
7. 429, 일시적 제한, agent 시작 실패 또는 반복 timeout이 발생하면 다음 batch를 3~4개로 축소하고 실패 관점은 한 번만 재시도한다.
8. 남은 reviewer는 축소된 batch로 이어서 실행하며 필수 관점을 생략하지 않는다.
9. 수정 후 이전 결과를 폐기하고 fingerprint·trigger·활성 reviewer를 다시 계산한다.

## 2. 필수성과 실패 정책

- 필수: Line, Correctness, Security
- 변경 유형상 활성화된 조건부 reviewer도 해당 변경에서는 필수
- agent 시작 실패·timeout·turn 소진 시 main agent가 같은 관점을 직접 수행한다.
- fallback도 완료하지 못하면 해당 관점은 `UNKNOWN`이며 성공 또는 commit을 차단한다.
- 선택 관점을 조용히 누락하지 않는다. `PASS`, `FINDING`, `N/A`, `UNKNOWN` 중 하나를 기록한다.
- `UNKNOWN`은 `N/A`가 아니다. 적용되지 않는다는 근거가 있을 때만 `N/A`다.

## 3. Finding 공통 스키마

Main agent는 reviewer 출력을 다음 필드로 정규화한다.

```json
{
  "id": "reviewer:file:symbol-or-hunk:category",
  "reviewer": "cca-correctness-reviewer",
  "fingerprint": "현재 diff fingerprint",
  "severity": "CRITICAL|MAJOR|MINOR|NOTE",
  "status": "OPEN|FIXED|REJECTED|N_A|UNKNOWN",
  "file": "relative/path",
  "line_or_hunk": "line 또는 hunk",
  "category": "stable-category",
  "evidence": "코드와 실행 경로 근거",
  "failure_scenario": "재현 가능한 영향",
  "suggested_fix": "최소 수정 방향",
  "validation": "필요한 검증",
  "blocking": true
}
```

규칙:

- `id`는 같은 fingerprint에서 안정적이어야 한다.
- secret·개인정보 값은 필드에 복사하지 않는다.
- 정확한 위치가 없으면 finding이 아니라 조사 항목으로 분리한다.
- 수정 후 fingerprint가 바뀌면 기존 finding을 새 결과로 덮지 않고 `FIXED` 또는 `STALE`로 연결한다.

## 4. 중복 제거

- 같은 file/symbol, failure scenario, root cause는 하나로 통합한다.
- 가장 직접적인 reviewer를 owner로 지정한다.
- 다른 reviewer는 `related_reviewers` 근거만 추가한다.
- 심각도 충돌은 더 높은 등급을 자동 채택하지 않고 main agent가 실제 영향으로 재판정한다.

## 5. 보고

- 실행·fallback·N/A·UNKNOWN reviewer 수
- trigger별 활성 근거
- fingerprint별 finding 변화
- 중복 통합 수
- budget 또는 agent 실패로 완료하지 못한 관점

을 최종 보고에 포함한다.
