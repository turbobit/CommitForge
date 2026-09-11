# Fast Commit 규칙

CommitForge의 빠른 커밋 경로 `/cf`, `/cfr`, `/ccf`가 공유하는 계약이다. `/cc`,
`/cca`의 Atomic Commit 규칙을 대체하지 않고, 의도적으로 다른 목적을 가진 별도
경로다.

1~7절은 **단일 묶음 커밋**(`/cf`, `/cfr`)의 규칙이다. 8절은 **빠른 의미 분리
다중 커밋**(`/ccf`)의 규칙이며, 3절 차단 스캔만 공유한다.

## 0. 세 가지 경로 비교

| | `/cfr` | `/cf` | `/ccf` |
|---|---|---|---|
| Git 변경 | 없음 | staging·commit | staging·commit |
| 커밋 수 | 단일(미리보기) | 단일 | 의미 단위 여러 개 |
| 분리 단위 | 없음 | 없음 | 파일만 (hunk 분리 없음) |
| worktree lock | 획득 | 획득 | **lock을 획득하지 않는다** |
| Diff snapshot | 생성·정리 | 생성·정리 | `guard.sh snapshot`으로 생성, 성공 시 `release-snapshot`으로 정리 |
| fingerprint 재검사 | 함 | 함 | 안 함 |
| 프로젝트 검증 | 식별만 | `--verify`일 때만 | 안 함 |
| 차단 스캔 | 함 | 함 | 함 |

`/ccf`는 같은 worktree에서 다른 CommitForge 명령과 동시에 실행하면 안 된다.
동시 실행 보호를 포기한 대가로 가장 빠르다.

## 1. 위치와 한계

Fast Commit은 아직 커밋되지 않은 변경 전체를 **의미 단위로 분리하지 않고 하나의
commit으로 묶는다**. 따라서 결과물은 정의상 **Atomic Commit이 아니다**.

적합한 상황:

- 실험 중 중간 저장, WIP 보존, 자리 이동 전 임시 커밋
- 이미 단일 의도인 것이 확실한 작은 변경
- 곧 squash하거나 rebase로 재정리할 개인 branch

적합하지 않은 상황:

- 공유 branch와 release 대상 히스토리
- cherry-pick·revert 단위를 보존해야 하는 변경
- 리뷰어가 commit 단위로 읽어야 하는 변경

이 경우에는 `/cc` 또는 `/cca`를 사용한다. `/cf`와 `/cfr`은 결과 보고에서 이
한계를 반드시 사용자에게 다시 알린다.

## 2. 대상 범위

기본 대상은 **아직 커밋되지 않은 모든 변경**이다.

- staged 변경
- unstaged tracked 변경
- untracked 파일 중 `.gitignore`에 걸리지 않은 것

이미 staged된 변경이 있어도 중단하지 않는다. staged와 unstaged를 구분해 재구성
하지 않고 하나의 index로 합친다. index를 되돌리거나 working tree 파일을 수정하지
않는다.

`--scope <경로...>`가 주어지면 해당 경로 안의 변경만 대상으로 하고, 범위 밖
변경은 시작 상태 그대로 둔다.

## 3. 차단 스캔 (생략 불가)

staging 전과 staged diff 확인 시 두 번 수행한다.
아래 항목은 **어떤 인자로도 생략할 수 없다**.
`--verify`, `--no-verify`, `--scope` 모두 이 스캔을 끄지 못한다.

1. secret/credential 후보: API key, token, private key, 패스워드 형태 문자열
   (값 자체는 결과에 재출력하지 않고 파일과 줄 위치만 보고한다)
2. 자격 파일: `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `id_rsa`,
   `credentials.json`, cloud 자격 파일
3. 의도하지 않은 산출물: 빌드 디렉터리, 캐시, 로그, 대용량 바이너리,
   `node_modules`, 가상환경, coverage 산출물 등 untracked 대량 유입
4. **merge conflict marker**: `<<<<<<<`, `=======`, `>>>>>>>`
5. `git diff --cached --check` 위반 (whitespace 오류, conflict marker)
6. 진행 중 merge/rebase/cherry-pick/revert/bisect

하나라도 걸리면 **commit하지 않고 중단한다**. 이미 `git add`를 수행했다면 index는
그대로 두고 사용자에게 상태와 복구 방법을 보고한다. Guard snapshot은 보존한다.

untracked 대량 유입이 프로젝트 의도일 수 있으면 임의 판단으로 통과시키지 말고
파일 목록과 크기를 제시한 뒤 `--scope`로 범위를 좁히도록 안내한다.

## 4. 대표 type 선정

Conventional Commits는 단일 type을 전제하므로, 섞인 의도에서 하나의 **대표 type**을
고른다.

우선순위는 다음과 같다.

```text
feat > fix > perf > refactor > test > docs > build/ci > style > chore
```

- 해당 type의 변경이 하나라도 있으면 더 앞선 type이 대표가 된다.
- 대표 type이 `feat`이고 Breaking Change가 있으면 `!`와 `BREAKING CHANGE:`
  trailer를 사용한다.
- scope는 변경 파일들의 **공통 상위 경로**에서 유도한다. 공통 경로가 저장소
  루트뿐이면 scope를 생략한다.
- 사용자가 인자로 `type(scope): 제목` 형태를 직접 주면 그것을 우선한다.

## 5. 메시지 형식

```text
type(scope): 한글 제목

이 커밋은 Atomic Commit이 아니다. 아래 의도가 함께 묶여 있다.

- feat: ...
- fix: ...
- docs: ...

