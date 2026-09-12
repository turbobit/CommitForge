#!/usr/bin/env python3
"""Validate CommitForge JSON or SARIF review reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FINDING_FIELDS = {
    "id",
    "reviewer",
    "fingerprint",
    "severity",
    "status",
    "file",
    "line_or_hunk",
    "category",
    "evidence",
    "failure_scenario",
    "suggested_fix",
    "validation",
    "blocking",
}
SEVERITIES = {"CRITICAL", "MAJOR", "MINOR", "NOTE"}
STATUSES = {"OPEN", "FIXED", "REJECTED", "N_A", "UNKNOWN", "BASELINED", "STALE"}

# review-execution.md §3.6 adds these two. They stay out of FINDING_FIELDS
# because that set is what every finding must carry, and a review that never
# reached the verification step legitimately omits them -- but a value that IS
# present has to be valid here for the same reason the ledger validates it at
# write time.
VERIFICATIONS = {"ISOLATED", "SELF", "UNVERIFIED"}
CONFIDENCE_MIN = 1
CONFIDENCE_MAX = 10


def validate_json(payload: dict) -> None:
    if payload.get("schema") != "commitforge-review/v1":
        raise ValueError("지원하지 않는 CommitForge JSON schema")
    if not isinstance(payload.get("findings"), list):
        raise ValueError("findings 배열 누락")
    for index, finding in enumerate(payload["findings"]):
        if not isinstance(finding, dict):
            raise ValueError(f"finding {index} 객체 형식 오류")
        missing = FINDING_FIELDS - set(finding)
        if missing:
            raise ValueError(f"finding {index} 필드 누락: {sorted(missing)}")
        if finding["severity"] not in SEVERITIES:
            raise ValueError(f"finding {index} severity 형식 오류")
        if finding["status"] not in STATUSES:
            raise ValueError(f"finding {index} status 형식 오류")
        if not isinstance(finding["blocking"], bool):
            raise ValueError(f"finding {index} blocking 형식 오류")
        for field in FINDING_FIELDS - {"blocking"}:
            if not isinstance(finding[field], str):
                raise ValueError(f"finding {index} {field} 문자열 형식 오류")
        verification = finding.get("verification")
        if verification is not None and verification not in VERIFICATIONS:
            raise ValueError(f"finding {index} verification 형식 오류")
        confidence = finding.get("confidence")
        if confidence is not None:
            # `bool` subclasses `int`, so `True` would pass as the lowest
            # confidence there is instead of failing as the type error it is.
            if isinstance(confidence, bool) or not isinstance(confidence, int):
                raise ValueError(f"finding {index} confidence 형식 오류")
            if not CONFIDENCE_MIN <= confidence <= CONFIDENCE_MAX:
                raise ValueError(f"finding {index} confidence 범위 오류")


def validate_sarif(payload: dict) -> None:
    if payload.get("version") != "2.1.0":
        raise ValueError("SARIF version은 2.1.0이어야 합니다")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("SARIF runs 누락")
    for run in runs:
        name = run.get("tool", {}).get("driver", {}).get("name")
        if name != "CommitForge":
            raise ValueError("SARIF tool driver가 CommitForge가 아님")
        if not isinstance(run.get("results", []), list):
            raise ValueError("SARIF results 형식 오류")
        for index, result in enumerate(run.get("results", [])):
            if not isinstance(result, dict):
                raise ValueError(f"SARIF result {index} 객체 형식 오류")
            if not result.get("ruleId"):
                raise ValueError(f"SARIF result {index} ruleId 누락")
            if not result.get("message", {}).get("text"):
                raise ValueError(f"SARIF result {index} message 누락")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.report.read_text(encoding="utf-8"))
    if payload.get("version") == "2.1.0":
        validate_sarif(payload)
    else:
        validate_json(payload)
    print(json.dumps({"ok": True, "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
