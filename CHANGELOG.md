# Changelog

## 1.23.3 — 2026-10-08

- 리뷰 원장이 reviewer 원문을 근거로 요구한다. `ACTIVE` reviewer는 반환을 snapshot의
  `reviewer-output/` 아래 비어 있지 않은 파일로 저장한 뒤 `output_path`로 기록해야 하며,
  없으면 `ledger_reviewer_output_missing`으로 `finish`가 막힌다. 컨텍스트 컴팩션으로
  반환이 사라진 채 판정이 채워지던 경로를 막는다
- reviewer `status`에 `FALLBACK`을 추가했다. agent가 실패해 lead가 직접 수행한 관점은
  `FALLBACK`으로 기록하며, 필수 관점이 `FALLBACK`만이면 `ledger_reviewer_fallback`으로
  막힌다. 선택 관점은 차단하지 않는다
- hunk 판정에 `basis`(`reviewer`·`lead_fallback`)를 추가하고 `status`에 `by_basis`로
  집계한다. lead가 쓴 PASS와 reviewer가 본 PASS를 보고에서 구분한다
- 테스트 하네스가 subprocess 출력을 UTF-8로 읽도록 고정했다. 한국어 Windows 로캘
  (cp949)에서 `guard.py`·`ledger.py` 출력을 읽다 reader thread가 죽던 문제를 막는다

## 1.23.2 — 2026-10-08

- 스킬과 에이전트 frontmatter의 `effort` 고정값을 제거했다. `/cr`, `/cca`, `/cp`,
  `/cpr`가 `effort: max`를 강제해, 명령만 실행해도 세션 설정과 무관하게 최대 강도로
  돌던 문제를 막는다. 이제 `effort`를 명시하지 않으면 `settings.json`의 `effortLevel`을
  따른다. 특정 명령의 강도를 고정하려면 해당 `SKILL.md` 또는 에이전트 frontmatter에
  `effort`를 다시 추가한다

## 1.23.1 — 2026-10-06

- 게이트가 저장소 밖 복구 사본 경로를 symlink를 푼 실제 경로로 비교하고, macOS·Windows
  에서는 대소문자를 무시한다. `ln -s` 링크를 거친 삭제나 `rm -rf ~/.CLAUDE`가
  통과하던 문제를 막는다. 저장소 안 증거(snapshot·잠금·`refs/commitforge`)도 같은 방식으로
  비교한다
- 값을 정적으로 알 수 없는 삭제·덮어쓰기(변수, `$(...)`, xargs 입력)와 인터프리터
  인라인 코드는 `commitforge`·`.claude`가 보이면 거부한다. `expanduser('~/.claude/...')`
  로 사본을 지우는 코드가 통과하던 문제를 막는다
- `finish`·`release-snapshot`은 snapshot 표식에 적힌 경로 대신 그 snapshot에 정해진
  사본 경로만 지운다. 조작된 표식이 다른 실행의 사본을 지우지 못한다
- 보안 리뷰가 찾은 나머지 옵션 해석 차이(`env -iC`, `cp -tDIR`, rsync `-t`·
  `--remove-source-files`, find `-regex` 문법, 생략형 refspec)는 최선 노력 한계로
  `safety-and-concurrency.md` 2.2절에 적었다

## 1.23.0 — 2026-10-06

- Guard `begin`이 **저장소 밖 복구 사본**을 만든다. recovery ref와 snapshot은 `.git`
  안에 있어 저장소 안의 `rm -rf`·`update-ref -d` 한 번에 보호하려던 작업과 함께
  사라질 수 있다. 시작 HEAD와 달랐던 경로의 시작 시점 내용을
  `~/.claude/commitforge/recovery/<저장소>-<id>/<snapshot>/`에 `changes.tar`와
  `manifest.json`으로 남긴다(`COMMITFORGE_RECOVERY_DIR`로 위치 변경, 합계 512MiB 초과 시
  경고만). 보존 검사 결과는 `recovery_copy`와 `restore_copy_hint`(`tar -xf ...`)를 함께
  보고한다. 정상 `finish`·`release-snapshot`은 사본을 지우고 `abort`는 남기며, 30일이
  지난 사본은 다음 `begin`이 정리한다. 게이트는 이 디렉터리와 상위 디렉터리의 삭제·덮어쓰기도
  막는다
- 보안: 1.22.0의 훅 launcher는 `python -c`로 게이트를 실행해 현재 디렉터리가 import
  경로 맨 앞에 왔다. 프로젝트 최상위의 `json.py` 같은 파일이 git을 언급하는 모든 Bash
  호출에서 실행되고 게이트도 꺼졌다. launcher가 `sys.path[0]`을 게이트 디렉터리로
  바꾼다. uninstall은 1.22.0 launcher 항목도 인식한다. **1.22.0 사용자는 다시 설치한다**
- 잠금을 잡고 만든 snapshot은 표식에 `locked`를 기록한다. 잠금이 풀린 실행이
  token·snapshot을 명시해 `conserve`를 불러도 `lock_not_owned`로 보고된다. 같은 세션의
  잠금 없는 snapshot은 잠금을 잡은 동안에도 명시한 token으로 검사된다
- 게이트 우회 보강: `find`의 이름 검사를 실제 증거 경로와 대조하고(`-exec` 덮어쓰기,
  `refs/commitforge` 안에서 시작하는 경우 포함), `cp`·`install`·`ln`·`rsync`·`tee`·`dd`
  덮어쓰기(glob 대상 포함), 해석할 수 없는 경로의 `rm`, xargs `update-ref`,
  `push`·`fetch`·`notes`·`symbolic-ref`로 recovery ref를 쓰거나 지우는 경우(와일드카드
  refspec 포함), `env -C`·`sudo -D`(붙여 쓴 형태 포함)의 작업 디렉터리를 처리한다
- `clean`이 여러 owner snapshot을 검사할 때 현재 작업 트리를 한 번만 해시한다
- 1.22.0 `MANIFEST.json`에 `CHANGELOG.md`가 중복으로 기록된 것을 바로잡았다

## 1.22.0 — 2026-10-06

- **변경 보존 게이트**(`worktree_gate.py`)를 추가했다. 한 `/ccf` 실행이 커밋 순서를
  고친다며 `git checkout <commit> -- .`, `reset --hard`, cherry-pick을 실행해
  커밋되지 않은 파일 세 개를 잃었다. 보존 검사는 token을 잘못 옮겨 적어 실행되지
  못했고, 모델은 사용자 요청 없이 `clean`을 실행한 뒤 snapshot과 recovery ref를
  `rm -rf`·`update-ref -d`로 지웠다. 문서 규칙만으로는 막을 수 없는 사례다
