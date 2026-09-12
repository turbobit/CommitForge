# 조건부 전문 Reviewer

기본 reviewer에 모든 전문 영역을 항상 추가하지 않는다. 저장소 스캔에서 아래 trigger가 하나라도 확인될 때만 해당 agent를 실행한다. 파일명만이 아니라 diff의 실제 의미를 근거로 판정한다.

`scripts/reviewer_triggers.py`는 경로·명시적 맥락에서 확인 가능한 최소 활성 집합을 제공한다. 이 결과는 reviewer를 빼는 근거가 아니며 main agent의 의미 분석으로 확장한다.

스크립트는 `active`와 함께 `inactive`를 반환한다. `inactive`의 각 항목은 그대로 `N_A` 기록의 출발점이며, 근거를 의미 분석으로 보강하거나 활성으로 승격한다. 비활성 목록을 기억에 의존해 나열하지 않는다.

**파일명이 침묵하는 경우가 있다.** 이름에 신호가 없지만 내용이 trigger인 변경(예: 잠금·복구를 구현하는 `guard.py`)은 스크립트가 잡지 못한다. 이때는 diff의 의미를 근거로 직접 활성화하고, 필요하면 `--context`에 판단 근거를 넘긴다. `--context`가 매치되면 evidence에는 매치된 **패턴만** 남고 전달한 문장은 기록되지 않는다.

## 활성화 표

| Agent | Trigger |
|---|---|
| `cca-data-migration-reviewer` | schema·migration·ORM model·index·저장 형식·backfill·데이터 변환 |
| `cca-dependency-supply-chain-reviewer` | dependency manifest·lockfile·package registry·CI 권한·Docker base image·artifact provenance |
| `cca-reliability-recovery-reviewer` | queue·job·network·cache·분산 lock·retry·circuit breaker·failover·graceful shutdown |
| `cca-privacy-governance-reviewer` | 개인정보·민감정보·analytics·tracking·consent·retention·export·deletion |
| `cca-release-deployment-reviewer` | version·manifest·checksum·installer·release artifact·CI/CD 배포·feature flag·rollback |
| `cca-requirements-product-reviewer` | 사용자 요구·ticket·ADR·acceptance criteria·API 명세 등 비교 가능한 명시적 기준이 제공됨 |

## 실행 규칙

1. Main agent가 trigger와 관련 파일·hunk를 기록한다.
2. 활성화하지 않은 agent는 실행하지 않고 `N/A`와 비활성화 근거를 reviewer coverage에 기록한다.
3. 활성화한 agent에는 전체 diff와 함께 trigger가 된 정확한 근거를 제공한다.
4. Requirements/Product reviewer는 명시적 기준이 없으면 추측하지 않고 반드시 `N/A`다.
   기준 문서가 **같은 diff 안에서 작성·수정된 경우**는 독립 기준이 아니다. 구현과
   기준이 함께 바뀌면 서로를 정당화할 수 있으므로, 이때는 "구현이 기준을
   만족하는가"가 아니라 "기준 자체가 이전 합의·외부 근거와 어긋나지 않는가"를
   판정하고, 비교 가능한 이전 버전이 없으면 `N/A`와 그 사유를 남긴다.
5. 한 finding이 여러 관점에 걸치면 가장 직접적인 owner 하나로 통합하고 다른 관점은 교차 근거만 남긴다.
6. 수정 후 trigger를 다시 판정한다. 새 trigger가 생기면 해당 reviewer를 추가하고, 기존 활성 reviewer는 새 diff로 전부 재실행한다.

## 차단 원칙

- 데이터 손실·복구 불가 migration, 검증되지 않은 공급망 변경, 일반 장애에서 회복 불가, 법적·명시적 개인정보 요구 위반, 명시적 acceptance criteria 위반은 근거가 확정되면 차단한다.
- 정책·법률·제품 의도가 제공되지 않은 영역은 일반론만으로 차단하지 않는다.
- 새 dependency 도입, migration 재설계, 운영 인프라 변경처럼 범위가 커지는 수정은 자동 수행하지 않는다.
