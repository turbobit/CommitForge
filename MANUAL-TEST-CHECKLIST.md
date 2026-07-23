# 수동 End-to-End 시험 체크리스트

중요 저장소가 아닌 임시 저장소 또는 별도 worktree에서 수행합니다.

## 1. 설치 확인

```bash
claude --version
python3 verify.py
```

Claude Code에서 `/`를 입력해 다음이 보이는지 확인합니다.

- `ccr`
- `cc`
- `cca`

custom reviewer가 보이지 않으면 Claude Code를 재시작합니다.

## 2. `/ccr` read-only 확인

서로 다른 의도의 작은 변경 두 개와 테스트 하나를 만듭니다.

```text
/ccr 테스트용 변경
```

확인:

- 2개 이상의 적절한 Atomic Commit 계획
- 파일/hunk와 분리 이유
- 한글 제목/본문 초안
- `git status`가 실행 전과 동일
- 실제 commit 없음

## 3. `/cc` 실행 확인

```text
/cc 테스트용 변경
```

확인:

- 소스 파일 내용은 바뀌지 않고 index/commit만 변경
- 의미별 여러 commit
- 각 제목이 `type(scope): 한글 제목`
- 구현과 직접 테스트가 논리적으로 함께 배치
- 마지막 `git status` clean
- snapshot 삭제와 lock 해제 보고
- push 없음

```bash
git log --oneline --decorate -10
git show --stat HEAD
```

## 4. `/cca --no-fix` 확인

새로운 작은 변경을 만든 뒤:

```text
/cca --no-fix 테스트 변경
```

확인:

- 5개 reviewer 또는 main fallback
- 근거가 있는 finding
- 소스 자동 수정 없음
- blocker가 없을 때 검증 후 commit
- reviewer finding이 과장되지 않음

## 5. `/cca` 자동 수정 확인

의도적으로 명백하고 국소적인 회귀 테스트 누락 또는 null 경계 오류를 만든 테스트 저장소에서:

```text
/cca 테스트 변경
```

확인:

- 문제를 실제 코드 근거로 검증
- 최소 범위 수정
- 재리뷰
- targeted test
- 수정된 현재 diff로 commit 계획 재생성
- unrelated 리팩터링 없음

## 6. 동시 실행 차단

같은 worktree의 두 Claude Code 세션에서 `/cc`를 거의 동시에 실행합니다.

확인:

- 첫 실행만 guard lock 획득
- 두 번째 실행은 Git 변경 없이 중단
- lock을 강제 삭제하지 않음

실제 병렬 개발은 별도 worktree에서 시험합니다.

## 7. 실패 복구

commit hook 실패를 재현하거나 작업을 중단합니다.

확인:

- 소유 lock 해제
- snapshot 보존 위치 보고
- `guard.py status`에서 snapshot 확인
- 다른 세션 snapshot 미삭제
