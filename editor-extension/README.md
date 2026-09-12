# CommitForge 확장

CommitForge를 VS Code와 Cursor에서 설치·관리하고 명령을 실행합니다. 확장은
`.claude/` 아래에 직접 쓰지 않습니다 — 설치·업그레이드·제거는 항상 번들된
`install.py`/`uninstall.py`를 실행해서 처리하므로, 확장으로 설치하든 CLI로
설치하든 결과가 항상 같습니다.

## 기능

- **설치 관리** — project·global 범위의 설치 상태를 트리 뷰에 나란히 표시하고,
  행별 인라인 버튼으로 설치·업그레이드·재설치·검증·제거를 실행합니다.
- **상태 표시** — lock 보유 여부, Diff snapshot, git 자체 lock 같은 진행 중인
  경고를 상태바와 사이드바에 보여줍니다. 폴링하지 않고 창 포커스 복귀, 명령
  전송 직후, 수동 새로고침, 파일 변화(`.claude/**`, lock, snapshot) 시점에만
  갱신합니다.
- **명령 실행** — 명령과 옵션을 QuickPick으로 골라 Claude Code가 실행 중인
  터미널로 전송합니다. 옵션은 각 명령 `SKILL.md`의 `argument-hint`를 파싱해
  만들므로 하드코딩하지 않습니다.
- **Source Control 패널 단축 버튼** — VS Code의 기본 Source Control 뷰
  제목 줄에서 바로 `/cr`·`/cc`를 실행하고, "..." 메뉴에서 `/ccf`·`/cf`·
  `/cca`·전체 명령 목록까지 갑니다. 옵션 없이 바로 전송하는 경로이지만
  lock 사전 경고와 전송 전 확인은 QuickPick과 똑같이 거칩니다.

## 요구사항

- Python 3.9 이상
- Claude Code

확장은 CommitForge 패키지(`.claude/`, `install.py`, `uninstall.py`,
`MANIFEST.json`)를 내장하고 있어 별도로 저장소를 체크아웃할 필요가 없습니다.

## 설치

Marketplace에 공개하지 않으므로 `.vsix`를 직접 만들어 설치합니다. Node.js 20
이상이 필요합니다.

### 1. `.vsix` 만들기

CommitForge 저장소를 클론한 뒤:

```bash
cd editor-extension
npm install
npm run package
```

`editor-extension/commitforge.vsix`가 생성됩니다. 이 파일 하나에 확장과
CommitForge 패키지가 모두 들어 있습니다.

### 2. 에디터에 설치

명령 팔레트(<kbd>Cmd/Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>)에서
**`Extensions: Install from VSIX...`** 를 실행하고 방금 만든
`commitforge.vsix`를 고릅니다. Cursor와 VS Code 모두 같은 절차입니다.

CLI를 쓴다면:

```bash
cursor --install-extension editor-extension/commitforge.vsix
# VS Code는
code --install-extension editor-extension/commitforge.vsix
```

설치 후 창을 다시 불러오면(`Developer: Reload Window`) 상태바 왼쪽에
`CommitForge`가 나타납니다.

### 3. 프로젝트에 CommitForge 설치

확장이 설치됐다고 CommitForge가 프로젝트에 설치된 것은 아닙니다. 사이드바의
CommitForge 아이콘을 열면 설치 상태가 보이고, `설치` 행의 **`[설치]`** 버튼이나
팔레트의 `CommitForge: 설치`로 범위(project/global)를 골라 설치합니다. 변경
예정 내용을 `--dry-run`으로 먼저 보여주고 확인을 받습니다.

### 업그레이드와 제거

- **업그레이드**: 저장소를 `git pull`한 뒤 1·2단계를 다시 실행해 확장을 새
  `.vsix`로 덮어씁니다. 그다음 트리의 `[업그레이드]` 버튼으로 프로젝트 설치본을
  갱신합니다.
- **제거**: 트리의 `[제거]` 버튼(또는 `CommitForge: 제거`)으로 프로젝트에서
  CommitForge를 먼저 지우고, 에디터의 확장 목록에서 확장을 제거합니다.

## 비목표 (1단계)

다음은 이 확장의 1단계 범위 밖입니다.

- 헤드리스 실행(`claude -p`)
- SARIF → Problems 패널 연동
- 리뷰 결과 전용 패널, diff 점프
- 저장 시 자동 리뷰 등 자동 트리거
- Marketplace·OpenVSX 공개 배포 (설치는 로컬 `.vsix`로만 합니다)

## 명령 팔레트

