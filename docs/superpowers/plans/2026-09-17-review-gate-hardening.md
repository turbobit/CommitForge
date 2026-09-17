# 리뷰 게이트 강화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/cr`이 계약 위험(architecture)과 성능(performance) 관점을 기계적으로 강제하게 만들고, 필수 role 집합을 명령어별로 선언할 수 있는 구조를 갖춘다.

**Architecture:** `ledger.py`의 `REQUIRED_REVIEWER_ROLES`를 단일 튜플에서 skill별 dict로 바꾸고, `init --skill <name>`이 원장에 skill을 저장한다. `coverage()`가 저장된 skill로 role 집합을 조회하며, 필드가 없으면 기존 3개 role로 폴백해 하위 호환을 유지한다. `guard.py`는 `coverage()` 결과만 읽으므로 변경하지 않는다.

**Tech Stack:** Python 3 표준 라이브러리만 사용한다. 테스트는 `unittest`이며 `python3 -m unittest`로 실행한다. 외부 의존성을 추가하지 않는다.

**Spec:** `docs/superpowers/specs/2026-09-17-review-gate-hardening-design.md`

## Global Constraints

- 리포지터리 루트는 `/Users/turbobit/dev/CommitForge`다. 모든 경로는 이 루트 기준이다.
- 새 의존성을 추가하지 않는다. 표준 라이브러리만 쓴다.
- `guard.py`를 수정하지 않는다. role 매핑은 `ledger.py` 안에서 끝난다.
- reviewer status는 `ACTIVE`, `N_A`, `UNKNOWN`만 허용한다. `N/A` 철자는 batch 전체를 거부한다.
- hunk verdict 철자는 `N_A`다. `N/A`가 아니다.
- 기존 테스트를 수정하지 않는다. `--skill` 없는 `init`은 기존 3개 role로 폴백해야 하며, `tests/test_ledger.py:1858`의 `["correctness", "line", "security"]` 단언이 그대로 통과해야 한다.
- 문서는 한국어로 쓴다. 기존 문서의 어투와 용어를 따른다.
- `MANIFEST.json`과 `checksums.sha256`은 직접 편집하지 않는다. `python3 release.py`로만 생성한다.
- 커밋 메시지는 한국어 본문에 Conventional Commits 타입 접두사를 쓴다. 기존 이력 예: `fix(review): reviewer 입력 파일 경로 격리 규칙 추가`.

---

### Task 1: `ledger.py` 명령어별 role 매핑

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/ledger.py:46` (상수), `:914` (coverage 호출), `:946-977` (reviewer_roles), `:1005-1023` (cmd_init), `:1450-1453` (init 파서)
- Test: `tests/test_ledger.py`

**Interfaces:**
- Consumes: 없음. 첫 번째 태스크다.
- Produces:
  - `REQUIRED_REVIEWER_ROLES: dict[str, tuple[str, ...]]` — skill 이름 → 필수 role 튜플
  - `DEFAULT_REVIEWER_ROLES: tuple[str, ...]` — `("line", "correctness", "security")`
  - `required_roles_for(skill: Any) -> tuple[str, ...]`
  - `reviewer_roles(reviewers: dict[str, Any], required: tuple[str, ...] = DEFAULT_REVIEWER_ROLES) -> dict[str, str | None]`
  - `ledger.py init --skill <name>` CLI 플래그. 원장 `run.json`에 `"skill"` 키로 저장된다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_ledger.py`의 `ReviewerCoverageGateTest` 클래스 **뒤에** 새 클래스를 추가한다.

