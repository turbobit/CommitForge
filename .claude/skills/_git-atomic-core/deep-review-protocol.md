# CommitForge 심층 리뷰 프로토콜

## 목차

1. 변경 라인 원장
2. 제거된 동작
3. Cross-file 추적
4. Wrapper와 Proxy
5. 재사용·중복·품질
6. Architecture
7. UX와 Accessibility
8. Observability
9. 근거와 완료 조건

## 1. 변경 라인 원장

모든 diff hunk를 빠짐없이 원장에 배정한다. “전체 diff를 읽음”만으로 완료 처리하지 않는다.

각 hunk에서 다음을 기록한다.

- 파일과 hunk 범위
- 추가·수정·삭제된 구문
- 변경 의도와 사용자 가시 동작
- 입력·출력·상태·부작용
- 호출자·피호출자·타입·설정·테스트
- 적용할 전문 reviewer
- 확인 결과: `PASS`, `FINDING`, `N/A`

공백·formatting·generated hunk도 분류하고 원인을 확인한다. Binary는 생성 원본, 크기, 포맷, 소비 경로를 확인할 수 없으면 수동 검토 대상으로 표시한다.

## 2. 제거된 동작

삭제 라인은 새 코드보다 강하게 검토한다.

- branch, guard, validation, fallback, cleanup, retry, timeout
- 기본값, feature flag, permission, rate limit
- event, callback, notification, analytics, log
- public symbol, API field, enum case, serialization key
- test가 보존하던 contract와 edge case
- migration, rollback, compatibility shim

삭제가 의도인지 관련 호출부·문서·테스트·history로 확인한다. 대체 경로가 없거나 호출자가 남아 있으면 회귀 finding으로 올린다.

## 3. Cross-file 추적

변경 symbol과 contract를 저장소 전체에서 추적한다.

- 정의 → 구현 → wrapper/adapter → 호출자 → UI/API 소비자
- 타입/schema → serializer → transport → storage → migration
- config/env → loader → default → runtime branch → deployment
- event producer → queue/broker → consumer → retry/DLQ
- interface/trait → 모든 구현 → mock/fake → test fixture

파일별 리뷰로 끝내지 않는다. 한쪽만 바뀐 contract, stale caller, 누락된 구현, 이름만 같은 다른 symbol을 구분한다.

## 4. Wrapper와 Proxy

위임 계층은 원본 의미가 보존되는지 확인한다.

- 모든 인자, named/default/variadic 인자와 순서
- nullability, generic/type parameter, overload
- return type, identity, laziness, stream/iterator semantics
- exception/error code/stack/cause 변환
- async/await, cancellation, timeout, backpressure
- transaction, resource ownership, close/dispose 책임
- auth context, tenant, locale, timezone, request metadata
- HTTP headers, status, body, cache, redirect
- trace/span/baggage/correlation context
- retry/idempotency와 중복 부작용
- method binding, receiver/`this`, proxy trap

wrapper가 값을 보정하거나 오류를 삼키거나 호출 횟수를 바꾸면 의도와 테스트 근거를 요구한다.

## 5. 재사용·중복·품질

새 구현 전에 동일하거나 더 일반적인 기존 경로를 검색한다.

- 같은 domain의 helper/service/component/query/schema
- 이름은 다르지만 동일한 control flow나 validation
- 이미 검증된 표준 라이브러리·프로젝트 abstraction
- copy-paste 후 diverge할 상수·정책·error mapping

재사용은 결합도를 낮출 때만 권장한다. 우연히 비슷한 코드, 서로 다른 변경 주기, 의미가 다른 domain을 억지로 통합하지 않는다.

품질 항목:

- cyclomatic/cognitive complexity
- 긴 함수·과도한 nesting·boolean flag
- dead/unreachable code와 stale compatibility path
- mutable shared state와 hidden side effect
- 이름·책임·추상화 수준 불일치
- 테스트하기 어려운 시간·랜덤·전역 의존성
- 주석과 실제 동작 불일치

## 6. Architecture

- 계층·모듈·domain boundary 위반
- dependency direction과 circular dependency
- public API 누수와 내부 타입 노출
- sync/async, client/server, process/network 경계
- 데이터 소유권과 단일 source of truth
- transaction boundary와 eventual consistency
- cache/source-of-truth 관계
- 확장 지점과 backward compatibility
- feature flag·migration·배포 순서
- failure domain, blast radius, rollback 가능성

취향 기반 재설계는 finding이 아니다. 현재 diff가 만든 구체적 결합·회귀·운영 위험만 보고한다.

## 7. UX와 Accessibility

사용자 상호작용 변경에만 적용한다.

- loading, empty, error, offline, retry, partial success
- disabled/pending/double-submit와 진행 피드백
- 입력값 보존, undo, destructive confirmation
- keyboard-only 조작과 논리적 focus 순서
- focus 이동·복원·trap
- accessible name, label, role, state, live region
- semantic heading·landmark·list·table
- color-only 전달, contrast, text scaling, zoom/reflow
- touch target, pointer 대체, motion 감소
- localization, RTL, 날짜·숫자·복수형
- screen reader에서 동적 상태와 오류 전달

시각적 수치나 실제 보조기기 동작을 실행 없이 추측하지 않는다. 정적 근거와 필요한 수동 검증을 구분한다.

## 8. Observability

동작·실패·운영 경로 변경에 적용한다.

- 구조화 log level과 action 가능한 context
- secret/PII/token 및 과도한 payload 금지
- request/job/user/tenant correlation
- metric counter/gauge/histogram과 단위
- bounded label cardinality
- trace/span parent 전달과 비동기 경계
- retry, timeout, fallback, queue, DLQ 가시성
- error 분류와 alert 가능한 signal
- SLI/SLO 영향과 alert threshold 근거
- sampling과 high-volume/hot-path 비용
- dashboard/runbook/release marker 필요성

성공 로그만 있고 실패 signal이 없거나 오류를 삼키는 경로를 찾는다. 모든 함수에 로그·metric을 강요하지 않는다.

## 9. 근거와 완료 조건

finding은 다음을 포함한다.

- 정확한 파일·line/hunk
- 실행 경로·사용자 시나리오·운영 시나리오
- 현재 diff가 만든 영향
- 관련 symbol과 cross-file 근거
- 최소 수정 방향
- 필요한 자동·수동 검증
- 심각도와 차단 여부

심층 리뷰 완료 조건:

- 모든 hunk가 원장에 존재
- 모든 삭제 동작에 대체·의도 판정
- 변경 contract의 호출자·구현 추적
- 적용 가능한 전문 관점에 `PASS/FINDING/N/A`
- 중복 finding 통합
- 근거 없는 일반론·취향·범위 밖 개선 제거
