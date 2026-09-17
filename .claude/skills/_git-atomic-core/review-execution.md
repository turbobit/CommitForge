# Reviewer 실행·결과 규약

## 0. 실행 구조 선택

Agent Team은 `/cr`의 source-read-only 실행, `/ccr`, `/cpr`와 `/cca`의
**read-only 리뷰 단계**에서 사용할 수 있다. `/cca`가 이후 수정·검증·staging·
commit으로 이어지더라도 teammate의 권한과 생명주기는 리뷰 단계에서 끝난다.
`/cr --fix`, `/cc`, `/cp`와 그 밖의 실행형 흐름은 기존 custom subagent 구조를
유지한다. 모든 명령에서 lead만 파일·Git·remote 상태를 변경한다.

대상 명령은 reviewer를 시작하기 직전에 다음 도구로 환경 활성 상태를 확인한다.

```bash
python3 "<absolute-CF_CORE>/scripts/agent_team_mode.py"
```

선택 규칙:

1. `--no-team`이면 환경과 무관하게 subagent를 사용한다.
2. `--team`이고 환경 결과의 `enabled=true`이며 팀 coordination 도구를 사용할 수
   있으면 사소한 변경도 기본 3명 Agent Team을 사용한다.
3. `--team`인데 환경이 꺼져 있거나 coordination 도구를 사용할 수 없으면
   subagent로 fallback하고 이유를 보고한다. 환경변수를 직접 변경하지 않는다.
4. 명시 옵션이 없고 `enabled=true`이면 Agent Team을 기본으로 선택하고 Claude
   Code가 요구하는 사용자 승인을 거쳐 생성한다. 승인이 없거나 거절되면
   subagent로 fallback한다.
5. 다음을 **모두** 만족하는 명백히 사소한 변경만 Team 생성을 축소할 수 있다.
   - 변경 파일 2개 이하, 추가+삭제 80줄 이하
   - 단일 package/domain/runtime boundary
   - security, privacy, migration, dependency/supply-chain, reliability,
     concurrency 고위험 trigger 없음
   - cross-file public contract, schema, API, event, shared type 변경 없음
6. 사소하지 않은 변경은 명령과 규모에 무관하게 core 3명을 기본으로 한다.
   규모는 Team 사용 여부가 아니라 shard 수와 조건부 specialist 추가 여부에만
   영향을 준다.

Agent Team 선택 시:

- 별도 team 생성·삭제 도구를 찾지 않는다. 현재 세션의 implicit team에서
  `Agent`로 이름 있는 core teammate 3명을 생성하고 활성 specialist는 환경
  상한 안에서 추가한다.
- 기존 `.claude/agents/cca-*.md` custom agent를 teammate type으로 재사용하고,
  각 teammate prompt에 묶어서 담당할 관점과 정확한 read-only 경계를 명시한다.
- lead가 공유 task를 만들고 owner를 배정한다. teammate는 진행 상태를 갱신하고
  `SendMessage`로 관련 finding과 반론을 peer에게 직접 전달한다.
- 파일 수로 균등 분할하지 않는다. package/domain/runtime boundary로 hunk를
  shard하고, 아래 위험 관점 owner를 겹쳐 배치한다. public contract·schema·API·
  event·shared type·migration은 생산자와 소비자 shard가 함께 검토한다.
- large-diff 공지에서는 shard mode와 Team 인원은 별개임을 밝히고 실제로 초과한
  값과 적용 threshold만 보고한다. 계산하지 않은 값이나 임의 threshold를
  추정하지 않는다.
- 공통 contract·보안 경계처럼 둘 이상의 영역에 걸친 finding은 관련 teammate가
  서로 메시지로 교차검증한 뒤 lead에게 근거와 이견을 함께 반환한다.
- teammate는 source, index, snapshot, lock, branch, remote를 변경하거나 Guard를
  실행하지 않는다. Guard의 획득·검증·종료는 lead만 수행한다.