```python
class SkillScopedReviewerRolesTest(LedgerTestCase):
    """spec §3.1: 필수 role 집합은 원장을 만든 skill이 결정한다.

    `--skill` 없이 만든 원장은 기존 3개 role만 요구한다. 진행 중이던 리뷰가
    강제 확대로 갑자기 차단되지 않게 하는 폴백이며, 기존 테스트가 그대로
    통과하는 것이 이 폴백의 회귀 테스트다.
    """

    CR_ACTIVE = [
        {"name": "cca-line-reviewer", "status": "ACTIVE"},
        {"name": "cca-correctness-reviewer", "status": "ACTIVE"},
        {"name": "cca-security-reviewer", "status": "ACTIVE"},
        {"name": "cca-architecture-reviewer", "status": "ACTIVE"},
        {"name": "cca-performance-reviewer", "status": "ACTIVE"},
    ]

    def prepared(self, *skill: str) -> tuple[dict, list[str]]:
        (self.tmp / "tracked.txt").write_text("base\nadded\n", encoding="utf-8")
        started = self.begin()
        argv = ["init", "--session", started["session"], "--scope", "working"]
        if skill:
            argv += ["--skill", skill[0]]
        self.ledger(*argv)
        _, built = self.ledger("inventory", "--session", started["session"])
        return started, [entry["id"] for entry in built["entries"]]

    def cover(self, session: str, ids: list[str], reviewers: list[dict]) -> None:
        self.record(
            session,
            {
                "verdicts": [{"id": i, "verdict": "PASS"} for i in ids],
                "reviewers": reviewers,
            },
        )

    def verify(self, session: str, check: bool = True):
        return self.guard(
            "verify-review", "--session", session,
            "--source-read-only", "--require-ledger", check=check,
        )

    def test_cr_requires_architecture_and_performance(self) -> None:
        started, ids = self.prepared("cr")
        self.cover(started["session"], ids, self.CR_ACTIVE[:3])
        proc, refused = self.verify(started["session"], check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(refused["reason"], "ledger_reviewer_missing")
        self.assertEqual(
            sorted(refused["reviewer_roles_missing"]), ["architecture", "performance"]
        )

    def test_cr_passes_with_all_five_roles(self) -> None:
        started, ids = self.prepared("cr")
        self.cover(started["session"], ids, self.CR_ACTIVE)
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["ledger"]["reviewer_roles_missing"], [])

    def test_ledger_without_skill_keeps_the_three_base_roles(self) -> None:
        started, ids = self.prepared()
        self.cover(started["session"], ids, self.CR_ACTIVE[:3])
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])
        self.assertEqual(
            sorted(verified["ledger"]["reviewer_roles"]),
            ["correctness", "line", "security"],
        )

    def test_unmapped_skill_falls_back_to_the_base_roles(self) -> None:
        started, ids = self.prepared("cfr")
        self.cover(started["session"], ids, self.CR_ACTIVE[:3])
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])

    def test_agent_team_bundled_name_satisfies_architecture(self) -> None:
        # review-execution.md §0의 core 3번은 한 teammate가 Architecture,
        # Language/API, Quality, Compatibility를 함께 맡는다. role은 이름
        # 부분일치로 판정하므로 묶음 이름 하나가 architecture를 만족해야 한다.
        started, ids = self.prepared("cr")
        reviewers = [
            {"name": "core-correctness-line-state", "status": "ACTIVE"},
            {"name": "core-security-privacy-supply-chain", "status": "ACTIVE"},
            {"name": "core-architecture-language-quality-compatibility",
             "status": "ACTIVE"},
            {"name": "spec-performance-reliability", "status": "ACTIVE"},
        ]
        self.cover(started["session"], ids, reviewers)
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["ledger"]["reviewer_roles_missing"], [])

    def test_reasoned_n_a_satisfies_performance(self) -> None:
        # 문서 전용 diff에는 성능 차원이 없다. 게이트는 명시적 N_A를 요구할
        # 뿐 ACTIVE를 강요하지 않는다.
        started, ids = self.prepared("cr")
        reviewers = self.CR_ACTIVE[:4] + [
            {"name": "cca-performance-reviewer", "status": "N_A"}
        ]
        self.cover(started["session"], ids, reviewers)
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])

    def test_empty_denominator_still_passes_with_extra_roles(self) -> None:
        # guard.py의 `if summary["total"]:`가 빈 분모에서 관점 게이트를
        # 건너뛴다. role이 늘어도 "검토 대상 없음" 종료는 열려 있어야 한다.
        started = self.begin()
        self.ledger(
            "init", "--session", started["session"],
            "--scope", "working", "--skill", "cr",
        )
        self.ledger("inventory", "--session", started["session"])
        _, verified = self.verify(started["session"])
        self.assertTrue(verified["ok"])
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_ledger.SkillScopedReviewerRolesTest -v`

Expected: FAIL. `--skill` 플래그가 없으므로 `argparse`가 `unrecognized arguments: --skill cr`로 종료하고 `self.ledger(...)`가 `AssertionError`를 낸다.

- [ ] **Step 3: role 매핑 상수를 만든다**

`ledger.py:46`의 다음 한 줄을 찾는다.

