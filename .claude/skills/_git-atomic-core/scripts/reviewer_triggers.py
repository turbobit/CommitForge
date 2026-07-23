#!/usr/bin/env python3
"""Return a conservative minimum set of conditional CommitForge reviewers."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable


RULES: dict[str, tuple[str, ...]] = {
    "cca-data-migration-reviewer": (
        r"(^|/)(migrations?|schema|prisma)(/|$)",
        r"\.(sql|ddl)$",
        r"(^|/)(models?|entities)/",
        r"(backfill|data[-_]?migration)",
    ),
    "cca-dependency-supply-chain-reviewer": (
        r"(^|/)(package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml)$",
        r"(^|/)(requirements.*\.txt|pyproject\.toml|poetry\.lock)$",
        r"(^|/)(cargo\.(toml|lock)|go\.(mod|sum)|pubspec\.lock)$",
        r"(^|/)(dockerfile|compose.*\.ya?ml)$",
        r"(^|/)\.github/workflows/",
    ),
    "cca-reliability-recovery-reviewer": (
        r"(^|/)(queues?|jobs?|workers?|consumers?|schedulers?)(/|$)",
        r"(retry|backoff|circuit[-_]?breaker|dead[-_]?letter|dlq)",
        r"(failover|leader[-_]?election|distributed[-_]?lock)",
        r"(graceful[-_]?shutdown|readiness|liveness)",
    ),
    "cca-privacy-governance-reviewer": (
        r"(analytics|tracking|telemetry|consent|privacy)",
        r"(retention|data[-_]?deletion|data[-_]?export)",
        r"(personal[-_]?data|pii|pseudonym|anonym)",
    ),
    "cca-requirements-product-reviewer": (
        r"(^|/)(adr|requirements?|specs?|acceptance)(/|[-_.])",
        r"(^|/)(tickets?|stories)/",
        r"(acceptance[-_ ]criteria|user[-_ ]story)",
    ),
}


def classify(paths: Iterable[str], context: str = "") -> dict[str, object]:
    haystacks = [path.replace("\\", "/").lower() for path in paths]
    if context:
        haystacks.append(context.lower())

    evidence: dict[str, list[str]] = {}
    for reviewer, patterns in RULES.items():
        matches: list[str] = []
        for value in haystacks:
            if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
                matches.append(value)
        if matches:
            evidence[reviewer] = sorted(set(matches))

    return {
        "active": sorted(evidence),
        "evidence": evidence,
        "policy": "minimum-floor-main-agent-may-add-semantic-triggers",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--context", default="")
    args = parser.parse_args()
    print(json.dumps(classify(args.paths, args.context), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
