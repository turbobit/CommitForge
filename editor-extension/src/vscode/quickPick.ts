import * as vscode from "vscode";
import type { CommandOption, CommandSpec } from "../core/catalog";
import { compose, isWriteCommand, type SelectedOption } from "../core/composer";
import type { GuardStatus } from "../core/guard";
import type { StateStore } from "../state";
import { resolveTarget, sendCommand } from "./terminal";

const RECENT_KEY = "commitforge.recentCommands";
const RECENT_MAX = 5;

/**
 * 모드별 관련 옵션 힌트(spec §6.1). `/cca`는 옵션이 31개인데 모드별로
 * 관련성이 갈리지만 `argument-hint`는 이 조건부 관계를 담지 않는다.
 *
 * 이 표는 **정렬과 그룹 헤더에만** 쓰고 필터로 쓰지 않는다. 힌트에 없는
 * 옵션은 "기타" 그룹에 그대로 나타난다 — CommitForge에 새 옵션이 생겨도
 * 숨겨지지 않고, 이 표가 낡아도 정렬만 어색해질 뿐 기능은 유지된다.
 */
export const MODE_GROUPS: Record<string, string[]> = {
  release: [
    "--target",
    "--bump",
    "--channel",
    "--package",
    "--tag-prefix",
    "--from",
    "--prepare",
    "--tag",
    "--dry-run",
  ],
  emergency: ["--incident", "--severity", "--diagnose", "--rollback-first"],
  today: ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
  "3days": ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
  weekly: ["--since", "--branches", "--exclude-bots", "--commits", "--all-authors", "--week-start", "--timezone"],
};

export interface OptionGroup {
  label: string;
  options: CommandOption[];
}

/**
 * 힌트 표를 정렬·그룹 헤더로만 쓴다. 관련 옵션을 먼저 두고, 힌트에 없는
 * 옵션은 전부 "기타"(또는 모드가 없거나 힌트가 없으면 "옵션") 그룹에 그대로
 * 남긴다 — 옵션이 사라지는 경로가 없다.
 */
export function groupOptionsByMode(
  spec: Pick<CommandSpec, "options">,
  mode: string | undefined,
): OptionGroup[] {
  const preferredNames = mode ? MODE_GROUPS[mode] : undefined;
  if (!preferredNames || preferredNames.length === 0) {
    return spec.options.length > 0 ? [{ label: "옵션", options: spec.options }] : [];
  }

  const preferred = new Set(preferredNames);
  const related = spec.options.filter((option) => preferred.has(option.name));
  const rest = spec.options.filter((option) => !preferred.has(option.name));

  const groups: OptionGroup[] = [];
  if (related.length > 0) groups.push({ label: `${mode} 관련`, options: related });
  if (rest.length > 0) groups.push({ label: related.length > 0 ? "기타" : "옵션", options: rest });
  return groups;
}

/** 최근 실행 목록 맨 앞에 command를 두고 중복을 없앤 뒤 max개로 자른다. */
export function pushRecent(recent: readonly string[], command: string, max = RECENT_MAX): string[] {
  return [command, ...recent.filter((item) => item !== command)].slice(0, max);
}

function humanAge(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
  return `${Math.floor(seconds / 3600)}시간`;
}

/**
 * 쓰기 명령이 다른 세션이 쥔 lock과 충돌할 수 있으면 경고 문구를 만든다.
 * 순수 함수 — 전송 여부 판단은 호출자(runCommandFlow)가 한다(spec §6.4).
 */
export function lockWarning(guard: GuardStatus | null, command: string): string | null {
  if (!guard?.lockOwner) return null;
  if (!isWriteCommand(command)) return null;

  const session = guard.lockOwner.session ?? "알 수 없음";
  const age = humanAge(guard.lockAgeSeconds ?? 0);
  const host = guard.lockOwnerHostname ?? "알 수 없는 호스트";

  return `다른 세션이 lock을 보유 중입니다: session ${session} · ${age} 경과 · ${host}`;
}