```python
REQUIRED_REVIEWER_ROLES = ("line", "correctness", "security")
```

아래로 교체한다. 위에 붙어 있는 기존 주석(`# review-execution.md §2 makes Line, Correctness and Security mandatory on every change.`로 시작하는 블록)도 함께 갱신한다.

```python
# review-execution.md §2 makes Line, Correctness and Security mandatory on
# every change, and spec 2026-09-17 adds Architecture (contract and
# compatibility) and Performance for `/cr`. The set is keyed by the skill that
# created the ledger because `/cca`, `/cpr`, `/cp` and `/ccr` will each carry a
# different one when they adopt the ledger; only `cr` creates one today.
#
# Matching is by role keyword rather than by exact agent filename: Agent Team
# mode packs these perspectives into named core teammates
# (`core-correctness-line-state`), and a filename match would make the rule
# unsatisfiable in the structure the skill selects by default. That is also why
# review-execution.md §3.5 forbids abbreviating a role keyword in a teammate
# name -- `core-arch-...` would silently fail to satisfy `architecture`.
REQUIRED_REVIEWER_ROLES: dict[str, tuple[str, ...]] = {
    "cr": ("line", "correctness", "security", "architecture", "performance"),
}

# A ledger with no `skill` field predates the mapping, and an unmapped name is
# a skill that has not declared its set yet. Both fall back to the original
# three rather than to `/cr`'s five: widening the requirement under a review
# that is already in flight would block it for a perspective its own skill
# never asked for.
DEFAULT_REVIEWER_ROLES = ("line", "correctness", "security")


def required_roles_for(skill: Any) -> tuple[str, ...]:
    """Return the mandatory role keywords for the skill that owns a ledger."""
    if not isinstance(skill, str):
        return DEFAULT_REVIEWER_ROLES
    return REQUIRED_REVIEWER_ROLES.get(skill, DEFAULT_REVIEWER_ROLES)
```

- [ ] **Step 4: `reviewer_roles`가 role 집합을 인자로 받게 한다**

`ledger.py:946`의 시그니처를 바꾼다.

```python
def reviewer_roles(
    reviewers: dict[str, Any],
    required: tuple[str, ...] = DEFAULT_REVIEWER_ROLES,
) -> dict[str, str | None]:
```

같은 함수 본문에서 `REQUIRED_REVIEWER_ROLES`를 참조하는 두 줄을 `required`로 바꾼다.

```python
    resolved: dict[str, str | None] = {role: None for role in required}
```

```python
        for role in required:
```

- [ ] **Step 5: `coverage`가 저장된 skill로 조회하게 한다**

`ledger.py:914`의 다음 한 줄을 찾는다.

```python
    roles = reviewer_roles(reviewers)
```

교체한다.

```python
    roles = reviewer_roles(reviewers, required_roles_for(data.get("skill")))
```

`coverage(ctx, ledger_dir, data)`의 시그니처는 바꾸지 않는다. `guard.py:1423`이 이미 `data`를 넘기고 있고, `guard.py:1403`의 `{}` 호출은 원장이 없는 `--allow-unledgered` 우회 경로라 기본값 폴백이 올바른 동작이다.

- [ ] **Step 6: `init`에 `--skill` 플래그를 추가한다**

`ledger.py:1453`의 다음 줄을 찾는다.

```python
    init.add_argument("--scope", action="append", default=[])
```

바로 아래에 추가한다.

```python
    init.add_argument(
        "--skill",
        help="이 원장을 만든 skill 이름(예: cr). 필수 reviewer 관점 집합을 결정한다",
    )
```

플래그 이름은 반드시 `--skill`이다. `--command`는 쓸 수 없다. `ledger.py:1448`이 서브파서에 `dest="command"`를 이미 사용하므로 `args.command`가 충돌한다.

- [ ] **Step 7: `cmd_init`이 skill을 저장하게 한다**

`ledger.py:1005-1012`의 신규 원장 dict에 `"skill"`을 추가한다.

```python
            data: dict[str, Any] = {
                "session": guard.safe_session(args.session),
                "token": resolved_token,
                "stage": "init",
                "iteration": 1,
                "active_generation": "",
                "scopes": scopes,
                "skill": args.skill or "",
            }
```

기존 원장 분기(`else:` 아래, `data["scopes"] = declared + added` 다음 줄)에 추가한다.