- 설치 시 모든 세션의 Bash 호출에 `PreToolUse` 훅을 등록한다. 훅은 bash 문법을 직접
  해석하고, git 명령이 작용할 worktree에 잠금이 있으면 커밋 skill이 쓰는 명령만
  허용 목록으로 통과시킨다. 정적으로 확인할 수 없는 명령(변수·`$(...)`로 정해지는
  하위 명령·옵션·저장소, 정의되지 않은 alias, 해석할 수 없는 셸·인터프리터 코드)은
  거부한다. 공유 ref를 바꾸는 명령은 다른 worktree의 잠금도 존중한다
- Guard 명령의 `--session`은 훅이 받은 현재 세션이어야 하고, 잠금 중 `clean`은 사용자의
  직전 입력이 `/<명령> clean`일 때만 통과한다
- snapshot·잠금·`refs/commitforge` 삭제와 덮어쓰기는 잠금과 관계없이 거부한다.
  glob, `cd`, 변수, find, `update-ref --stdin`까지 해석한다. xargs로 넘긴 경로는
  명령에 그 이름이 있을 때만 막는다. `ledger/.lock` 제거만 허용한다
- 훅은 launcher로 감싸 설치한다. 스크립트가 없으면(프로젝트 이동, 다운그레이드)
  통과하고, uninstall은 옮겨진 경로의 옛 항목도 제거한다
- Guard는 session을 신원으로 쓴다. `conserve`·`finish`·`abort`·`verify-review`·
  `audit-snapshot`은 현재 잠금 owner와 세션이 같으면 넘겨받은 `--token`이 틀려도
  무시하고(`token_ignored`) 진행한다. `release-snapshot`만 token을 요구한다
- 잠금을 잃은 실행의 `conserve`·`abort`는 `lock_not_owned`로 실패하면서 그 세션
  snapshot의 보존 검사 결과(lost, recovery_ref)를 함께 보고한다
- Guard `clean`은 요청 세션 값을 먼저 검증하고, 잠금을 푼 뒤 owner snapshot의 보존
  검사 결과를 `conservation`으로 보고한다. 유실이 있으면 경고를 붙인다
- `/cc`·`/ccf`·`/cf`에 "Guard 명령 실패" 절차를 추가했다. 어떤 사유든 실패하면
  커밋을 멈추고 `abort`한 뒤 보고한다. 커밋 순서가 틀렸어도 history를 고치지 않는다
- `/cca learn`의 비교 파일, hunk patch, `/cp` PR 본문을 snapshot 최상위가 아니라
  `learn/`·`patches/`·`pr/` 하위 디렉터리에 쓰도록 문서를 고쳤다. 최상위 파일은
  `finish`의 무결성 감사가 거부해 `/cca learn`이 항상 실패했다

## 1.21.1 — 2026-10-02

- Windows에서 SessionStart·SessionEnd 훅이 `powershell.exe: command not found`로
  실패하던 문제를 고쳤다. Claude Code가 훅을 실행하는 Git Bash의 PATH에
  WindowsPowerShell 디렉터리가 없으면 훅 명령 맨 앞의 `powershell.exe`를 찾지
  못했다. 이제 설치기가 `SystemRoot` 기준 절대 경로
  (`C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`)를 슬래시 형태로
  기록해 Git Bash·cmd.exe·PowerShell 어디서든 PATH와 무관하게 실행된다.
  `/cr` 편집 훅도 같다
- 설치기·제거기가 이전 형식(`powershell.exe`만 쓴 명령)과 새 형식을 모두
  CommitForge 훅으로 인식한다. 기존 Windows 설치는 `install.py`를 다시 실행하면
  훅이 교체된다

## 1.21.0 — 2026-10-03

- `/ccf`를 **`/cc`에서 hunk 단위 분리만 뺀 명령**으로 개편했다. 이전 `/ccf`는
  속도를 위해 worktree lock, fingerprint 재검사, 의존성 계획, 프로젝트 검증을
  건너뛰고 staging 규칙 문서도 읽지 않았다. 이제 Guard `begin`·`finish`·`abort`,
  커밋마다 fingerprint 재검사, 의존성 계획, 기본 프로젝트 검증, `clean`을 `/cc`와
  똑같이 쓴다. `git add -p`와 `git apply --cached`는 쓰지 않으므로 patch 적용
  실패와 index 재구성 위험이 없다
- 한 파일에 의도가 섞이면 가장 지배적인 의도의 커밋에 파일째 넣고 커밋 본문과
  보고에 함께 들어간 의도를 적는다. 선행 조건이 깨지면 커밋을 합치거나 그
  파일의 커밋을 앞에 둔다
- `fast-commit-rules.md`는 `/cf`·`/cfr` 전용이 됐다. 1.20.0 이하 `/ccf`가 lock
  없이 남긴 snapshot을 지우는 `release-snapshot`은 유지한다
- Guard에 **변경 보존 검사**를 추가했다. 다른 장비에서 `/ccf`가 `git add` 뒤
  `git reset --hard`를 실행해 기존 파일 수정 수백 개가 사라졌는데, working
  tree가 깨끗해 성공으로 처리되고 snapshot까지 지워진 사례가 계기다. clean
  여부는 성공의 증거가 아니다
- `begin`이 시작 working tree 전체를 git tree로 기록하고
  `refs/commitforge/snapshots/<snapshot>` ref로 고정한다. 실제 index와 파일은
  바꾸지 않는다. snapshot 디렉터리가 사라져도 git 안에서 복원할 수 있다
- 새 `conserve` 명령과 `finish`·`release-snapshot`은 시작 시점에 바뀌어 있던
  경로가 시작 HEAD 내용으로 돌아갔거나 사라졌는지(`lost`), HEAD가 되감겼는지
  (`head_rewound`)를 확인하고, 해당하면 `worktree_changes_lost`로 거부해
  snapshot과 ref를 보존한다. 우회 옵션은 없다. 정상 `finish`는 ref도 지운다
- `/cc`·`/ccf`·`/cf`는 커밋마다 `conserve`를 실행하고, 유실을 감지하면 커밋을
  멈추고 `abort`한 뒤 `git restore --source=<ref> --worktree -- <path>` 복원
  명령을 안내한다. staging 정리 용도로 reset·checkout·stash·clean을 쓰지
  않는다는 규칙도 명시했다
- 검사는 `finish`에 들어가므로 `/cca`, `/cr --fix`, `/cp`에도 적용된다.
  `/cca` 자동 수정이 파일 전체를 시작 HEAD와 같게 되돌리면 유실로 판정해
  실패로 끝나고 snapshot이 남는다

## 1.20.0 — 2026-09-19

