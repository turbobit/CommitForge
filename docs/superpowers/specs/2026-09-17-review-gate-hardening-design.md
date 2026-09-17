# 리뷰 게이트 강화 설계 — 관점 강제 확장과 명령어별 role 매핑

- 작성일: 2026-09-17
- 상태: 검토 대기
- 범위: 리뷰 커버리지 갭 4건(A)과 명령어별 필수 role 매핑 구조(B)
- 비목표: `/cca`·`/cpr`·`/cp`·`/ccr`에 원장을 도입하는 것. 후속 과제로 §7에 분리한다.

## 1. 배경

`/cr` 등 리뷰 명령어가 정확성·보안·신뢰성/성능·계약 위험을 실제로 검사하는지 조사한 결과, 네 항목 모두 문서와 agent 정의 수준에서는 명시적으로 커버되고 있었다. 실질적 차이는 **기계 강제 여부**였다.

조사 중 원래 예상보다 큰 비대칭이 하나 더 확인됐다. **원장(ledger)은 `/cr` 전용이다.** `/cca`·`/cpr`·`/cp`·`/ccr`은 `ledger.py`를 전혀 호출하지 않으며, `cr/SKILL.md:444`가 "원장을 만들지 않는 `/cpr`·`/cca`"로 이를 명시한다. 유일한 기계 강제 지점인 `REQUIRED_REVIEWER_ROLES`가 `/cr`에만 걸리므로, **실제로 커밋을 만드는 `/cca`는 정확성·보안조차 기계 강제가 없다.**

이 설계는 갭 4건을 닫고, 나머지 명령어가 원장에 올라탈 수 있는 구조까지만 만든다.

### 확인된 갭

| # | 갭 | 근거 |
|---|---|---|
| 1 | `/cpr`·`/cp`에 심각도 정의가 없다 | `review-gates.md`는 `/cr`(`cr/SKILL.md:111`)과 `/cca`(`cca/SKILL.md:89`)만 로드한다. `/cpr`·`/cp`는 `pull-request-workflow.md:124`로 "CRITICAL/MAJOR 차단" 규칙은 갖지만, 무엇이 CRITICAL인지 정의한 `review-gates.md` §2를 읽지 않는다 |
| 2 | 성능·계약 위험이 기계 강제 밖이다 | `ledger.py:46`의 `REQUIRED_REVIEWER_ROLES`가 `("line", "correctness", "security")`뿐이다. Performance가 `N_A`로 기록되면 게이트를 통과한다 |
| 3 | `confidence_threshold` 기각 금지 목록이 보안 편향이다 | `review-policy.md:44-45`가 secret·인증인가·데이터 손실만 보호한다. 목록이 피해 유형이 아니라 보안 카테고리처럼 읽힌다 |
| 4 | trigger 경로 패턴이 복수형·스키마 파일을 놓친다 | `reviewer_triggers.py:24`의 `(migrations?\|schema\|prisma)`는 `schema`만 있고 복수형이 없다. 실측: `src/schemas/user.py` → 미탐지, `src/schema/user.py` → 탐지 |

## 2. 목표와 비목표

### 목표

- `/cr`에서 계약 위험과 성능 관점을 **기계적으로 강제**한다. 조용한 생략을 명시적 `N_A` 판단으로 바꾼다.
- 필수 role 집합을 **명령어별로 선언할 수 있는 구조**를 만든다. 후속 과제가 구조 변경 없이 올라탈 수 있어야 한다.
- `/cpr`·`/cp`가 심각도를 정의된 기준으로 판정하게 한다.
- 기각 금지 목록을 reviewer가 아니라 **피해 유형**으로 판정하게 한다.

### 비목표

- `/cca`·`/cpr`·`/cp`·`/ccr`의 원장 도입. §7의 후속 과제다.
- `confidence_threshold`의 코드 구현. 현재 이 값은 스크립트에 구현이 없고(`ledger.py`는 `confidence`가 1~10 정수인지만 검증한다, `ledger.py:1282-1301`) §3.6의 격리 검증은 전부 모델 지시문이다. 이 설계는 그 구조를 바꾸지 않고 지시문만 정정한다.
- 원장 스키마 변경. `--skill` 필드 추가는 기존 원장과 호환된다.

## 3. 설계

### 3.1 B — 명령어별 role 매핑

`REQUIRED_REVIEWER_ROLES`를 튜플에서 skill별 dict로 바꾼다.