```python
            if args.skill:
                data["skill"] = args.skill
```

조건부인 이유는 `init`이 두 번 호출되기 때문이다. `/cr`은 Guard `begin` 직후 `--scope working`으로 한 번, §2에서 범위를 계산한 뒤 `--scope range:<A>..<B>`로 한 번 더 부른다. 두 번째 호출에서 `--skill`이 빠져도 첫 번째가 저장한 값을 덮어 지우면 안 된다.

- [ ] **Step 8: 테스트를 실행해 통과를 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_ledger -v`

Expected: PASS. 새 `SkillScopedReviewerRolesTest` 7건과 기존 `ReviewerCoverageGateTest`가 모두 통과한다. 기존 클래스가 통과하는 것이 폴백 회귀 테스트다.

- [ ] **Step 9: guard 테스트로 회귀가 없는지 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_guard tests.test_session_lifecycle -v`

Expected: PASS. `guard.py`를 바꾸지 않았으므로 전부 통과해야 한다. 실패하면 `coverage()` 반환 형태가 깨진 것이므로 Step 5를 다시 본다.

- [ ] **Step 10: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/ledger.py tests/test_ledger.py
git commit -m "$(cat <<'EOF'
feat(ledger): 필수 reviewer 관점을 명령어별로 선언 가능하게 변경

REQUIRED_REVIEWER_ROLES를 단일 튜플에서 skill별 매핑으로 바꾸고 init에
--skill을 추가한다. /cr은 architecture와 performance를 포함한 5개 관점을
요구하며, skill이 없거나 매핑에 없는 원장은 기존 3개로 폴백해 진행 중인
리뷰가 강제 확대로 차단되지 않게 한다.
EOF
)"
```

---

### Task 2: `/cr` 배선과 계약 위험 검토 항목

**Files:**
- Modify: `.claude/skills/cr/SKILL.md:246-249` (init 호출), `:256-259` (두 번째 init 호출)
- Modify: `.claude/skills/_git-atomic-core/review-execution.md` (§0 core 3 예시 이름, §3.5 축약 금지 규약)
- Modify: `.claude/agents/cca-architecture-reviewer.md` (검토 항목)

**Interfaces:**
- Consumes: Task 1의 `ledger.py init --skill <name>` 플래그
- Produces: 없음. 문서와 agent 정의만 바꾼다.

- [ ] **Step 1: `/cr`의 첫 번째 `init` 호출에 `--skill cr`을 넣는다**

`cr/SKILL.md` §1.5.2의 다음 블록을 찾는다.

````markdown
```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" init \
  --session "$COMMITFORGE_SESSION_ID" --scope working
```
````

교체한다.

````markdown
```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" init \
  --session "$COMMITFORGE_SESSION_ID" --scope working --skill cr
```
````

- [ ] **Step 2: 두 번째 `init` 호출 설명에 skill 보존을 명시한다**

같은 문서에서 range scope를 선언하는 블록을 찾는다.

````markdown
```bash
python3 ".claude/skills/_git-atomic-core/scripts/ledger.py" init \
  --session "$COMMITFORGE_SESSION_ID" --scope "range:<A>..<B>"
```
````

블록은 그대로 두고 바로 아래에 문단을 추가한다.

```markdown
두 번째 `init`에는 `--skill`을 다시 넘기지 않아도 된다. 첫 호출이 저장한 값이
보존되며, 넘기더라도 같은 값이면 결과가 같다.
```

- [ ] **Step 3: `review-execution.md` §3.5에 축약 금지 규약을 추가한다**

§3.5의 다음 항목을 찾는다.

```markdown
- 관점 판정은 agent 파일명이 아니라 **이름에 포함된 역할 키워드**로 해석한다.
  Agent Team의 `core-correctness-line-state` 같은 teammate 하나가 두 역할을 함께
  만족시킬 수 있다.
```

바로 아래에 추가한다.

```markdown
- **role 키워드는 축약하지 않는다.** 매칭이 부분일치이므로 `architecture`를
  `arch`로 줄인 `core-arch-lang-quality`는 그 역할을 만족시키지 못하고, 제대로
  수행한 리뷰가 `ledger_reviewer_missing`으로 차단된다. teammate 이름에는
  `line`, `correctness`, `security`, `architecture`, `performance`를 철자
  그대로 포함한다.
