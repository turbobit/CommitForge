#!/usr/bin/env python3
"""Calculate a deterministic next SemVer version and local tag name."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, Optional


SEMVER = re.compile(
    r"^(?P<core>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))"
    r"(?:-(?P<channel>alpha|beta|rc)\.(?P<number>[1-9]\d*))?$"
)
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        parts = value.split(".")
        if len(parts) != 3:
            raise ValueError(f"잘못된 SemVer: {value}")
        return cls(*(int(part) for part in parts))

    def render(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, kind: str) -> "Version":
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"지원하지 않는 bump: {kind}")


@dataclass(frozen=True)
class ParsedTag:
    raw: str
    prefix: str
    version: Version
    channel: Optional[str]
    number: Optional[int]


def split_tag(tag: str, required_prefix: Optional[str] = None) -> Optional[ParsedTag]:
    prefixes = [required_prefix] if required_prefix is not None else ["v", ""]
    for prefix in prefixes:
        if prefix is None or not tag.startswith(prefix):
            continue
        match = SEMVER.fullmatch(tag[len(prefix) :])
        if not match:
            continue
        return ParsedTag(
            raw=tag,
            prefix=prefix,
            version=Version.parse(match.group("core")),
            channel=match.group("channel"),
            number=int(match.group("number")) if match.group("number") else None,
        )
    return None


def repository_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "Git tag 목록 조회 실패")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def choose_current(tags: Iterable[str], prefix: str) -> Optional[ParsedTag]:
    parsed = [item for tag in tags if (item := split_tag(tag, prefix))]
    stable = [item for item in parsed if item.channel is None]
    candidates = stable or parsed
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item.version,
            1 if item.channel is None else 0,
            item.number or 0,
        ),
    )


def parse_target(value: str) -> tuple[Version, Optional[str], Optional[int]]:
    normalized = value[1:] if value.startswith("v") else value
    match = SEMVER.fullmatch(normalized)
    if not match:
        raise ValueError(f"잘못된 target SemVer: {value}")
    return (
        Version.parse(match.group("core")),
        match.group("channel"),
        int(match.group("number")) if match.group("number") else None,
    )


def calculate(
    tags: list[str],
    *,
    bump: str,
    target: Optional[str],
    channel: str,
    package: Optional[str],
    tag_prefix: Optional[str],
) -> dict[str, object]:
    if package and not PACKAGE_NAME.fullmatch(package):
        raise ValueError("package 이름에는 영문자, 숫자, 점, 밑줄, 하이픈만 허용됩니다")
    prefix = tag_prefix if tag_prefix is not None else (f"{package}-v" if package else "v")
    if (
        not prefix
        or prefix.endswith(".")
        or prefix.endswith(".lock")
        or any(character in prefix for character in " ~^:?*[\\")
        or ".." in prefix
        or "@{" in prefix
    ):
        raise ValueError("Git ref에 안전하지 않은 tag prefix입니다")
    current = choose_current(tags, prefix)
    current_version = current.version if current else Version(0, 0, 0)

    explicit_channel: Optional[str] = None
    explicit_number: Optional[int] = None
    if target:
        next_version, explicit_channel, explicit_number = parse_target(target)
        if explicit_channel and channel != "stable" and explicit_channel != channel:
            raise ValueError("target prerelease channel과 --channel이 충돌합니다")
        effective_channel = explicit_channel or (
            None if channel == "stable" else channel
        )
    else:
        next_version = current_version.bump(bump)
        effective_channel = None if channel == "stable" else channel

    if target and current and (
        next_version < current.version
        or (next_version == current.version and effective_channel is not None)
    ):
        reason = (
            "더 낮습니다"
            if next_version < current.version
            else "동일한 core의 prerelease입니다"
        )
        raise ValueError(
            f"target이 현재 stable version({current.version.render()})과 충돌합니다: "
            f"{reason}"
        )

    number: Optional[int] = explicit_number
    if effective_channel and number is None:
        matching_numbers = []
        for raw in tags:
            parsed = split_tag(raw, prefix)
            if (
                parsed
                and parsed.version == next_version
                and parsed.channel == effective_channel
                and parsed.number is not None
            ):
                matching_numbers.append(parsed.number)
        number = max(matching_numbers, default=0) + 1

    version_text = next_version.render()
    if effective_channel:
        version_text += f"-{effective_channel}.{number}"
    next_tag = f"{prefix}{version_text}"
    if next_tag in tags:
        raise ValueError(f"이미 존재하는 tag: {next_tag}")

    return {
        "current_tag": current.raw if current else None,
        "current_version": current.version.render() if current else None,
        "bump": bump,
        "target_version": version_text,
        "channel": effective_channel or "stable",
        "prerelease_number": number,
        "package": package,
        "tag_prefix": prefix,
        "next_tag": next_tag,
        "tag_exists": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bump", choices=("major", "minor", "patch"), default="patch")
    parser.add_argument("--target")
    parser.add_argument(
        "--channel",
        choices=("stable", "rc", "beta", "alpha"),
        default="stable",
    )
    parser.add_argument("--package")
    parser.add_argument("--tag-prefix")
    parser.add_argument("--existing-tag", action="append", default=[])
    args = parser.parse_args()
    tags = args.existing_tag or repository_tags()
    try:
        payload = calculate(
            tags,
            bump=args.bump,
            target=args.target,
            channel=args.channel,
            package=args.package,
            tag_prefix=args.tag_prefix,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