- 모든 task가 terminal 상태이고 필수 관점 결과가 lead에게 전달된 뒤 teammate를
  종료한다. resume 후 teammate가 복원되지 않으면 미완료 task를 subagent 또는
  lead가 다시 검증한다.
- `/cca`에서는 최초 리뷰 결과가 모두 집계되고 Team이 종료된 것을 확인한 뒤에만
  lead가 수정할 수 있다. teammate가 살아 있거나 미완료 task가 있으면 수정 단계로
  넘어가지 않는다.
- `/cca`에서 lead가 수정하면 이전 Team과 reviewer 상태를 재사용하지 않는다.
  전체 diff fingerprint와 trigger를 다시 계산하고 새 read-only Team을 생성한다.
  core 3명은 새 fingerprint의 전체 diff를 다시 검토하고 specialist만 새 trigger의
  최소 활성 집합으로 다시 구성한다. 이 `Team 리뷰 → 집계·종료 → lead 수정 →
  fingerprint 갱신 → 새 Team 재리뷰` 주기는 `--iterations` 상한까지 반복한다.
- 반복 중 사용자의 종료 예약은 `graceful-stop.md`의 latch와 안전 경계를 적용한다.
  종료 예약 뒤에는 허용된 현재 경계만 완료하고 새 수정·반복·commit을 시작하지 않는다.
- `/cca --no-fix`와 source-read-only 확장 모드는 Team 리뷰·집계 후 수정 단계 없이
  종료한다. staged diff 재리뷰는 lead가 수행하며, 고위험 unit의 관련 reviewer를
  다시 실행하더라도 read-only 경계를 유지한다.
- team 시작·messaging·task coordination이 실패하면 미완료 관점만 subagent로
  fallback한다. `UNKNOWN` 처리와 필수 관점 차단 규칙은 동일하다.

기본 구성:

- `/cr`·`/cpr`와 `/cca`의 read-only 리뷰 단계: 다음 3개 core를 기본으로 사용한다.
  1. **Correctness + Line + State/Concurrency**: 모든 hunk·삭제·예외 경로,
     race·idempotency·resource lifecycle과 fail-open/fail-closed 동작
  2. **Security + Privacy + Supply Chain + Integrity**: authn/authz·입력·암호화·
     secret·데이터 최소화뿐 아니라 설정, transitive dependency, build/CI,
     artifact provenance·SBOM·서명과 software/data integrity
  3. **Architecture + Language/API + Quality + Compatibility**: 경계·의존 방향,
     public contract, 버전별 API 의미, maintainability, backward/forward
     compatibility와 deprecation

  teammate 이름은 각 묶음의 role 키워드를 축약 없이 포함한다. 예:
  `core-correctness-line-state`, `core-security-privacy-supply-chain`,
  `core-architecture-language-quality-compatibility`. 축약하면 §3.5의 관점
  게이트가 역할을 인식하지 못한다.

- 다음 trigger는 core에 억지로 합치지 않고 조건부 specialist로 다룬다.
  - 문서·주석·표시용 metadata만의 변경이 아닌 실행 코드·설정·API·schema·bug
    fix·refactoring: **Testing/Independent Verification** 필수
  - I/O·async·queue·network·cache·retry·timeout·resource·분산 상태:
    **Performance/Reliability/Observability/Operability**, traces/metrics/logs의
    correlation·alert·민감정보 비노출
  - listener/timer/subscription·장기 실행 프로세스·대형 렌더·동기 blocking:
    **자원 고갈과 응답성**. 메모리 누수와 무한 증가, CPU 점유와 stuck,
    main thread·event loop 정지를 "느린 코드"와 구분해 판정한다. 상세 항목은
    `cca-performance-reviewer`가 보유한다.
  - UI 변경: **UX/Accessibility**, WCAG 2.2, 사용자 흐름
  - schema·저장 형식 변경: **Data/Migration**, backfill·부분 배포·rollback
  - 비교 가능한 ticket·ADR·명세: **Requirements/Product**, acceptance criterion
  - CI/CD·infra·feature flag·배포 순서 변경:
    **Release/Deployment/Rollback** → `cca-release-deployment-reviewer`
  - Flutter·React·DB·암호화·결제·분산 시스템 등 전문 기술:
    **Domain/Framework** → 전용 agent가 없다. `cca-language-api-reviewer`가
    언어·프레임워크 의미를 맡고, 그것으로 덮이지 않는 도메인 지식은 lead가 직접
    수행한다. 어느 쪽이든 관점 상태를 기록하며, 수행하지 못하면 `UNKNOWN`이다.
