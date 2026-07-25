#!/usr/bin/env python3
"""Report Agent Team availability and CommitForge's read-only team-first policy."""

from __future__ import annotations

import json
import os


def main() -> None:
    raw = os.environ.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS")
    enabled = raw == "1"
    print(
        json.dumps(
            {
                "ok": True,
                "enabled": enabled,
                "source": "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",
                "default_mode": "team_first" if enabled else "subagent_fallback",
                "eligible_commands": ["cr_read_only", "ccr", "cpr"],
                "default_team_size": {
                    "cr_read_only": 3,
                    "cpr": 3,
                    "ccr": 3,
                },
                "trivial_downgrade": {
                    "max_files": 2,
                    "max_changed_lines": 80,
                    "requires_single_domain": True,
                    "requires_no_high_risk_trigger": True,
                    "requires_no_cross_file_contract": True,
                    "disabled_by_force_team": True,
                },
                "conditional_specialists": [
                    "testing_independent_verification",
                    "performance_reliability_observability",
                    "ux_accessibility",
                    "data_migration",
                    "requirements_product",
                    "release_deployment_rollback",
                    "domain_framework",
                ],
                "testing_policy": "required_for_any_non_documentation_behavior_change",
                "specialist_policy": "triggered_addition_with_explicit_active_na_unknown",
                "reason": (
                    "environment_enabled_team_first"
                    if enabled
                    else "environment_not_enabled"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
