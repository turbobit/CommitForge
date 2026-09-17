# 리뷰 원장 공용 프로토콜

원장은 hunk 커버리지의 **분모를 모델이 아니라 스크립트가 소유**하게 만든다.
컨텍스트가 압축되어도 디스크에 남으며, 종료 게이트는 대화 기억이 아니라 이
파일을 검사한다.

이 문서는 원장을 쓰는 모든 명령어의 공통 규약이다. 명령어별 차이는 §1의 표와 각
`SKILL.md`에만 둔다.

## 1. 명령어별 선언

`init --skill <name>`이 저장한 값이 그 실행의 **필수 reviewer 관점 집합**을
결정한다. 정본은 `scripts/ledger.py`의 `REQUIRED_REVIEWER_ROLES`이며 아래 표는 그
사본이다. 둘이 어긋나면 코드가 이긴다.

| skill | scope | 필수 관점 |
|---|---|---|
| `cr` | `working`, 필요 시 `range:<A>..<B>` | line, correctness, security, architecture, performance |
| `cca` | `working` | line, correctness, security, architecture, performance, git |
| `cpr` | `range:<A>..<B>` | line, correctness, security, architecture, performance, release |
| `cp` | `range:<A>..<B>` | line, correctness, security, architecture, performance, release |

`--skill`을 넘기지 않으면 line·correctness·security 세 개로 폴백한다. 진행 중이던
리뷰가 강제 확대로 갑자기 차단되지 않게 하는 하위 호환 장치이며, 새 실행에서
의도적으로 쓰는 값이 아니다.

`/ccr`이 표에 없는 것은 의도다. `/ccr`은 Guard `begin`을 호출하지 않아 snapshot이
없고, 원장은 snapshot 안에 산다. snapshot을 주면 배타적 worktree 락도 함께 잡게
되어 가벼운 계획 명령이 리뷰와 동시에 돌 수 없게 된다. `/cc`·`/cca`가 그 계획을
어차피 재분석하므로, 얻는 커버리지보다 잃는 것이 크다.

## 2. 실행 순서

```
Guard begin
  ↓
status            재개 여부 판정
init --scope ...  신규 실행이면 즉시
  ↓
리뷰 범위 계산
  ↓
init --scope ...  범위가 늦게 정해지는 scope만 추가 선언
inventory         모든 scope를 선언한 뒤 한 번
  ↓
record            reviewer batch 결과를 받을 때마다 즉시
  ↓
(수정했다면) advance → 재리뷰 → record
  ↓
report            finish 이전에 최종 보고 재료 확보
verify-review     불변식과 원장 게이트
finish
```

`init`이 Guard `begin` 직후여야 컴팩트 이후 재개가 가능하다. 커밋 범위
`<A>..<B>`는 `period_range.py`·`git merge-base`·`pr_context.py`로 계산되기 전에는
알 수 없으므로, 그 scope만 나중에 한 번 더 선언한다.

## 3. 재개

```bash
python3 "<CF_CORE>/scripts/ledger.py" status --session "$COMMITFORGE_SESSION_ID"
```

- `exists`가 `false`면 신규 실행이다.
- `exists`가 `true`이고 `fingerprint_matches_current`가 `true`면 **처음부터 다시
  리뷰하지 않는다.** `pending`에 남은 id만 이어서 검토한다. 컴팩트로 대화 기억을
  잃었더라도 원장이 진행 상황의 정본이다.
- `fingerprint_matches_current`가 `false`면 원장과 저장소가 어긋난 상태다. 임의로
  진행하지 말고 사용자에게 보고한다. `null`은 `inventory` 전의 정상 상태이므로
  어긋난 것이 아니다.

## 4. scope 선언

scope는 **실제 리뷰 대상과 일치해야 한다.** 선언하지 않은 scope는 분모에 들어가지
않으므로, 그 범위를 아무리 충실히 리뷰해도 종료 게이트에는 보이지 않는다.

```bash
python3 "<CF_CORE>/scripts/ledger.py" init \
  --session "$COMMITFORGE_SESSION_ID" --scope working --skill <name>
```

`init`은 파괴적이지 않다. 기존 scope에 **합집합**으로 더하며 `iteration`과 이미
기록한 판정을 보존한다. 이미 선언된 scope를 다시 선언하면 아무 일도 없다.
`--skill`은 첫 호출 값이 보존되므로 두 번째 호출에서는 생략한다.

게이트의 `ledger_empty_inventory`는 **snapshot에 변경이 있는데 분모가 0**일 때만
발생한다. 원인은 리뷰 대상 scope 미선언이거나 분모 유실이다. 분모가 0이어도
snapshot이 비어 있으면 차단하지 않는다. 아무것도 바뀌지 않은 저장소의 리뷰는
정상적인 빈 리뷰다.

## 5. 분모 생성

모든 scope를 선언한 뒤 한 번 실행한다.

```bash
python3 "<CF_CORE>/scripts/ledger.py" inventory --session "$COMMITFORGE_SESSION_ID"
```

반환된 id 집합이 커버리지의 분모다. 직접 만들거나 수정하지 않는다.

- 같은 결과를 다시 만들 때만 멱등하다. 이미 분모가 있는 세대에서 다른 id 집합이
  나오면 `ledger_inventory_conflict`로 거부한다.
- `inventory` 이후에 scope를 추가하면 활성 세대가 해제되므로 다시 실행해 분모를
  넓힌다. 넓어진 분모는 상위집합이므로 기존 판정은 그대로 유효하다.
- `coverage.scopes_without_entries`에 남은 scope는 분모에 아무것도 넣지 못한
  범위다. 빈 범위면 정상이지만 base·기간·PR 계산 오류 신호일 수 있으므로 최종
  보고에 표시한다.
