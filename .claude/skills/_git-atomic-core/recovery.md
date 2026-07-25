# 스냅샷과 복구

## 빠른 현재 프로젝트 잠금 정리

원래 owner session/token으로 `abort`하기 어렵고 기존 실행이 끝났음을 확인한
경우 모든 CommitForge 명령의 첫 인자로 `clean`을 사용할 수 있다.

```text
/cr clean
```

이는 현재 Git worktree의 CommitForge advisory lock을 해제하고 기존 snapshot은
보존한다. 다른 저장소·worktree는 건드리지 않는다. 알려진 Git lock은 안전한
stale 조건을 모두 충족할 때만 함께 제거한다. 활성 세션의 CommitForge lock도
해제할 수 있으므로 기존 실행이 계속 중인지 먼저 확인한다.

## 상태 확인

Skill 설치 위치에 맞게 guard를 실행한다.

```bash
python3 .claude/skills/_git-atomic-core/scripts/guard.py status
```

개인 설치라면:

```bash
python3 ~/.claude/skills/_git-atomic-core/scripts/guard.py status
```

## 스냅샷 구성

- `.cca-snapshot.json`: 소유 세션, HEAD, branch, fingerprint

`.cca-snapshot.json`의 `snapshot_files`에는 복구 자산별 크기와 SHA-256이 저장된다. 복구 전 `guard.py audit-snapshot`을 실행해 snapshot 자체가 생성 후 변조되거나 손상되지 않았는지 확인한다.

기본 `/cr`의 `--source-read-only` 실패는 소스·working diff·untracked 내용이 시작 상태와 달라졌다는 뜻이다. 자동 복원하지 말고 snapshot과 현재 상태를 비교해 원인을 보고한 뒤 `abort`로 snapshot을 보존한다.
- `staged.diff`: 작업 시작 시 index 변경
- `working.diff`: 작업 시작 시 index 대비 working tree 변경
- `status.txt`
- `status-porcelain-v2.z`
- `untracked.tar.gz`: 크기 한도 내 추적되지 않은 파일
- `untracked.z`: untracked 경로 목록
- `*.stat`

## 수동 복구 원칙

복구 전에 현재 작업을 별도로 보존하고, 원래 snapshot의 `head`와 동일한 기준인지 확인한다. 자동으로 기존 작업 위에 덮어쓰지 않는다.

깨끗한 동일 HEAD 작업 트리에서 일반적인 복구 순서:

```bash
git apply --index --binary /path/to/snapshot/staged.diff
git apply --binary /path/to/snapshot/working.diff
tar -xzf /path/to/snapshot/untracked.tar.gz
```

먼저 `--check`를 권장한다.

```bash
git apply --check --binary /path/to/snapshot/staged.diff
git apply --check --binary /path/to/snapshot/working.diff
```

staged와 working patch의 기준이 다를 수 있으므로 실제 복구는 저장소 상태에 따라 달라진다. 충돌이 있으면 중단하고 patch를 수동 검토한다.

## 비정상 종료 잠금

`guard.py status`에서 `project_root`, `git_dir`, `lock_scope`, owner의
session/token과 snapshot을 확인한다. 잠금은 표시된 `git_dir`에만 적용되므로
다른 저장소의 잠금과 혼동하지 않는다.

`status`는 `stale_candidate`, `lock_age_seconds`, `stale_after_seconds`,
`lock_owner_hostname`, `lock_owner_same_host`도 보고한다. `stale_candidate: true`는
잠금이 임계값(기본 3600초)보다 오래됐다는 뜻일 뿐 owner가 죽었다는 증거가 아니다.

생성 시각이 오래됐다는 사실만으로 stale lock이라고 단정하지 않는다. 원래
세션이 종료됐거나 더 이상 해당 작업을 수행하지 않는다는 것을 확인한 뒤
owner의 session/token으로 `abort`를 실행한다. Guard는 두 값과 정확히 일치하는
스냅샷이 하나면 경로를 자동 선택한다. 원래 세션으로 돌아갈 수 없는 경우에도
이 확인을 마쳤다면 현재 세션에서 같은 명령을 실행할 수 있다.

```bash
python3 .../guard.py abort \
  --session "<owner-session>" \
  --token "<owner-token>"
```

일치하는 스냅샷이 없거나 여러 개라 자동 선택할 수 없을 때만 `status`의
`lock_owner_snapshots`를 확인하고 `--snapshot "<snapshot-path>"`를 추가한다.

이 명령은 snapshot을 보존하고 해당 소유 잠금만 해제한다. 잠금 디렉터리를 무조건 삭제하지 않는다.

## 오래된 잠금 회수

owner token을 그대로 쓸 수 있으면 위의 `abort`가 우선이다. token 확보가 어렵고
원래 실행이 끝났음을 확인했다면 회수를 요청할 수 있다.

```bash
python3 .../guard.py begin --session "<현재-세션>" --reclaim-stale
```

같은 호스트의 잠금이면서 `stale_candidate`이거나 owner session이 현재 session과
같을 때만 해제 후 재획득한다. 거부 사유는 `reclaim_refused_reason`에
`different_host`, `lock_not_stale`, `lock_contents_unexpected`,
`lock_owner_scope_mismatch` 등으로 표시된다. 성공하면 결과의 `reclaimed_lock`,
`reclaim_reason`, `previous_owner`, `previous_lock_age_seconds`를 보고한다.
기존 owner의 snapshot은 보존된다.

임계값 기본값은 3600초이며 `--stale-after <초>`로 바꾼다. `/cr clean` 계열과의
차이는 다음과 같다.

- `clean`: 나이·호스트와 무관하게 현재 worktree 잠금을 해제만 하고 종료한다.
- `begin --reclaim-stale`: 안전 조건을 만족할 때만 해제하고 곧바로 새 잠금과
  snapshot을 확보해 작업을 이어간다.
