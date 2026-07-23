# 프로젝트별 Atomic Commit 프로필

프로젝트 자동 감지 결과는 보조 신호다. 저장소 자체 규칙이 항상 우선한다.

## Flutter/Dart

- `pubspec.yaml`과 `pubspec.lock`의 동일 의존성 변경은 함께 둔다.
- 생성 파일(`*.g.dart`, `*.freezed.dart`)은 원본 annotation/model과 생성 정책에 맞춰 함께 둔다.
- Widget와 해당 golden/widget test는 기능 단위로 묶는다.
- platform 폴더(iOS/Android/macOS/Windows) 설정은 Dart 기능과 독립적이면 `build`로 분리한다.
- localization 원본과 생성 결과의 관계를 확인한다.
- formatting-only `dart format` 변경을 로직과 분리한다.

## Next.js/React/TypeScript

- Server/Client Component 경계 변경을 검토한다.
- Server Action/API contract와 호출부를 함께 둔다.
- route, loader/action, UI가 한 사용자 기능을 완성하면 한 커밋일 수 있다.
- 전역 포맷팅/import 정리는 분리한다.
- package manifest와 lockfile을 함께 둔다.
- database migration과 generated client 변경의 관계를 확인한다.
- hydration, cache/revalidation, runtime(edge/node) 영향에 대한 테스트를 고려한다.

## Python

- public type/signature 변경과 호출부를 함께 둔다.
- migration과 ORM model을 함께 검토한다.
- `__pycache__`, `.pytest_cache`, virtualenv는 커밋하지 않는다.
- formatting/ruff auto-fix가 광범위하면 로직에서 분리한다.
- dependency file과 lockfile을 함께 둔다.
- sync/async 경계 변경을 별도 위험 요소로 검토한다.

## Rust

- `Cargo.toml`과 정책상 추적되는 `Cargo.lock`을 함께 둔다.
- public trait/type 변경과 모든 필수 구현을 함께 둔다.
- `cargo fmt` 광범위 변경은 분리한다.
- unsafe 변경은 보안/correctness gate를 강화한다.
- feature flag와 conditional compile 경로 테스트를 함께 검토한다.

## Go

- interface 변경과 구현/호출부를 함께 둔다.
- generated mock/protobuf는 원본 변경과 함께 둔다.
- `go.mod`와 `go.sum`을 함께 검토한다.
- `gofmt` 외 광범위한 정리는 로직에서 분리한다.
- goroutine/channel 변경은 leak/deadlock/race를 검토한다.

## Java/Kotlin/Gradle

- API signature와 구현/호출부를 함께 둔다.
- Gradle catalog/build file과 lock/verification metadata 관계를 확인한다.
- migration과 entity/repository를 함께 검토한다.
- generated sources를 직접 수정하지 않는다.
- formatting plugin 결과가 광범위하면 분리한다.

## Database/Infrastructure

- migration은 forward/rollback/compatibility를 설명한다.
- Terraform lock/provider 변경은 실제 config 변경과 연결한다.
- deployment config와 애플리케이션 feature flag의 배포 순서를 본문에 기록한다.
- secret 값은 절대 커밋하지 않고 template/example만 사용한다.
- CI workflow 변경은 애플리케이션 기능과 독립적이면 `ci`로 분리한다.