```

- [ ] **Step 4: `review-execution.md` §0의 core 3 예시 이름을 박는다**

§0 "기본 구성"의 core 3 목록에서 3번 항목을 찾는다.

```markdown
  3. **Architecture + Language/API + Quality + Compatibility**: 경계·의존 방향,
     public contract, 버전별 API 의미, maintainability, backward/forward
     compatibility와 deprecation
```

아래로 교체한다.

```markdown
  3. **Architecture + Language/API + Quality + Compatibility**: 경계·의존 방향,
     public contract, 버전별 API 의미, maintainability, backward/forward
     compatibility와 deprecation

  teammate 이름은 각 묶음의 role 키워드를 축약 없이 포함한다. 예:
  `core-correctness-line-state`, `core-security-privacy-supply-chain`,
  `core-architecture-language-quality-compatibility`. 축약하면 §3.5의 관점
  게이트가 역할을 인식하지 못한다.
```

- [ ] **Step 5: `cca-architecture-reviewer.md`에 계약 위험 항목을 보강한다**

`.claude/agents/cca-architecture-reviewer.md`의 검토 항목 목록에서 `- 확장 지점과 backward compatibility` 줄을 찾아 아래로 교체한다.

```markdown
- 확장 지점과 backward compatibility
- 하위 호환을 깨는 public contract 변경과 그 소비자. 어떤 호출자가 어떤 버전에서
  깨지는지 짚는다
- 기본값과 feature flag 기본 상태의 변경. 기존 배포가 새 기본값을 만났을 때의
  동작과, 값을 명시하지 않은 호출자의 영향을 확인한다
- schema·저장 형식 변경에 필요한 migration 누락. `review-gates.md` §2는 이를
  MAJOR 차단 사유로 둔다
```

이 항목들은 `ledger.py`가 `architecture` role을 강제하기 때문에 필요하다. 강제되는 이름과 실제 검토 내용이 어긋나면 게이트가 형식만 채우게 된다.

- [ ] **Step 6: `/cr`의 skill 인자가 실제로 저장되는지 수동 확인한다**

Run:
```bash
cd /Users/turbobit/dev/CommitForge && grep -n 'skill cr' .claude/skills/cr/SKILL.md
```

Expected: `--scope working --skill cr`을 포함한 줄 1건이 출력된다.

- [ ] **Step 7: 커밋한다**

```bash
git add .claude/skills/cr/SKILL.md .claude/skills/_git-atomic-core/review-execution.md .claude/agents/cca-architecture-reviewer.md
git commit -m "$(cat <<'EOF'
feat(review): /cr에 계약 위험·성능 관점 강제를 배선

/cr의 ledger init에 --skill cr을 넘겨 architecture와 performance를 필수
관점으로 만든다. 강제되는 이름과 검토 내용이 어긋나지 않도록
architecture reviewer에 하위 호환·기본값·migration 누락 항목을 보강하고,
부분일치 매칭이 깨지지 않게 teammate 이름의 role 키워드 축약을 금지한다.
EOF
)"
```

---

### Task 3: `/cpr`·`/cp`에 심각도 정의 공급

**Files:**
- Modify: `.claude/skills/cpr/SKILL.md:84-92` (필수 규칙 목록)
- Modify: `.claude/skills/cp/SKILL.md:83-91` (필수 규칙 목록)
- Modify: `.claude/skills/_git-atomic-core/review-gates.md:1` (제목과 범위)
- Modify: `.claude/skills/_git-atomic-core/README.md:13` (범위 설명)

**Interfaces:**
- Consumes: 없음. Task 1·2와 독립이다.
- Produces: 없음.

- [ ] **Step 1: `review-gates.md`의 제목과 적용 범위를 고친다**

파일 첫 줄을 찾는다.

```markdown
# `/cr`·`/cca` 리뷰 및 품질 게이트
```

아래로 교체한다.

```markdown
# 리뷰 및 품질 게이트

적용 범위는 섹션마다 다르다.

- §1~§4는 리뷰를 수행하는 모든 명령어에 적용된다. finding 요건, 심각도 정의,
  reviewer 관점 체크리스트, 자동 수정 정책이 여기에 있다.
- §5는 `/cr` 완료 Gate, §6은 `/cca` Commit Gate로 해당 명령어에만 적용된다.