| 명령 | 설명 |
|---|---|
| `CommitForge: 명령 실행` | 명령과 옵션을 골라 확인 후 터미널로 전송 |
| `CommitForge: 설치` | 범위(project/global)를 골라 dry-run 확인 후 설치 |
| `CommitForge: 제거` | 범위를 골라 dry-run 확인 후 제거 |
| `CommitForge: 설치 검증` | 설치본의 해시·경로·hook 등록 상태를 재판정해 Output에 출력 (`verify.py`가 아니라 이 확장의 판정 로직을 다시 실행합니다) |
| `CommitForge: 상태 새로고침` | 상태를 다시 읽음 |
| `CommitForge: 뷰 열기` | 사이드바의 CommitForge 트리 뷰에 포커스 |
| `CommitForge: lock 해제(clean)` | `guard.py clean`을 직접 부르지 않고 `/cr clean`을 터미널로 보냅니다 |

`CommitForge: 업그레이드`, `CommitForge: 재설치`는 내부적으로 설치와 같은
동작(`install.py`가 백업 후 덮어씀)을 하는 별칭 명령입니다. 인자 없이(팔레트에서)
실행해도 범위(project/global)를 묻는 QuickPick이 뜨고 실제로 설치를
수행하지만, 명령을 나눈 이유는 트리 인라인 버튼의 tooltip을 상태에 맞게
보여주기 위해서일 뿐이라 팔레트에 "설치"가 사실상 중복 노출되는 것을 막으려고
`package.json`의 `commandPalette`에서 `when: false`로 숨겨 팔레트에는 나타나지
않습니다. `CommitForge: 스냅샷 폴더 열기`는 트리의 스냅샷 행(경로)이 있어야
동작하는 명령이라 인자 없이 팔레트에서 실행하면 아무 일도 하지 않으므로 같은
방식으로 숨겼습니다. Source Control 패널 단축 버튼(`commitforge.send.*`)과
"값 복사"(`commitforge.copyValue`)도 같은 이유로 팔레트에서 숨깁니다 — 아래
두 절에서 설명하는 자리(SCM 제목 줄·트리 우클릭)에서만 쓰는 명령입니다.

## Source Control 패널

CommitForge는 Git 워크플로 도구이므로, 전용 사이드바로 가지 않고도 기본
Source Control 패널(diff·staging·commit이 있는 그 패널) 제목 줄에서 바로
실행할 수 있습니다. **git 저장소를 열었을 때만** 나타납니다.

- 제목 줄 아이콘 두 개: $(search) `/cr`(리뷰), $(git-commit) `/cc`(순차 커밋).
  아이콘 자리가 좁아 이 둘만 상시 노출합니다.
- "..." 메뉴(넘침 메뉴) 안의 **CommitForge** 하위 메뉴: `/ccf`(파일 단위
  빠른 커밋), `/cf`(전체를 한 커밋으로), `/cca`(리뷰·수정·검증·commit 전체
  실행), `CommitForge: 명령 실행`(옵션까지 고르는 전체 QuickPick).

버튼을 누르면 옵션 없이 바로 그 명령을 보냅니다(QuickPick에서 Enter를 누른
것과 같은 동작) — 옵션이 필요하면 "..." 메뉴의 `CommitForge: 명령 실행`으로
갑니다. **전송 경로는 QuickPick과 완전히 같습니다**: 다른 세션이 lock을 쥐고
있으면 전송 전에 경고하고(`/cc`처럼 쓰기 명령일 때), `commitforge.confirmBeforeSend`가
켜져 있으면 전송 전 미리보기 확인을 거칩니다.

버튼은 실행 시점에 `WorkspaceState.catalog`(현재 설치된 `SKILL.md`의
`argument-hint`에서 만든 카탈로그)에서 해당 명령을 찾아 조립합니다. 명령
문자열을 하드코딩하지 않으므로, CommitForge가 미설치이거나 upstream에서 명령
이름이 바뀌어 카탈로그에 없으면 엉뚱한 문자열을 보내는 대신 경고 메시지를
띄웁니다.

## 트리 뷰 (사이드바)

활동 표시줄의 CommitForge 아이콘을 클릭하면 다음을 보여줍니다.