- 리뷰 heuristic에 **도달성(reachability)** 축을 도입해 "이론적 가능성"과 "실제
  위험"을 분리했다. `confidence`는 "이 주장이 코드에서 성립하는가"만 재는
  인식론적 축이라, 트리거 주체가 없는 경로도 끝까지 짚기만 하면 10을 받고
  임계값 8을 그대로 통과했다. `review-execution.md` §3.2가 `실재`·`조건부`·
  `이론` 3단계를 정의하고, 정하지 못하면 `이론`이며 `이론`은 보고하지 않는다
- §3.6 격리 검증이 두 질문에 **따로** 답한다. 묶어 물으면 성립 여부에 대한
  확신이 실재성으로 새어 들어가 축을 도입한 의미가 사라진다. 탐지자가 적은
  도달성 한 줄도 검증자에게 넘기지 않는다 — 확인이 아니라 새 판정이어야 한다.
  `이론`과 `조건부`+`성립불가`는 `REJECTED`, `조건부`+`확인불가`는 **심각도를
  유지한 채** `blocking`만 내린다. `NOTE`로 옮기면 보고서에서 사실상 사라져
  정보를 잃기 때문이다
- 되돌릴 수 없는 피해 5종은 이 강등에서 제외된다. `review-policy.md`의 기존
  `confidence_threshold` 보호 목록을 **재사용**하고, 그 목록이 이제 두 게이트를
  함께 관장함을 같은 파일에 명시했다. 규칙이 두 벌로 갈라지면 한쪽만 고쳐질 수
  있다
- reviewer 17개 전부에 `보고 제외`·`판정 precedent` 절을 갖췄다. 1.18.0이 17개
  전체에 추가했다고 기록했지만 실제로는 security·correctness·performance·
  quality 4개에만 들어가 있었고, 나머지 13개는 한 줄짜리 문장뿐이어서 이론적
  finding을 거르지 못했다. 이번에 13개를 채워 기록과 실제를 맞춘다
- 각 reviewer의 도달성 절은 **관점마다 다른 트리거 주체**를 규정한다. Security는
  공격자가 실제로 제어하는 입력, Performance는 실제 데이터 규모와 호출 빈도,
  Testing은 "테스트가 없다"가 아니라 회귀해도 아무도 모르는 동작 변경, Quality는
  런타임이 아니라 이 코드를 다음에 고칠 사람이 부딪히는 지점이다. UX의 렌더
  결과에 의존하는 수치는 finding이 아니라 수동 시험 항목으로 분리된다
- Data/Migration과 Reliability에는 해당 피해 유형이 `조건부`여도 차단에서
  강등되지 않음을 명시해, 등급을 낮춰 잡는 우회를 막는다
- `reporting.md`의 두 보고 형식에 도달성 집계를 추가했다. 강등분은 심각도를
  유지하므로 미해결 MAJOR와 별도 줄로 적는다
- 원장 스키마·`ledger.py`·`report_validator.py`·SARIF는 변경하지 않았다. 강제는
  프롬프트와 격리 검증 층에서만 이뤄지므로 기존 원장과 호환이 깨지지 않는다.
  다만 도달성 누락을 원장이 거부하지는 않는다

## 1.19.0 — 2026-09-17

- `/cpr`·`/cp`에 리뷰 원장을 도입했다. 원장 규약을 cr/SKILL.md에서
  `_git-atomic-core/review-ledger.md`로 추출해 참조로 바꾸고, 두 명령은
  committed range를 scope로 원장을 연다. PR은 배포 순서와 rollback이 실제가
  되는 지점이라 필수 관점에 release를 더한다. `/ccr`은 제외 — Guard begin을
  호출하지 않아 snapshot이 없으며, snapshot을 주면 배타적 락이 가벼운 계획
  명령을 리뷰와 동시에 돌 수 없게 만든다
- `/cca`에 리뷰 원장과 봉인(seal)을 추가했다. `/cca`는 리뷰 뒤 의도적으로
  staging·commit을 해서 헤드 전이가 세대 fingerprint를 어긋나게 만들고
  `ledger_stale`을 일으켰다. seal은 staging 직전에 게이트와 동일한 검사를
  수행해 통과한 실행만 봉인하고, advance는 봉인을 해제한다
- seal과 게이트의 판정을 `guard.py`의 `_ledger_gate_failure`에서 공용화했다.
  두 곳에 같은 판정을 두면 어긋날 수 있고, seal이 게이트보다 느슨해지는 순간
  우회가 된다
- `/cr`에 계약 위험·성능 관점 강제를 배선하고, 필수 reviewer 관점을
  명령어별로 선언 가능하게 변경했다. `/cpr`·`/cp`에 심각도 정의를 공급하고
  기각 금지 목록을 피해 유형 기준으로 재정의했다. data/migration trigger가
  놓치던 경로 3종을 추가했다
- 익스텐션의 설치 시 다운그레이드 경고를 추가했다. 정리(reinstall)·업그레이드
  명령은 번들 payload를 덮어쓰는데, 설치본이 번들보다 최신이면 버전이 뒤로
  밀린다. 막지는 않되 dry-run 출력과 확인 모달에 다운그레이드임을 밝힌다
- 익스텐션 버전을 저장소 VERSION에 맞춘다. 1.16.0에 머물러 있어 번들과
  설치본 비교의 기준 자체가 낡아 있었다
- 버전 차이를 손상으로 오판하던 설치 판정을 수정하고, 잘린 누락·불일치
  목록에 총계와 남은 개수를 표시한다. payload 개수 단언은 절대값 대신
  분류 불변식으로 바꾼다
- 리뷰 게이트 강화의 설계 문서와 구현 계획을 `docs/superpowers/`에 추가했다

## 1.18.0 — 2026-09-13

- 모든 reviewer agent(17개)에 확신도(confidence)·보고 제외·판정 precedent
  섹션을 추가했다. review-execution.md에 §3.1 확신도 등급 기준과 §3.6 격리
  검증을 도입하고, ledger.py·report_validator.py에 confidence·verification
  필드 검증과 verification summary를 추가한다. examples/review.yml에
  confidence_threshold 설정이 들어간다
- reviewer 관점 게이트로 Line·Correctness·Security 관점을 필수화했다.
  coverage에 reviewer_roles·missing·unknown을 추가하고, finish·verify-review
  에서 `ledger_reviewer_missing`·`ledger_reviewer_unknown`으로 차단한다
  (`ledger_invalid_reviewer_status` 포함)
- `cca-release-deployment-reviewer`를 신규 추가하고 reviewer_triggers.py를
  대폭 확장했다(inactive, exclusions, context). large-diff 규모별 관점 배분
  지침과 performance 관점의 메모리 누수·CPU 점유·main thread 정지 설명도
  보강했다
