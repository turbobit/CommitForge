# 안전한 Staging 전략

## 1. 절대 원칙

- `git add -A` 또는 `git add .`를 기본 전략으로 사용하지 않는다.
- 현재 atomic unit에 포함되는 path/hunk만 stage한다.
- working tree의 사용자 코드를 staging 편의를 위해 편집하지 않는다.
- `git reset --hard`, `git checkout -- .`, `git clean`을 사용하지 않는다.
- pathspec 앞에 `--`를 사용하여 옵션처럼 보이는 파일명을 안전하게 처리한다.
- stage 직후 항상 `git diff --cached`로 실제 index 내용을 검토한다.
- 커밋 직전 `git diff --cached --check`로 whitespace 오류를 확인한다.

## 2. 전체 인벤토리

먼저 다음 네 영역을 구분한다.

1. 기존 staged tracked 변경
2. unstaged tracked 변경
3. untracked 파일
4. rename/delete/submodule 등 특수 상태

권장 확인 명령:

```bash
git status --short --branch --untracked-files=all
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
```

## 3. 파일 전체가 하나의 atomic unit인 경우

다른 hunk와 섞이지 않은 파일만 명시적으로 stage한다.

```bash
git add -- path/to/file-a path/to/file-b
```

삭제와 rename도 `git add -- <path>` 또는 관련 old/new path를 명시한다. stage 후 실제 rename 감지가 의도와 일치하는지 `git diff --cached --summary`로 확인한다.

## 4. 한 파일에 여러 의도가 섞인 경우

우선순위:

1. 현재 환경에서 신뢰할 수 있으면 `git add -p -- <path>`
2. 그렇지 않으면 선택 hunk만 포함한 patch를 만들어 index에 적용
3. 안전하게 분리할 수 없으면 관련 변경을 합치거나 중단하고 이유를 보고

Patch 방식:

1. `git diff HEAD -- <path>`로 최종 변경을 확인한다.
2. 현재 index에 해당 파일의 혼합 변경이 있으면 스냅샷 확보 후 그 파일만 `git restore --staged -- <path>`로 HEAD 기준으로 되돌린다.
3. 원하는 hunk와 충분한 context만 포함한 patch 파일을 세션 스냅샷 디렉터리 아래에 만든다.
4. `git apply --cached --check <patch>`로 검증한다.
5. 검증 성공 시 `git apply --cached <patch>`를 수행한다.
6. `git diff --cached -- <path>`와 `git diff -- <path>`를 모두 확인한다.

Patch 파일은 프로젝트 작업 트리에 두지 않는다. 커밋 성공 후 세션 스냅샷과 함께 제거한다.

## 5. staged와 unstaged가 같은 파일에 존재하는 경우

`git add -- <file>`은 unstaged 내용까지 모두 index에 올리므로 금지한다.

다음 중 하나를 선택한다.

- 기존 staged hunk가 atomic이면 그대로 커밋하고 나머지는 다음 커밋으로 둔다.
- index의 해당 파일만 안전하게 비운 뒤 선택 patch로 재구성한다.
- 분리가 불확실하면 자동 커밋을 중단하고 정확한 충돌 지점을 보고한다.

## 6. 새 파일 부분 staging

새 파일 전체가 하나의 unit이면 명시적으로 `git add -- <file>`한다.

새 파일 내부에 여러 의도가 섞여 꼭 분리해야 한다면:

```bash
git add -N -- path/to/new-file
```

로 intent-to-add 상태를 만든 뒤 선택 patch를 index에 적용할 수 있다. 단, 복잡한 새 파일을 인위적으로 나누어 중간 커밋을 불완전하게 만들지 않는다.

## 7. 삭제와 rename

- 삭제가 의도된 것인지 관련 참조를 확인한다.
- rename과 대규모 수정이 섞이면 가능한 rename-only 커밋 후 수정 커밋으로 분리한다.
- Git의 rename 감지는 휴리스틱이므로 old/new 파일 관계를 직접 확인한다.
- case-only rename은 대소문자 비구분 파일시스템에서 특별히 주의한다.
- 파일 이동 후 import 경로 변경이 없으면 빌드가 깨지는 경우 같은 커밋에 포함한다.

## 8. 커밋 후보 검증

각 commit 후보마다 다음을 확인한다.

```bash
git diff --cached --stat
git diff --cached --name-status
git diff --cached --summary
git diff --cached --check
git diff --cached
```

검증 항목:

- 계획에 없는 파일/hunk가 들어갔는가?
- 필요한 파일/hunk가 빠졌는가?
- secret, debug code, 임시 로그가 포함됐는가?
- 포맷팅이 로직과 불필요하게 섞였는가?
- rename/delete가 의도와 일치하는가?
- 테스트와 구현의 관계가 완결됐는가?
- staged diff가 비어 있지 않은가?

## 9. Commit hook 실패

- hook 실패 원인을 먼저 읽고 해결한다.
- 사용자가 `--no-verify`를 명시하지 않았다면 자동으로 우회하지 않는다.
- hook이 파일을 수정했다면 변경사항 전체를 다시 분석한다.
- hook이 생성한 변경을 무조건 기존 커밋에 추가하지 않는다.
- 실패한 commit 후 index와 working tree 상태를 다시 확인한다.

## 10. TOCTOU 재검사

분석 시점과 실행 시점 사이에 다른 세션이나 프로세스가 변경할 수 있다.

- 계획 수립 후 guard fingerprint를 기록한다.
- stage 직전 상태가 예상 fingerprint와 다르면 재분석한다.
- 자신의 stage/commit 후에는 새 fingerprint를 기준점으로 갱신한다.
- 설명되지 않는 외부 변경이 감지되면 즉시 중단한다.
- 잠금은 협조적(advisory) 잠금일 뿐 다른 Git 도구를 강제로 막지 못한다.

## 11. Commit 후

```bash
git show --stat --oneline --decorate --no-renames HEAD
git status --short --branch --untracked-files=all
```

남은 변경을 처음부터 다시 분석한다. 이전 계획을 기계적으로 계속 적용하지 않는다.
