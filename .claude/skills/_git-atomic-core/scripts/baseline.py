#!/usr/bin/env python3
"""Validate CommitForge review baseline entries."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def validate(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "commitforge-baseline/v1":
        raise ValueError("지원하지 않는 baseline schema")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("entries 배열 누락")
    seen = set()
    expired = []
    today = dt.date.today()
    for index, entry in enumerate(entries):
        for field in ("id", "reason", "owner", "expires"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"entry {index}: {field} 누락")
        fingerprint = entry.get("fingerprint")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise ValueError(f"entry {index}: fingerprint 형식 오류")
        if entry["id"] in seen:
            raise ValueError(f"entry {index}: 중복 id {entry['id']}")
        seen.add(entry["id"])
        try:
            expiry = dt.date.fromisoformat(entry["expires"])
        except ValueError as error:
            raise ValueError(f"entry {index}: expires 날짜 형식 오류") from error
        if expiry < today:
            expired.append(entry["id"])
    return {"ok": True, "entries": len(entries), "expired": expired}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.baseline), ensure_ascii=False))


if __name__ == "__main__":
    main()