- 원장의 침묵 통과 경로를 막았다. 미판정 hunk가 finish에 도달하는 3개 경로,
  분모 누락·원장 손상·세대 전이 순서, 빈 리뷰와 prefix 고정·존재 검사를
  처리하고 verify.py 필수 목록에 ledger.py를 추가한다
- `/cr` 원장 사용 순서와 판정 어휘 문서를 실제 구현에 맞췄다

## 1.17.0 — 2026-09-12

- `/cr`에 리뷰 원장을 도입했다. `ledger.py`가 Guard 스냅샷과 커밋 범위에서 hunk
  분모를 기계 생성하고, 판정·finding·reviewer 상태를 디스크에 적재한다
- `guard.py verify-review`와 `finish`가 **스냅샷에 원장이 있으면 flag 없이도**
  커버리지를 검사한다. 미판정 hunk, `UNKNOWN`, 빈 분모, 어긋난 fingerprint가
  있으면 완료를 차단한다. `--require-ledger`는 "원장이 아예 없으면 추가로
  실패한다"는 의미이며, `--allow-unledgered`는 명시적 탈출구로 우회 사실이
  출력에 남는다. 원장을 만들지 않는 `/cpr`·`/cca`는 영향이 없다
- `ledger.py init`은 재실행해도 파괴적이지 않다. scope를 합집합으로 더하고
  `iteration`·기록된 판정을 보존한다. 커밋 범위는 계산된 뒤에 선언한다
- `inventory`는 2세대 이후 live working tree에서 분모를 만들고, 이미 만들어진
  세대를 다른 id 집합으로 덮어쓰지 않는다(`ledger_inventory_conflict`)
- 모든 diff 수집을 `diff.noprefix`·`diff.mnemonicPrefix`·`diff.srcPrefix`·
  `diff.dstPrefix` 설정과 무관하게 `a/`·`b/` prefix가 붙도록 고정하고, 경로는
  `+++`/`---`/`rename to` 헤더에서 읽어 공백을 포함한 경로도 정확히 식별한다
- 분모가 0이어도 snapshot이 비어 있으면 차단하지 않는다. 아무것도 바뀌지 않은
  저장소의 `/cr`은 정상적인 빈 리뷰이며 "검토 대상 없음"으로 종료한다.
  snapshot에 변경이 있는데 분모가 0일 때만 `ledger_empty_inventory`다
- 대규모 diff 리뷰에서 컨텍스트 압축으로 변경 원장이 유실되어도 미검토 hunk가
  침묵 통과하지 않는다. 커버리지 판정 근거가 대화 기억에서 디스크로 옮겨졌다
- 분모에서 hunk가 빠지던 경로를 닫았다. `begin` 이후 편집하면 `inventory`가
  snapshot 대신 live working tree를 읽고(이전에는 `iteration`만 보다가 `init`의
  scope 추가 경로에서 낡은 snapshot을 읽으면서 세대 이름만 현재 fingerprint로
  붙어 `ledger_stale`이 발동하지 못했다), 충돌 상태의 `diff --cc`/`* Unmerged
  path`와 `diff.submodule`·`diff.ignoreSubmodules` 설정에 가려지던 submodule
  포인터 변경을 모두 센다. 중복 선언한 scope는 분모를 두 배로 만들지 않는다
- `append_jsonl`이 잘린 마지막 줄에 이어붙이지 않는다. 이전에는 다음 batch가
  조각에 붙어 조용히 사라지고 그다음 batch가 원장을 영구 손상시켰다
- 원장 손상·미초기화가 exit 3이 아니라 `ledger_corrupt`·`ledger_missing`으로
  보고된다. `run.json` 필드 타입, JSONL 레코드 형태, `init` 이전의 잠금 획득이
  모두 진단 가능한 실패가 됐다
- `advance`는 저장소가 실제로 바뀌지 않았으면 `ledger_advance_noop`으로 거부해
  완료된 세대를 잃지 않게 하고, `report`는 이전 세대의 finding까지 모아
  보고한다. 이전에는 수정 후 `advance` 한 번으로 모든 finding이 사라졌다
- `--allow-unledgered`로 통과한 `finish`는 snapshot을 보존한다. 우회 내역의
  유일한 기록이 원장이기 때문이다. 원장이 없을 때의 게이트 출력도 다른 경로와
  같은 필드 집합을 갖는다
- `guard.emit`이 surrogate escape 경로를 담은 payload에서 죽지 않는다. 이전에는
  UnicodeEncodeError로 JSON 없이 exit 1이었다
- reviewer 계약의 hunk 판정 철자를 `N_A`로 통일했다. `N/A`는 batch 전체가
  거부되므로 `cca-line-reviewer`와 `review-execution.md`가 원장과 어긋나 있었다
- `/cr` §4의 원장 세대 전이를 재리뷰 **앞으로** 옮겼다. 뒤에 두면 재리뷰 판정이
  낡은 세대에 기록됐다가 전이 시점에 버려져 `finish`가 차단됐다

## 1.16.0 — 2026-09-11

- `/ccf`가 **전부 성공하면 Diff snapshot을 정리**하고, 차단·실패·중단 시에는
  보존하도록 변경. 이전에는 성공해도 항상 남아 수동으로 지워야 했음
- Guard에 `release-snapshot` 서브커맨드 추가. `finish`·`abort`는 `verify_owner`로
  lock 소유자를 검증하므로 lock을 획득하지 않는 `/ccf`에는 쓸 수 없어, snapshot
  marker의 session·token만 검증하고 lock은 읽지도 해제하지도 않는 경로를 분리
- 삭제는 **무결성 감사 통과**와 **working tree clean**을 모두 만족할 때만 수행.
  손상·변조된 snapshot이나 커밋되지 않은 변경이 남은 상태에서는 거부하고 보존
- `--scope` 모드는 범위 밖 변경 때문에 dirty이므로 거부되며, 범위 밖이 시작
  상태대로 보존됐음을 확인한 경우에만 `--allow-dirty`로 정리
- `/ccf`에 `--keep-snapshot` 추가. 성공해도 snapshot을 보존
- `guard.py snapshot`이 응답에 `token`을 포함. 이 token은 lock 소유권이 아니라
  해당 snapshot에 대한 소유 증명이며 `release-snapshot`에만 사용
- `clean`은 이전과 같이 이 snapshot을 삭제하지 않음. 관련 문서의 정리 안내를
  `release-snapshot` 기준으로 수정