`/cpr`·`/cp`의 차단 조건은 `pull-request-workflow.md`가 따로 정의한다. 이 문서는
그 규칙이 참조하는 심각도의 의미를 제공한다.
```

- [ ] **Step 2: `/cpr`의 필수 규칙에 `review-gates.md`를 추가한다**

`cpr/SKILL.md`의 필수 규칙 목록에서 다음 줄을 찾는다.

```markdown
5. `.claude/skills/_git-atomic-core/review-execution.md`
```

바로 아래에 삽입하고, 이후 항목 번호를 하나씩 밀어 6·7·8·9로 만든다. 결과는 다음과 같아야 한다.

```markdown
5. `.claude/skills/_git-atomic-core/review-execution.md`
6. `.claude/skills/_git-atomic-core/review-gates.md`
7. `.claude/skills/_git-atomic-core/review-policy.md`
8. `.claude/skills/_git-atomic-core/validation-strategy.md`
9. `.claude/skills/_git-atomic-core/large-diff-review.md`
```

- [ ] **Step 3: `/cp`의 필수 규칙에 `review-gates.md`를 추가한다**

`cp/SKILL.md`에서 Step 2와 똑같은 편집을 한다. 두 파일의 목록은 1~8번이 동일하다.

```markdown
5. `.claude/skills/_git-atomic-core/review-execution.md`
6. `.claude/skills/_git-atomic-core/review-gates.md`
7. `.claude/skills/_git-atomic-core/review-policy.md`
8. `.claude/skills/_git-atomic-core/validation-strategy.md`
9. `.claude/skills/_git-atomic-core/large-diff-review.md`
```

- [ ] **Step 4: `README.md`의 범위 설명을 고친다**

`.claude/skills/_git-atomic-core/README.md:13`의 다음 줄을 찾는다.

```markdown
- `review-gates.md`: `/cr`·`/cca` 품질 gate
```

교체한다.

```markdown
- `review-gates.md`: 심각도 정의와 reviewer 관점 체크리스트(모든 리뷰 명령어), `/cr` 완료 Gate와 `/cca` Commit Gate
```

- [ ] **Step 5: 네 파일이 일관되는지 확인한다**

Run:
```bash
cd /Users/turbobit/dev/CommitForge && grep -rn 'review-gates' .claude/skills/cr/SKILL.md .claude/skills/cca/SKILL.md .claude/skills/cpr/SKILL.md .claude/skills/cp/SKILL.md .claude/skills/_git-atomic-core/README.md
```

Expected: `/cr`, `/cca`, `/cpr`, `/cp` 네 skill 모두에 `review-gates.md` 참조가 있고, README에 새 설명이 보인다. `/cpr`·`/cp`는 조사 시점에 참조가 없었으므로 이 두 건이 새로 나타나는 것이 성공 신호다.

- [ ] **Step 6: 커밋한다**

```bash
git add .claude/skills/cpr/SKILL.md .claude/skills/cp/SKILL.md .claude/skills/_git-atomic-core/review-gates.md .claude/skills/_git-atomic-core/README.md
git commit -m "$(cat <<'EOF'
fix(review): /cpr·/cp에 심각도 정의를 공급

두 명령어는 pull-request-workflow.md로 "CRITICAL/MAJOR 차단" 규칙을
갖지만 무엇이 CRITICAL인지 정의한 review-gates.md를 읽지 않아, 정의 없는
심각도로 blocker를 판정하고 있었다. 문서를 필수 규칙에 추가하고 섹션별
적용 범위를 명시한다.
EOF
)"
```

---

### Task 4: 기각 금지 목록을 피해 유형으로 재정의

**Files:**
- Modify: `.claude/skills/_git-atomic-core/review-policy.md:44-45`

**Interfaces:**
- Consumes: 없음.
- Produces: 없음.

- [ ] **Step 1: 기각 금지 규칙을 교체한다**

`review-policy.md`에서 다음 두 줄을 찾는다.

```markdown
- `confidence_threshold`로 secret, 인증·인가, 데이터 손실 finding을 일괄 기각할 수
  없다. 이 영역은 검증이 명시적 근거로 기각한 경우에만 `REJECTED`다.
```

아래로 교체한다.

```markdown
- `confidence_threshold`로 일괄 기각할 수 없는 영역이 있다. 이 목록은 **되돌릴 수
  없는 피해**를 기준으로 하며, 검증이 명시적 근거로 기각한 경우에만 `REJECTED`다.
  - secret·자격증명 노출
  - 인증·인가 우회
  - 데이터 손실·손상
  - 복구 불가능한 migration·데이터 변환. `review-gates.md` §2 CRITICAL의
    "잘못된 migration으로 복구 곤란한 상태"와 같은 기준이다
  - 재시작 없이 회복되지 않는 자원 고갈
