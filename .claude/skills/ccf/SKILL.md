---
name: ccf
description: 아직 커밋되지 않은 변경을 의미별로 빠르게 분리해 여러 개의 commit을 만든다. 파일 단위 그룹핑만 사용하고 worktree lock, fingerprint 재검사, 의존성 정밀 분석, 프로젝트 검증을 생략하되 Diff snapshot과 secret 차단 스캔은 유지한다. snapshot은 전부 성공하면 정리하고 실패하거나 중단하면 보존한다. 사용자가 직접 /ccf로 요청할 때만 사용한다.
argument-hint: "[추가 맥락] [--scope <경로...>] [--no-verify] [--keep-snapshot]"
disable-model-invocation: true
model: inherit
effort: medium
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git show *)
  - Bash(git rev-parse *)
  - Bash(git ls-files *)
  - Bash(git add *)
  - Bash(git restore --staged *)
  - Bash(git commit *)
  - 'Bash(bash ".claude/skills/_git-atomic-core/scripts/guard.sh" snapshot *)'
---

# `/ccf` — CommitForge 빠른 의미 분리 커밋

사용자 참고 맥락:

```text
$ARGUMENTS
```

`/cc`의 빠른 경로다. 아직 커밋되지 않은 변경을 **의미별로 분리해 여러 개의 commit**을 만들되, `/cc`의 정밀 분석 단계를 덜어내 훨씬 빠르게 끝낸다.

단일 커밋으로 전부 묶고 싶으면 `/ccf`가 아니라 `/cf`를 쓴다.

| | `/cc` | `/ccf` | `/cf` |
|---|---|---|---|
| 커밋 수 | 의미 단위 여러 개 | **의미 단위 여러 개** | 단일 |
| 분리 단위 | 파일 + hunk | **파일만** | 없음 |
| 의존성 그래프 분석 | 함 | 명백한 순서만 | 없음 |
| worktree lock | 획득 | **획득하지 않음** | 획득 |
| Diff snapshot | 생성·정리 | **성공 시 정리 · 실패 시 보관** | 생성·정리 |
| fingerprint 재검사 | 커밋마다 | 안 함 | 함 |
| 프로젝트 검증 | 기본 실행 | 안 함 | `--verify`만 |
| secret·conflict 차단 | 함 | 함 | 함 |

## 무엇을 덜어내는가

속도는 다음을 **생략**해서 얻는다.

- **hunk 단위로 분리하지 않는다.** 한 파일에 여러 의도가 섞여 있어도 쪼개지 않고, 그 파일에서 가장 지배적인 의도의 그룹에 통째로 넣는다.
- 커밋 사이 fingerprint 재검사와 중간 빌드 상태 확인을 하지 않는다.
- 의존성 그래프를 정밀하게 세우지 않는다. 명백한 선행 관계만 순서에 반영한다.
- 프로젝트 테스트·lint·build를 실행하지 않는다.
- reviewer를 실행하지 않는다.

그 결과 **완전한 Atomic Commit이 아닐 수 있다.** 파일 하나에 리팩터링과 기능 추가가 섞여 있으면 그 커밋은 두 의도를 함께 담는다. 공유 branch와 release 히스토리에는 `/cc` 또는 `/cca`를 사용한다.

## 받아들이는 위험

이 명령은 **worktree lock을 획득하지 않는다.** 따라서:

- 같은 worktree에서 `/cc`, `/cca`, `/cf`, `/cp`와 **동시에 실행하지 않는다.** 동시에 돌면 index를 서로 덮어써 작업을 잃을 수 있다.
- 다른 세션의 lock이 있어도 멈추지 않는다. 이 명령은 lock을 읽지도 존중하지도 않는다.
- fingerprint를 재검사하지 않으므로 실행 도중 외부에서 파일이 바뀌면 그대로 커밋된다.

대신 복구 수단으로 **Diff snapshot은 남긴다.** 시작 HEAD를 기록해 두었다가 결과가 잘못되면 되돌릴 수 있다.

```bash
git reset --soft <시작 HEAD>
```

snapshot은 **전부 성공했을 때만** 7절에서 정리한다. 중간에 차단·실패·중단되면 정리하지 않고 그대로 남겨 복구에 쓴다. `clean`은 이 snapshot을 삭제하지 않는다. 동시 세션 안전성이나 검증이 필요하면 `/cc`를 사용한다.

## Skill 경로 확정 (필수 Preflight)

`SKILL_DIR`는 **이 SKILL.md가 들어 있는 디렉터리의 절대경로**다.
설치된 `SessionStart` 훅이 실제 Claude 세션 ID를 `COMMITFORGE_SESSION_ID`에
설정한다. 값이 비어 있으면 기존 세션이므로 Claude Code를 재시작한 뒤 다시 실행한다.