- VS Code·Cursor용 에디터 확장(`editor-extension/`) 추가. 워크스페이스의
  설치 상태(project·global)와 lock·snapshot·경고를 상태바와 사이드바 트리
  뷰로 보여주고, 명령과 옵션을 골라 확인 후 Claude Code 터미널로 전송. 확장은
  `.claude/` 아래에 직접 쓰지 않고 항상 번들된 `install.py`/`uninstall.py`를
  실행해 CLI 설치와 결과가 동일하게 유지됨
- `install.py`가 설치 시 `.claude/.commitforge-install.json` 마커(버전·범위·
  Python 경로·core 경로)를 기록하고 `uninstall.py`가 제거. 해시 대조만으로는
  구분할 수 없던 설치본 버전을 마커로 표시할 수 있게 되어 CLI 단독 사용자와
  에디터 확장 모두에 도움

## 1.15.0 — 2026-09-11

- Fast Commit 경로 `/cf`, `/cfr`, `/ccf` 추가. `/cc`의 정밀 Atomic 분석이 과한
  실험·WIP 상황에서 훨씬 빠르게 commit하기 위한 별도 경로
- `/cf`는 아직 커밋되지 않은 모든 변경(staged·unstaged·untracked)을 하나의
  index로 합쳐 단일 commit을 생성. 대표 type은
  `feat > fix > perf > refactor > test > docs > build/ci > style > chore`
  우선순위로 고르고 섞인 의도를 본문에 모두 나열해 정보 손실 방지
- `/cfr`은 `/cf`가 만들 커밋을 읽기 전용으로 미리 보여주며 대상 파일, 대표 type
  근거, 메시지 초안, 차단 사유, 권장 후속 명령을 보고
- `/ccf`는 의미 분리를 유지한 다중 commit을 최소 경로로 생성. 파일 단위
  그룹핑만 사용하고 hunk 분리·fingerprint 재검사·의존성 정밀 분석·프로젝트
  검증·reviewer를 생략
- 세 명령 모두 secret·자격 파일·merge conflict marker·산출물 대량 유입 차단
  스캔을 유지하며, 이 스캔은 `--verify`·`--no-verify`·`--scope` 어느 것으로도
  끌 수 없음
- `/cf`는 프로젝트 검증을 기본 생략하고 `--verify`로만 실행. `--no-verify`는
  commit hook까지 우회
- `/ccf`는 속도를 위해 worktree lock을 획득하지 않음. 대신 Guard에 lock 없이
  Diff snapshot만 만드는 `guard.py snapshot` 서브커맨드를 추가해 복구 수단은
  유지하며, 이 snapshot은 소유 token이 공개되지 않아 자동 삭제되지 않음
- `/cf`와 `/ccf`의 결과는 완전한 Atomic Commit이 아닐 수 있으므로 결과 보고에서
  그 사실과 `/cc`·`/cca` 권장을 항상 명시
- core에 `fast-commit-rules.md` 추가, `reporting.md`에 `/cf`·`/cfr`·`/ccf`
  보고 형식 추가, `recovery.md`에 lock 없는 snapshot 복구 절차 추가

## 1.14.1 — 2026-07-31

- Claude Code의 `Stop`을 세션 종료로 잘못 해석해 여러 turn에 걸친 `/cr`·`/cca`
  도중 Guard lock이 조기 해제되던 lifecycle 버그 수정
- `Stop`·`StopFailure`에서는 lock을 유지하고 `/clear`·`/exit`·`/resume`·로그아웃
  등의 실제 `SessionEnd`에서만 소유 lock을 해제하도록 이벤트 경계 교정
- 새 설치에는 `SessionStart`·`SessionEnd` hook만 등록하고 재설치 시 구버전의
  `Stop`·`StopFailure` handler를 자동 제거
- 구버전 설정이 새 스크립트를 먼저 호출하는 전환 구간에서도 turn 종료 이벤트를
  no-op 처리해 lock을 보존하고, 다중 turn·업그레이드 회귀 테스트 추가
- 설치·제거 시 lifecycle hook 소유권을 경로 부분 일치가 아닌 정확한 설치 스크립트
  경로로 판정해 이름이 비슷한 사용자 정의 hook을 보존

## 1.14.0 — 2026-07-26

- `/cca` 최초 리뷰와 수정 후 재리뷰를 read-only Agent Team core 3명과 조건부
  specialist로 실행하고, Team 종료 후에만 lead가 수정·검증·staging·commit
- 수정할 때마다 이전 결과를 무효화하고 fingerprint·trigger를 갱신한 새 Team으로
  전체 diff를 재리뷰하는 `--iterations` 반복 계약 유지
- `/cca` 반복 중 “종료 예약”을 받으면 현재 안전 경계에서 teammate를 회수하고
  Guard를 `abort`해 lock을 해제하며 snapshot을 보존하는 graceful stop 추가
- 최초 리뷰와 매 재리뷰 시작 시 현재 반복 횟수와 graceful stop 사용법 안내
- Windows에서 임시 경로의 표기·대소문자 정규화 차이로 lifecycle hook 보존 테스트가
  잘못 실패하던 문제 수정
- GitHub Actions의 중복 Ubuntu 검증 job과 중복 live eval step을 제거하고 기준
  검증 통과 후에만 세 portability job을 실행하며, 같은 ref의 이전 run은 자동 취소
- Dependabot GitHub Actions 갱신을 하나의 주간 그룹·PR로 제한해 중복 update
  workflow와 PR 검증 run을 축소

## 1.13.0 — 2026-07-26

- 설치 시 Claude Code `SessionStart`, `Stop`, `StopFailure`, `SessionEnd` lifecycle
  hook을 사용자 설정에 병합해 Guard owner를 실제 Claude `session_id`와 결합
- 정상 응답 종료, API 실패, `/clear`, `/exit`, `/resume`, 로그아웃에서 종료 세션과
  owner가 정확히 일치하는 현재 worktree 잠금만 자동 해제하고 Diff snapshot은 보존
- 수동·자동 `/compact`에서는 잠금을 유지하고 같은 session ID를 다시 바인딩해 진행 중
  리뷰·검증의 동시 실행 보호가 끊기지 않도록 처리
- 다른 세션의 잠금, 다른 저장소, 비정상 lock 내용은 자동 종료 정리가 건드리지 않는
  fail-closed `guard.py session-end` 경로와 회귀 테스트 추가
- 단기 Guard 프로세스 PID를 활성 세션으로 오인하지 않도록 owner 필드를
  `guard_pid`에서 의미가 명확한 `begin_pid`로 변경
- 프로젝트 설치는 `.claude/settings.local.json`, 전역 설치는
  `~/.claude/settings.json`을 사용하며 기존 사용자 설정·hook을 보존하고 제거 시
  CommitForge lifecycle hook만 제거
