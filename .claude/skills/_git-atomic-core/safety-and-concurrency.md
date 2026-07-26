# 안전·동시 실행 규칙

## 1. 작업 유실 방지

절대 자동 실행 금지:

- `git reset --hard`
- `git clean -f`, `git clean -fd`, `git clean -fdx`
- `git checkout -- .`
- `git restore --worktree .`
- `git stash drop`, `git stash clear`
- `git branch -D`
- `git reflog expire`
- `git gc --prune=now`
- `git push --force`, `git push --force-with-lease`
- 사용자 요청 없는 `git commit --amend`
- 사용자 요청 없는 rebase, squash, history rewrite

커밋 skill은 push하지 않는다. 유일한 예외인 `/cp`는 사용자가 직접 호출했을 때 검증된 현재 branch를 force 없이 push하고 새 Pull Request 하나만 생성한다.

tag 생성도 기본적으로 금지한다. 유일한 예외는 `/cca release --prepare --tag`이며 다음을 모두 만족해야 한다.

- 결정론적 version/tag 계산 결과 사용
- tag 미존재 재확인
- release commit과 최종 검증 성공
- clean working tree
- 최종 HEAD를 가리키는 로컬 annotated tag

이 예외도 tag push, GitHub Release, publish, deploy를 허용하지 않는다. `/cr`은 어떤 모드에서도 tag를 만들지 않는다.

## 2. Diff 스냅샷

`/cc`, `/cr`, `/cca`, `/cpr`, `/cp`는 작업 시작 전에 guard를 실행한다.

스냅샷은 현재 worktree의 실제 Git directory 아래에 생성된다.

- staged binary diff
- unstaged binary diff
- status
- untracked manifest와 가능한 경우 tar archive
- HEAD/branch/fingerprint
- 세션 소유권 token

성공적으로 모든 의도된 커밋과 검증이 끝나면 `finish`로 해당 세션 스냅샷만 제거한다.

스냅샷 metadata에는 보존 파일별 크기와 SHA-256이 기록된다. `finish`는 삭제 직전에 이 inventory를 다시 감사하며 누락·크기 변화·해시 불일치가 있으면 성공 처리와 삭제를 차단한다. 필요하면 `audit-snapshot`으로 중간 상태를 별도 확인한다.

`/cr`은 `verify-review`와 `finish --review-only`를 사용한다. Guard가 시작 snapshot과 종료 시점의 HEAD, branch, staged binary diff를 비교하며 하나라도 달라지면 snapshot을 삭제하거나 성공 처리하지 않는다. 기본 `/cr`은 두 명령에 `--source-read-only`도 사용해 working binary diff, porcelain status, untracked 내용까지 일치시킨다. 일반 리뷰에서 사용자가 `--fix`를 명시한 경우에만 source read-only 검사를 생략한다. `release`·`emergency`·`learn`은 `--fix`와 관계없이 source read-only다.

`verify-review`와 `finish`는 `--session`만 주면 현재 worktree에서 동일 session인
lock owner의 token과 유일한 snapshot을 자동 선택한다. 명시적인 token 또는
snapshot이 있으면 자동으로 대체하지 않고 정확히 검증한다. 따라서 잘못된
cross-worktree 경로나 basename은 계속 fail-closed다.

`/cpr`은 같은 source read-only 불변식을 그대로 적용한다. `/cp`가 `main` 또는 `master`에서 새 branch를 만드는 경우에만 `--expected-branch`로 그 이름 하나를 허용하며 HEAD commit, staged/working diff와 untracked 내용은 모두 시작 상태와 같아야 한다.

실패·중단·부분 완료 시:

- `abort`로 잠금만 해제
- 스냅샷은 보존
- 위치와 원인을 보고
- 다른 세션 스냅샷은 절대 삭제하지 않음

## 3. Advisory Lock

guard는 worktree별 Git directory에 원자적으로 잠금 디렉터리를 만든다.

- 설치된 `SessionStart` 훅이 Claude가 제공한 실제 `session_id`를
  `COMMITFORGE_SESSION_ID`로 전달하며, Guard owner에는 이 값만 사용한다.
