---
name: ccr
description: 현재 Git 변경사항을 읽기 전용으로 분석해 최적의 Atomic Commit 순서, 분리 기준, 포함 파일·hunk, 한글 메시지 초안과 검증 계획을 제시한다. 실제 staging이나 commit은 수행하지 않는다.
argument-hint: "[추가 맥락] [--scope <경로...>] [--compact]"
disable-model-invocation: true
model: inherit
effort: high
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git show *)
  - Bash(git branch *)
  - Bash(git rev-parse *)
  - Bash(git ls-files *)
  - Bash(git check-attr *)
  - Bash(git check-ignore *)
  - Bash(git cat-file *)
  - Bash(git submodule status *)
  - Bash(git worktree list *)
---

# `/ccr` — CommitForge Atomic Commit 계획 리뷰

사용자 참고 맥락:

```text
$ARGUMENTS
```

**읽기 전용 명령이다.** Git index, working tree, branch, stash, commit, 파일 내용을 변경하지 않는다. 테스트·빌드처럼 산출물을 만들 수 있는 명령도 실행하지 않는다.

## 필수 지침 로드

다음을 읽는다.

1. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/atomic-commit-rules.md`
2. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/commit-message-guide.md`
3. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/project-profiles.md`
4. `${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`
5. 필요하면 `${CLAUDE_SKILL_DIR}/../_git-atomic-core/examples.md`

## 1. 인자 해석

- 일반 문장은 작업 목적과 분리 의도에 참고한다.
- `--scope <경로...>`가 있으면 분석 범위를 제한하되, 의존성 판단에 필요한 관련 파일은 읽을 수 있다.
- `--compact`가 있으면 본문 초안은 핵심 bullet만 제시한다.
- 알 수 없는 인자는 자연어 맥락으로 취급한다.

## 2. 저장소 상태 확인

다음을 실행한다.

```bash
git status --short --branch --untracked-files=all
git rev-parse --show-toplevel
git branch --show-current
git diff --cached --name-status
git diff --name-status
git diff --cached
git diff
git ls-files --others --exclude-standard
git diff --cached --check
git diff --check
```

추가로 최근 메시지 스타일을 확인한다.

```bash
git log -20 --pretty=format:'%h%x09%s'
```

다음을 명시한다.

- branch와 HEAD
- staged/unstaged/untracked
- staged와 unstaged가 같은 파일에 섞였는지
- merge/rebase/cherry-pick 등 진행 상태 징후
- rename/delete/submodule/binary
- 분석 시점 이후 변경되면 계획이 무효화될 수 있음

변경이 없으면 계획을 만들지 말고 “분석할 변경 없음”을 보고한다.

## 3. 의미 분석

각 file/hunk를 다음 기준으로 분류한다.

- 기능 추가
- 버그 수정
- 동작 보존 리팩터링
- 성능
- 테스트-only
- 문서
- build/의존성
- CI
- style/formatting
- generated/migration/lockfile
- 의도 불명 또는 임시 변경

필요한 관련 구현, 호출부, 타입, 테스트, 설정, migration을 읽는다. `git diff`만으로 의도를 확정할 수 없으면 “추정”으로 표시한다.

특히 확인:

- 숨은 리팩터링과 기능 변경 혼합
- 직접 회귀 테스트 누락
- rename/move와 로직 변경 혼합
- lockfile의 설명되지 않는 대규모 변경
- generated file과 원본 불일치
- debug log, TODO/FIXME, 임시 코드
- secret/credential 가능성(값은 재출력하지 않음)
- API/schema/config Breaking Change
- 서로 다른 package/domain의 독립성

## 4. Commit Dependency Graph

각 후보 unit 사이의 의존성을 판단한다.

- 어느 변경이 선행되어야 빌드·타입·테스트가 성립하는가?
- 독립적으로 cherry-pick/revert 가능한가?
- 양방향 의존이면 합쳐야 하는가?
- backward-compatible 전환 단계가 필요한가?
- migration/deployment 순서가 필요한가?

기계적인 type 순서보다 실제 의존성과 중간 상태의 건전성을 우선한다.

## 5. 계획 작성

`${CLAUDE_SKILL_DIR}/../_git-atomic-core/reporting.md`의 `/ccr` 형식을 따른다.

각 커밋마다 반드시 제시:

1. 권장 순서
2. `type(scope): 한글 제목`
3. 하나의 목적
4. 포함 파일
5. 파일 내부 분리가 필요하면 포함 hunk를 함수/구문/변경 내용으로 식별
6. 제외할 file/hunk
7. 분리 또는 그룹화 이유
8. 선행 의존성
9. 상세한 한글 본문 초안
10. 권장 targeted 검증
11. Breaking Change·migration·배포 위험
12. 예상 staging 방식
   - whole-file
   - `git add -p`
   - 선택 patch
   - 기존 staged 우선

파일 전체를 단순 나열하지 말고, 같은 파일의 서로 다른 hunk가 다른 커밋에 들어가면 명확히 표시한다.

## 6. 자체 검토

계획을 한 번 더 비판적으로 검토한다.

- 한 커밋에 `및/그리고`로 연결된 독립 목적이 있는가?
- 구현과 필수 테스트를 과도하게 분리했는가?
- 중간 커밋이 빌드/타입을 깨뜨리는가?
- 파일 단위로 기계적으로 쪼갰는가?
- 포맷팅을 로직에 섞었는가?
- staged 사용자 의도를 무시했는가?
- scope 밖 필수 의존성을 누락했는가?
- 메시지가 diff보다 과장됐는가?

필요하면 계획을 수정한 뒤 최종안만 제시한다.

## 7. 최종 요약

한글로 다음을 끝에 표시한다.

- 예상 커밋 수
- 권장 순서 한 줄 요약
- 실행 전 차단 요소
- 사용자 판단이 필요한 항목
- `/cc` 실행 시 재분석이 필요한 이유
- **실제 Git 상태를 변경하지 않았음**

`/ccr` 결과를 파일에 저장하거나 staging/commit하지 않는다.