다른 어떤 명령보다 먼저 `CF_CORE`를 확정한다.

1. `CF_CORE = <이 SKILL.md의 디렉터리>/../_git-atomic-core`로 둔다.
2. 실패하면 `Glob`으로 `**/_git-atomic-core/scripts/guard.py`를 찾아 다시 정한다.
3. 이후 `.claude/skills/_git-atomic-core`를 확정된 `CF_CORE` 절대경로로 바꾼다.

둘 다 실패하면 fail-closed다. core 미설치로 보고하고 즉시 종료한다.

## 필수 지침 로드

속도를 위해 두 파일만 읽는다.

1. `.claude/skills/_git-atomic-core/fast-commit-rules.md`
2. `.claude/skills/_git-atomic-core/reporting.md`

`atomic-commit-rules.md`, `staging-strategy.md`, `validation-strategy.md`, `review-*`는 읽지 않는다. 이것들이 필요하면 `/cc`를 쓴다.

`.commitforge/profile.md`와 `.commitforge/profile.json`이 있으면 읽어 메시지·scope 선호만 반영한다.

`clean`은 이 명령의 인자가 아니다. 잠금 정리는 `/cc clean`, `/cf clean`을 사용한다.

## 0. 인자 해석

- 일반 문장은 그룹 판단과 커밋 메시지에 참고한다.
- `--scope <경로...>`가 있으면 지정 범위만 커밋한다. 범위 밖 변경은 그대로 유지한다.
- `--no-verify`가 있으면 commit hook을 우회한다. 없으면 hook은 존중한다.
- `--keep-snapshot`이 있으면 전부 성공해도 snapshot을 삭제하지 않고 보존한다.
- 알 수 없는 인자는 자연어 맥락으로 취급한다.
- push, amend, rebase, squash, reset은 이 skill이 스스로 수행하지 않는다.

## 1. Diff snapshot 확보

lock 없이 snapshot만 만든다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" snapshot \
  --session "$COMMITFORGE_SESSION_ID"
```

- `ok: true`면 `snapshot` 경로, `token`, `head`(시작 HEAD)를 작업 완료까지 보관한다. 경로와 시작 HEAD는 최종 보고에 적고, `token`은 7절 정리에만 쓰며 보고에 출력하지 않는다.
- `ok: false`이면 **중단한다.** 특히 진행 중 merge/rebase/cherry-pick/revert/bisect가 있으면 이 명령을 실행하지 않는다.
- 명령이 아예 실행되지 못한 경우(exit code 126·127, `command not found`, Python 미탐지)도 같은 실패다. snapshot 없이 커밋하지 않는다. Preflight로 `CF_CORE`를 다시 확정해 한 번만 재시도한다.

## 2. 인벤토리 1회

한 번만 수집하고 이후 다시 전체 스캔하지 않는다.

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git log -20 --pretty=format:'%h%x09%s'
```

변경이 없으면 "커밋할 변경 없음"을 보고하고 종료한다.

## 3. 차단 스캔 (생략 불가)

`fast-commit-rules.md` 3절을 적용한다. `--no-verify`로도 끄지 않는다.

```bash
git diff --check
git diff --cached --check
```