- 이 목록은 **어느 reviewer가 찾았는지가 아니라 피해 유형으로** 판정한다.
  Performance reviewer가 찾은 데이터 손실도 보호되고, Security reviewer가 찾은
  저영향 finding은 보호되지 않는다.
- 하위 호환성 파괴는 이 목록에 넣지 않는다. rollback으로 회복 가능하므로 기준에
  들지 않으며, 목록을 더 넓히면 `confidence_threshold`가 잡음 억제 기능을 잃는다.
```

- [ ] **Step 2: 목록이 의도대로 읽히는지 확인한다**

Run:
```bash
cd /Users/turbobit/dev/CommitForge && sed -n '/일괄 기각할 수 없는 영역/,/잡음 억제 기능을 잃는다/p' .claude/skills/_git-atomic-core/review-policy.md
```

Expected: 다섯 개의 피해 유형, 피해 유형 기준 문단, 하위 호환성 제외 근거가 모두 출력된다.

- [ ] **Step 3: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/review-policy.md
git commit -m "$(cat <<'EOF'
fix(review): 기각 금지 목록을 피해 유형 기준으로 재정의

기존 목록은 secret·인증인가·데이터 손실만 담아 보안 카테고리처럼 읽혔고,
performance reviewer가 찾은 데이터 손실이 보호되는지 불분명했다. 판정
기준이 reviewer가 아니라 되돌릴 수 없는 피해임을 명시하고 복구 불가능한
migration과 자원 고갈을 추가한다. rollback으로 회복 가능한 하위 호환성
파괴는 제외하고 그 근거를 남긴다.
EOF
)"
```

---

### Task 5: `reviewer_triggers.py` 경로 패턴

**Files:**
- Modify: `.claude/skills/_git-atomic-core/scripts/reviewer_triggers.py:23-28` (data-migration RULES)
- Test: `tests/test_reviewer_triggers.py`

**Interfaces:**
- Consumes: 없음.
- Produces: 없음. `classify()`의 반환 형태는 그대로다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_reviewer_triggers.py`의 `ReliabilityTriggerTest` 클래스 **앞에** 추가한다.

```python
class DataMigrationTriggerTest(unittest.TestCase):
    """spec §3.5: 실측된 미탐지 경로가 활성화되어야 한다."""

    def test_plural_schema_directory_activates_data_migration(self) -> None:
        # 기존 패턴은 `schema`만 있어 복수형 디렉터리를 놓쳤다.
        result = classify("src/schemas/user.py")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_singular_schema_directory_still_activates(self) -> None:
        result = classify("src/schema/user.py")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_schema_definition_files_activate_data_migration(self) -> None:
        for path in ("api/user.proto", "events/click.avsc"):
            with self.subTest(path=path):
                result = classify(path)
                self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_storage_format_paths_activate_data_migration(self) -> None:
        result = classify("config/storage-format.yaml")
        self.assertIn("cca-data-migration-reviewer", result["active"])

    def test_unrelated_source_does_not_activate_data_migration(self) -> None:
        # 패턴은 하한선이다. 넓히더라도 평범한 소스를 끌어들이면 안 된다.
        result = classify("src/ui/button.tsx", "docs/readme.md")
        self.assertNotIn("cca-data-migration-reviewer", result["active"])
```

- [ ] **Step 2: 테스트를 실행해 실패를 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_reviewer_triggers.DataMigrationTriggerTest -v`

Expected: FAIL 3건. `test_plural_schema_directory_activates_data_migration`,
`test_schema_definition_files_activate_data_migration`,
`test_storage_format_paths_activate_data_migration`이 `AssertionError`를 낸다. 나머지 2건은 이미 통과한다.

- [ ] **Step 3: 패턴을 고친다**

`reviewer_triggers.py:23-28`의 다음 블록을 찾는다.

```python
    "cca-data-migration-reviewer": (
        r"(^|/)(migrations?|schema|prisma)(/|$)",
        r"\.(sql|ddl)$",
        r"(^|/)(models?|entities)/",
        r"(backfill|data[-_]?migration)",
    ),
```