- macOS·Linux·Windows에서 셸이 만든 임의 세션 문자열 대신 설치 hook이 전달한
  `COMMITFORGE_SESSION_ID`만 사용하도록 모든 실행 계약과 복구 문서 갱신

## 1.12.1 — 2026-07-26

- `/cr`의 `PreToolUse` Write/Edit 훅이 셸에 존재하지 않는
  `${CLAUDE_SKILL_DIR}` 환경변수에 의존하지 않도록 설치 시 현재 Python과
  `cr_edit_gate.py`의 절대경로를 고정
- 모든 Skill frontmatter의 Guard·검토 보조 스크립트 권한 패턴도 설치 시 core
  절대경로로 고정하고, 모델용 경로·세션 표기는 셸 환경변수와 구분되는 명시적
  placeholder로 변경
- 검증기가 Skill frontmatter뿐 아니라 모든 Skill Markdown의 `${...}` 런타임
  변수형 placeholder를 거부하도록 보강해 같은 종류의 hook·permission·명령
  경로 회귀를 패키징 전에 차단
- 공백·작은따옴표가 포함된 설치 경로와 Windows 명령줄 quoting을 처리하고,
  `CLAUDE_SKILL_DIR`가 없는 환경에서 설치된 훅이 실제로 fail-closed 실행되는
  회귀 테스트 추가
- 프로젝트 검증 명령은 광범위하게 자동 승인하지 않는 안전 경계를 유지하되,
  실행 전 “allowed-tools 밖이라 거부될 수 있음” 같은 추측성 문구를 금지하고
  실제 permission 요청·거절·환경 실패가 발생했을 때만 정확히 보고
- 모든 명령의 성공·실패·중단 결과에 승인 대기, reviewer, 검증, Guard 정리를
  포함한 전체 소요 시간을 분 단위로 표시하고 JSON review report에도
  `timing.elapsed_minutes` 추가

## 1.12.0 — 2026-07-25

- `/ccr`, `/cc`, `/cr`, `/cca`, `/cpr`, `/cp`에 현재 Git worktree의
  CommitForge advisory lock만 명시적으로 해제하는 `clean` 조기 종료 명령 추가
- `clean`은 다른 저장소·worktree, working tree/index/commit과 보존된 Diff
  snapshot을 건드리지 않으며 잠금 없음 재실행은 성공한 no-op 처리
- `/cr` source-read-only, `/ccr`, `/cpr`에 환경·변경 규모·domain·고위험
  trigger 기반 선택적·적응형 Agent Team 모드와 `--team`·`--no-team` 추가
- 읽기 전용 대상은 Agent Teams 환경 활성 시 Team-first를 기본으로 변경하고,
  모든 대상 명령을 core 3명으로 단순화. 파일 2개·80 changed lines 이하의
  저위험 단일 domain만 Team 생략
- 대형 변경을 파일 수로 균등 분할하지 않고 package/domain/runtime shard와
  core 3명·조건부 specialist 관점을 겹쳐 배정하며 lead aggregator가 contract와
  hunk coverage 통합
- 대형 diff 시작 공지에 실제 초과 값·적용 threshold와 core 3명+specialist
  구조를 분리해 표시하고, 계산하지 않은 hunk 수나 임의 threshold 보고를 금지
- 문서 전용이 아닌 행위 변경은 Testing/Independent Verification을 필수
  specialist로 활성화하고 Reliability, UX, Migration, Requirements, Release,
  Domain/Framework는 의미 trigger로 조건부 추가
- `/cr --fix`, `/cc`, `/cca`, `/cp`는 기존 custom subagent + lead 단독 변경
  구조를 유지하고 Team 환경이 꺼졌거나 coordination 실패 시 subagent fallback
- Agent Team을 명령별 core 역할과 조건부 specialist로 구성하고 shared task와
  peer messaging을 통해 cross-file contract와 finding을 교차검증하도록 실행 계약 보강
- OWASP Top 10:2025·ASVS 5.0, WCAG 2.2, NIST SSDF와 OpenTelemetry 최신 관점을
  반영해 공급망·artifact integrity/provenance, exceptional conditions,
  compatibility, observability/alerting, 접근성·migration/rollback 검토 강화
- Agent Teams 환경변수는 정확히 `1`일 때만 활성으로 판정하며 CommitForge가
  사용자 환경을 설정·변경하지 않는다는 경계 추가
- 모든 명령 본문 첫 섹션에 `${CLAUDE_SKILL_DIR}` 해석 규칙과 `CF_CORE` 확정
  Preflight를 추가해 skills 루트로 잘못 치환된 경로가 만드는 실행 실패 차단
- Guard 실행 자체가 실패한 경우(exit code 126·127, `command not found`,
  Python 미탐지)도 fail-closed 사유로 명시해 Guard 생략 후 진행을 금지
- Guard owner에 `hostname`을 기록하고 `begin`·`status` 결과에 `stale_candidate`,
  `lock_owner_same_host`, `lock_owner_same_session`, `stale_after_seconds` 보고
- 같은 호스트의 오래된 잠금이나 동일 세션 재진입만 회수하는
  `begin --reclaim-stale [--stale-after <초>]` 추가. 기존 owner의 snapshot은 보존하고
  다른 호스트·신선한 잠금·비정상 잠금 내용은 `reclaim_refused_reason`으로 거부
- 잠금 충돌 결과의 `recovery`에 `clean_hint`, `clean_argv`, `reclaim_hint`를 추가해
  복구 경로를 명시
- Git 자체 lock(`index.lock` 등) 차단을 `reason=git_external_lock`으로 분리하고 각
  lock의 `size`, `age_seconds`, `writer_pids`, `stale_candidate` 진단 보고. 크기 0,
  5분 경과, 쓰기 프로세스 없음을 모두 만족할 때만 stale 후보로 표시하며 읽기 전용
  핸들은 사용 중으로 보지 않음
- 명시적 `clean`은 알려진 Git lock(`index.lock`, `HEAD.lock`,
  `packed-refs.lock`, `config.lock`)이 5분 이상·0바이트·writer 없음·진행 중 Git
  operation 없음·검사 중 identity 불변을 모두 만족할 때만 제거
- macOS `lsof` 접근 모드, Linux `/proc` fd flags, Windows Win32 share-mode로
  writer를 판별하고 Finder·Spotlight·Explorer·인덱서의 읽기 전용 핸들은 제외.
  판별 불능은 자동 제거하지 않는 fail-closed 상태로 처리
- `clean`이 제거한 Git lock과 안전 조건 미충족으로 남긴 Git lock을 각각
  `git_locks_removed`, `git_lock_cleanup`, `git_locks`로 보고
