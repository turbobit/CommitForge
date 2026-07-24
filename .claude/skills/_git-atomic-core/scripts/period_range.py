#!/usr/bin/env python3
"""Calculate deterministic local calendar boundaries for period review modes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_now(value: Optional[str], timezone: dt.tzinfo) -> dt.datetime:
    if value is None:
        return dt.datetime.now(timezone)
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def resolve_timezone(value: str) -> dt.tzinfo:
    if value.upper() in {"UTC", "Z"}:
        return dt.timezone.utc
    fixed = re.fullmatch(r"([+-])(\d{2}):(\d{2})", value)
    if fixed:
        hours = int(fixed.group(2))
        minutes = int(fixed.group(3))
        if hours > 23 or minutes > 59:
            raise ValueError(f"잘못된 UTC offset: {value}")
        delta = dt.timedelta(hours=hours, minutes=minutes)
        if fixed.group(1) == "-":
            delta = -delta
        return dt.timezone(delta)
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"지원할 수 없는 IANA timezone: {value}") from error


def render_offset(value: dt.datetime) -> str:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("UTC offset을 확인할 수 없습니다")
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def calculate(
    mode: str,
    *,
    now_value: Optional[str] = None,
    timezone_name: Optional[str] = None,
    week_start: str = "monday",
) -> dict[str, str]:
    if timezone_name:
        timezone = resolve_timezone(timezone_name)
        rendered_timezone = timezone_name
    else:
        local_now = dt.datetime.now().astimezone()
        timezone = local_now.tzinfo
        if timezone is None:
            raise ValueError("로컬 timezone을 확인할 수 없습니다")
        rendered_timezone = str(timezone)

    now = parse_now(now_value, timezone)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if mode == "weekly":
        if week_start == "monday":
            days_since_start = now.weekday()
        else:
            days_since_start = (now.weekday() + 1) % 7
        start -= dt.timedelta(days=days_since_start)

    return {
        "mode": mode,
        "timezone": rendered_timezone,
        "utc_offset": render_offset(now),
        "week_start": week_start if mode == "weekly" else "",
        "start": start.isoformat(),
        "end": now.isoformat(),
        "label": (
            start.date().isoformat()
            if mode == "today"
            else f"{start.date().isoformat()}..{now.date().isoformat()}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("today", "weekly"))
    parser.add_argument("--timezone")
    parser.add_argument("--week-start", choices=("monday", "sunday"), default="monday")
    parser.add_argument("--now", help=argparse.SUPPRESS)
    args = parser.parse_args()
    print(
        json.dumps(
            calculate(
                args.mode,
                now_value=args.now,
                timezone_name=args.timezone,
                week_start=args.week_start,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