/**
 * 카탈로그에서 이름으로 CommandSpec을 찾는다. SCM 패널 단축 버튼(spec 요청 1)의
 * 핵심 규칙을 담는다: 단축 버튼은 하드코딩된 명령 문자열을 보내지 않고, 항상
 * 실행 시점의 `WorkspaceState.catalog`(SKILL.md의 argument-hint에서 생성됨)에서
 * 찾아야 한다. 카탈로그에 없으면(미설치이거나 upstream에서 이름이 바뀌었으면)
 * `undefined`를 반환해 호출자가 "엉뚱한 문자열을 보내지 않고" 사용자에게
 * 알리게 한다.
 */
export function resolveShortcutSpec(
  catalog: readonly CommandSpec[],
  name: string,
): CommandSpec | undefined {
  return catalog.find((spec) => spec.name === name);
}

/**
 * lock 경고 모달의 답에 따라 무엇을 보낼지, 최근 목록에 남길지 정한다.
 *
 * "clean 실행"은 사용자가 카탈로그에서 고른 명령이 아니라 lock 충돌을
 * 피하려는 보조 동작이다 — 트리 `[해제(clean)]` 버튼(runCleanLock)이 같은
 * `/cr clean`을 `remember:false`로 보내는 것과 정확히 같은 상황이므로 같은
 * 정책을 따른다. 예전에는 이 경로만 `remember:true`로 흘러 "카탈로그에서
 * 고른 게 아닌 보조 명령은 남기지 않는다"는 정책과 모순됐다. "그래도
 * 보내기"는 사용자가 원래 고른 명령을 그대로 보내는 것이므로 기존
 * `remember:true`를 유지한다.
 */
export function resolveWarningAnswer(
  answer: string | undefined,
  originalCommand: string,
): { command: string; remember: boolean } | undefined {
  if (answer === "clean 실행") return { command: "/cr clean", remember: false };
  if (answer === "그래도 보내기") return { command: originalCommand, remember: true };
  return undefined;
}

function optionDetail(option: CommandOption): string {
  switch (option.kind) {
    case "flag":
      return option.exclusiveWith ? `${option.exclusiveWith} 와 배타` : "플래그";
    case "value":
      return `값 필요 ${option.placeholder ?? ""}`.trim();
    case "enum":
      return `값: ${option.values?.join(", ") ?? ""}`;
    case "range":
      return `${option.range?.[0] ?? 0}-${option.range?.[1] ?? 0} 범위의 정수`;
  }
}

async function askValue(option: CommandOption): Promise<string | undefined> {
  if (option.kind === "enum") {
    return vscode.window.showQuickPick(option.values ?? [], {
      placeHolder: `${option.name} 값`,
    });
  }
  return vscode.window.showInputBox({
    prompt: `${option.name} 값`,
    placeHolder: option.kind === "range" ? `${option.range?.[0]}-${option.range?.[1]}` : option.placeholder,
    ignoreFocusOut: true,
  });
}

interface OptionPickItem extends vscode.QuickPickItem {
  option?: CommandOption;
}

