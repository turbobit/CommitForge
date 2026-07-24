# 스냅샷과 복구

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

`guard.py status`에서 owner의 session/token과 snapshot을 확인한다. 해당 세션이 더 이상 실행 중이 아님을 확인한 뒤 같은 token으로 `abort`를 실행한다.

```bash
python3 .../guard.py abort \
  --session "<owner-session>" \
  --token "<owner-token>" \
  --snapshot "<snapshot-path>"
```

이 명령은 snapshot을 보존하고 해당 소유 잠금만 해제한다. 잠금 디렉터리를 무조건 삭제하지 않는다.