- 각 specialist는 `ACTIVE`, 근거 있는 `N/A`, `UNKNOWN` 중 하나를 기록한다.
  활성 specialist를 환경 상한 때문에 추가할 수 없으면 가장 가까운 core owner와
  lead가 해당 관점을 명시적으로 교차검증한다. 그것도 완료하지 못하면
  `UNKNOWN`으로 성공을 차단하며 조용히 생략하지 않는다.
- `/cpr`은 Release/Deployment/Rollback trigger를 항상 평가하고 build pipeline,
  artifact provenance, 호환성, migration 순서, rollback과 관찰 가능성을
  관련 core와 조건부 specialist가 교차검증한다.
- `/ccr`: Git/Atomicity, Architecture+Dependencies, Correctness+Testing의 3개
  묶음을 고정 기본으로 사용한다. multi-domain은 인원을 늘리는 대신 domain shard와
  cross-file dependency task를 세 owner에게 배정한다.

이 구성은 security를 단순 취약 dependency 검사로 축소하지 않고 전체 공급망과
무결성까지 보며, logging을 “로그가 있음”이 아니라 실제 correlation·alert·대응
가능성으로 판정한다. 자동 생성 코드나 reviewer 제안도 신뢰 신호로 취급하지
않고 실제 코드 경로, contract와 독립 검증 증거로 재판정한다.

## 1. 실행 단계

1. 동일 fingerprint에서 변경 경로와 의미를 triage한다.
2. `/cr` 기본 10개 또는 `/cca` 기본 11개 reviewer를 준비한다.
3. `reviewer_triggers.py` 결과를 조건부 reviewer의 **최소 활성 집합**으로 사용한다.
4. 코드 의미에서 추가 trigger가 확인되면 reviewer를 더 활성화한다. 스크립트가 비활성이라고 판정해도 의미 근거가 있으면 생략하지 않는다.
5. 동시 실행 수를 정한다. `.commitforge/review.yml`에 `max_parallel`이 있으면 **그
   값이 상한이다.** 없으면 기본 동시 실행 목표는 6개 agent다. 어느 경우든 현재
   Claude Code의 유효 concurrency 상한이 더 낮으면 그 값을 따른다.
   `review-policy.md`의 "기본 4"는 `review.yml`을 **작성할 때 권장하는 값**이지
   정책 파일이 없는 저장소의 기본값이 아니다.
6. 고위험 또는 대형 diff이고 독립 reviewer가 충분하면 최대 8개까지 병렬 실행한다.
   `max_parallel`이 지정돼 있으면 그 값을 넘지 않고, 환경 상한도 초과하지 않는다.
7. 429, 일시적 제한, agent 시작 실패 또는 반복 timeout이 발생하면 다음 batch를 3~4개로 축소하고 실패 관점은 한 번만 재시도한다.
8. 남은 reviewer는 축소된 batch로 이어서 실행하며 필수 관점을 생략하지 않는다.
9. 수정 후 이전 결과를 폐기하고 fingerprint·trigger·활성 reviewer를 다시 계산한다.

## 1.5 Reviewer 입력 전달

Reviewer에게 diff·log·맥락을 넘기는 방법은 둘뿐이다.

1. agent prompt에 직접 담는다. 이것이 기본이다.
2. 그대로 담기에 너무 크면 파일로 떨구고 **경로**를 넘긴다.