- 변경이 없어도 `inventory`를 건너뛰지 않는다. 생략하면 `finish`가
  `ledger_no_generation`으로 차단한다.

## 6. 판정 기록

reviewer batch 결과를 받을 때마다 **즉시** 기록한다. 다음 batch를 시작하기 전에
기록한다.

```bash
python3 "<CF_CORE>/scripts/ledger.py" record \
  --session "$COMMITFORGE_SESSION_ID" <<'JSON'
{"verdicts": [{"id": "working:src/auth.py#3", "verdict": "PASS", "reviewer": "cca-line-reviewer"},
              {"id": "working:src/auth.py#7", "verdict": "FINDING", "finding_ids": ["cr-001"]}],
 "findings": [{"id": "cr-001", "severity": "CRITICAL", "file": "src/auth.py"}],
 "reviewers": [{"name": "cca-line-reviewer", "status": "ACTIVE"}]}
JSON
```

- hunk 판정 철자는 `N_A`다. `N/A`는 `ledger_invalid_verdict`로 거부된다.
- reviewer status는 `ACTIVE`, `N_A`, `UNKNOWN`만 허용한다. `N/A`는
  `ledger_invalid_reviewer_status`로 거부된다.
- **거부는 batch 전체에 적용된다.** 판정 하나가 틀리면 같은 batch의 `PASS`도 전부
  버려진다. 거부되면 batch를 고쳐 다시 보내며, 판정을 낮춰 통과시키지 않는다.
- `FINDING`은 finding 레코드의 `id`를 `finding_ids`로 연결한다. 비어 있으면
  `ledger_finding_missing`으로 거부된다.
- `inventory`에 없는 id는 거부된다. 판정 대상은 분모에서만 고른다.
- 원장에 쓰는 주체는 lead뿐이다. reviewer subagent와 Agent Team teammate는
  기록하지 않는다.
- 기록 후에는 그 판정을 컨텍스트에 유지하지 않아도 된다. 원장이 정본이다.

관점은 hunk 분모와 **별개 축**이다. reviewer 하나가 모든 hunk를 `PASS`로 채우면
분모는 가득 차지만 필수 관점은 한 번도 돌지 않았을 수 있다. 상세는
`review-execution.md` §3.5다.

## 7. 수정 후 세대 전이

수정했다면 **재리뷰보다 먼저** 세대를 전이한다. 전이 전 활성 세대는 수정 이전
분모라서, 그대로 기록하면 수정이 만든 hunk가 `ledger_unknown_id`로 거부되고 성공한
판정도 전이 시점에 버려진다.

```bash
bash "<CF_CORE>/scripts/guard.sh" fingerprint
python3 "<CF_CORE>/scripts/ledger.py" advance \
  --session "$COMMITFORGE_SESSION_ID" --fingerprint "<fingerprint 값>"
```

`--fingerprint`는 Guard가 계산한다. 직접 만들거나 `begin` 결과의 옛 값을
재사용하지 않는다.

`advance`는 새 세대의 분모를 snapshot이 아니라 live working tree에서 만들며,
수정이 만든 hunk도 분모에 들어간다. 새 세대는 판정이 비어 있으므로 재리뷰 결과를
전부 다시 `record`한다. 저장소가 실제로 바뀌지 않았으면 `ledger_advance_noop`으로
거부하는데, 완료된 세대를 잃지 않기 위한 것이므로 우회하지 말고 수정이 적용됐는지
확인한다.

세대를 전이하면 이전 세대의 §3.6 격리 검증 결과도 함께 무효다. 새 세대의 finding은
다시 검증한다.

## 8. 보고와 종료

`report`는 **`finish` 이전에** 받아 보관한다. `finish`는 lock을 해제하고 snapshot을
삭제하므로 그 뒤에는 `owner_not_found`로 실패한다.

```bash
python3 "<CF_CORE>/scripts/ledger.py" report --session "$COMMITFORGE_SESSION_ID"
```

원장 게이트는 **snapshot에 원장이 있으면 flag와 무관하게 항상** 동작한다.
`--require-ledger`는 "원장이 아예 없으면 추가로 실패한다"는 뜻이다.

게이트 차단 사유:

| reason | 의미 |
|---|---|
| `ledger_no_generation` | `inventory`를 실행하지 않았다 |
| `ledger_stale` | 원장 세대와 현재 저장소 fingerprint가 다르다. 수정 후 `advance`를 빠뜨렸다 |
| `ledger_inventory_mismatch` | 분모가 생성 시점 이후 잘리거나 손상됐다 |
| `ledger_empty_inventory` | snapshot에 변경이 있는데 분모가 0이다 |
| `ledger_incomplete` | 미판정 hunk가 남았다 |
| `ledger_unknown` | `UNKNOWN` 판정이 남았다 |
| `ledger_reviewer_missing` | 필수 관점 기록이 없다 |
| `ledger_reviewer_unknown` | 필수 관점이 `UNKNOWN`이다 |

## 9. `--allow-unledgered`

원장이 불완전해도 통과시키는 탈출구다. 사용자가 명시적으로 요청한 경우에만 쓴다.

사용했다면 **`bypassed_reason`**, `ledger_bypassed`, `pending_count`, `pending`을
최종 보고에 반드시 표시한다. `ledger_stale`·`ledger_missing`·
`ledger_inventory_mismatch`·`ledger_empty_inventory` 우회는 모두 `pending_count`가
0이라, `bypassed_reason`을 빼면 가장 위험한 우회가 "미판정 0건"이라는 무해한
문장으로 보고된다. 우회한 `finish`는 snapshot을 삭제하지 않으므로 응답의
`snapshot` 경로도 보고한다.
