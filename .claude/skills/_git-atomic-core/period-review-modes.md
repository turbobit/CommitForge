# Today·Weekly 기간 리뷰

`/cca today|weekly`와 `/cr today|weekly`에서 이 규칙을 사용한다.

## 1. 경계와 대상

먼저 `period_range.py`로 정확한 경계를 계산한다.

```bash
python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/period_range.py" today
python3 "${CLAUDE_SKILL_DIR}/../_git-atomic-core/scripts/period_range.py" weekly
```

- `today`: 호스트 로컬 달력의 오늘 00:00부터 현재까지다. 최근 24시간이 아니다.
- `weekly`: 기본 월요일 00:00부터 현재까지다. 최근 7일이 아니다.
- `--week-start sunday`이면 일요일 00:00을 사용한다.
- `--timezone <IANA|±HH:MM>`이면 해당 시간대를 사용한다. 해석할 수 없으면 임의 대체하지 않는다.
- 최종 보고에 timezone, UTC offset, 시작·종료 ISO 시각을 표시한다.
- 현재 branch에서 `HEAD`로 도달 가능한 commit만 포함한다.
- 기본 작성자는 `git config --get user.email`과 일치시킨다. `--all-authors`면 제한을 제거한다.
- 작성자 email이 없으면 전체 작성자를 사용했다는 경고를 남긴다.
- 포함 판정은 committer timestamp를 기준으로 하고 author·committer 시각을 모두 원장에 기록한다.

권장 조회:

```bash
git config --get user.email
git log --since="<start>" --until="<end>" --topo-order --reverse \
  --pretty=format:'%H%x09%P%x09%an%x09%ae%x09%aI%x09%cI%x09%s'
```

## 2. 커밋 원장과 Net Effect

1. 포함 commit마다 hash, parents, author, committer time, subject, name-status, numstat을 기록한다.
2. non-merge commit 통계와 merge commit을 분리한다. merge의 전체 diff를 다시 합산해 중복 계산하지 않는다.
3. oldest included commit의 첫 parent를 context base로 기록한다. root commit이면 empty tree를 사용한다.
4. 선택 작성자 원장은 commit별 변화로 계산하고, branch 전체 net effect는 `<context-base>..HEAD`로 별도 계산한다.
5. revert, fixup, 후속 correction, 같은 줄의 반복 변경을 연결해 “시도한 변화”와 “최종 남은 변화”를 구분한다.
6. commit 경계를 넘어 생기는 API·schema·설정·migration·호출자·테스트 불일치를 검토한다.
7. working tree는 `period commits`와 별도 원장으로 유지하고 마지막에 상호작용을 검토한다.

finding에는 원인을 다음 중 하나로 귀속한다.

- `period-commit:<hash>`
- `period-interaction:<hash>..<hash>`
- `working-tree`
- `period-to-working:<hash>`
- `pre-existing` — 기간 시작 전부터 존재하며 이번 변화가 확대하지 않음

## 3. 리뷰 강도

- 기간의 모든 최종 net hunk를 Line·Correctness·Security와 적용 가능한 reviewer에 배정한다.
- 제거된 동작, wrapper/proxy 의미 보존, cross-file contract를 commit 경계와 net diff 양쪽에서 확인한다.
- 기간 중 추가됐다가 제거된 위험 동작도 이력상 회귀 신호로 보고하되 현재 blocker와 구분한다.
- 테스트가 중간 commit에서 깨졌다가 후속 commit에서 복구됐는지, 최종 HEAD에서 실제로 통과하는지 구분한다.
- 기간이 대형 diff 기준을 넘으면 domain shard와 cross-file aggregator를 사용한다.
- 분석하지 못한 commit 또는 hunk는 `UNKNOWN`이며 성공으로 숨기지 않는다.

## 4. `/cr` 동작

- 기간 commit과 현재 working tree를 함께 심층 리뷰한다.
- 기간 commit과 그로 인한 현재 HEAD 문제는 읽기 전용이다. history를 수정하거나 자동 corrective change를 만들지 않는다.
- 현재 working hunk가 만든 확정적 문제만 기본 `/cr` 정책에 따라 국소 수정할 수 있다.
- `--no-fix`이면 working tree도 수정하지 않는다.
- Atomic Commit 계획·메시지·staging·commit·push는 항상 금지한다.
- working tree가 깨끗해도 기간 commit이 있으면 리뷰를 수행한다.
- 기간 commit이 없고 working tree도 깨끗할 때만 “검토 대상 없음”으로 종료한다.

## 5. `/cca` 동작

- 기간 commit은 분석·보고에만 사용하며 amend, rebase, squash, reset 또는 재생성하지 않는다.
- 현재 미커밋 변경만 기본 `/cca` 파이프라인으로 수정·검증·Atomic Commit한다.
- 과거 기간 commit에서 발견한 문제를 이유로 clean working tree에 새 수정을 자동 생성하지 않는다. 별도 후속 작업으로 제안한다.
- working tree가 깨끗하면 기존 기간 commit 보고만 반환한다.
- 새 commit은 기존 기간 commit과 구분하고 최종 기간 통계에는 함께 표시한다.

## 6. Today 보고

- 정확한 경계·작성자 조건·현재 branch
- 시간순 commit 원장과 각 목적
- 기존 commit과 working/new commit 구분
- 최종 net effect와 되돌려진 변화
- finding 귀속과 현재 blocker
- 변경 파일·추가·삭제 통계와 검증 결과

## 7. Weekly 보고

Today 보고에 다음을 더한다.

- 날짜별 commit·변경량·검증 상태
- package/domain별 작업 묶음
- 작성자별 집계(`--all-authors`일 때)
- 반복 수정·revert·flaky test·누적 위험 추세
- 미완료 기능, 테스트·문서·migration·관측성 공백
- 다음 주 우선순위. 근거 없는 제품 일정이나 담당자는 추측하지 않는다.