2번의 중간 파일은 **Guard snapshot 아래 `agent-input/` 하위 디렉터리에만** 만든다.
snapshot 절대경로는 `begin` 응답의 `snapshot`이며 각 skill이 시작 시 보관한다.

```bash
mkdir -p "<snapshot>/agent-input"
git diff --binary > "<snapshot>/agent-input/working.diff"
```

- `/tmp`, `/var/tmp`, `$TMPDIR`, 홈 디렉터리, 저장소 작업 트리에는 만들지 않는다.
  snapshot 이름은 `<timestamp>-<session>-<random>`이라 저장소·세션마다 반드시 다르지만,
  시스템 temp 아래의 경로를 mode 이름이나 저장소 이름으로 지으면 **여러 저장소가 같은
  값을 고른다.** mode에서 파생한 `/tmp/cr3days/ui.diff` 같은 이름이 전형적인 예다.
- 경로가 겹쳐도 **오류는 나지 않는다.** 다른 저장소가 덮어쓴 파일이 그대로 읽히고
  reviewer만 엉뚱한 코드를 본다. 원장 분모는 실제 `git diff`로 만들어지므로 정상적으로
  채워지고, 관점 게이트도 통과하며, Guard의 source-read-only fingerprint는 Git 상태만
  비교하므로 이 경로를 감시하지 않는다. 어느 층에서도 걸리지 않는 조용한 오염이다.
- 파일은 snapshot **root가 아니라 하위 디렉터리**에 둔다. `finish`의 snapshot 감사는
  root의 파일 목록을 checksum inventory와 대조하므로 root에 추가한 파일은 `unexpected`로
  성공을 차단한다. 하위 디렉터리는 감사 대상이 아니다. `ledger/`와 같은 위치다.
- 별도 정리는 하지 않는다. `finish`가 snapshot을 재귀 삭제하며 함께 사라지고,
  `abort`나 `--keep-snapshot`이면 리뷰 근거와 함께 보존된다.
- 작업 트리에 만들면 `--source-read-only` 검증이 untracked 변경으로 잡아 정상 리뷰를
  실패시킨다. `.gitignore`로 가리는 방법으로 우회하지 않는다.
- 파일로 넘기더라도 reviewer는 여전히 read-only다. agent에 쓰기 권한이나 Bash를 주는
  근거가 되지 않는다.

## 2. 필수성과 실패 정책

- 필수: Line, Correctness, Security. `/cr`은 여기에 Architecture(계약·호환성)와
  Performance를 더한 5개다. 집합은 원장을 만든 skill이 결정하며 `ledger.py`의
  `REQUIRED_REVIEWER_ROLES`가 정본이다.
- 변경 유형상 활성화된 조건부 reviewer도 해당 변경에서는 필수
- agent 시작 실패·timeout·turn 소진 시 main agent가 같은 관점을 직접 수행한다.
- fallback도 완료하지 못하면 해당 관점은 `UNKNOWN`이며 성공 또는 commit을 차단한다.
- 선택 관점을 조용히 누락하지 않는다. `PASS`, `FINDING`, `N_A`, `UNKNOWN` 중 하나를 기록한다.
- 필수 3개 관점은 문서 규칙에 그치지 않고 원장 게이트가 강제한다. 분모가 비어 있지
  않은 실행에서 세 관점 중 하나라도 기록이 없으면 `ledger_reviewer_missing`,
  `UNKNOWN`이면 `ledger_reviewer_unknown`으로 `finish`와 `verify-review`가
  차단된다. 관점은 역할 키워드로 해석하므로 Agent Team의 묶음 teammate 이름도
  그대로 인정된다. 기록 방법은 이 문서 §3.5를 따른다.
- reviewer `status`는 `ACTIVE`, `N_A`, `UNKNOWN`만 허용한다. hunk 판정과 마찬가지로
  `N/A` 철자는 `ledger_invalid_reviewer_status`로 batch 전체가 거부된다.
