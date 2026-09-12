import { findOption, type CommandOption, type CommandSpec } from "./catalog";

export interface SelectedOption {
  name: string;
  value?: string;
}

export interface Selection {
  mode?: string;
  freeText?: string;
  options: SelectedOption[];
}

/** working tree나 Git history를 바꾸는 명령. 전송 전 lock 확인이 필요하다. */
export const WRITE_COMMANDS: readonly string[] = ["cc", "cf", "ccf", "cca", "cp"];

export function isWriteCommand(name: string): boolean {
  return WRITE_COMMANDS.includes(name);
}

/** sendText에서 개행은 Enter다. 명령이 절반만 전송되는 것을 막는다. */
export function sanitizeFreeText(input: string): string {
  return input.replace(/[\r\n]+/g, " ").replace(/\s+/g, " ").trim();
}

// 브랜치명·경로·ref·semver가 전부 여기 들어간다. 이 집합 밖의 문자가 하나라도
// 있으면 감싼다.
const SAFE_UNQUOTED = /^[A-Za-z0-9_.\-/:=@+,]+$/;

function quote(value: string): string {
  // 화이트리스트: 안전하다고 알려진 문자로만 이루어진 값만 그대로 둔다.
  // 이전에는 공백·큰따옴표·백슬래시가 있을 때만 감싸는 블랙리스트였는데,
  // 한 글자(홑따옴표)를 빠뜨려 조용히 깨졌다 — /cr의 PreToolUse
  // hook(cr_edit_gate.py)이 터미널로 전송된 원문 인자를 Python
  // shlex.split()으로 재파싱하고, 감싸지 않은 홑따옴표는
  // "닫는 따옴표 없음" 오류를 내 --fix 인식 자체가 실패한다. 블랙리스트는
  // 앞으로도 같은 종류의 구멍을 계속 만들 수 있으므로 화이트리스트로 뒤집는다.
  if (SAFE_UNQUOTED.test(value)) return value;
  // 감쌀 때는 백슬래시와 큰따옴표를 이스케이프해 따옴표 구조가 깨지지 않게
  // 한다. 홑따옴표는 큰따옴표로 감싸면 이스케이프 없이도 안전하다(shlex와
  // POSIX 쉘 이중따옴표 규칙 모두에서).
  const escaped = value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `"${escaped}"`;
}

function validateValue(option: CommandOption, selected: SelectedOption): void {
  if (option.kind === "flag") {
    if (selected.value !== undefined) {
      throw new Error(`${option.name} 은 값을 받지 않습니다`);
    }
    return;
  }

  const value = selected.value?.trim();
  if (!value) throw new Error(`${option.name} 에 값이 필요합니다`);

  // 자유 텍스트(freeText)의 개행은 서식이라 공백으로 바꾸지만, 옵션 값의
  // 개행은 입력이 잘못됐다는 뜻이다. sendText에서 개행은 Enter이므로
  // 공백으로 조용히 바꾸면 엉뚱한 값이 전송된다 — 전송 전에 막는다.
  if (/[\r\n]/.test(value)) {
    throw new Error(`${option.name} 값에 개행을 넣을 수 없습니다`);
  }

  if (option.kind === "enum" && !option.values?.includes(value)) {
    throw new Error(
      `${option.name} 값 "${value}" 은 허용되지 않습니다. 가능한 값: ${option.values?.join(", ")}`,
    );
  }

  if (option.kind === "range") {
    const [min, max] = option.range ?? [0, 0];
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) {
      throw new Error(`${option.name} 은 정수여야 합니다`);
    }
    if (parsed < min || parsed > max) {
      throw new Error(`${option.name} 은 ${min}-${max} 범위여야 합니다`);
    }
  }
}

export function compose(spec: CommandSpec, selection: Selection): string {
  const parts = [`/${spec.name}`];

  if (selection.mode !== undefined) {
    if (!spec.modes.includes(selection.mode)) {
      throw new Error(`/${spec.name} 에 없는 모드입니다: ${selection.mode}`);
    }
    parts.push(selection.mode);
  }

  if (selection.freeText) {
    const text = sanitizeFreeText(selection.freeText);
    if (text) parts.push(text);
  }

  const chosen = new Set(selection.options.map((option) => option.name));
  for (const selected of selection.options) {
    const option = findOption(spec, selected.name);
    if (!option) throw new Error(`/${spec.name} 에 없는 옵션입니다: ${selected.name}`);
    if (option.exclusiveWith && chosen.has(option.exclusiveWith)) {
      throw new Error(`${option.name} 과 ${option.exclusiveWith} 는 함께 쓸 수 없습니다`);
    }
    validateValue(option, selected);
  }

  // spec 정의 순서로 정렬해 같은 선택이 항상 같은 문자열이 되게 한다.
  const order = new Map(spec.options.map((option, index) => [option.name, index]));
  const sorted = [...selection.options].sort(
    (a, b) => (order.get(a.name) ?? 0) - (order.get(b.name) ?? 0),
  );

  for (const selected of sorted) {
    parts.push(selected.name);
    if (selected.value !== undefined) parts.push(quote(selected.value.trim()));
  }

  return parts.join(" ");
}
