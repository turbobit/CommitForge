#!/usr/bin/env python3
"""Static package verifier."""

from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REQUIRED = [
    ".claude/skills/cc/SKILL.md",
    ".claude/skills/ccr/SKILL.md",
    ".claude/skills/cca/SKILL.md",
    ".claude/skills/_git-atomic-core/scripts/guard.py",
    ".claude/skills/_git-atomic-core/scripts/guard.sh",
    ".claude/agents/cca-git-reviewer.md",
    ".claude/agents/cca-correctness-reviewer.md",
    ".claude/agents/cca-security-reviewer.md",
    ".claude/agents/cca-performance-reviewer.md",
    ".claude/agents/cca-testing-reviewer.md",
]


def frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise ValueError("YAML frontmatter 시작 누락")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("YAML frontmatter 종료 누락")
    return text[4:end]


def main() -> None:
    errors = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"필수 파일 누락: {rel}")

    for command in ("cc", "ccr", "cca"):
        path = ROOT / f".claude/skills/{command}/SKILL.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        try:
            fm = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        for field in ("description:", "disable-model-invocation: true", "argument-hint:"):
            if field not in fm:
                errors.append(f"{path}: frontmatter 필드 누락 {field}")
        if len(text.splitlines()) > 500:
            errors.append(f"{path}: SKILL.md 500줄 초과")

    guard = ROOT / ".claude/skills/_git-atomic-core/scripts/guard.py"
    if guard.exists():
        proc = subprocess.run(
            [sys.executable, str(guard), "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(f"guard.py --help 실패: {proc.stderr}")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "required_files": len(REQUIRED)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
