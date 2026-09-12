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
confidence_threshold: 8
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

- `max_parallel`은 1~8이며 이 파일에 쓸 때 권장하는 값은 4다. 지정하면
  `review-execution.md` §1의 동시 실행 수 상한이 된다. **이 값은 `review.yml`이
  없는 저장소의 기본값이 아니다.** 정책 파일이 없으면 §1의 기본 목표 6이 적용된다.
- Line, Correctness, Security는 비활성화할 수 없다.
- trigger가 확인된 조건부 reviewer는 비활성화할 수 없다.
- `blocking_severity`는 `CRITICAL`, `MAJOR`, `MINOR` 중 하나다.
- `confidence_threshold`는 1~10 정수이며 기본 8이다. `review-execution.md` §3.6의
  격리 검증이 이 값 미만으로 판정한 finding을 `REJECTED`로 바꾼다. 값을 낮추면
  잡음이 늘고, 높이면 실제 결함을 기각할 수 있다. 검증 대상 자체는
  `blocking_severity` 이상으로 한정된다.
- `confidence_threshold`로 secret, 인증·인가, 데이터 손실 finding을 일괄 기각할 수
  없다. 이 영역은 검증이 명시적 근거로 기각한 경우에만 `REJECTED`다.
- exclude는 generated/vendor noise를 줄이기 위한 것이며 secret, public contract, migration, 호출자 영향은 제외하지 않는다.
- policy가 잘못되거나 상충하면 안전한 기본값을 사용하고 경고한다.
- requirements source가 실제로 존재할 때만 Requirements/Product reviewer 근거로 사용한다.
- 프로젝트 프로필의 commit 스타일보다 review policy가 우선한다.