- 정상 응답 종료와 API 실패의 `Stop`·`StopFailure`, `/clear`·`/exit`·`/resume` 등의
  `SessionEnd`에서 종료 세션과 owner가 정확히 일치할 때만 잠금을 자동 해제한다.
  자동 해제에서도 Diff snapshot은 보존한다.
- 수동·자동 `/compact`는 같은 세션의 연속 실행이므로 잠금을 해제하지 않는다.
  compact 뒤 `SessionStart`가 같은 ID를 다시 바인딩한다.
- 같은 worktree에서 동시에 `/cc`, `/cr`, `/cca`, `/cpr`, `/cp`를 실행하면 두 번째 실행은 중단
- 잠금 식별자는 명령 이름이나 부모 폴더가 아니라 `git rev-parse --git-dir`로 얻은 실제 worktree Git directory
- 같은 부모 폴더 아래의 서로 다른 Git 저장소는 각자의 Git directory를 사용하므로 서로 차단하지 않음
- 같은 저장소의 일반 하위 폴더는 동일한 Git directory로 해석되므로 서로 차단
- 다른 Git 클라이언트까지 강제로 막는 잠금은 아님
- `index.lock` 등 Git 자체 잠금이 있으면 중단
- merge/rebase/cherry-pick/revert/bisect 진행 중이면 중단
- 잠금을 임의 파일 삭제로 강제 해제하지 않음
- 사용자가 모든 slash command의 첫 인자로 정확히 `clean`을 요청한 경우에만
  Guard의 `clean`이 현재 worktree의 CommitForge advisory lock을 명시적으로
  해제함. 다른 worktree와 snapshot은 건드리지 않음
- `SessionEnd`를 전달할 수 없는 강제 종료·전원 손실 후 stale lock은 해당 저장소에서 `guard.py status`로 `project_root`,
  `git_dir`, 소유자와 스냅샷을 확인한 뒤 소유 session/token으로 `abort` 처리
- 생성 시각이 오래됐다는 이유만으로 stale이라고 단정하지 않으며, 원래 세션의 종료를 먼저 확인

### stale 후보 판정과 회수

Guard는 owner에 `hostname`을 기록하고 `status`·`begin` 결과에 다음을 보고한다.

- `lock_age_seconds`, `stale_after_seconds`, `stale_candidate`
- `lock_owner_hostname`, `lock_owner_same_host`, `current_hostname`
- `begin` 충돌에서는 `lock_owner_same_session`, `reclaim_refused_reason`

`stale_candidate`는 `lock_age_seconds >= stale_after_seconds`(기본 3600초)라는
뜻일 뿐 원래 세션이 죽었다는 증거가 아니다. Guard는 이 값만으로 잠금을 자동
해제하지 않는다.

사용자가 원래 실행의 종료를 확인한 뒤에만 회수한다.

```bash
python3 .../guard.py begin --session "$COMMITFORGE_SESSION_ID" --reclaim-stale
```

`--reclaim-stale`은 다음을 모두 만족할 때만 기존 잠금을 해제하고 재획득한다.

- owner `hostname`이 현재 호스트와 같음 (`different_host`면 거부)
- `stale_candidate`가 `true`이거나 owner session이 현재 session과 동일
  (`lock_not_stale`이면 거부)
- 잠금 경로가 일반 디렉터리이고 내용이 `owner.json` 하나뿐
  (`lock_path_unsafe`, `lock_contents_unexpected`면 거부)
- owner의 `worktree`·`git_dir`가 현재 저장소와 일치
  (`lock_owner_scope_mismatch`면 거부)

기존 owner의 snapshot은 삭제하지 않는다. 임계값은 `--stale-after <초>`로 조정한다.

### Git 자체 lock

`index.lock`, `HEAD.lock`, `packed-refs.lock`, `config.lock`은 CommitForge가 아니라
Git이 만든 파일이다. `begin`은 이 파일이 있으면 `reason=git_external_lock`으로
중단한다. `begin`, `status`, `--reclaim-stale`은 이 파일을 삭제하지 않는다.

