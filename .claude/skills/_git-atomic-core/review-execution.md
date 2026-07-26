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

- 다음 trigger는 core에 억지로 합치지 않고 조건부 specialist로 다룬다.
  - 문서·주석·표시용 metadata만의 변경이 아닌 실행 코드·설정·API·schema·bug
    fix·refactoring: **Testing/Independent Verification** 필수
  - I/O·async·queue·network·cache·retry·timeout·resource·분산 상태:
    **Performance/Reliability/Observability/Operability**, traces/metrics/logs의
    correlation·alert·민감정보 비노출
  - UI 변경: **UX/Accessibility**, WCAG 2.2, 사용자 흐름
  - schema·저장 형식 변경: **Data/Migration**, backfill·부분 배포·rollback
  - 비교 가능한 ticket·ADR·명세: **Requirements/Product**, acceptance criterion
  - CI/CD·infra·feature flag·배포 순서 변경:
    **Release/Deployment/Rollback**
  - Flutter·React·DB·암호화·결제·분산 시스템 등 전문 기술:
    **Domain/Framework**
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
