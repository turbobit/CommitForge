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

function quote(value: string): string {
  if (!/[\s"]/.test(value)) return value;
  // 감쌀 때는 백슬래시와 큰따옴표를 이스케이프해 따옴표 구조가 깨지지 않게 한다.
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
