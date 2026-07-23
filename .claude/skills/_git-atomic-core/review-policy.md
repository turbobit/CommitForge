# 프로젝트 리뷰 정책

저장소 루트의 `.commitforge/review.yml`이 있으면 읽는다. 명시적 사용자 요청과 저장소 안전 규칙 다음 우선순위로 적용한다.

지원 필드:

```yaml
required_reviewers:
  - correctness
  - security
disabled_reviewers: []
max_parallel: 4
blocking_severity: MAJOR
exclude:
  - vendor/**
  - generated/**
large_diff:
  files: 40
  hunks: 200
  lines: 3000
output:
  format: human
  path: null
baseline: .commitforge/review-baseline.json
requirements:
  sources:
    - docs/requirements/**
    - docs/adr/**
```

규칙:

- `max_parallel`은 1~8, 기본 4다.
- Line, Correctness, Security는 비활성화할 수 없다.
- trigger가 확인된 조건부 reviewer는 비활성화할 수 없다.
- `blocking_severity`는 `CRITICAL`, `MAJOR`, `MINOR` 중 하나다.
- exclude는 generated/vendor noise를 줄이기 위한 것이며 secret, public contract, migration, 호출자 영향은 제외하지 않는다.
- policy가 잘못되거나 상충하면 안전한 기본값을 사용하고 경고한다.
- requirements source가 실제로 존재할 때만 Requirements/Product reviewer 근거로 사용한다.
- 프로젝트 프로필의 commit 스타일보다 review policy가 우선한다.
