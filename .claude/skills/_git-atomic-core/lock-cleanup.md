# 현재 프로젝트 잠금 정리

모든 CommitForge 명령은 첫 번째 위치 인자가 정확히 `clean`이면 일반 흐름보다 먼저
다음 명령만 실행하고 종료한다.

```bash
bash "<absolute-CF_CORE>/scripts/guard.sh" clean \
  --request-session "$COMMITFORGE_SESSION_ID"
```

`<absolute-CF_CORE>`는 각 SKILL.md의 Preflight에서 확정한 `_git-atomic-core` 절대경로다.
경로를 확정하지 못했으면 잠금을 건드리지 않고 미설치로 보고한다.

규칙:

- 현재 실행 디렉터리의 `git rev-parse --git-dir`로 확인한 **현재 worktree 잠금만**
  대상으로 한다.
- 다른 저장소·다른 worktree의 잠금, 작업 파일, index, commit, branch를
  건드리지 않는다.
- 보존된 Diff snapshot은 삭제하지 않는다.
- 잠금이 없으면 성공한 no-op으로 보고한다.
- `clean` 뒤의 다른 인자는 무시하고 일반 명령 흐름, Guard `begin`, reviewer,
  테스트, staging, commit, push를 실행하지 않는다.
- 기존 owner 세션이 실제 실행 중이어도 명시적인 `clean` 요청은 잠금을 해제한다.
  이 경우 기존 실행이 Guard 보호를 잃는다는 경고와 기존 owner, 현재
  `project_root`, `git_dir`, `lock_path`, 보존 snapshot을 보고한다.
- Guard 결과의 `ok`와 `lock_released`를 그대로 보고한다. 실패했는데 성공으로
  표현하거나 잠금 디렉터리를 수동 삭제하지 않는다.
- Guard 명령이 실행되지 못한 경우(exit code 126·127, `No such file or directory`,
  `command not found`, Python 미탐지)도 실패다. 잠금이 정리됐다고 보고하지 않는다.
- `clean`은 알려진 Git lock(`index.lock`, `HEAD.lock`, `packed-refs.lock`,
  `config.lock`)이 임계시간 이상·0바이트·writer 없음·진행 중 Git operation 없음이고
  검사 중 identity가 바뀌지 않았을 때만 제거한다.
- writer 판별은 macOS/Unix의 `lsof` 접근 모드, Linux `/proc` fd flags,
  Windows Win32 share-mode를 사용한다. Finder·Spotlight·Explorer·인덱서의
  읽기 전용 핸들은 writer가 아니다. 판별 불능은 자동 삭제하지 않는다.
- `git_locks_removed`, `git_lock_cleanup`과 남아 있는 `git_locks`를 함께 보고한다.
  남은 lock이 있으면 "정리 완료"로만 표현하지 말고 경로, `age_seconds`, `size`,
  `writer_pids`, `stale_candidate`, skip reason을 보고한다.