```python
REQUIRED_REVIEWER_ROLES: dict[str, tuple[str, ...]] = {
    "cr": ("line", "correctness", "security", "architecture", "performance"),
}

DEFAULT_REVIEWER_ROLES = ("line", "correctness", "security")
```

**플래그 이름은 `--skill`이다.** `--command`는 쓸 수 없다. `ledger.py:1448`이 서브파서에 `dest="command"`를 이미 사용하므로 `args.command`가 충돌한다.

- `ledger.py init`이 `--skill <name>`을 받아 원장 데이터에 `"skill": "cr"`로 저장한다.
- `coverage()`가 저장된 값으로 role 집합을 조회한다. 값이 없거나 매핑에 없는 이름이면 `DEFAULT_REVIEWER_ROLES`로 폴백한다.
- `reviewer_roles()`가 고정 상수 대신 조회된 집합을 받는다.

`guard.py`는 변경하지 않는다. `coverage()` 결과의 `reviewer_roles_missing`·`reviewer_roles_unknown`만 읽으므로(`guard.py:1342-1345`, `:1423`) 매핑이 `ledger.py` 안에서 끝난다.

**이번 사이클에는 `cr` 항목만 채운다.** 원장을 만들지도 않는 명령어의 role 집합을 지금 채우면 end-to-end로 검증할 수 없는 설정이 된다. 후속 과제가 자기 항목을 추가한다.

폴백이 `DEFAULT_REVIEWER_ROLES`인 이유는 기존 원장과의 호환이다. `skill` 필드가 없는 원장은 `/cr`이 만든 것이지만, 이 경우 기존 3개 role만 요구하는 쪽이 안전하다. 강제가 갑자기 늘어 진행 중이던 리뷰가 차단되는 것보다, 다음 실행부터 5개가 적용되는 쪽이 낫다.

### 3.2 갭 2 — `/cr`의 role 확장

`architecture`가 계약·호환성을 소유한다. 이 키워드는 `cca-architecture-reviewer`와 Agent Team core 3번(`review-execution.md:83-85`의 "Architecture + Language/API + Quality + Compatibility")에 모두 매칭되므로 새 agent 파일이나 이름 변경이 필요 없다.

다만 강제되는 이름과 실제 검토 내용을 일치시켜야 한다. `cca-architecture-reviewer.md`의 검토 항목에 다음을 명시적으로 보강한다.

- 하위 호환성을 깨는 public contract 변경과 그 소비자
- 기본값·feature flag 기본 상태 변경이 기존 배포에 미치는 영향
- schema·저장 형식 변경에 필요한 migration 누락

성능 차원이 없는 diff(문서 전용 등)에서는 lead가 `performance: N_A`를 근거와 함께 기록한다. 이것이 부담이 아니라 의도된 동작이다. 지금 조용히 생략되는 관점을 명시적 판단으로 바꾸는 것이 이 갭의 목적이다. 변경이 없는 실행은 `guard.py:1341`의 `if summary["total"]:`가 게이트 자체를 건너뛰므로 영향받지 않는다.

#### 이름 축약 회귀 위험

role은 reviewer **이름의 부분일치**로 판정한다(`ledger.py:946-977`). Agent Team에서 lead가 core 3을 `core-arch-lang-quality`처럼 줄여 이름 지으면 `"architecture"`가 매칭되지 않아, 제대로 수행한 리뷰가 `ledger_reviewer_missing`으로 차단된다. `line`·`correctness`·`security`는 축약할 일이 드물어 지금까지 드러나지 않았지만 `architecture`는 `arch`로 줄이기 쉽다.

**대응: 규약 명시.** `review-execution.md` §3.5에 "필수 role 키워드는 축약 없이 이름에 그대로 포함한다"를 추가하고, §0 core 3의 예시 이름을 박아둔다.

alias 테이블(`arch` → `architecture`)은 채택하지 않는다. lead의 이름 자유도는 높아지지만 인정할 축약 목록이 계속 늘고, 매칭 로직에 오탐 경로가 생긴다. 규칙을 한 곳에 두고 매칭은 단순하게 유지하는 쪽이 낫다.

### 3.3 갭 1 — `/cpr`·`/cp`의 심각도 정의

