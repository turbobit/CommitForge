import { describe, expect, it } from "vitest";
import { decideTerminal } from "../src/vscode/terminal";

describe("decideTerminal", () => {
  it("기억해 둔 터미널이 아직 열려 있으면 그것을 재사용한다", () => {
    expect(decideTerminal(["CommitForge", "bash"], "CommitForge", "CommitForge")).toEqual({
      kind: "reuse",
      name: "CommitForge",
    });
  });

  it("기억해 둔 터미널이 닫혔지만 확장 이름의 터미널이 남아 있으면 그것을 쓴다", () => {
    expect(decideTerminal(["CommitForge"], "다른이름", "CommitForge")).toEqual({
      kind: "reuse",
      name: "CommitForge",
    });
  });

  it("열린 터미널이 하나도 없으면 새로 만든다", () => {
    expect(decideTerminal([], undefined, "CommitForge")).toEqual({ kind: "create" });
  });

  it("열린 터미널이 있지만 확장 것도 기억한 것도 아니면 사용자에게 묻는다", () => {
    expect(decideTerminal(["bash", "zsh"], undefined, "CommitForge")).toEqual({ kind: "ask" });
  });

  it("기억해 둔 이름이 있어도 이미 열린 터미널 목록에 없으면 재사용하지 않는다", () => {
    expect(decideTerminal(["bash"], "닫힌터미널", "CommitForge")).toEqual({ kind: "ask" });
  });
});