Guard는 각 lock에 대해 `path`, `size`, `age_seconds`, `modified_at`,
`writer_pids`, `stale_candidate`를 보고한다. 정상적인 index 연산은 1초 이내에
끝나므로 다음을 모두 만족할 때만 stale 후보로 표시한다.

- `age_seconds >= stale_after_seconds` (기본 300초, `--git-lock-stale-after`로 조정)
- 파일 크기가 0
- 쓰기 모드로 파일을 연 프로세스가 없음

macOS/Unix는 `lsof`의 `w`·`u` 접근 모드, Linux는 `/proc`의 fd flags,
Windows는 Win32 share-mode를 사용한다. Finder·Spotlight·Explorer·인덱서의
읽기 전용 핸들은 writer로 보지 않는다. 판별할 수 없으면 `writer_pids`는 `null`이며
stale 후보로 표시하지 않는다.

명시적 `clean`만 stale 후보를 다시 검사해 제거할 수 있다. 진행 중 Git operation이
없고, symbolic link가 아니며, writer가 없고, 두 검사 사이에 device/inode/크기/mtime이
바뀌지 않아야 한다. 하나라도 불명확하면 fail-closed로 보존하고 skip reason을
보고한다.

명시적 `clean`은 owner token 복구가 어려운 비정상 종료를 위한 운영자
override다. 활성 owner도 잠금을 잃을 수 있으므로 Guard는 기존 owner와 보존
snapshot, 경고를 결과에 포함한다. `clean` 이후 일반 명령을 자동 재개하지
않으며 사용자가 다음 명령을 별도로 실행한다.

## 4. 여러 Claude Code 세션

동일 작업 트리에서 여러 세션이 동시에 파일을 편집하면 어떤 프롬프트도 완전한 안전을 보장할 수 없다.

권장 방식:

```bash
git worktree add ../repo-feature-a -b feature/a
git worktree add ../repo-feature-b -b feature/b
```

각 세션을 서로 다른 worktree에서 실행한다. 각 worktree는 별도 index와 guard lock을 가진다.

동일 worktree에서 병렬 세션이 필요하다면:

- 편집 세션과 커밋 세션을 동시에 실행하지 않음
- `/ccr`은 read-only이지만 분석 중 변경되면 계획이 낡을 수 있음
- `/cc`·`/cr`·`/cca`·`/cpr`·`/cp` 시작 후 다른 세션의 Git/파일 변경을 중지
- 예상하지 못한 fingerprint 변화 시 중단

## 5. 진행 중 Git 작업

다음 상태에서는 자동 커밋을 시작하지 않는다.

- merge conflict
- rebase
- cherry-pick
- revert
- bisect
- unresolved index
- detached HEAD가 의도인지 불명확한 상태
- unborn branch의 복잡한 부분 staging

상태와 필요한 수동 조치를 보고한다. 자동으로 `--continue`, `--abort`, `--skip`하지 않는다.

## 6. Hook과 서명

- commit hook을 기본적으로 존중한다.
- hook 실패를 `--no-verify`로 자동 우회하지 않는다.
- 서명 설정 실패 시 임의로 `commit.gpgsign`을 끄지 않는다.
- hook이 파일을 수정하면 전체 diff와 계획을 다시 분석한다.
- 사용자가 `--no-verify`를 명시한 경우에만 hook 우회를 허용하며 결과에 기록한다.

## 7. 민감정보

커밋 전 diff에서 다음을 확인한다.

- API key, token, password, private key
- `.env`, credential 파일
- 인증 cookie/session
- 개인정보·운영 데이터
- 내부 URL과 인프라 식별자
- 비정상적인 고엔트로피 문자열

민감정보 가능성이 있으면 커밋을 중단한다. 값을 출력에 그대로 재현하지 않고 파일과 위치만 마스킹해 보고한다.

## 8. Scope 제한

`--scope`로 일부만 커밋하는 경우:

- scope 밖 변경을 stage하지 않음
- scope 밖 변경 fingerprint가 바뀌지 않았는지 확인
- 작업 트리가 dirty인 채 종료될 수 있음
- 모든 제외 변경이 그대로임을 검증한 경우에만 `finish --allow-dirty` 사용
- 검증이 불확실하면 snapshot을 보존하고 잠금만 해제
