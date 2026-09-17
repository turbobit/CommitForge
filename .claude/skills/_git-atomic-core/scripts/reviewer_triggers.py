#!/usr/bin/env python3
"""Return a conservative minimum set of conditional CommitForge reviewers.

The result is a floor, never a ceiling: `active` is what a path or an explicit
context can prove, and the main agent adds semantic triggers on top. `inactive`
exists so the other half of the contract is machine-readable too -- a reviewer
that is not activated still has to be recorded as `N_A` with a reason, and a
lead that has to enumerate the non-matches from memory is exactly how a
perspective goes missing in silence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable


CONTEXT_SOURCE = "context"

RULES: dict[str, tuple[str, ...]] = {
    "cca-data-migration-reviewer": (
        # `schemas?` because a plural directory (`src/schemas/`) is as common as
        # the singular and was silently missed.
        r"(^|/)(migrations?|schemas?|prisma)(/|$)",
        # Schema definition files carry the storage contract even when no
        # directory name says so.
        r"\.(sql|ddl|proto|avsc)$",
        r"(^|/)(models?|entities)/",
        r"(backfill|data[-_]?migration)",
        r"(storage[-_]?format)",
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
        # Locking, staleness, crash recovery and concurrency are the same
        # failure domain. "lock" needs the lookbehind so `block`, `clock` and
        # `blocklist` do not match; the genuine compounds are listed next to it.
        r"(?<![a-z])locks?",
        r"(deadlock|unlock|relock)",
        r"(recovery|recover)",
        r"(?<![a-z])stale",
        r"(concurren|crash)",
    ),
    "cca-privacy-governance-reviewer": (
        r"(analytics|tracking|telemetry|consent|privacy)",
        r"(retention|data[-_]?deletion|data[-_]?export)",
        r"(personal[-_]?data|pii|pseudonym|anonym)",
    ),
    "cca-release-deployment-reviewer": (
        r"(^|/)version(\.|$)",
        r"(^|/)manifest\.",
        r"(^|/)checksums?\.",
        r"(^|/)install(er)?[-_.]",
        r"(release|deploy|rollback)",
        r"(feature[-_]?flag|canary|blue[-_]?green)",
        r"(^|/)\.github/workflows/",
    ),
    "cca-requirements-product-reviewer": (
        # A directory of criteria, or a criteria document -- never a source
        # file that merely happens to be called `spec.ts`. Requirements review
        # needs a written criterion to compare the implementation against.
        r"(^|/)(adr|requirements?|specs?|acceptance)/",
        r"(^|/)(adr|requirements?|specs?|acceptance)[-_.][^/]*\.(md|txt|rst|adoc)$",
        r"(^|/)(tickets?|stories)/",
        r"(acceptance[-_ ]criteria|user[-_ ]story)",
    ),
}

# A haystack matching one of these is not evidence for that reviewer, even when
# a rule pattern also matches it. Lockfiles carry the word "lock" but are a
# supply-chain artifact, not a locking primitive.
EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "cca-reliability-recovery-reviewer": (
        r"(^|/)(package-lock\.json|packages\.lock\.json|yarn\.lock|pnpm-lock\.yaml)$",
        r"(^|/)(poetry\.lock|cargo\.lock|pubspec\.lock|composer\.lock|gemfile\.lock)$",
    ),
}

NO_MATCH_REASON = "경로·명시적 맥락에서 trigger 근거를 찾지 못했습니다."


def _excluded(reviewer: str, value: str) -> bool:
    return any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in EXCLUSIONS.get(reviewer, ())
    )


def classify(paths: Iterable[str], context: str = "") -> dict[str, object]:
    """Match paths and context against the rules, partitioned active/inactive.

    Evidence records the pattern that matched, not the text it matched against.
    A context string is caller-supplied prose that can carry a token, a
    customer name or a path the user pasted; copying it into the result would
    push it straight into the ledger's finding records, which
    `review-execution.md` forbids. The source label says `context` and the
    pattern says why -- enough to justify the activation, nothing to leak.
    """
    haystacks = [(path, path.replace("\\", "/").lower()) for path in paths]
    if context:
        haystacks.append((CONTEXT_SOURCE, context.lower()))

    evidence: dict[str, list[dict[str, str]]] = {}
    for reviewer, patterns in RULES.items():
        matches: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for source, value in haystacks:
            if _excluded(reviewer, value):
                continue
            for pattern in patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    key = (source, pattern)
                    if key not in seen:
                        seen.add(key)
                        matches.append({"source": source, "matched": pattern})
                    break
        if matches:
            evidence[reviewer] = matches

    active = sorted(evidence)
    return {
        "active": active,
        "evidence": evidence,
        "inactive": [
            {"reviewer": name, "reason": NO_MATCH_REASON}
            for name in sorted(RULES)
            if name not in evidence
        ],
        "known_reviewers": sorted(RULES),
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
