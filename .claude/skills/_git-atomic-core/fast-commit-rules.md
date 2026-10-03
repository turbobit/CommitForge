# Fast Commit 규칙

CommitForge의 빠른 커밋 경로 `/cf`, `/cfr`이 공유하는 **단일 묶음 커밋** 계약이다.
`/cc`, `/cca`의 Atomic Commit 규칙을 대체하지 않고, 의도적으로 다른 목적을 가진
별도 경로다.

파일 단위 의미 분리 다중 커밋인 `/ccf`는 이 문서를 따르지 않는다. `/ccf`는 `/cc`와
같은 Guard·fingerprint·검증 절차를 쓰고 hunk 단위 분리만 하지 않으므로
`ccf/SKILL.md`와 `/cc`의 공통 지침을 따른다.

## 0. 두 가지 경로 비교

| | `/cfr` | `/cf` |
|---|---|---|
| Git 변경 | 없음 | staging·commit |
| 커밋 수 | 단일(미리보기) | 단일 |
| worktree lock | 획득 | 획득 |
| Diff snapshot | 생성·정리 | 생성·정리 |
| fingerprint 재검사 | 함 | 함 |
| 프로젝트 검증 | 식별만 | `--verify`일 때만 |
| 차단 스캔 | 함 | 함 |

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