- `UNKNOWN`은 `N_A`가 아니다. 적용되지 않는다는 근거가 있을 때만 `N_A`다.
- hunk 판정의 철자는 `N_A`다. 원장은 `N/A`를 `ledger_invalid_verdict`로 거부하며,
  거부는 batch 전체를 버리므로 같은 batch의 `PASS`도 함께 사라진다. reviewer 산문에
  쓰는 “해당 없음”의 `N/A`와 혼동하지 않는다.

## 3. Finding 공통 스키마

Main agent는 reviewer 출력을 다음 필드로 정규화한다.

```json
{
  "id": "reviewer:file:symbol-or-hunk:category",
  "reviewer": "cca-correctness-reviewer",
  "fingerprint": "현재 diff fingerprint",
  "severity": "CRITICAL|MAJOR|MINOR|NOTE",
  "status": "OPEN|FIXED|REJECTED|N_A|UNKNOWN|BASELINED|STALE",
  "confidence": 8,
  "verification": "ISOLATED|SELF|UNVERIFIED",
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
- `severity`와 `status`의 허용값은 `ledger.py`의 `FINDING_SEVERITIES`·
  `FINDING_STATUSES`, `report_validator.py`의 `SEVERITIES`·`STATUSES`와 정확히
  같아야 한다. 원장은 finding을 기록하는 곳이고 validator는 내보낸 JSON/SARIF를
  검사하는 곳이라, 한쪽만 아는 값이 생기면 기록은 되지만 내보낼 수 없는 리뷰가
  된다. `BASELINED`는 `baseline-and-suppressions.md`가 붙이는 상태이므로 이
  목록에서 빠뜨리지 않는다.
- `confidence`는 1~10 정수다. reviewer가 매기고 §3.6의 검증이 갱신한다.
  5 이하는 reviewer가 애초에 보고하지 않는다. 등급 기준은 §3.1이다.
- `verification`은 §3.6의 검증 경로를 기록한다. reviewer는 이 필드를 채우지 않고
  lead가 검증 후에 쓴다.
- `category`는 소문자 snake_case로 쓰고 같은 실행 안에서 일관되게 유지한다.
  reviewer agent가 통제 어휘를 제시하면 그것을 따른다. 이 값은 `id`의 마지막
  segment로 들어가고 그 `id`가 SARIF의 `ruleId`가 되므로 자유 문장이나 공백을
  넣지 않는다.
- secret·개인정보 값은 필드에 복사하지 않는다.
- 정확한 위치가 없으면 finding이 아니라 조사 항목으로 분리한다.
- 수정 후 fingerprint가 바뀌면 기존 finding을 새 결과로 덮지 않고 `FIXED` 또는 `STALE`로 연결한다.
- 이 스키마가 곧 원장의 finding 레코드다. 별도 스키마를 만들지 않고
  `ledger.py record`의 `findings` 배열에 그대로 넣는다.
- `FINDING` 판정에는 대응하는 finding의 `id`를 verdict의 `finding_ids` 배열에
  넣어야 한다. 비어 있으면 `ledger_finding_missing`으로 batch 전체가 거부된다.
- 원장에 쓰는 주체는 lead뿐이다. teammate와 reviewer subagent는 결과를 lead에게
  반환하고, lead가 수신 즉시 적재한다.
- `cca-*` reviewer agent에 Bash를 부여하지 않는다. 읽기 전용 경계이자 원장의
  단일 writer를 보장하는 조건이다.

## 3.1 Confidence 등급 기준

`confidence`는 모든 reviewer가 같은 자로 매겨야 한다. §3.6의 임계값
(`confidence_threshold`, 기본 8)은 reviewer를 가리지 않고 적용되므로, reviewer마다
기준이 다르면 같은 8이 어떤 관점에서는 확정이고 어떤 관점에서는 짐작이 되어
임계값이 의미를 잃는다.

| 등급 | 기준 |
|---|---|
| 9~10 | 문제가 발생하는 경로를 코드에서 끝까지 짚을 수 있다 |
| 8 | 알려진 결함 패턴이고 도달 경로가 확인된다 |
| 6~7 | 특정 조건·설정·입력에서만 성립한다 |
| 5 이하 | 추측이다. **보고하지 않는다.** |

- 관점별 reviewer는 이 표를 자기 영역의 용어로 구체화할 수 있지만 등급의 의미를
  바꾸지 않는다. 예를 들어 Security의 9~10은 "공격 경로를 끝까지 짚을 수 있다"이고
  Correctness의 9~10은 "실패하는 입력과 그 결과를 짚을 수 있다"이다.
- **확신과 심각도는 다른 축이다.** 확신이 낮다고 심각도를 낮추지 않고, 심각도가
  높다고 확신을 올리지 않는다. 확신이 모자라면 등급을 낮추는 것이 아니라 보고하지
  않는 것이 맞다.
- 6~7로 보고할 때는 성립 조건을 `evidence`에 명시한다. 조건을 적지 못하면 그것은
  6~7이 아니라 5 이하다.

## 3.5 Reviewer 관점 기록

hunk 분모는 "누가 봤는지"를 표현하지 못한다. reviewer 하나가 모든 hunk를 `PASS`로
채우면 분모는 가득 차지만 Correctness와 Security는 한 번도 돌지 않았을 수 있다.
그래서 관점은 별도 축으로 기록하고 게이트가 따로 확인한다.

- `reviewers`의 `status`는 `ACTIVE`, `N_A`, `UNKNOWN`만 허용한다. `N/A` 철자는
  `ledger_invalid_reviewer_status`로 **batch 전체**가 거부된다. verdict와 같은 함정이다.
- 필수 관점은 매 실행에서 반드시 기록한다. 하나라도 없으면
  `ledger_reviewer_missing`, `UNKNOWN`이면 `ledger_reviewer_unknown`으로
  `finish`와 `verify-review`가 차단된다. 기본 집합은 **Line, Correctness,
  Security**이고 `/cr`은 **Architecture, Performance**를 더한 5개다. 어느
  집합인지는 `init --skill`이 저장한 값이 결정한다.
- 관점 판정은 agent 파일명이 아니라 **이름에 포함된 역할 키워드**로 해석한다.
  Agent Team의 `core-correctness-line-state` 같은 teammate 하나가 두 역할을 함께
  만족시킬 수 있다.
- **role 키워드는 축약하지 않는다.** 매칭이 부분일치이므로 `architecture`를
  `arch`로 줄인 `core-arch-lang-quality`는 그 역할을 만족시키지 못하고, 제대로
  수행한 리뷰가 `ledger_reviewer_missing`으로 차단된다. teammate 이름에는
  `line`, `correctness`, `security`, `architecture`, `performance`를 철자 그대로
  포함한다.
- **같은 이름**을 다시 기록하면 나중 값이 이긴다. 시작에 실패해 `UNKNOWN`이던
  reviewer가 재시도에 성공하면 `ACTIVE`로 다시 기록해 해소한다.
- **다른 이름**이 같은 역할을 덮으면 가장 나쁜 상태가 채택된다.
  `cca-security-reviewer`가 `ACTIVE`여도 `core-security-sweep`이 `UNKNOWN`이면
  그 역할은 `UNKNOWN`이다. 한 관점을 나눠 맡았으면 가장 약한 기록만큼만 해소된 것이다.
- 비활성 조건부 reviewer는 `N_A`로 기록한다. `reviewer_triggers.py`의 `inactive`
  목록이 그 출발점이며, 비활성 목록을 기억으로 나열하지 않는다.
- 적용 대상이 없어 `N_A`인 경우와, 확인하지 못해 `UNKNOWN`인 경우를 섞지 않는다.
  `UNKNOWN`은 성공을 차단하는 상태이고 `N_A`는 근거 있는 종결이다.
- 분모가 비어 있는 실행(변경 없음)에는 관점 게이트를 적용하지 않는다. 빈 리뷰의
  "검토 대상 없음" 종료는 그대로 유지된다.

```bash
python3 "<absolute-CF_CORE>/scripts/ledger.py" record \
  --session "$COMMITFORGE_SESSION_ID" <<'JSON'
{"verdicts": [],
 "reviewers": [{"name": "cca-line-reviewer", "status": "ACTIVE"},
               {"name": "cca-correctness-reviewer", "status": "ACTIVE"},
               {"name": "cca-security-reviewer", "status": "ACTIVE"},
               {"name": "cca-data-migration-reviewer", "status": "N_A"}]}
