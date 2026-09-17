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
- 해당 skill의 필수 관점은 `disabled_reviewers`로 비활성화할 수 없다. 기본은
  Line, Correctness, Security이고 `/cr`은 Architecture, Performance를 더한
  5개다. 적용되지 않는 관점은 비활성화가 아니라 근거 있는 `N_A`로 기록한다.
- trigger가 확인된 조건부 reviewer는 비활성화할 수 없다.
- `blocking_severity`는 `CRITICAL`, `MAJOR`, `MINOR` 중 하나다.
- `confidence_threshold`는 1~10 정수이며 기본 8이다. `review-execution.md` §3.6의
  격리 검증이 이 값 미만으로 판정한 finding을 `REJECTED`로 바꾼다. 값을 낮추면
  잡음이 늘고, 높이면 실제 결함을 기각할 수 있다. 검증 대상 자체는
  `blocking_severity` 이상으로 한정된다.
- `confidence_threshold`로 일괄 기각할 수 없는 영역이 있다. 이 목록은 **되돌릴 수
  없는 피해**를 기준으로 하며, 검증이 명시적 근거로 기각한 경우에만 `REJECTED`다.
  - secret·자격증명 노출
  - 인증·인가 우회
  - 데이터 손실·손상
  - 복구 불가능한 migration·데이터 변환. `review-gates.md` §2 CRITICAL의
    "잘못된 migration으로 복구 곤란한 상태"와 같은 기준이다
  - 재시작 없이 회복되지 않는 자원 고갈
- 이 목록은 **어느 reviewer가 찾았는지가 아니라 피해 유형으로** 판정한다.
  Performance reviewer가 찾은 데이터 손실도 보호되고, Security reviewer가 찾은
  저영향 finding은 보호되지 않는다.
- 하위 호환성 파괴는 이 목록에 넣지 않는다. rollback으로 회복 가능하므로 기준에
  들지 않으며, 목록을 더 넓히면 `confidence_threshold`가 잡음 억제 기능을 잃는다.
- exclude는 generated/vendor noise를 줄이기 위한 것이며 secret, public contract, migration, 호출자 영향은 제외하지 않는다.
- policy가 잘못되거나 상충하면 안전한 기본값을 사용하고 경고한다.
- requirements source가 실제로 존재할 때만 Requirements/Product reviewer 근거로 사용한다.
- 프로젝트 프로필의 commit 스타일보다 review policy가 우선한다.