secret/credential 후보, 자격 파일(`.env`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`), **merge conflict marker**(`<<<<<<<`, `=======`, `>>>>>>>`), 의도하지 않은 산출물 대량 유입을 확인한다.

하나라도 걸리면 **어떤 커밋도 만들지 않고 중단한다.** secret 값 자체는 재출력하지 않고 파일과 줄 위치만 보고한다.

## 4. 파일 단위 그룹핑

`fast-commit-rules.md` 8절을 적용한다. 각 파일을 **하나의 그룹에만** 배정한다.

그룹 기준은 다음 순서로 판단한다.

1. 변경 성격: 기능 추가 / 버그 수정 / 리팩터링 / 성능 / 테스트 / 문서 / build·CI / style
2. 같은 성격 안에서 domain·package·디렉터리
3. 구현과 그 직접 회귀 테스트는 같은 그룹에 둔다
4. lockfile·generated 파일은 그것을 유발한 그룹에 함께 둔다

한 파일에 여러 의도가 섞이면 **파일 단위로만 분리한다.** `git add -p`나 선택 patch를 쓰지 않고, 가장 지배적인 의도의 그룹에 파일 전체를 넣은 뒤 그 사실을 커밋 본문과 최종 보고에 적는다.

순서는 명백한 선행 관계(타입·시그니처 정의 → 사용처, migration → 코드)만 반영하고, 그 외에는 위 그룹 순서를 따른다.

그룹이 하나뿐이면 커밋도 하나다. 억지로 쪼개지 않는다.

## 5. 그룹별 commit 반복

각 그룹마다 다음을 수행한다. 그룹 사이에 전체 재스캔을 하지 않는다.

```bash
git add -- <그룹에 속한 파일 경로...>
git diff --cached --name-status
git diff --cached --check
```

확인할 것:

- staged 목록이 이 그룹의 파일 목록과 정확히 일치
- 계획 밖 경로(다른 그룹, `--scope` 위반) 없음
- staged diff가 비어 있지 않음

같은 파일에 staged와 unstaged가 함께 있으면 `git add <file>`로 파일 전체를 stage해 둘을 합친다. `/ccf`는 hunk 단위로 분리하지 않는다.

어긋나면 `git restore --staged -- <경로>`로 index만 되돌리고 그룹을 다시 구성한다. working tree 파일은 수정하지 않는다.

메시지 형식:

```text
type(scope): 한글 제목

- 변경 목적과 핵심 동작
- (해당하면) 이 커밋에는 파일 단위 그룹핑 때문에 함께 들어간 다른 의도
```

- type/scope는 영문 소문자, 제목과 본문은 한글, 제목은 가급적 72자 이내
- diff에 없는 사실을 쓰지 않는다. `/ccf`는 검증을 실행하지 않으므로 **검증 항목을 본문에 쓰지 않는다.**
- Breaking Change면 `!`와 `BREAKING CHANGE:` trailer를 사용한다
- 메시지는 stdin 또는 message file로 정확히 전달한다. `--amend`는 사용하지 않는다
- `--no-verify`가 있으면 `git commit --no-verify`를 사용한다

커밋 후 hash와 제목을 기록한다. hook이 파일을 수정했으면 그 사실을 보고하고, 남은 그룹 배정을 그 파일에 맞게 조정한다.

## 6. 사후 확인

```bash
git log --oneline <시작 HEAD>..HEAD
git status --short --branch --untracked-files=all
```

계획한 모든 그룹이 커밋됐고, 기본 모드에서 working tree와 index가 깨끗한지 확인한다.

## 7. Snapshot 정리

**전부 성공했을 때만** 1절의 snapshot을 삭제한다.

```bash
bash ".claude/skills/_git-atomic-core/scripts/guard.sh" release-snapshot \
  --session "<session>" \
  --token "<token>" \
  --snapshot "<snapshot>"
```

실행 조건은 다음을 **모두** 만족할 때다.

- 3절 차단 스캔을 통과했다
- 계획한 모든 그룹이 커밋됐고 누락된 그룹이 없다
- 기본 모드에서 working tree와 index가 깨끗하다

다음 경우에는 **이 명령을 실행하지 않는다.** snapshot을 그대로 남기는 것이 복구 수단이다.

- 차단 스캔에 걸려 중단했다
- 그룹 커밋 중 하나라도 실패했거나 도중에 중단했다
- 커밋되지 않고 남은 의도된 변경이 있다
- 결과가 계획과 어긋나 사용자 확인이 필요하다
- `--keep-snapshot`이 주어졌다

`--scope` 모드는 범위 밖 변경이 남아 working tree가 dirty이므로 guard가 삭제를 거부한다. 범위 밖 변경이 시작 상태 그대로 보존됐음을 확인한 경우에만 `--allow-dirty`를 추가한다. 확인할 수 없으면 정리하지 않는다.

guard가 무결성 검증 실패나 dirty를 이유로 거부하면 **그 결과를 그대로 보고하고 snapshot을 수동 삭제하지 않는다.** `rm -rf`로 우회하지 않는다.

## 8. 최종 보고

`.claude/skills/_git-atomic-core/reporting.md`의 `/ccf` 형식을 따라 한글로 보고한다.

반드시 포함:

- 순서별 hash와 제목, 각 커밋의 목적과 파일 수
- 파일 단위 그룹핑 때문에 의도가 섞인 커밋 목록
- 시작 HEAD → 최종 HEAD
- 남은 변경과 clean 여부
- snapshot을 정리했으면 그 사실, 보존했으면 경로와 보존 이유
- **worktree lock을 획득하지 않았고 프로젝트 검증을 실행하지 않았다**는 사실
- 되돌리려면 `git reset --soft <시작 HEAD>`
- push하지 않았음
- 결과가 **완전한 Atomic Commit이 아닐 수 있다**는 경고와, 공유 히스토리에는 `/cc` 또는 `/cca`를 권장한다는 안내

성공 여부를 과장하지 않는다. 실행하지 않은 검증을 "시도함"으로 보고하지 않는다. 중간에 실패하면 이미 생성된 커밋과 현재 index 상태, 보존된 snapshot 경로, 복구 지침을 그대로 보고한다.

snapshot을 정리했으면 되돌릴 때 `git reset --soft <시작 HEAD>`로 커밋만 되돌릴 수 있고 snapshot 복원은 불가능하다는 점을 함께 알린다.
