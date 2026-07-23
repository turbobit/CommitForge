# 언어·프레임워크 API 함정 카탈로그

## 목차

1. 공통 API
2. JavaScript·TypeScript
3. React·Next.js
4. Dart·Flutter
5. Python
6. Go
7. Rust
8. Java·Kotlin
9. Swift·Objective-C
10. C·C++
11. SQL·Database
12. Shell·CI·Infrastructure

관련 언어·프레임워크 섹션만 읽는다. 버전과 프로젝트 설정을 확인하지 않은 채 규칙을 적용하지 않는다.

## 1. 공통 API

- optional/nullable/absent/empty의 의미 구분
- 단위, 범위, timezone, locale, encoding
- enum 확장과 exhaustive consumer
- pagination, ordering, duplicate, cursor 안정성
- backward/forward compatibility와 unknown field
- error taxonomy, status code, retryability
- timeout, cancellation, idempotency
- streaming, buffering, partial result
- resource ownership과 lifecycle
- serialization precision과 schema default

## 2. JavaScript·TypeScript

- `null`/`undefined`, truthiness, `??`와 `||`
- `==` coercion, `NaN`, `-0`, floating precision
- object/array 얕은 복사와 mutation
- optional chaining이 오류를 숨기는지
- Promise 미대기, floating promise, rejection
- `Promise.all` fail-fast와 cancellation 부재
- async callback을 `forEach`에 사용
- closure stale value와 event listener cleanup
- `this` binding, method extraction, Proxy/Reflect receiver
- structural typing, excess property, variance, unsafe cast
- discriminated union exhaustiveness
- Date parsing과 local/UTC 변환
- JSON에서 `undefined`, bigint, Date, Map/Set 손실
- Node stream backpressure와 buffer 보유
- ESM/CJS interop, default import, side-effect import

## 3. React·Next.js

- hook dependency와 stale closure
- render 중 side effect, Strict Mode 이중 실행
- effect cleanup과 request race
- state identity, mutation, key 안정성
- controlled/uncontrolled input 전환
- hydration mismatch와 browser-only API
- Server/Client Component 경계와 serialization
- Server Action/API auth와 cache invalidation
- route/runtime edge-node 호환성
- suspense/loading/error boundary
- optimistic update rollback과 duplicate submit
- focus 관리, semantic HTML, ARIA 오용

## 4. Dart·Flutter

- nullable promotion이 closure/field에서 깨지는 경우
- `late` 초기화와 lifecycle
- `Future` 미대기, sync/async error 경계
- `BuildContext`를 async gap 뒤 사용
- `setState`/controller/stream을 dispose 뒤 호출
- controller, subscription, focus node dispose
- `Iterable` lazy evaluation과 반복 부작용
- `DateTime` local/UTC, duration/calendar 차이
- `==`/`hashCode` 불일치와 collection key
- JSON numeric/type cast와 missing key
- Widget key, list identity, rebuild 범위
- constraints, unbounded layout, text scaling
- platform channel codec·thread·error mapping
- isolate로 보낼 수 없는 객체와 copy 비용

## 5. Python

- mutable default argument와 shared class attribute
- truthiness와 `None` 구분
- shallow copy, iterator/generator 소진
- late-binding closure
- broad exception, exception chaining, context manager
- async coroutine 미대기와 blocking I/O
- cancellation을 잡아 삼키는 코드
- naive/aware datetime과 timezone
- decimal/float, integer division
- dataclass equality/hash/frozen
- type narrowing, invariant container, `Any` 누수
- descriptor/property와 monkey patch
- multiprocessing serialization과 fork state
- ORM lazy load, transaction scope, N+1

## 6. Go

- nil interface와 typed nil
- zero value와 optional 의미
- slice backing array aliasing과 append
- map 동시 접근·iteration order
- loop variable capture와 goroutine lifecycle
- context 전달·취소·deadline
- channel close ownership, leak, deadlock
- `defer` 위치와 loop resource 보유
- error wrapping과 `errors.Is/As`
- partial write/read 처리
- pointer/value receiver와 interface 구현
- JSON `omitempty`, unknown field, numeric precision
- HTTP body close, reuse, timeout
- data race와 atomic/mutex 범위

## 7. Rust

- ownership 이동과 의도치 않은 clone
- borrow lifetime 우회와 interior mutability
- `unwrap`/`expect`의 런타임 경로
- `Option`/`Result` 변환에서 정보 손실
- integer overflow, cast truncation, indexing panic
- iterator lazy evaluation과 side effect
- async task cancellation·detach·blocking
- lock을 `.await` 너머 보유
- `Send`/`Sync`, shared mutation, deadlock
- unsafe invariant, aliasing, FFI ownership
- feature flag·target별 compile 경로
- serde default/rename/unknown field
- error source chain과 public error compatibility

## 8. Java·Kotlin

- boxed/primitive null과 equality
- Java `equals/hashCode`, Kotlin data class identity
- mutable collection 노출과 defensive copy
- generic variance·type erasure·unchecked cast
- Optional/nullable 혼용
- checked/unchecked exception 변환
- stream lazy evaluation과 parallel stream
- executor/thread pool lifecycle
- coroutine scope, dispatcher, cancellation
- synchronized/volatile/atomic과 memory visibility
- resource try-with-resources/use
- timezone, locale, charset default
- Jackson/JPA proxy·lazy load·constructor/default
- Spring transaction/self-invocation/proxy 경계

## 9. Swift·Objective-C

- optional 강제 해제와 implicit optional
- value/reference semantics와 copy-on-write
- retain cycle, weak/unowned lifecycle
- actor isolation, `Sendable`, main actor
- Task cancellation과 detached task
- closure escaping과 capture
- Objective-C nullability·selector bridging
- NSError/throw mapping
- Codable missing/default/enum 호환성
- collection index와 Unicode string index
- UI lifecycle, main thread, state restoration

## 10. C·C++

- buffer bounds, integer overflow, signedness
- lifetime, dangling pointer/reference/view
- ownership, double free, leak
- uninitialized memory와 padding
- aliasing, alignment, undefined behavior
- exception safety와 partial construction
- RAII와 C resource wrapper
- move 후 상태와 copy/move assignment
- virtual destructor, slicing, ABI
- data race, atomics memory order, lock ordering
- FFI calling convention·allocation boundary
- format string과 null termination

## 11. SQL·Database

- NULL three-valued logic
- join cardinality와 accidental fan-out
- nondeterministic order, pagination drift
- transaction isolation, lost update, phantom
- upsert conflict key와 idempotency
- migration backward compatibility와 lock
- default/backfill/not-null 순서
- timezone·collation·encoding
- decimal precision과 overflow
- index 사용 불가 predicate
- cascade/delete와 tenant scope
- ORM query count와 lazy load

## 12. Shell·CI·Infrastructure

- quoting, word splitting, glob, newline path
- `set -e` 예외와 pipeline exit status
- command substitution과 secret 노출
- temporary file permission·cleanup·race
- PowerShell object/string·error semantics
- environment precedence와 empty/unset
- matrix·conditional·cache key
- unpinned action/image/dependency
- credential permission과 fork PR
- Terraform replacement·state·provider lock
- container user, filesystem, signal, healthcheck
- rollout order, readiness, rollback, feature flag
