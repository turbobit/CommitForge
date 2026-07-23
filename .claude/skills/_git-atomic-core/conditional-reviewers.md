# 조건부 전문 Reviewer

기본 reviewer에 모든 전문 영역을 항상 추가하지 않는다. 저장소 스캔에서 아래 trigger가 하나라도 확인될 때만 해당 agent를 실행한다. 파일명만이 아니라 diff의 실제 의미를 근거로 판정한다.

`scripts/reviewer_triggers.py`는 경로·명시적 맥락에서 확인 가능한 최소 활성 집합을 제공한다. 이 결과는 reviewer를 빼는 근거가 아니며 main agent의 의미 분석으로 확장한다.

## 활성화 표

| Agent | Trigger |
|---|---|
| `cca-data-migration-reviewer` | schema·migration·ORM model·index·저장 형식·backfill·데이터 변환 |
| `cca-dependency-supply-chain-reviewer` | dependency manifest·lockfile·package registry·CI 권한·Docker base image·artifact provenance |
| `cca-reliability-recovery-reviewer` | queue·job·network·cache·분산 lock·retry·circuit breaker·failover·graceful shutdown |
| `cca-privacy-governance-reviewer` | 개인정보·민감정보·analytics·tracking·consent·retention·export·deletion |
| `cca-requirements-product-reviewer` | 사용자 요구·ticket·ADR·acceptance criteria·API 명세 등 비교 가능한 명시적 기준이 제공됨 |

## 실행 규칙

1. Main agent가 trigger와 관련 파일·hunk를 기록한다.
2. 활성화하지 않은 agent는 실행하지 않고 `N/A`와 비활성화 근거를 reviewer coverage에 기록한다.
3. 활성화한 agent에는 전체 diff와 함께 trigger가 된 정확한 근거를 제공한다.
4. Requirements/Product reviewer는 명시적 기준이 없으면 추측하지 않고 반드시 `N/A`다.
5. 한 finding이 여러 관점에 걸치면 가장 직접적인 owner 하나로 통합하고 다른 관점은 교차 근거만 남긴다.
6. 수정 후 trigger를 다시 판정한다. 새 trigger가 생기면 해당 reviewer를 추가하고, 기존 활성 reviewer는 새 diff로 전부 재실행한다.

## 차단 원칙

- 데이터 손실·복구 불가 migration, 검증되지 않은 공급망 변경, 일반 장애에서 회복 불가, 법적·명시적 개인정보 요구 위반, 명시적 acceptance criteria 위반은 근거가 확정되면 차단한다.
- 정책·법률·제품 의도가 제공되지 않은 영역은 일반론만으로 차단하지 않는다.
- 새 dependency 도입, migration 재설계, 운영 인프라 변경처럼 범위가 커지는 수정은 자동 수행하지 않는다.