JSON
```

## 3.6 Finding 격리 검증

탐지자가 자기 주장을 스스로 심사하면 이미 내린 결론을 정당화하는 쪽으로 기운다.
그래서 검증은 **탐지와 분리된 단계**이며, 검증자는 그 finding이 어떻게 나왔는지
모르는 상태에서 판정한다.

### 대상

`blocking_severity`(기본 `MAJOR`) 이상인 finding만 검증한다. 모든 finding을
검증하면 reviewer 수만큼 비용이 곱해진다. 그 미만은 reviewer가 매긴 `confidence`를
그대로 쓰고 `verification`은 `UNVERIFIED`다.

### 입력 제한

검증자에게 주는 것은 셋뿐이다.

1. finding 진술(위치, category, severity, failure scenario)
2. 해당 코드와 필요한 호출자
3. 그 관점의 보고 제외 규칙과 precedent

**탐지 단계의 추론 과정은 넘기지 않는다.** 근거 문단을 그대로 전달하면 격리가
깨진다. 검증자는 "이 주장이 코드에서 성립하는가"만 새로 판정하고 `confidence`를
1~10으로 반환한다.

### 실행 형태

환경에 따라 아래 순서로 강등한다. 가능한 가장 높은 단계를 쓴다.

| 조건 | 형태 | `verification` |
|---|---|---|
| Agent Team 활성 | 탐지하지 않은 teammate에게 검증 task 배정 | `ISOLATED` |
| subagent 실행 가능 | finding별 병렬 subagent | `ISOLATED` |
| 둘 다 불가 | lead가 별도 pass로 판정 | `SELF` |

`SELF` pass에서도 입력 제한은 유지한다. 탐지 근거를 다시 읽지 않고 finding 진술과
코드만 새로 확인한다. 완전한 격리가 아니므로 **최종 보고에 `SELF`로 검증한 finding
수를 표시한다.** 가장 약한 경로가 가장 강한 경로와 같아 보이게 보고하지 않는다.

검증 자체를 완료하지 못하면 `UNVERIFIED`다. 조용히 통과시키지 않고 그 수를 보고한다.

### 판정 반영

- `confidence`가 임계값(`.commitforge/review.yml`의 `confidence_threshold`, 기본 8)
  미만이면 `status`를 `REJECTED`로 바꾼다.
- `REJECTED` finding을 **삭제하지 않는다.** baseline 처리와 같은 원칙이다.
  기록은 남기고 상태만 바꾸며, 차단 판단에서만 제외한다.
- `REJECTED`로 바뀌어 그 hunk에 남은 finding이 없으면 hunk 판정을 `FINDING`에서
  `PASS`로 되돌릴 수 있다. 근거를 함께 기록한다.
- 검증이 severity를 낮추자고 판단해도 자동 적용하지 않는다. §4와 같이 lead가 실제
  영향으로 재판정한다.

### 수정 후

`cr/SKILL.md` §4의 `advance`로 세대를 전이하면 이전 검증 결과도 함께 무효다. 새
세대의 finding은 다시 검증한다. 이전 세대의 `REJECTED`를 근거로 같은 finding을
재검증 없이 기각하지 않는다.

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
- §3.6 검증 결과: `ISOLATED`·`SELF`·`UNVERIFIED` finding 수와 `REJECTED` 수.
  `ledger.py report`의 `verification`에서 가져온다. `SELF`와 `UNVERIFIED`가 있으면
  그 이유를 함께 적는다.

을 최종 보고에 포함한다.