async function buildWithOptions(spec: CommandSpec): Promise<string | undefined> {
  let mode: string | undefined;
  if (spec.modes.length > 0) {
    const picked = await vscode.window.showQuickPick(
      [{ label: "(모드 없음)" }, ...spec.modes.map((m) => ({ label: m }))],
      { placeHolder: `/${spec.name} 모드` },
    );
    if (!picked) return undefined;
    if (picked.label !== "(모드 없음)") mode = picked.label;
  }

  const items: OptionPickItem[] = [];
  for (const group of groupOptionsByMode(spec, mode)) {
    items.push({ label: group.label, kind: vscode.QuickPickItemKind.Separator });
    items.push(
      ...group.options.map((option) => ({
        label: option.name,
        detail: optionDetail(option),
        option,
      })),
    );
  }

  const chosen = await vscode.window.showQuickPick(items, {
    placeHolder: `/${spec.name} 옵션 (여러 개 선택 가능)`,
    canPickMany: true,
  });
  if (!chosen) return undefined;

  const options: SelectedOption[] = [];
  for (const item of chosen) {
    if (!item.option) continue; // 그룹 헤더(Separator)는 선택 대상이 아니다
    if (item.option.kind === "flag") {
      options.push({ name: item.option.name });
      continue;
    }
    const value = await askValue(item.option);
    if (value === undefined) return undefined;
    options.push({ name: item.option.name, value });
  }

  let freeText: string | undefined;
  if (spec.acceptsFreeText) {
    freeText = await vscode.window.showInputBox({
      prompt: "추가 맥락 (선택)",
      ignoreFocusOut: true,
    });
    if (freeText === undefined) return undefined;
  }

  try {
    return compose(spec, { mode, freeText, options });
  } catch (error) {
    void vscode.window.showErrorMessage(
      error instanceof Error ? error.message : String(error),
    );
    return undefined;
  }
}

/**
 * 전송 정책(spec §6.2·§6.3): 미리보기 확인 → 대상 터미널 확정 → 전송 →
 * 전송 직후 상태 갱신(spec §7.1). `remember`가 참이면 최근 목록에 남긴다 —
 * `/cr clean`처럼 사용자가 카탈로그에서 고른 게 아닌 보조 명령은 남기지
 * 않는다.
 */
async function sendToTerminal(
  store: StateStore,
  context: vscode.ExtensionContext,
  command: string,
  remember: boolean,
): Promise<void> {
  const confirm = vscode.workspace
    .getConfiguration("commitforge")
    .get<boolean>("confirmBeforeSend", true);
  if (confirm) {
    const answer = await vscode.window.showInformationMessage(
      `터미널로 보냅니다: ${command}`,
      { modal: true },
      "보내기",
    );
    if (answer !== "보내기") return;
  }

  const terminal = await resolveTarget(context);
  if (!terminal) return;

  sendCommand(terminal, command);

  if (remember) {
    const recent = context.workspaceState.get<string[]>(RECENT_KEY, []);
    await context.workspaceState.update(RECENT_KEY, pushRecent(recent, command));
  }

  // spec §7.1: 명령 전송 직후 갱신한다. lock 상태가 반영되기까지 약간의
  // 시간이 걸리므로 1초 뒤로 미룬다 — 반복 폴링이 아니라 이 시점 한 번뿐이다.
  setTimeout(() => void store.refresh(), 1000);
}

/**
 * lock 경고 → 확인 → 전송의 공유 로직(spec §6.3·§6.4). `runCommandFlow`(전체
 * QuickPick)와 `runShortcut`(SCM 패널 단축 버튼) 둘 다 명령 문자열을 조립한
 * 뒤에는 이 함수 하나로 수렴한다 — 단축 버튼이라고 lock 사전 경고나 전송 전
 * 확인(`commitforge.confirmBeforeSend`)을 건너뛰지 않는다.
 */
async function sendResolvedCommand(
  store: StateStore,
  context: vscode.ExtensionContext,
  commandName: string,
  command: string,
): Promise<void> {
  const warning = lockWarning(store.current?.guard ?? null, commandName);
  if (warning) {
    const answer = await vscode.window.showWarningMessage(
      warning,
      { modal: true, detail: "그래도 보내면 Claude가 거부할 수 있습니다." },
      "그래도 보내기",
      "clean 실행",
    );
    const resolved = resolveWarningAnswer(answer, command);
    if (!resolved) return;
    await sendToTerminal(store, context, resolved.command, resolved.remember);
    return;
  }

  await sendToTerminal(store, context, command, true);
}

