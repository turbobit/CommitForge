# Finding Baseline과 예외

기본 경로는 `.commitforge/review-baseline.json`이다.

```json
{
  "schema": "commitforge-baseline/v1",
  "entries": [
    {
      "id": "reviewer:path:symbol:category",
      "reason": "현재 변경과 무관한 기존 부채",
      "owner": "team-or-user",
      "expires": "2026-12-31",
      "fingerprint": null
    }
  ]
}
```

규칙:

- stable finding ID가 정확히 일치해야 한다.
- reason, owner, expires가 모두 필요하다.
- 만료된 entry는 적용하지 않는다.
- fingerprint가 있으면 같은 fingerprint에서만 적용한다.
- CRITICAL, secret, 인증·인가 우회, 데이터 손실 finding은 suppress하지 않는다.
- baseline은 finding을 삭제하지 않고 `BASELINED` 상태와 근거를 붙인다.
- 새 코드가 기존 finding의 영향을 확대하면 baseline을 적용하지 않는다.
- `baseline.py <baseline-path>`로 구조와 만료일을 확인한다.