- Guard `begin` 실패 후 `git status`·`git diff`·`git log` 또는 `git -C <경로>`로
  우회해 작업을 이어가는 것을 모든 명령에서 명시적으로 금지
- `verify-review`·`finish`가 session과 일치하는 현재 worktree owner token과
  유일한 snapshot을 자동 해석하도록 보강해 장시간 리뷰 후 인자 유실·basename
  오사용·존재하지 않는 `snapshot-path` 추측을 제거. 명시적 오입력은 계속 거부

## 1.10.1 — 2026-07-25

- Guard 잠금 충돌 결과에 `project_root`, `git_dir`, `lock_scope`, owner를 구조화해 다른 저장소의 잠금과 구분
- 잠금 범위가 실제 worktree Git directory이며 같은 부모 아래 독립 저장소는 서로 차단하지 않는다는 계약 명시
- 독립 저장소 동시 실행과 같은 저장소 하위 폴더 중복 차단 회귀 테스트 추가
- 중간 종료로 남은 stale lock을 현재 세션에서도 확인 후 안전하게 `abort`할 수 있도록 복구 지침 보강
- `abort --session --token`이 일치하는 owner snapshot을 자동 선택하도록 복구 API 개선
- 잠금 충돌과 status 결과에 `lock_owner_snapshots`와 구조화된 recovery 정보 추가
- 실제 `abort` 성공 결과 전에는 잠금 해제를 단정하거나 `begin`을 재시도하지 않는 `/cr` 계약 추가
- Guard가 `lock_age_seconds`와 실행 가능한 `recovery.abort_argv`를 반환해 시간대 오산·깨진 명령 방지
- `/cr` Guard begin 실패 후 변경 스캔·reviewer·테스트를 실행하지 않는 fail-closed 시작 Gate 강화
- `/cpr`, `/cp`를 포함하도록 Guard 중복 실행 오류 메시지 갱신

## 1.10.0 — 2026-07-24

- `/cpr` read-only Pull Request 미리보기 명령 추가
- `/cp` 심층 검토·검증 후 일반 branch push와 GitHub Pull Request 생성 명령 추가
- 동일 head의 열린 PR 중복 생성, non-fast-forward, stale tracking ref, dirty tree와 blocking finding 차단
- 현재가 `main`/`master`이면 변경 의미에 맞는 충돌 없는 branch 이름을 `/cpr`에서 제안하고 `/cp`에서 실제 생성
- 자동 분기 시 예상 branch 변경만 허용하고 HEAD commit·source·index 불변을 Guard로 검증
- PR 옵션·안전 경계·설치·수동 검증·파일 구조 문서 보강

## 1.9.2 — 2026-07-24

- README 첫 화면을 명령 선택·release 안전 경계·30초 시작 중심으로 재배치
- 주요 문서 섹션으로 바로 이동할 수 있는 탐색 링크 추가
- `/cr` 읽기 전용 분석과 `/cca` 실행형 확장 모드를 한 표로 비교
- 설치·명령 사용법·옵션·Atomic 메시지·권한 섹션의 제목과 설명 순서 정돈
- remote push 금지와 `/cca release --prepare --tag`의 로컬 tag 예외를 안전 섹션에서 재강조
- README 핵심 정보 순서와 시인성 요소를 정적 테스트로 고정

## 1.9.1 — 2026-07-24

- README 상단에 release tag 실행 경계를 눈에 띄는 안내로 추가
- `/cca release --prepare --tag`만 로컬 annotated tag를 실제 생성한다고 명시
- `/cr release --prepare --tag`는 예상 version/CHANGELOG·commit·tag를 읽기 전용으로 시뮬레이션한다고 명시
- 두 흐름 모두 remote tag push, GitHub Release, publish, deploy를 수행하지 않는 경계 재강조

## 1.9.0 — 2026-07-24

- `/cr release`, `/cr emergency`, `/cr learn` 읽기 전용 분석 모드 추가
- 세 `/cr` 확장 모드에서 `--fix`가 있어도 Edit·Write Hook이 차단되도록 실행 경계 강화
- `/cca release`에 `--target`, `--bump`, `--channel`, `--package`, `--tag-prefix`, `--from`, `--dry-run`, `--prepare`, `--tag` 계약 추가
- 기존 tag를 기준으로 stable/rc/beta/alpha와 monorepo package tag 번호를 결정론적으로 자동 증가하는 계산기 추가
- `/cca release --prepare --tag`에서만 검증된 최종 HEAD에 로컬 annotated tag를 생성하고 push·publish·deploy는 분리
- emergency 모드에 incident·severity·diagnose·rollback-first·base·scope 기반 진단, 완화, 최소 hotfix, 관찰·복구 절차 추가
- learn 모드에 preview·since·branches·exclude-bots·package 범위와 근거·반례·확신도를 가진 JSON/Markdown 프로필 추가
- README, 설치 안내, 수동 시험 체크리스트와 품질 보고서에 실행형 `/cca`와 읽기 전용 `/cr`의 차이를 보강

## 1.8.0 — 2026-07-24

- `/cr 3days`, `/cca 3days` 최근 3개 달력일 리뷰·커밋 모드 추가
- `3days`를 선택 시간대의 이틀 전 00:00부터 현재까지로 정의하고 rolling 72시간과 구분
- 기간 경계 계산기와 고정 시각 회귀 테스트에 `3days` 추가
- reviewer 기본 동시 실행을 6개로 확대하고 고위험·대형 diff는 환경 상한 안에서 최대 8개까지 사용
- rate-limit, agent 시작 실패, 반복 timeout 발생 시 후속 batch를 3~4개로 자동 축소
- README, 설치 안내, 수동 체크리스트와 품질 보고서에 새 기간 모드와 적응형 병렬 정책 반영

## 1.7.1 — 2026-07-24

- README 옵션 표의 `|` 구분자가 열로 잘못 해석되는 Markdown 렌더링 오류 수정
- 공통 리뷰, today·weekly 기간, `/cca` 확장 모드 옵션을 적용 범위별로 재구성
- `--output` 보고서 생성 시점과 저장소 내부 출력의 미커밋 처리 명시
- 빠른 명령 선택표, 재설치 기반 업그레이드 절차, 기간 옵션 기본값과 예시 추가
- 기본 `/cr`의 작업 트리 불변 검증 범위와 Permission Hook 설명 최신화
- README 파일 구조에 `/cr` Skill과 `cr_edit_gate.py` 누락 보완

## 1.7.0 — 2026-07-24

