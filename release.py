#!/usr/bin/env python3
"""Generate or verify deterministic CommitForge release metadata and archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "MANIFEST.json"
CHECKSUMS = ROOT / "checksums.sha256"
EXCLUDED = {".gitignore", "MANIFEST.json", "checksums.sha256"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_paths() -> list[str]:
    try:
        raw = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        paths = sorted(
            item.decode()
            for item in raw.split(b"\0")
            if item and item.decode() not in EXCLUDED
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not MANIFEST.is_file():
            raise RuntimeError("Git 저장소와 기존 MANIFEST.json을 모두 찾을 수 없습니다")
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        paths = sorted(item["path"] for item in existing.get("files", []))
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"일반 파일이 아닌 release 항목: {missing}")
    return paths


def render_metadata() -> tuple[bytes, bytes, list[str]]:
    paths = source_paths()
    files = []
    for rel in paths:
        data = (ROOT / rel).read_bytes()
        files.append({"path": rel, "size": len(data), "sha256": sha256(data)})

    manifest = {
        "name": "CommitForge",
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "reproducible": True,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files),
        "files": files,
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()

    checksum_entries = [
        (rel, (ROOT / rel).read_bytes()) for rel in paths
    ] + [("MANIFEST.json", manifest_bytes)]
    checksum_bytes = (
        "\n".join(f"{sha256(data)}  {rel}" for rel, data in checksum_entries)
        + "\n"
    ).encode()
    return manifest_bytes, checksum_bytes, paths


def write_metadata(manifest: bytes, checksums: bytes) -> None:
    MANIFEST.write_bytes(manifest)
    CHECKSUMS.write_bytes(checksums)


def check_metadata(manifest: bytes, checksums: bytes) -> None:
    mismatches = []
    if not MANIFEST.is_file() or MANIFEST.read_bytes() != manifest:
        mismatches.append("MANIFEST.json")
    if not CHECKSUMS.is_file() or CHECKSUMS.read_bytes() != checksums:
        mismatches.append("checksums.sha256")
    if mismatches:
        raise RuntimeError(
            "release metadata가 현재 source와 일치하지 않습니다: "
            + ", ".join(mismatches)
        )


def archive_paths(paths: list[str]) -> list[str]:
    return paths + ["MANIFEST.json", "checksums.sha256"]


def create_zip(output: Path, paths: list[str], prefix: str) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in archive_paths(paths):
            source = ROOT / rel
            info = zipfile.ZipInfo(f"{prefix}/{rel}", (1980, 1, 1, 0, 0, 0))
            mode = stat.S_IMODE(source.stat().st_mode)
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())


def create_tar_gz(output: Path, paths: list[str], prefix: str) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for rel in archive_paths(paths):
                    source = ROOT / rel
                    info = archive.gettarinfo(str(source), arcname=f"{prefix}/{rel}")
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)


def create_archives(output_dir: Path, paths: list[str]) -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    prefix = f"commit-forge-v{version}"
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{prefix}.zip"
    tar_path = output_dir / f"{prefix}.tar.gz"
    create_zip(zip_path, paths, prefix)
    create_tar_gz(tar_path, paths, prefix)
    archive_checksums = output_dir / f"{prefix}-ARCHIVE-SHA256.txt"
    archive_checksums.write_text(
        f"{sha256(zip_path.read_bytes())}  {zip_path.name}\n"
        f"{sha256(tar_path.read_bytes())}  {tar_path.name}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when metadata differs instead of writing it",
    )
    parser.add_argument(
        "--archives-dir",
        type=Path,
        help="Also create deterministic ZIP and TAR.GZ archives",
    )
    args = parser.parse_args()

    manifest, checksums, paths = render_metadata()
    if args.check:
        check_metadata(manifest, checksums)
    else:
        write_metadata(manifest, checksums)

    if args.archives_dir:
        check_metadata(manifest, checksums)
        create_archives(args.archives_dir.resolve(), paths)

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "check" if args.check else "write",
                "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
                "files": len(paths),
                "archives": str(args.archives_dir) if args.archives_dir else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