/**
 * SCM 패널 단축 버튼(`commitforge.send.*`)의 공유 핸들러. 버튼마다 명령은
 * 다르지만 로직은 한 벌뿐이다 — `handleInstall`이 install/upgrade/reinstall
 * 셋에 공유되는 것과 같은 패턴이다.
 *
 * 옵션 없이 바로 전송한다(QuickPick에서 Enter를 누른 것과 같은 동작). 모드나
 * 옵션이 필요하면 사용자는 여전히 `commitforge.run`(전체 QuickPick)의 톱니(⚙)
 * 경로를 쓸 수 있다.
 */
export async function runShortcut(
  store: StateStore,
  context: vscode.ExtensionContext,
  name: string,
): Promise<void> {
  const state = store.current;
  if (!state) return;

  const spec = resolveShortcutSpec(state.catalog, name);
  if (!spec) {
    void vscode.window.showWarningMessage(
      `/${name} 명령을 카탈로그에서 찾지 못했습니다. CommitForge가 설치돼 있는지, 명령 이름이 바뀌지 않았는지 확인하십시오.`,
    );
    return;
  }

  await sendResolvedCommand(store, context, spec.name, `/${spec.name}`);
}

export async function runCommandFlow(
  store: StateStore,
  context: vscode.ExtensionContext,
): Promise<void> {
  const state = store.current;
  if (!state) return;

  if (state.catalog.length === 0) {
    void vscode.window.showWarningMessage(
      "CommitForge 명령을 찾지 못했습니다. 먼저 설치하십시오.",
    );
    return;
  }

  const recent = context.workspaceState.get<string[]>(RECENT_KEY, []);
  const items: Array<vscode.QuickPickItem & { spec?: CommandSpec; literal?: string }> = [
    ...state.catalog.map((spec) => ({
      label: `/${spec.name}`,
      description: spec.description,
      buttons: [{ iconPath: new vscode.ThemeIcon("gear"), tooltip: "옵션 지정" }],
      spec,
    })),
  ];
  if (recent.length > 0) {
    items.push({ label: "최근", kind: vscode.QuickPickItemKind.Separator });
    items.push(...recent.map((literal) => ({ label: literal, literal })));
  }

  const picked = await new Promise<
    { item: (typeof items)[number]; withOptions: boolean } | undefined
  >((resolve) => {
    const quickPick = vscode.window.createQuickPick<(typeof items)[number]>();
    quickPick.items = items;
    quickPick.placeholder = "실행할 CommitForge 명령";
    quickPick.onDidTriggerItemButton((event) => {
      resolve({ item: event.item, withOptions: true });
      quickPick.hide();
    });
    quickPick.onDidAccept(() => {
      const selected = quickPick.selectedItems[0];
      resolve(selected ? { item: selected, withOptions: false } : undefined);
      quickPick.hide();
    });
    quickPick.onDidHide(() => {
      resolve(undefined);
      quickPick.dispose();
    });
    quickPick.show();
  });

  if (!picked) return;

  let command: string | undefined;
  let commandName: string;

  if (picked.item.literal) {
    command = picked.item.literal;
    commandName = command.slice(1).split(/\s/)[0] ?? "";
  } else if (picked.item.spec) {
    commandName = picked.item.spec.name;
    command = picked.withOptions
      ? await buildWithOptions(picked.item.spec)
      : `/${picked.item.spec.name}`;
  } else {
    return;
  }

  if (!command) return;

  await sendResolvedCommand(store, context, commandName, command);
}

/**
 * 트리 "잠금" 노드의 `[해제(clean)]` 버튼(spec §7.3)이 호출한다. `guard.py
 * clean`을 확장이 직접 부르지 않는다(spec §4.2) — 실행 중인 다른 Claude
 * Code 세션이 모르는 사이 lock이 사라지는 것을 막기 위해, 항상 `/cr clean`을
 * 터미널로 보낸다.
 */
export async function runCleanLock(
  store: StateStore,
  context: vscode.ExtensionContext,
): Promise<void> {
  if (!store.current) return;
  await sendToTerminal(store, context, "/cr clean", false);
}