`/cpr`·`/cp`는 `pull-request-workflow.md:124`로 "CRITICAL/MAJOR, secret, 데이터 손실, 인증 우회, 미검토 hunk, 필수 reviewer `UNKNOWN`: 차단"이라는 규칙을 이미 갖고 있다. 없는 것은 **무엇이 CRITICAL이고 MAJOR인지의 정의**이며, 그것은 `review-gates.md` §2에 있다.

- `cpr/SKILL.md`와 `cp/SKILL.md`의 필수 규칙 목록에 `review-gates.md`를 추가한다.
- `review-gates.md`의 제목에서 명령어 한정을 제거하고, 문서 첫머리에 섹션별 적용 범위를 명시한다. §1~§3은 모든 리뷰 명령어에 적용되고, §5는 `/cr` 완료 Gate, §6은 `/cca` Commit Gate로 명령어 한정이다.
- `README.md:13`의 "`review-gates.md`: `/cr`·`/cca` 품질 gate" 설명을 실제 범위에 맞게 고친다.

`/cpr`·`/cp`용 §7 readiness 매핑은 만들지 않는다. `pull-request-workflow.md:124`가 이미 차단 조건을 정의하므로 중복이다.

### 3.4 갭 3 — 기각 금지 목록을 피해 유형으로 재정의

현재 `review-policy.md:44-45`는 secret·인증인가·데이터 손실을 보호한다. 문제는 이 목록이 **보안 카테고리처럼 읽힌다**는 점이다. 그래서 performance reviewer가 찾은 데이터 손실은 보호되는지 불분명하고, 계약 위험은 아무 보호가 없다.

목록의 실제 원리는 **되돌릴 수 없는 피해**다. 이것을 명시하고 두 항목을 추가한다.

- 판정 기준이 reviewer가 아니라 **피해 유형**임을 명시한다. performance reviewer가 찾은 데이터 손실도 보호되고, security reviewer가 찾은 저영향 finding은 보호되지 않는다.
- 추가: 복구 불가능한 migration·데이터 변환(`review-gates.md` §2 CRITICAL의 "잘못된 migration으로 복구 곤란한 상태"와 같은 기준)
- 추가: 재시작 없이 회복되지 않는 자원 고갈(`cca-performance-reviewer.md:46`의 "heap 증가가 OOM·강제 재시작으로 이어지는 경로")

**하위 호환성 파괴는 추가하지 않는다.** rollback으로 회복 가능하므로 "되돌릴 수 없는 피해" 기준에 들지 않는다. 목록을 더 넓히면 `confidence_threshold`가 무의미해져 잡음 억제 기능을 잃는다. 이 제외 근거를 문서에 함께 남긴다.

### 3.5 갭 4 — trigger 경로 패턴

실측으로 확인한 미탐지 사례에 대응한다.

| 경로 | 현재 | 원인 |
|---|---|---|
| `src/schemas/user.py` | 미탐지 | `schema`에 복수형이 없다 |
| `api/user.proto` | 미탐지 | 스키마 정의 파일 확장자가 없다 |
| `config/storage-format.yaml` | 미탐지 | 저장 형식 신호가 없다 |

`cca-data-migration-reviewer`의 패턴을 다음과 같이 고친다.

- `(^|/)(migrations?|schemas?|prisma)(/|$)` — 복수형 허용
- `\.(sql|ddl|proto|avsc)$` — 스키마 정의 파일 추가
- `(storage[-_]?format)` — 저장 형식 변경 신호

**실측된 미탐지 사례에만 대응하고 그 이상은 넣지 않는다.** 예를 들어 `serializ`(serializer·serialization) 같은 넓은 패턴은 후보로 검토했으나 채택하지 않았다. 측정된 누락 사례가 없고, serialization key 변경은 이미 필수 관점인 Line이 담당한다(`deep-review-protocol.md:44`의 "public symbol, API field, enum case, serialization key").

`reviewer_triggers.py`의 docstring이 명시하듯 이 결과는 하한선(floor)이고 의미 기반 확장은 lead의 몫이다. 과도한 패턴은 조건부 reviewer를 불필요하게 활성화해 비용만 늘린다.

## 4. 변경 파일