- `/cr`의 기본 동작을 소스 수정 없는 read-only 리뷰로 변경
- 현재 working hunk의 확정적·국소 문제 수정은 `--fix`를 명시한 경우에만 허용
- `/cr today`, `weekly`, `--base`, `--range`, `pr`도 같은 opt-in 수정 정책 적용
- committed range finding만으로 corrective working change를 자동 생성하지 않는 경계 강화
- Skill 범위 PreToolUse Hook이 기본 `/cr`의 Edit·Write·NotebookEdit 호출을 실행 전에 차단
- `/cca`는 기존 기본 수정 정책과 `--no-fix` 옵션 유지
- Live eval에서 별도 `--no-fix` 없이 `/cr`의 HEAD·index·working tree 불변 검증

## 1.6.0 — 2026-07-24

- `/cr today`, `/cr weekly` 기간 심층 리뷰 모드 추가
- `/cca today`를 커밋 원장·net effect·revert·후속 수정·교차 커밋 finding 귀속으로 강화
- `/cca weekly`에 날짜·domain·작성자 집계와 반복 수정·미완료 위험 분석 추가
- today는 로컬 달력 자정, weekly는 기본 월요일 자정으로 명확히 정의
- `--all-authors`, `--week-start monday|sunday`, `--timezone <IANA|±HH:MM>` 기간 옵션 추가
- 기존 기간 commit은 불변으로 유지하고 `/cr`은 Atomic 계획 없이, `/cca`는 미커밋 변경만 commit하도록 경계 강화
- Python 3.9 호환 기간 경계 계산기와 고정 시각 회귀 테스트 추가
- clean working tree의 오늘 커밋을 검토하는 실제 Claude Code E2E 평가 추가

## 1.5.0 — 2026-07-23

- `/cr --base`, `--range`, `pr`로 branch·commit range·GitHub PR 심층 리뷰 지원
- `.commitforge/review.yml` 기반 프로젝트별 reviewer·대형 diff·출력·baseline 정책 추가
- `commitforge-review/v1` JSON과 SARIF 2.1.0 보고서 및 계약 validator 추가
- 소유자·사유·만료일·fingerprint 기반 finding baseline과 고위험 억제 금지 규칙 추가
- 대형 diff의 domain shard, cross-file contract 집계, 문맥 부족 `UNKNOWN` 차단 추가
- snapshot 파일별 크기·SHA-256 inventory와 삭제 전 무결성 감사 추가
- 실제 Claude Code `/cr --no-fix` opt-in 평가 harness와 회귀 scenario 추가
- Ubuntu Python 3.9/3.13, macOS, Windows CI matrix 추가
- LF checkout과 UTF-8 Python 출력을 고정해 Windows 검증의 재현성 확보
- GitHub Actions를 전체 commit SHA로 고정하고 Dependabot 업데이트 설정 추가

## 1.4.0 — 2026-07-23

- Guard `verify-review`와 `finish --review-only`로 `/cr`의 HEAD·branch·staged diff 불변 조건을 프로그램 수준에서 강제
- 조건부 reviewer 최소 활성 집합을 계산하는 보수적 trigger 도구와 golden fixture 평가 추가
- finding stable ID, fingerprint, severity, status, evidence, blocking 공통 schema 추가
- reviewer 최대 병렬 수, 필수 관점, fallback과 `UNKNOWN` 차단 정책 추가
- Node.js 24 기반 GitHub Actions에서 metadata·test·syntax·checksum·installer를 자동 검증
- `release.py`로 manifest·checksum 검증과 재현 가능한 ZIP/TAR.GZ 생성 지원

## 1.3.0 — 2026-07-23

- `/cr`에서 Atomic Commit 전용 Git reviewer와 staging plan Gate를 제거해 순수 review-only 경계 보장
- `/cr` 종료 Gate에 HEAD·staged diff 불변과 Commit 계획·메시지·staging 금지 조건 추가
- Testing reviewer가 `review-only` 모드에서 Atomic Commit 배치 제안을 생략하도록 분기
- Data/Migration, Dependency/Supply Chain, Reliability/Recovery 전문 reviewer 추가
- Privacy/Governance, Requirements/Product 전문 reviewer를 명시적 trigger 기반으로 추가
- 조건부 reviewer 활성화·N/A 근거·수정 후 trigger 재평가 규칙 추가

## 1.2.0 — 2026-07-23

- 모든 diff hunk를 PASS/FINDING/N/A로 추적하는 엄격한 line-by-line 원장 추가
- 제거된 동작과 cross-file contract 회귀 검토 강화
- wrapper/proxy/adapter의 인자·반환·오류·취소·context 의미 보존 검사
- Architecture, Language/API, UX/Accessibility, Observability, Quality 전문 reviewer 추가
- 기존 구현 재사용·중복·복잡도·유지보수성 검토 추가
- JavaScript/TypeScript, React/Next.js, Dart/Flutter, Python, Go, Rust, JVM, Swift, C/C++, SQL, Infrastructure API 함정 카탈로그 추가
- 미검토 hunk가 있으면 commit을 차단하는 심층 Coverage Gate 추가
- `/cr` 심층 코드 리뷰 명령 추가: 리뷰·국소 수정·전면 재리뷰·검증만 수행하고 Atomic Commit 계획·staging·commit·push는 제외
- reviewer shell 권한 제거와 설치·제거 registry 일치 검증 강화

## 1.1.0 — 2026-07-23

- 프로젝트 이름과 사용자 문서를 CommitForge로 통일
- `/cca today`로 오늘의 기존 commit과 미커밋 변경 통합 분석
- `/cca release`로 tag 기준 릴리스 검토·버전 제안·릴리스 노트 초안 지원
- `/cca emergency`로 최소 범위 hotfix 리뷰·검증·commit 지원
- `/cca learn`으로 최근 history 기반 `.commitforge/profile.md` 생성
- `/ccr`, `/cc`, `/cca`에서 CommitForge 프로젝트 프로필 자동 반영
- 설치·제거 백업 디렉터리를 CommitForge 명칭으로 변경

## 1.0.0 — 2026-07-23

- 권장 Claude Code Skills 형식으로 `/cc`, `/ccr`, `/cca` 제공
- 한글 Conventional Commit 제목·상세 본문 규칙
- 파일 및 hunk 단위 Atomic Commit 분리
- commit dependency graph와 순차 실행
- worktree별 advisory lock
- staged/unstaged binary diff snapshot
- untracked manifest/hash/archive
- repository fingerprint를 통한 TOCTOU 감지
- 실패 시 snapshot 보존과 소유 lock만 해제
- Git, correctness, security, performance, testing 전문 subagent 5종
- `/cca` review-fix-review 검증 loop
- 언어·프레임워크별 기본 프로필
- macOS/Linux/Windows 설치 및 제거 스크립트
- guard 통합 테스트와 package verifier