영향 범위와 호환성:
실제 수행한 검증:
```

- 섞인 의도를 **하나도 빠뜨리지 않고** 불릿으로 나열한다. 정보 손실을 막는 것이
  대표 type 방식의 전제다.
- 제목은 대표 type이 설명하는 가장 지배적인 변경을 기준으로 쓰고, 여러 목적을
  `및`으로 억지로 합치지 않는다.
- diff에 없는 사실이나 실행하지 않은 검증을 쓰지 않는다.
- `--amend`, squash, rebase는 Fast Commit의 범위가 아니다.

## 6. 검증 정책

Fast Commit은 **기본적으로 프로젝트 검증을 실행하지 않는다**. 대신:

| 인자 | 프로젝트 검증(test/lint/build) | commit hook |
|---|---|---|
| (없음) | 생략 | 존중 |
| `--verify` | `validation-strategy.md`의 빠른 검증 실행 | 존중 |
| `--no-verify` | 생략 | 우회 |

- `--verify`와 `--no-verify`를 함께 쓰면 오류다.
- `--verify` 검증이 실패하면 commit하지 않고 중단한다. `/cf`는 소스 코드를
  수정하지 않으므로 실패를 해결하지 않는다.
- 3절 차단 스캔과 Guard 계약은 위 표와 무관하게 항상 수행한다.

## 7. `/cfr` read-only 경계

`/cfr`은 `/cf`와 동일한 판단을 수행하되 Git 상태를 바꾸지 않는다.

- `git add`, `git commit`, `git restore`, `git apply`를 실행하지 않는다.
- 3절 차단 스캔은 `git diff`, `git diff --check`, `git ls-files --others`로
  index 변경 없이 수행한다. `git diff --cached --check`는 현재 index에 대해서만
  읽기로 사용한다.
- 결과로 대상 파일 목록, 대표 type 근거, 메시지 초안, 차단 사유, 권장 후속
  명령을 제시한다.
- 분석 이후 working tree가 바뀌면 초안이 무효가 될 수 있음을 명시한다.

## 8. `/ccf` 빠른 의미 분리

`/ccf`는 1·2·4·5·6·7절이 아니라 이 절을 따른다. 3절 차단 스캔만 동일하게
적용한다. 목표는 `/cc`와 같은 **여러 개의 의미 단위 커밋**을 훨씬 짧은 시간에
만드는 것이다.

### 8.1 파일 단위 그룹

각 파일을 **하나의 그룹에만** 배정한다. 그룹 기준은 다음 순서로 판단한다.

1. 변경 성격: 기능 추가 / 버그 수정 / 리팩터링 / 성능 / 테스트 / 문서 /
   build·CI / style
2. 같은 성격 안에서 domain·package·디렉터리
3. 구현과 그 직접 회귀 테스트는 같은 그룹에 둔다
4. lockfile·generated 파일은 그것을 유발한 그룹에 함께 둔다

그룹이 하나뿐이면 커밋도 하나다. 억지로 쪼개지 않는다.

### 8.2 생략하는 것

속도는 다음을 생략해서 얻는다.

- **hunk 단위 분리를 하지 않는다.** `git add -p`와 선택 patch를 쓰지 않는다.
  한 파일에 여러 의도가 섞이면 가장 지배적인 의도의 그룹에 파일 전체를 넣는다.
- 커밋 사이 fingerprint 재검사와 중간 빌드 상태 확인을 하지 않는다.
- 의존성 그래프를 정밀하게 세우지 않는다. 명백한 선행 관계(타입·시그니처 정의
  → 사용처, migration → 코드)만 순서에 반영한다.
- 프로젝트 테스트·lint·build와 reviewer를 실행하지 않는다.

### 8.3 남는 한계

파일 단위 그룹핑 때문에 결과는 **완전한 Atomic Commit이 아닐 수 있다**. 한 파일에
리팩터링과 기능 추가가 섞여 있으면 그 커밋은 두 의도를 함께 담는다.

의도가 섞인 커밋은 본문과 최종 보고에 그 사실을 명시하고, 공유 branch와 release
히스토리에는 `/cc` 또는 `/cca`를 권장한다.

### 8.4 Snapshot과 복구

`/ccf`는 `guard.sh snapshot`으로 **lock을 획득하지 않고** Diff snapshot만 만든다.

`finish`·`abort`는 `verify_owner`로 lock 소유자를 검증하므로 lock이 없는 이
snapshot에는 쓸 수 없다. 대신 `release-snapshot`이 lock을 건드리지 않고 snapshot
marker의 session·token만 검증해 삭제한다. `clean`은 이 snapshot을 삭제하지 않는다.

정리 시점은 결과에 따라 갈린다.

- **전부 성공**: `release-snapshot`으로 삭제한다. guard는 무결성 검증과 working
  tree clean 검사를 통과할 때만 삭제하고, 하나라도 어긋나면 거부한다.
- **차단·실패·중단**: 호출하지 않는다. snapshot이 그대로 남는 것이 복구 수단이다.
- **`--keep-snapshot`**: 성공해도 보존한다.
- **`--scope`**: 범위 밖 변경 때문에 dirty이므로 거부된다. 범위 밖이 시작 상태대로
  보존됐음을 확인한 경우에만 `--allow-dirty`를 붙인다.

guard가 거부하면 그 결과를 보고하고 수동 삭제로 우회하지 않는다.

시작 HEAD를 기록해 두고, 결과가 잘못되면 `git reset --soft <시작 HEAD>`로
되돌린다. snapshot을 이미 정리한 뒤에는 커밋만 되돌릴 수 있고 snapshot은 복원할
수 없다.
