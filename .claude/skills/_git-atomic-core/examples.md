# Atomic Commit 예시

## 예시 1: 리팩터링 + 기능

변경:

- API 요청 공통 빌더 추출
- retry 옵션 추가
- retry 테스트 추가
- README retry 설명 추가

권장:

1. `refactor(api): 요청 생성 로직을 공통 빌더로 통합`
   - 동작 보존 리팩터링과 기존 테스트
2. `feat(api): 실패 요청의 재시도 정책 추가`
   - 옵션, 구현, 직접 테스트
3. `docs(api): 재시도 설정과 동작 예시 추가`

README가 기능 사용에 필수적인 계약 문서이고 매우 짧다면 2번에 포함할 수도 있다.

## 예시 2: 한 파일에 버그와 포맷팅 혼합

한 파일의 상단 import 전체 정렬과 하단 null 처리 수정이 섞임.

권장:

1. 선택 patch로 null 처리와 회귀 테스트만 `fix` 커밋
2. import 정렬이 프로젝트 규칙에 필요한 경우 별도 `style` 커밋

## 예시 3: 의존성 변경

- `package.json`에 라이브러리 추가
- lockfile 갱신
- 새 라이브러리를 사용하는 기능 구현

라이브러리 추가만으로 빌드가 성립하고 독립적인 기반 변경이면:

1. `build(deps): 날짜 처리 라이브러리 추가`
2. `feat(report): 사용자 시간대 기준 날짜 필터 추가`

의존성 추가가 오직 기능 구현과 결합되고 별도 가치가 없으면 하나의 `feat` 커밋에 manifest/lockfile을 포함할 수 있다.

## 예시 4: API Breaking Change

- 응답 필드명 변경
- 서버와 모든 클라이언트 수정
- migration 안내

호환 단계가 불가능하고 같은 저장소에서 원자적으로 배포된다면 하나의 breaking commit:

`feat(api)!: 주문 상태 응답을 구조화된 객체로 전환`

서버와 클라이언트가 독립 배포되면 backward-compatible 단계로 여러 커밋/배포를 설계해야 하며 단순 파일 분리로 해결하지 않는다.

## 예시 5: Migration

- nullable 컬럼 추가
- 코드가 새/구 스키마 모두 지원
- 데이터 backfill
- NOT NULL 적용

배포 가능한 단계:

1. `feat(db): 주문에 선택적 처리 시각 필드 추가`
2. `chore(db): 기존 주문의 처리 시각 데이터 보정`
3. `refactor(db): 처리 시각 필드를 필수 값으로 전환`

각 단계의 배포/롤백 조건을 본문에 기록한다.

## Anti-pattern

- `feat: 여러 기능 추가 및 버그 수정`
- 파일 하나당 한 커밋
- 구현 없이 테스트만 실패하는 중간 커밋
- 전체 저장소 formatter 실행 결과를 기능 커밋에 혼합
- hook 실패 후 무조건 `--no-verify`
- staged diff를 보지 않고 `git commit`
- lockfile 변경 원인을 확인하지 않고 포함