교체한다.

```python
    "cca-data-migration-reviewer": (
        # `schemas?` because a plural directory (`src/schemas/`) is as common
        # as the singular and was silently missed.
        r"(^|/)(migrations?|schemas?|prisma)(/|$)",
        # Schema definition files carry the contract even when no directory
        # name says so.
        r"\.(sql|ddl|proto|avsc)$",
        r"(^|/)(models?|entities)/",
        r"(backfill|data[-_]?migration)",
        r"(storage[-_]?format)",
    ),
```

`serializ` 같은 넓은 패턴은 넣지 않는다. 측정된 누락 사례가 없고, serialization key 변경은 이미 필수 관점인 Line이 담당한다(`deep-review-protocol.md:44`).

- [ ] **Step 4: 테스트를 실행해 통과를 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_reviewer_triggers -v`

Expected: PASS. 새 클래스 5건과 기존 테스트가 모두 통과한다.

- [ ] **Step 5: eval 데이터가 깨지지 않았는지 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest tests.test_review_evals tests.test_review_features -v`

Expected: PASS. `evals/conditional-reviewer-triggers.json`이 활성 집합을 고정하고 있다면 여기서 실패가 드러난다. 실패하면 새 패턴이 기존 eval 기대치를 바꾼 것이므로, eval의 기대값이 실제로 틀렸는지 확인한 뒤에만 갱신한다.

- [ ] **Step 6: 커밋한다**

```bash
git add .claude/skills/_git-atomic-core/scripts/reviewer_triggers.py tests/test_reviewer_triggers.py
git commit -m "$(cat <<'EOF'
fix(review): data/migration trigger가 놓치던 경로 3종 추가

복수형 schema 디렉터리, 스키마 정의 파일(.proto/.avsc), 저장 형식 경로가
미탐지였다. 실측으로 확인한 사례에만 대응하고 각 패턴에 회귀 테스트를
붙인다. trigger 결과는 하한선이므로 패턴은 보수적으로 유지한다.
EOF
)"
```

---

### Task 6: 메타데이터 재생성과 전체 검증

**Files:**
- Modify: `MANIFEST.json`, `checksums.sha256` (`release.py`가 생성한다. 직접 편집하지 않는다)

**Interfaces:**
- Consumes: Task 1~5의 모든 파일 변경
- Produces: 없음.

- [ ] **Step 1: 전체 테스트를 실행한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 -m unittest discover -s tests -v`

Expected: PASS. 실패가 있으면 해당 태스크로 돌아간다. 여기서 처음 드러나는 실패는 태스크 간 상호작용이므로 메타데이터를 생성하기 전에 해결한다.

- [ ] **Step 2: 메타데이터가 낡았음을 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 release.py --check`

Expected: FAIL. 변경한 skill·agent·script 파일이 mismatch로 보고된다. 이것이 정상이다.

- [ ] **Step 3: 메타데이터를 재생성한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 release.py`

Expected: `{"ok": true, "mode": "write", ...}` JSON이 출력된다.

- [ ] **Step 4: 재생성 결과를 검증한다**

Run: `cd /Users/turbobit/dev/CommitForge && python3 release.py --check && python3 verify.py`

Expected: 두 명령 모두 성공한다. `verify.py`가 설치 무결성까지 확인한다.

- [ ] **Step 5: 변경 범위를 확인한다**

Run: `cd /Users/turbobit/dev/CommitForge && git status --short && git diff --stat`

Expected: `MANIFEST.json`과 `checksums.sha256`만 수정된 상태로 남아 있다. 다른 파일이 보이면 앞선 태스크의 커밋이 누락된 것이므로 먼저 확인한다.

- [ ] **Step 6: 커밋한다**

```bash
git add MANIFEST.json checksums.sha256
git commit -m "$(cat <<'EOF'
build(meta): 메타데이터 일관성 — 리뷰 게이트 강화 변경 해시 갱신
EOF
)"
```

---

## 완료 조건

- `python3 -m unittest discover -s tests`가 전부 통과한다
- `python3 release.py --check`가 통과한다
- `/cr`이 만든 원장은 `line`·`correctness`·`security`·`architecture`·`performance` 5개 관점을 요구한다
- `--skill` 없이 만든 원장은 기존 3개 관점만 요구한다
- `/cpr`·`/cp`가 `review-gates.md`를 로드한다
- `git status`가 clean이다