- **설치** — CommitForge는 project·global 중 **한쪽만 정상이어도** 명령을
  쓸 수 있습니다. `설치` 그룹 행 자체가 그 결론을 말합니다: 어느 범위가
  실제로 명령을 제공하는지(project 우선, 없으면 global)를 그룹 행
  description에 보여주고, 둘 다 미설치일 때만 "설치 필요"라고 알립니다.
  단, "사용 중"이라고 말하려면 그 범위가 실제로 건강해야 합니다 — `정상`
  또는 `버전 다름`(파일이 일관되게 있고 hook·core 경로도 정상이라 명령
  자체는 동작하고 버전만 다른 상태)일 때만 "사용 중"이라고 표시합니다.
  선택된 범위가 `설정 불완전`이나 `손상`이면 그룹 행이 그 사실을 그대로
  드러냅니다 — 예: `global 손상 · 확인 필요`(경고 아이콘) — "미설치가
  아니니 다 괜찮다"는 인상을 주지 않기 위해서입니다(상태바 위젯의 경고
  표시와 일관됩니다). 그 아래 project·global 행은 각각 상태(미설치/정상/
  버전 다름/설정 불완전/손상)와 버전을 보여주고, 상태별로 다른 버튼이
  붙습니다: 미설치 행은 `[설치]` 하나뿐이고, 정상 행은 `[검증]` `[제거]`,
  버전 다름 행은 `[업그레이드]` `[검증]` `[제거]`, 설정 불완전·손상 행은
  `[재설치]` `[검증]` `[제거]`가 붙습니다. 한쪽이 미설치인데 반대쪽이
  실제로 건강하게 설치돼 있으면, 그 미설치 행은 문제로 보이지 않도록
  색이 흐려지고(`disabledForeground`) description에 "없어도 됨"이
  붙습니다 — 반대쪽이 손상돼 있으면 이 "없어도 됨" 단서도 붙지 않습니다
  (실제로는 CommitForge가 동작하지 않을 수 있기 때문입니다). `[설치]`
  버튼은 이 경우에도 여전히 눌러 그 범위에 따로 깔 수 있습니다. 각 행에
  마우스를 올리면 tooltip으로 그 범위가 무엇을 뜻하는지(project = 이
  저장소에서만, global = 모든 프로젝트에서) 설명합니다.
- **잠금** — 보유자 세션·경과 시간·호스트를 보여줍니다. 세 자식 행 모두
  tooltip이 있어, 잘린 라벨 대신 전체 값을 볼 수 있습니다: `session ...`은
  전체 세션 ID, `N 경과`는 실제 잠금 생성 시각, `이 호스트`/`다른 호스트`는
  그 호스트명과(다른 머신이면) 여기서 해제하면 안 된다는 경고를 담습니다.
  `session ...`, `이 호스트`/`다른 호스트` 행은 우클릭하면 **값 복사**로
  전체 세션 ID·호스트명을 클립보드에 담을 수 있습니다(라벨이 잘려 보여도
  복사되는 값은 항상 전체 값입니다). `[해제(clean)]` 버튼은 lock을 다른
  세션이 쥐고 있는지와 무관하게 항상 나타나며, 클릭하면 `/cr clean`을
  보낼 수 있습니다.
- **스냅샷** — 개수를 보여주고, 각 스냅샷 행은 전체 경로 대신 디렉터리
  이름을 라벨로 써 읽기 쉽습니다(전체 경로는 description·tooltip에
  남습니다). **행을 클릭하면 그 스냅샷 폴더가 OS 파일 탐색기로 바로
  열립니다.** 우클릭하면 **폴더 열기**·**경로 복사**가 뜹니다. 스냅샷이
  하나 이상 있을 때만 그룹 행에 전체 폴더 열기 버튼도 나타납니다.
- **경고** — `index.lock` 등 git 자체 lock, 진행 중인 rebase/merge 같은
  복구 필요 상태.

git 저장소가 아닌 폴더를 열면 잠금·스냅샷·경고 그룹은 숨기고 설치 관리
기능만 유지합니다.

### 우클릭 메뉴

`설치` 행의 인라인 버튼(`[설치]`/`[업그레이드]`/`[재설치]`/`[검증]`/`[제거]`)과
`잠금` 행의 `[해제(clean)]`은 **우클릭 메뉴에도 똑같이 나타납니다** — 버튼
아이콘이 좁아 잘 안 보이거나, 트리 항목에 포커스가 없어 인라인 버튼이 숨어
있을 때도 우클릭으로 같은 동작을 실행할 수 있습니다. 복사할 값이 없는
항목(경과 시간 행 등)에는 값 복사 메뉴 자체가 뜨지 않습니다.

## 설정

| 키 | 기본값 | 설명 |
|---|---|---|
| `commitforge.pythonPath` | `""` (자동 탐색) | Python 인터프리터 경로. 비우면 `python3`, `python` 순으로 찾습니다. |
| `commitforge.terminal.name` | `CommitForge` | 확장이 만드는 터미널 이름 |
| `commitforge.terminal.launchCommand` | `claude` | 새 터미널에서 실행할 명령 |
| `commitforge.statusBar.enabled` | `true` | 상태바 표시 여부 |
| `commitforge.confirmBeforeSend` | `true` | 터미널로 보내기 전 명령을 확인합니다 |

## 개발

```bash
npm install
npm test          # 단위 테스트 (pretest가 sync-payload를 먼저 실행)
npm run typecheck
npm run build     # 버전 동기화 → 페이로드 동기화 → esbuild 번들
npm run package   # commitforge.vsix 생성
```

F5를 누르면 Extension Development Host가 뜹니다. `src/core/`는 VS Code
API에 의존하지 않는 순수 로직이라 `vitest`로 빠르게 검증하고, `src/vscode/`의
UI 배선은 자동 E2E 대신 `../MANUAL-TEST-CHECKLIST.md`의 「에디터 확장」
섹션으로 수동 확인합니다.
