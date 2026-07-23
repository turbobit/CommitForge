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

커밋 skill은 push하지 않는다. 원격 저장소 변경은 별도 사용자 요청이 필요하다.

## 2. Diff 스냅샷

`/cc`, `/cr`, `/cca`는 작업 시작 전에 guard를 실행한다.

스냅샷은 현재 worktree의 실제 Git directory 아래에 생성된다.

- staged binary diff
- unstaged binary diff
- status
- untracked manifest와 가능한 경우 tar archive
- HEAD/branch/fingerprint
- 세션 소유권 token

성공적으로 모든 의도된 커밋과 검증이 끝나면 `finish`로 해당 세션 스냅샷만 제거한다.

스냅샷 metadata에는 보존 파일별 크기와 SHA-256이 기록된다. `finish`는 삭제 직전에 이 inventory를 다시 감사하며 누락·크기 변화·해시 불일치가 있으면 성공 처리와 삭제를 차단한다. 필요하면 `audit-snapshot`으로 중간 상태를 별도 확인한다.

`/cr`은 `verify-review`와 `finish --review-only`를 사용한다. Guard가 시작 snapshot과 종료 시점의 HEAD, branch, staged binary diff를 비교하며 하나라도 달라지면 snapshot을 삭제하거나 성공 처리하지 않는다.

실패·중단·부분 완료 시:

- `abort`로 잠금만 해제
- 스냅샷은 보존
- 위치와 원인을 보고
- 다른 세션 스냅샷은 절대 삭제하지 않음

## 3. Advisory Lock

guard는 worktree별 Git directory에 원자적으로 잠금 디렉터리를 만든다.

- 같은 worktree에서 동시에 `/cc`, `/cr`, `/cca`를 실행하면 두 번째 실행은 중단
- 다른 Git 클라이언트까지 강제로 막는 잠금은 아님
- `index.lock` 등 Git 자체 잠금이 있으면 중단
- merge/rebase/cherry-pick/revert/bisect 진행 중이면 중단
- 잠금을 강제로 삭제하지 않음
- 비정상 종료 후 stale lock은 `guard.py status`로 소유자와 스냅샷을 확인한 뒤 소유 token으로 `abort` 처리

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
- `/cc`·`/cr`·`/cca` 시작 후 다른 세션의 Git/파일 변경을 중지
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