| 파일 | 변경 |
|---|---|
| `.claude/skills/_git-atomic-core/scripts/ledger.py` | role 매핑 dict, `--skill` 플래그, `coverage()` 조회, `reviewer_roles()` 시그니처 |
| `.claude/skills/_git-atomic-core/scripts/reviewer_triggers.py` | data-migration 패턴 3건 |
| `.claude/skills/cr/SKILL.md` | `ledger.py init`에 `--skill cr` 전달 |
| `.claude/skills/cpr/SKILL.md` | 필수 규칙에 `review-gates.md` 추가 |
| `.claude/skills/cp/SKILL.md` | 필수 규칙에 `review-gates.md` 추가 |
| `.claude/skills/_git-atomic-core/review-gates.md` | 제목·적용 범위 명시 |
| `.claude/skills/_git-atomic-core/review-execution.md` | §3.5 이름 축약 금지 규약, §0 core 3 예시 이름 |
| `.claude/skills/_git-atomic-core/review-policy.md` | 기각 금지 목록 재정의 |
| `.claude/skills/_git-atomic-core/README.md` | `review-gates.md` 범위 설명 |
| `.claude/agents/cca-architecture-reviewer.md` | 계약 위험 검토 항목 보강 |
| `tests/test_ledger.py` | role 단언 갱신, `--skill` 케이스 추가 |
| `tests/test_reviewer_triggers.py` | 미탐지 3건 회귀 테스트 |
| `MANIFEST.json`, `checksums.sha256` | `python3 release.py`로 재생성 |

## 5. 테스트

**기존 테스트는 수정하지 않는다.** `ReviewerCoverageGateTest.prepared()`가 `init`에 `--skill`을 넘기지 않으므로 §3.1의 폴백 경로를 타고, `tests/test_ledger.py:1858`의 `["correctness", "line", "security"]` 단언이 그대로 성립한다. 이는 하위 호환 설계가 의도대로 동작한다는 증거이기도 하므로, 기존 단언을 그대로 두는 것 자체가 회귀 테스트다.

새 role 집합은 `--skill cr`을 명시하는 별도 테스트 클래스에서 검증한다.

추가할 테스트:

- `--skill cr`로 init한 원장이 5개 role을 요구한다
- `--skill` 없이 init한 원장이 기존 3개 role만 요구한다(하위 호환)
- 매핑에 없는 `--skill` 값이 기본값으로 폴백한다
- `architecture`·`performance` 누락이 `ledger_reviewer_missing`을 낸다
- `core-architecture-language-quality-compatibility`라는 Agent Team 이름이 `architecture` role을 만족한다
- 분모가 빈 실행은 role이 늘어도 여전히 통과한다
- trigger 미탐지 3건이 활성화된다
- `python3 release.py --check`가 통과한다

## 6. 회귀 위험

| 위험 | 대응 |
|---|---|
| 이름 축약으로 정상 리뷰가 차단된다 | §3.2의 규약 명시. Agent Team 이름 테스트로 고정 |
| 진행 중이던 기존 원장이 갑자기 차단된다 | `skill` 필드 없으면 기존 3개 role로 폴백(§3.1) |
| 성능 관점 강제가 문서 변경에서 마찰을 만든다 | `N_A` 경로가 정상이며 빈 분모는 게이트를 건너뛴다 |
| trigger 패턴 확대가 오탐을 늘린다 | 패턴을 보수적으로 유지하고 각 패턴에 회귀 테스트를 붙인다 |

## 7. 후속 과제

이번 범위에서 제외했다. 각각 자기 스펙과 계획을 갖는다.

- **C. `/cca` 원장 도입.** 가장 복잡하다. 원장의 세대 모델(`advance`는 fingerprint 변화에 반응)은 `/cr`의 `리뷰 → 수정 → 재리뷰` 루프용이다. `/cca`는 staging과 commit이 붙어 실행 중 HEAD와 staged fingerprint가 의도적으로 바뀌고 `verify-review --source-read-only`가 적용되지 않는다. "원장을 staging 전에 닫는가, 커밋별 scope로 추적하는가"를 먼저 정해야 한다.
- **D. `/cpr`·`/cp` 원장 도입.** 둘 다 read-only이고 committed range만 보므로 `range:<A>..<B>` scope(`cr/SKILL.md:258`)를 재사용할 수 있다. C보다 기계적이다.
- **E. `/ccr` 원장 도입.** `/ccr`의 관점 구성은 Git/Atomicity, Architecture+Dependencies, Correctness+Testing이고 **Security가 core에 없다**(`review-execution.md:113-115`). 원장을 도입하면 security를 필수로 할지, 현재 구성을 인정할지 결정해야 한다.
