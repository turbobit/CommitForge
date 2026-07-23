# 검증 전략

## 1. 검증 명령 탐색

다음 우선순위로 프로젝트의 실제 명령을 찾는다.

1. `CLAUDE.md`, `AGENTS.md`, 기여 가이드
2. `package.json` scripts
3. `Makefile`, `justfile`, `Taskfile`
4. 언어별 manifest
5. CI workflow
6. README 개발 절차

추측한 명령보다 저장소가 선언한 명령을 우선한다. 의존성 설치, 버전 업그레이드, 네트워크 접근은 자동으로 수행하지 않는다.

## 2. 검증 계층

### 정적 Git 검증

항상 수행:

```bash
git diff --cached --check
git diff --cached
git status --short
```

### Targeted 검증

변경된 package/module에 한정해 빠른 검사:

- 관련 unit/regression test
- 관련 type check
- 관련 lint
- compile/check

### 전체 검증

`/cca`에서 비용이 합리적이고 프로젝트 명령이 명확하면 마지막에 수행:

- 전체 test
- 전체 type check
- build
- integration test는 환경이 준비된 경우

## 3. 언어별 기본 후보

실제 저장소 scripts가 없을 때만 후보로 고려한다.

### Node/TypeScript

- package manager를 lockfile로 판정
- `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`
- pnpm/yarn/bun이면 해당 package manager 사용
- 임의로 `npm install`하지 않음

### Flutter/Dart

- `dart format --output=none --set-exit-if-changed .`
- `flutter analyze`
- 변경 관련 `flutter test <path>`
- 필요 시 전체 `flutter test`
- 임의로 `flutter pub upgrade`하지 않음

### Python

- 저장소 설정에 따라 `pytest`, `ruff check`, `mypy`, `pyright`
- `uv run`, `poetry run`, venv 정책 존중
- 임의로 package 설치하지 않음

### Rust

- `cargo fmt --check`
- `cargo check`
- `cargo test`
- workspace/package 범위를 명시
- lockfile 정책 존중

### Go

- `gofmt` 차이 확인
- `go test ./...`
- `go vet ./...`
- 네트워크 모듈 다운로드가 필요하면 보고

### Java/Kotlin

- repository wrapper 사용: `./gradlew`, `./mvnw`
- 변경 module의 test/check 우선
- 시스템 전역 gradle/maven보다 wrapper 우선

## 4. Commit 단위 검증

가능한 경우 각 atomic commit이 독립적으로 검증 가능해야 한다.

- 빠른 targeted 검증은 commit 전
- 전체 검증은 최종 commit 후
- migration/build/config처럼 중간 검증이 어려우면 계획에 이유 기록
- 테스트가 매우 오래 걸리면 가장 관련성 높은 subset을 실행하고 미실행 범위를 보고

## 5. 실패 분류

### 변경으로 인한 실패

해결 전 commit을 차단한다.

### 기존 실패

현재 diff와 무관함을 근거로 구분할 수 있으면 경고로 기록하고 계속할 수 있다. 근거가 불충분하면 차단한다.

### 환경 실패

DB, credential, SDK, 네트워크 등 환경 부재:

- 변경 결함으로 단정하지 않음
- 명령, 오류 요약, 미검증 범위를 보고
- 해당 검증 없이 commit 가능한 위험 수준인지 판단

### 비결정적 실패

재실행만으로 숨기지 않는다. flaky 가능성과 횟수를 보고하고 changed behavior와 연관되면 차단한다.

## 6. `--no-verify`

사용자가 명시한 경우에만 프로젝트 테스트/검증과 commit hook 우회를 허용한다.

그래도 다음은 생략하지 않는다.

- staged diff 직접 검토
- `git diff --cached --check`
- secret/critical safety check
- repository state/lock check

최종 보고에 생략 범위를 명시한다.
