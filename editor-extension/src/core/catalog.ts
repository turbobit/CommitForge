import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { COMMAND_NAMES } from "./payload";

export type OptionKind = "flag" | "value" | "enum" | "range";

export interface CommandOption {
  name: string;
  kind: OptionKind;
  values?: string[];
  placeholder?: string;
  range?: [number, number];
  exclusiveWith?: string;
}

export interface CommandSpec {
  name: string;
  description: string;
  modes: string[];
  acceptsFreeText: boolean;
  options: CommandOption[];
}

const FREE_TEXT_TOKEN = "추가 맥락";
const RANGE_PATTERN = /^(\d+)-(\d+)$/;

/** "[...]" 단위로 쪼갠다. 중첩 대괄호는 argument-hint 문법에 없다. */
function bracketGroups(hint: string): string[] {
  return Array.from(hint.matchAll(/\[([^\]]*)\]/g), (m) => (m[1] ?? "").trim());
}

/**
 * `sep` 기준으로 쪼개되 `<...>` 안의 `sep`는 무시한다.
 * "--timezone <IANA|±HH:MM>" 같은 자리표시자 내부 파이프가 분할되지 않게 한다.
 */
function splitTopLevel(text: string, sep: string): string[] {
  const parts: string[] = [];
  let current = "";
  let insidePlaceholder = false;

  for (const ch of text) {
    if (ch === "<") insidePlaceholder = true;
    else if (ch === ">") insidePlaceholder = false;

    if (ch === sep && !insidePlaceholder) {
      parts.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts;
}

/** "--name", "--name <ph>", "--name 20-500", "--name a|b|c" 형태의 옵션 하나를 읽는다. */
function parseSingleOption(segment: string): CommandOption {
  const parts = segment.split(/\s+/);
  const head = parts[0] ?? "";

  // "--strict" — 불리언
  if (parts.length === 1) return { name: head, kind: "flag" };

  const rest = parts.slice(1).join(" ");

  // "--base <ref>" — 자유 입력 값
  if (rest.startsWith("<")) return { name: head, kind: "value", placeholder: rest };

  // "--commits 20-500" — 수치 범위
  const range = RANGE_PATTERN.exec(rest);
  if (range) {
    const min = range[1] ?? "0";
    const max = range[2] ?? "0";
    return { name: head, kind: "range", range: [Number(min), Number(max)] };
  }

  // "--format human|json|sarif" — 열거형
  return { name: head, kind: "enum", values: rest.split("|").map((s) => s.trim()).filter(Boolean) };
}

function parseGroup(group: string): CommandOption[] | { mode: string[] } | null {
  if (group === FREE_TEXT_TOKEN) return null;

  if (!group.startsWith("--")) {
    // "[clean|today|weekly]" 또는 "[clean]" — 모드 목록
    return { mode: group.split("|").map((s) => s.trim()).filter(Boolean) };
  }

  // 꺾쇠 밖의 "|"로 나눈다. 조각이 둘 이상이고 전부 "--"로 시작하면 배타 옵션 그룹이다.
  // ("--base <ref>|--range <A..B>", "--team|--no-team"). 그렇지 않으면
  // ("--format human|json|sarif" 처럼) 열거형 등 기존 문법으로 내려간다.
  const segments = splitTopLevel(group, "|");
  if (segments.length >= 2 && segments.every((seg) => seg.trim().startsWith("--"))) {
    const options = segments.map((seg) => parseSingleOption(seg.trim()));
    if (options.length === 2) {
      const [first, second] = options;
      if (first && second) {
        first.exclusiveWith = second.name;
        second.exclusiveWith = first.name;
      }
    }
    // 조각이 3개 이상이면 옵션은 모두 만들되 배타 관계는 표시하지 않는다.
    // (배타 힌트 없음이 옵션 소실보다 낫다.)
    return options;
  }

  return [parseSingleOption(group)];
}

export function parseArgumentHint(hint: string): Omit<CommandSpec, "name" | "description"> {
  const modes: string[] = [];
  const options: CommandOption[] = [];
  let acceptsFreeText = false;

  for (const group of bracketGroups(hint)) {
    if (group === FREE_TEXT_TOKEN) {
      acceptsFreeText = true;
      continue;
    }
    const parsed = parseGroup(group);
    if (parsed === null) continue;
    if (Array.isArray(parsed)) options.push(...parsed);
    else modes.push(...parsed.mode);
  }
  return { modes, acceptsFreeText, options };
}

function frontmatter(text: string): string {
  if (!text.startsWith("---\n")) throw new Error("SKILL.md frontmatter가 없습니다");
  const end = text.indexOf("\n---", 4);
  if (end < 0) throw new Error("SKILL.md frontmatter 종료가 없습니다");
  return text.slice(4, end);
}

/** YAML 파서를 들이지 않는다. 필요한 두 스칼라 필드만 읽는다. */
function scalarField(fm: string, key: string): string | null {
  const match = new RegExp(`^${key}:\\s*(.*)$`, "m").exec(fm);
  if (!match) return null;
  let value = (match[1] ?? "").trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  return value;
}

function firstSentence(text: string): string {
  const trimmed = text.replace(/\s+/g, " ").trim();
  const stop = trimmed.search(/[.。]\s/);
  return stop < 0 ? trimmed : trimmed.slice(0, stop + 1);
}

export function parseSkillFile(text: string, name: string): CommandSpec {
  const fm = frontmatter(text);
  const hint = scalarField(fm, "argument-hint");
  const parsed = hint
    ? parseArgumentHint(hint)
    : { modes: [], acceptsFreeText: false, options: [] };

  return {
    name,
    description: firstSentence(scalarField(fm, "description") ?? ""),
    ...parsed,
  };
}

export async function loadCatalog(skillsDir: string): Promise<CommandSpec[]> {
  const specs: CommandSpec[] = [];
  for (const name of COMMAND_NAMES) {
    try {
      const text = await readFile(join(skillsDir, name, "SKILL.md"), "utf8");
      specs.push(parseSkillFile(text, name));
    } catch {
      // 설치가 불완전하면 해당 명령만 빠진다. 나머지는 계속 제공한다.
    }
  }
  return specs;
}

export function findOption(spec: CommandSpec, name: string): CommandOption | undefined {
  return spec.options.find((option) => option.name === name);
}
