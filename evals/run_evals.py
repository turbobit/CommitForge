#!/usr/bin/env python3
"""Validate eval contracts or run live Claude Code /cr scenarios."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "evals/live-review-scenarios.json"
TRIGGERS = ROOT / ".claude/skills/_git-atomic-core/scripts/reviewer_triggers.py"


def run(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 180,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def load_classifier_module():
    spec = importlib.util.spec_from_file_location("reviewer_triggers", TRIGGERS)
    if spec is None or spec.loader is None:
        raise RuntimeError("trigger classifier를 불러올 수 없습니다")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_scenarios() -> list[dict]:
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    required = {
        "name",
        "base_files",
        "changed_files",
        "prompt",
        "expected_terms",
        "expected_reviewers",
    }
    for index, scenario in enumerate(scenarios):
        missing = required - set(scenario)
        if missing:
            raise ValueError(f"scenario {index} 필드 누락: {sorted(missing)}")
        if not scenario["prompt"].startswith("/cr") or "--no-fix" not in scenario["prompt"]:
            raise ValueError(f"scenario {index}: live eval은 /cr --no-fix만 허용")
        for change_index, change in enumerate(scenario.get("committed_changes", [])):
            if not isinstance(change.get("message"), str) or not isinstance(
                change.get("files"), dict
            ):
                raise ValueError(
                    f"scenario {index} committed change {change_index} 형식 오류"
                )
    return scenarios


def contract_check(scenarios: list[dict]) -> None:
    classifier = load_classifier_module()
    for scenario in scenarios:
        committed_paths = {
            path
            for change in scenario.get("committed_changes", [])
            for path in change["files"]
        }
        paths = sorted(
            set(scenario["base_files"])
            | set(scenario["changed_files"])
            | committed_paths
        )
        active = classifier.classify(paths, scenario["prompt"])["active"]
        conditional = [
            reviewer
            for reviewer in scenario["expected_reviewers"]
            if reviewer in classifier.RULES
        ]
        missing = sorted(set(conditional) - set(active))
        if missing:
            raise ValueError(
                f"{scenario['name']}: trigger classifier 누락 {missing}"
            )


def write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def live_case(scenario: dict, command: list[str], keep_temp: bool) -> dict:
    temp_path = Path(tempfile.mkdtemp(prefix="commitforge-live-eval-"))
    try:
        run(["git", "init"], temp_path)
        run(["git", "config", "user.name", "CommitForge Eval"], temp_path)
        run(["git", "config", "user.email", "eval@example.invalid"], temp_path)
        installed = run(
            [
                os.environ.get("PYTHON", "python3"),
                str(ROOT / "install.py"),
                "--scope",
                "project",
                "--target",
                str(temp_path),
            ],
            ROOT,
        )
        if installed.returncode != 0:
            raise RuntimeError(installed.stderr)

        write_files(temp_path, scenario["base_files"])
        run(["git", "add", "."], temp_path)
        old_commit_env = dict(os.environ)
        old_commit_env.update(
            {
                "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
                "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
            }
        )
        committed = run(
            ["git", "commit", "-m", "test: base"],
            temp_path,
            env=old_commit_env,
        )
        if committed.returncode != 0:
            raise RuntimeError(committed.stderr)

        for change in scenario.get("committed_changes", []):
            write_files(temp_path, change["files"])
            run(["git", "add", "."], temp_path)
            committed = run(
                ["git", "commit", "-m", change["message"]],
                temp_path,
            )
            if committed.returncode != 0:
                raise RuntimeError(committed.stderr)
        write_files(temp_path, scenario["changed_files"])

        start_head = run(["git", "rev-parse", "HEAD"], temp_path).stdout.strip()
        start_index = run(["git", "diff", "--cached", "--binary"], temp_path).stdout
        result = run([*command, scenario["prompt"]], temp_path, timeout=300)
        output = result.stdout + "\n" + result.stderr
        if result.returncode != 0:
            raise RuntimeError(
                f"{scenario['name']}: live command 실패 {result.returncode}\n{output}"
            )

        lowered = output.lower()
        missing_terms = [
            group
            for group in scenario["expected_terms"]
            if not any(term.lower() in lowered for term in group)
        ]
        end_head = run(["git", "rev-parse", "HEAD"], temp_path).stdout.strip()
        end_index = run(["git", "diff", "--cached", "--binary"], temp_path).stdout
        if start_head != end_head or start_index != end_index:
            raise RuntimeError(f"{scenario['name']}: /cr HEAD/index 불변 위반")
        if missing_terms:
            raise RuntimeError(
                f"{scenario['name']}: 기대 개념 누락 {missing_terms}\n{output}"
            )
        return {"name": scenario["name"], "ok": True}
    finally:
        if keep_temp:
            print(json.dumps({"kept": str(temp_path)}, ensure_ascii=False))
        else:
            shutil.rmtree(temp_path, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--command",
        default=os.environ.get(
            "COMMITFORGE_EVAL_COMMAND",
            (
                "claude -p --model sonnet --permission-mode dontAsk "
                "--max-budget-usd 5 --no-session-persistence"
            ),
        ),
    )
    parser.add_argument("--scenario")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.live:
        parser.error("--check 또는 --live가 필요합니다")

    scenarios = load_scenarios()
    if args.scenario:
        scenarios = [item for item in scenarios if item["name"] == args.scenario]
        if not scenarios:
            raise SystemExit(f"scenario를 찾을 수 없습니다: {args.scenario}")
    contract_check(scenarios)

    results = []
    if args.live:
        command = shlex.split(args.command)
        if not command:
            raise SystemExit("live command가 비어 있습니다")
        for scenario in scenarios:
            results.append(live_case(scenario, command, args.keep_temp))

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "live" if args.live else "check",
                "scenarios": len(scenarios),
                "results": results,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
