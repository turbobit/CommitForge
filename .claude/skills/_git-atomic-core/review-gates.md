# `/cr`·`/cca` 리뷰 및 품질 게이트

## 1. 리뷰 원칙

전문 reviewer 결과는 조언이며 사실 판정이 아니다. Main agent가 diff와 코드 근거를 직접 확인한 뒤 채택한다.

모든 finding은 다음을 포함해야 한다.

- 심각도: `CRITICAL`, `MAJOR`, `MINOR`, `NOTE`
- 파일과 가능한 정확한 위치
- 실제 실패 시나리오 또는 영향
- 근거
- 최소 수정 방향
- 현재 커밋을 차단하는지 여부

근거 없는 일반론, 취향, 범위 밖 리팩터링은 차단 finding이 아니다.

## 2. 차단 기준

### CRITICAL

다음 중 하나면 자동 커밋을 차단한다.

- 명백한 secret/credential 노출
- 인증·인가 우회
- 데이터 손실·손상 가능성
- 원격 코드 실행, injection, path traversal 등 중대한 취약점
- 확정적인 빌드/런타임 파손
- 잘못된 migration으로 복구 곤란한 상태
- 사용자 작업 유실 위험
- merge/rebase conflict 또는 저장소 상태 불일치

### MAJOR

기본적으로 수정 또는 명시적 판단 없이는 차단한다.

- 주요 기능이 요구와 다르게 동작
- 일반 경로에서 재현 가능한 회귀
- 오류 처리 누락으로 요청/작업 전체 실패
- 동시성 race, deadlock, duplicate processing
- 필수 호출부·타입·migration 누락
- changed behavior에 필요한 핵심 테스트 부재
- 큰 성능 회귀가 명확한 hot path

### MINOR

커밋을 반드시 차단하지는 않는다.

- 제한된 edge case
- 불명확한 naming
- 작은 중복
- 비핵심 문서 누락
- 경미한 비효율
- 유지보수성 개선

### NOTE

정보·향후 개선 사항이다. 현재 scope를 확대하지 않는다.

## 3. Reviewer 관점

### Git/Atomicity

- mixed concern
- 잘못된 commit 순서
- 불완전한 staging
- rename과 로직 혼합
- generated/lockfile 이상
- cherry-pick/revert/bisect 가능성

### Correctness

- null/empty/boundary
- 오류 전파
- 상태 전이
- API contract
- backward compatibility
- resource cleanup
- timezone/locale/encoding
- async/concurrency
- retry/idempotency

### Security

- trust boundary
- input validation/escaping
- authn/authz
- secret handling
- SQL/command/template injection
- XSS/CSRF/SSRF
- path traversal
- cryptography misuse
- dependency/config hardening

### Performance

- algorithmic complexity
- N+1 query
- repeated I/O
- unnecessary allocation/copy
- blocking on async path
- cache invalidation
- unbounded collection/concurrency
- expensive rebuild/render

### Testing/Documentation

- behavior change와 테스트 일치
- regression test
- flaky/non-deterministic test
- migration/release note
- public API docs
- config/env example
- generated artifact consistency

### Line-by-line/Removed Behavior

- 모든 hunk의 의도와 부작용
- 삭제된 guard/default/fallback/cleanup/API
- cross-file symbol·contract 영향
- wrapper/proxy 인자·반환·오류·취소·context 보존

### Architecture

- 계층·domain boundary와 dependency direction
- public API와 내부 타입 누수
- 데이터 소유권·transaction·cache
- failure domain·rollback·배포 순서

### Language/API

- 타입·nullability·generic·cast
- async·lifecycle·resource
- serialization·timezone·numeric precision
- framework·runtime·platform contract

### UX/Accessibility

- loading/empty/error/pending 상태
- keyboard·focus·semantics·screen reader
- contrast·text scaling·localization·RTL

### Observability

- log·metric·trace·alert
- correlation·cardinality·sampling
- 실패·retry·queue·rollback 가시성

### Quality/Reuse

- 기존 구현 재사용과 의미 중복
- 복잡도·책임·dead code
- hidden side effect·testability
- 국소적 동작 보존 리팩터링

## 4. 자동 수정 정책

`/cr`과 `/cca` 기본 동작은 다음 범위의 확정적 문제를 안전하게 수정할 수 있다.

- diff가 의도한 동작과 명백히 모순되는 오류
- 누락된 직접 호출부·타입 오류
- 명백한 secret 제거
- 단순하고 국소적인 예외 처리
- 변경 동작을 검증하는 직접 회귀 테스트
- hook/lint가 요구하는 국소 수정

수정하지 않는 항목:

- 요구가 불명확한 UX/비즈니스 결정
- 광범위한 재설계
- 취향 기반 리팩터링
- 새 의존성 설치
- 네트워크·환경 변경
- unrelated pre-existing issue
- 데이터 파괴적 migration

`--no-fix`가 있으면 어떤 소스 수정도 하지 않고 blocking finding에서 중단한다.

수정 후에는 모든 reviewer 결과를 폐기하고 현재 diff를 다시 리뷰한다.

## 5. 최종 Gate

커밋 실행 조건:

- 확인된 CRITICAL 0
- 미해결 MAJOR 0 또는 명백히 범위 밖인 이유 기록
- secret 가능성 0
- staging plan 완성
- 적절한 검증 명령 식별
- 사용자 작업 스냅샷 확보
- 예상치 못한 외부 변경 없음
- 미검토 hunk 0
- 적용 가능한 심층 reviewer 상태가 모두 PASS/FINDING/N/A

조건을 충족하지 못하면 커밋을 시작하지 않는다.
