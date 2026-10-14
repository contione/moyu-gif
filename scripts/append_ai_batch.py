"""Append locally animated PNG illustrations without replacing existing assets."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image

import package_site
from build_gifs import ALLOWED_CATEGORIES, DEFAULT_FONT, REQUIRED_FIELDS, load_font, save_outputs, unique_run_directory
from replace_ai_batch import (
    STATIC_SITE_FILES,
    atomic_copy,
    backup_live_file,
    copy_static_site_files,
    restore_live_file,
    sha256_file,
    validate_generated_outputs,
    validate_new_ids,
    validate_source_image,
    validate_sources,
    validate_zip_archive,
    write_live_manifest,
)


LIVE_FILES = ("data/gifs.json", "assets/moyu-gifs.zip")
WATCHED_PATHS = (*LIVE_FILES, *STATIC_SITE_FILES, "assets/gifs", "assets/posters", "assets/source", "_site")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true", help="Validate without writing any files")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--originals-root", type=Path, default=Path.home() / "Pictures" / "AI")
    return parser.parse_args()


def safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    parts = relative.split("/")
    if not relative or "\\" in relative or any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise RuntimeError(f"Unsafe relative path: {relative}")
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise RuntimeError(f"Refusing linked path: {candidate}")
    if candidate.resolve() != root.joinpath(*parts):
        raise RuntimeError(f"Path escapes its intended location: {candidate}")
    return candidate


def read_batch_manifest(path: Path) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise RuntimeError("Manifest must be a non-empty array")
    identifiers: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != REQUIRED_FIELDS:
            raise RuntimeError(f"Each record must contain exactly {sorted(REQUIRED_FIELDS)}")
        identifier = record["id"]
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z0-9-]+", identifier)
            or re.fullmatch(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", identifier)
            or identifier in identifiers
        ):
            raise RuntimeError(f"Invalid or duplicate id: {identifier!r}")
        identifiers.add(identifier)
        for field in ("title", "category", "motion"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise RuntimeError(f"Invalid {field}: {identifier}")
        if record["category"] not in ALLOWED_CATEGORIES:
            raise RuntimeError(f"Unsupported category: {identifier}")
        if not isinstance(record["tags"], list) or any(not isinstance(tag, str) or not tag.strip() for tag in record["tags"]):
            raise RuntimeError(f"Invalid tags: {identifier}")
        if record["file"] != f"assets/gifs/{identifier}.gif" or record["poster"] != f"assets/posters/{identifier}.webp":
            raise RuntimeError(f"Asset paths must derive from the id: {identifier}")
    return records


def asset_paths(records: list[dict[str, Any]], include_sources: bool = False) -> list[str]:
    paths = [record[field] for record in records for field in ("file", "poster")]
    if include_sources:
        paths.extend(f"assets/source/{record['id']}.png" for record in records)
    return paths


def snapshot(root: Path, paths: tuple[str, ...] | list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}

    def visit(relative: str) -> None:
        path = safe_path(root, relative)
        if path.is_dir():
            result[relative] = "directory"
            for child in sorted(path.iterdir()):
                visit(f"{relative}/{child.name}")
        elif path.is_file():
            result[relative] = sha256_file(path)
        elif path.exists():
            raise RuntimeError(f"Unsupported filesystem entry: {path}")
        else:
            result[relative] = None

    for relative in paths:
        visit(relative)
    return result


def ensure_absent(root: Path, paths: list[str]) -> None:
    for relative in paths:
        if safe_path(root, relative).exists():
            raise RuntimeError(f"Refusing to overwrite existing asset: {relative}")


def validate_stage(records: list[dict[str, Any]], stage: Path) -> None:
    validate_generated_outputs(records, stage)
    validate_generated_outputs(records, stage / "_site")
    for root in (stage, stage / "_site"):
        if read_batch_manifest(root / "data/gifs.json") != records:
            raise RuntimeError("Staged manifest differs from merged records")
        validate_zip_archive(root / "assets/moyu-gifs.zip", records)
    for relative in (*STATIC_SITE_FILES, *LIVE_FILES, *asset_paths(records)):
        if sha256_file(stage / relative) != sha256_file(stage / "_site" / relative):
            raise RuntimeError(f"Packaged site differs from staging: {relative}")
    with zipfile.ZipFile(stage / "assets/moyu-gifs.zip") as archive:
        if len(archive.namelist()) != len(records) + 1:
            raise RuntimeError("ZIP contains duplicate entries")
        for record in records:
            if archive.read(f"gifs/{record['id']}.gif") != (stage / record["file"]).read_bytes():
                raise RuntimeError(f"ZIP GIF differs from staging: {record['id']}")
        if archive.read("ATTRIBUTION.md") != (stage / "ATTRIBUTION.md").read_bytes():
            raise RuntimeError("ZIP attribution differs from staging")


def remove_publish_directory(root: Path, directory: Path) -> None:
    if directory.parent != root.resolve() or not directory.name.startswith(".append-publish-"):
        raise RuntimeError(f"Unsafe publish directory: {directory}")
    safe_path(root, directory.name)
    snapshot(root, [directory.name])
    shutil.rmtree(directory)


def deploy_staged_append(
    records: list[dict[str, Any]],
    merged_records: list[dict[str, Any]],
    stage: Path,
    repository_root: Path,
    expected_live: dict[str, str | None],
) -> None:
    repository_root = repository_root.resolve()
    new_paths = asset_paths(records, include_sources=True)
    validate_stage(merged_records, stage)
    ensure_absent(repository_root, new_paths)
    if snapshot(repository_root, WATCHED_PATHS) != expected_live:
        raise RuntimeError("Live files changed during build; append aborted")
    publication = Path(tempfile.mkdtemp(prefix=".append-publish-", dir=repository_root))
    installed: list[str] = []
    changed_files: list[tuple[Path, Path | None]] = []
    site_moved = False
    site_installed = False
    rollback_errors: list[str] = []
    live_site = repository_root / "_site"
    try:
        shutil.copytree(stage / "_site", publication / "new-site")
        backups = {
            relative: backup_live_file(safe_path(repository_root, relative), publication / "backup", repository_root)
            for relative in LIVE_FILES
        }
        if snapshot(repository_root, WATCHED_PATHS) != expected_live:
            raise RuntimeError("Live files changed while preparing publication")
        for relative in new_paths:
            destination = safe_path(repository_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = safe_path(stage, relative)
            expected_hash = sha256_file(source)
            with destination.open("xb") as output:
                installed.append(relative)
                with source.open("rb") as incoming:
                    shutil.copyfileobj(incoming, output)
            if sha256_file(destination) != expected_hash:
                raise RuntimeError(f"Asset changed while copying: {relative}")
        validate_generated_outputs(merged_records, repository_root)
        archive = safe_path(repository_root, "assets/moyu-gifs.zip")
        changed_files.append((archive, backups["assets/moyu-gifs.zip"]))
        atomic_copy(stage / "assets/moyu-gifs.zip", archive)
        validate_zip_archive(archive, merged_records)
        safe_path(repository_root, "_site")
        if live_site.exists():
            live_site.rename(publication / "old-site")
            site_moved = True
        (publication / "new-site").rename(live_site)
        site_installed = True
        if snapshot(stage / "_site", [child.name for child in (stage / "_site").iterdir()]) != snapshot(
            live_site, [child.name for child in live_site.iterdir()]
        ):
            raise RuntimeError("Published site differs from staging")
        manifest = safe_path(repository_root, "data/gifs.json")
        changed_files.append((manifest, backups["data/gifs.json"]))
        atomic_copy(stage / "data/gifs.json", manifest)
        if read_batch_manifest(manifest) != merged_records:
            raise RuntimeError("Published manifest differs from merged records")
    except Exception as error:
        for path, backup in reversed(changed_files):
            try:
                safe_path(repository_root, path.relative_to(repository_root).as_posix())
                restore_live_file(path, backup)
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        try:
            safe_path(repository_root, "_site")
            if site_installed:
                live_site.rename(publication / "failed-site")
            if site_moved:
                (publication / "old-site").rename(live_site)
        except Exception as rollback_error:
            rollback_errors.append(str(rollback_error))
        if not rollback_errors:
            for relative in installed:
                try:
                    safe_path(repository_root, relative).unlink(missing_ok=True)
                except Exception as rollback_error:
                    rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise RuntimeError(
                f"Append failed; rollback incomplete. Recovery files retained at {publication}: "
                + "; ".join(rollback_errors)
            ) from error
        raise
    finally:
        if not rollback_errors:
            try:
                remove_publish_directory(repository_root, publication)
            except (OSError, RuntimeError) as cleanup_error:
                print(f"Warning: publication files retained at {publication}: {cleanup_error}", file=sys.stderr)


def append_batch(arguments: argparse.Namespace) -> Path | None:
    repository_root = arguments.repo_root.expanduser().resolve()
    images_dir = arguments.images_dir.expanduser().resolve()
    font_path = arguments.font.expanduser().resolve()
    manifest_path = arguments.manifest.expanduser().resolve()
    manifest_hash = sha256_file(manifest_path)
    expected_live = snapshot(repository_root, WATCHED_PATHS)
    old_records = read_batch_manifest(safe_path(repository_root, "data/gifs.json"))
    records = read_batch_manifest(manifest_path)
    validate_new_ids(records, old_records)
    ensure_absent(repository_root, asset_paths(records, include_sources=True))
    for relative in (*STATIC_SITE_FILES, *asset_paths(old_records)):
        if not safe_path(repository_root, relative).is_file():
            raise RuntimeError(f"Missing required existing file: {relative}")
    if (repository_root / "_site").exists() and not (repository_root / "_site").is_dir():
        raise RuntimeError("Existing _site must be a directory")
    validate_generated_outputs(old_records, repository_root)
    load_font(font_path)
    source_paths = validate_sources(records, images_dir)
    source_hashes = {identifier: validate_source_image(safe_path(images_dir, path.name)) for identifier, path in source_paths.items()}
    if len(set(source_hashes.values())) != len(records):
        raise RuntimeError("Duplicate PNG SHA256 content")
    existing_source_hashes = {
        value for relative, value in expected_live.items()
        if relative.startswith("assets/source/") and relative.lower().endswith(".png")
    }
    if existing_source_hashes.intersection(source_hashes.values()):
        raise RuntimeError("PNG SHA256 duplicates an existing source")
    if arguments.check_only:
        return None

    run_directory = unique_run_directory(arguments.originals_root.expanduser().resolve())
    stage = run_directory / "repository-stage"
    stage.mkdir()
    copy_static_site_files(repository_root, stage)
    for relative in asset_paths(old_records):
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_path(repository_root, relative), destination)
    originals = run_directory / "source-images"
    originals.mkdir()
    tiles = []
    for record in records:
        identifier = record["id"]
        original = originals / f"{identifier}.png"
        shutil.copy2(safe_path(images_dir, original.name), original)
        if sha256_file(original) != source_hashes[identifier]:
            raise RuntimeError(f"Source changed before backup: {identifier}")
        destination = stage / "assets/source" / original.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
        with Image.open(original) as image:
            tile = Image.new("RGBA", image.size, "white")
            tile.alpha_composite(image.convert("RGBA"))
            tiles.append(tile.convert("RGB"))
    save_outputs(records, tiles, run_directory, stage, font_path, 20)
    merged_records = old_records + records
    write_live_manifest(merged_records, stage)
    previous_root = package_site.ROOT
    try:
        package_site.ROOT = stage
        package_site.main()
    finally:
        package_site.ROOT = previous_root
    validate_stage(merged_records, stage)
    if sha256_file(manifest_path) != manifest_hash:
        raise RuntimeError("Input manifest changed during build")
    for identifier, expected_hash in source_hashes.items():
        if sha256_file(safe_path(images_dir, f"{identifier}.png")) != expected_hash:
            raise RuntimeError(f"Source changed during build: {identifier}")
    deploy_staged_append(records, merged_records, stage, repository_root, expected_live)
    return run_directory


def main() -> int:
    arguments = parse_args()
    run_directory = append_batch(arguments)
    if run_directory is None:
        print("Append preflight passed; no files were written")
    else:
        print(f"Append complete; existing assets retained. Originals and staging: {run_directory}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(f"error: {error}") from error
