"""Safely restyle existing duck GIFs without changing the live manifest."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image

import package_site
from append_ai_batch import (
    STATIC_SITE_FILES,
    asset_paths,
    copy_static_site_files,
    read_batch_manifest,
    safe_path,
    snapshot,
)
from build_gifs import DEFAULT_FONT, load_font, save_outputs, unique_run_directory
from replace_ai_batch import (
    LIVE_ARCHIVE_RELATIVE,
    LIVE_SITE_RELATIVE,
    atomic_copy,
    backup_live_file,
    sha256_file,
    validate_generated_outputs,
    validate_source_image,
    validate_staged_site,
    validate_zip_archive,
)


LIVE_MANIFEST_RELATIVE = Path("data/gifs.json")
DUCK_PREFIX = "duck-office-"
FRAME_COUNT = 20


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="Selected existing-record manifest")
    parser.add_argument("--repo-root", type=Path, default=repository_root)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--check-only", action="store_true", help="Validate inputs without writing files")
    parser.add_argument("--originals-root", type=Path, default=Path.home() / "Pictures" / "AI", help=argparse.SUPPRESS)
    return parser.parse_args()


def resolve_file(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise RuntimeError(f"{label} is linked: {path}")
    resolved = expanded.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} not found or is linked: {path}")
    return resolved


def read_selected_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        records = read_batch_manifest(path)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Unable to read manifest: {path}: {error}") from error
    if not records:
        raise RuntimeError("Selected manifest must not be empty")
    if any(not record["id"].startswith(DUCK_PREFIX) for record in records):
        raise RuntimeError("Selected manifest may contain only duck-office records")
    return records


def read_live_records(repository_root: Path) -> list[dict[str, Any]]:
    manifest_path = safe_path(repository_root, LIVE_MANIFEST_RELATIVE.as_posix())
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError(f"Live manifest not found or is linked: {manifest_path}")
    try:
        return read_batch_manifest(manifest_path)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Live manifest is invalid: {manifest_path}: {error}") from error


def validate_selection(
    selected: list[dict[str, Any]],
    live_records: list[dict[str, Any]],
    repository_root: Path,
) -> dict[str, Path]:
    live_by_id = {record["id"]: record for record in live_records}
    missing = [record["id"] for record in selected if record["id"] not in live_by_id]
    mismatched = [record["id"] for record in selected if live_by_id.get(record["id"]) != record]
    if missing:
        raise RuntimeError(f"Selected records are not present in data/gifs.json: {', '.join(missing)}")
    if mismatched:
        raise RuntimeError(f"Selected records differ from data/gifs.json: {', '.join(mismatched)}")
    if len({record["id"] for record in selected}) != len(selected):
        raise RuntimeError("Selected manifest contains duplicate ids")

    validate_generated_outputs(selected, repository_root)
    source_paths: dict[str, Path] = {}
    for record in selected:
        source = safe_path(repository_root, f"assets/source/{record['id']}.png")
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Source PNG not found or is linked: {source}")
        validate_source_image(source)
        source_paths[record["id"]] = source
    return source_paths


def validate_repository_inputs(repository_root: Path, live_records: list[dict[str, Any]]) -> None:
    for relative in (*STATIC_SITE_FILES, LIVE_MANIFEST_RELATIVE.as_posix(), LIVE_ARCHIVE_RELATIVE.as_posix()):
        path = safe_path(repository_root, relative)
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Required repository file not found or is linked: {path}")
    for relative in asset_paths(live_records):
        path = safe_path(repository_root, relative)
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Required existing asset not found or is linked: {path}")
    site = safe_path(repository_root, LIVE_SITE_RELATIVE.as_posix())
    if site.is_symlink() or (site.exists() and not site.is_dir()):
        raise RuntimeError(f"Unsafe live site path: {site}")


def source_hashes(source_paths: dict[str, Path]) -> dict[str, str]:
    return {identifier: sha256_file(path) for identifier, path in source_paths.items()}


def load_tiles(selected: list[dict[str, Any]], source_paths: dict[str, Path]) -> list[Image.Image]:
    tiles = []
    for record in selected:
        with Image.open(source_paths[record["id"]]) as image:
            tile = Image.new("RGBA", image.size, (255, 255, 255, 255))
            tile.alpha_composite(image.convert("RGBA"))
            tiles.append(tile.convert("RGB"))
    return tiles


def copy_existing_stage(repository_root: Path, stage: Path, live_records: list[dict[str, Any]]) -> None:
    copy_static_site_files(repository_root, stage)
    for relative in (LIVE_MANIFEST_RELATIVE.as_posix(), *asset_paths(live_records)):
        source = safe_path(repository_root, relative)
        destination = stage / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def package_stage(stage: Path) -> None:
    previous_root = package_site.ROOT
    try:
        package_site.ROOT = stage
        package_site.main()
    finally:
        package_site.ROOT = previous_root


def remove_publication(repository_root: Path, publication: Path) -> None:
    if publication.parent != repository_root or not publication.name.startswith(".restyle-site-"):
        raise RuntimeError(f"Unsafe temporary publication path: {publication}")
    safe_path(repository_root, publication.name)
    snapshot(repository_root, [publication.name])
    shutil.rmtree(publication)


def deploy(
    selected: list[dict[str, Any]],
    live_records: list[dict[str, Any]],
    stage: Path,
    run_directory: Path,
    repository_root: Path,
    expected_snapshot: dict[str, str | None],
    expected_source_hashes: dict[str, str],
) -> None:
    watched = [
        LIVE_MANIFEST_RELATIVE.as_posix(),
        LIVE_ARCHIVE_RELATIVE.as_posix(),
        LIVE_SITE_RELATIVE.as_posix(),
        *STATIC_SITE_FILES,
        *asset_paths(live_records),
        *(f"assets/source/{record['id']}.png" for record in selected),
    ]
    if snapshot(repository_root, watched) != expected_snapshot:
        raise RuntimeError("Live files changed during build; restyle aborted")

    backup_root = run_directory / "live-backup"
    changed: list[tuple[Path, Path | None]] = []
    live_site = safe_path(repository_root, LIVE_SITE_RELATIVE.as_posix())
    site_backup = backup_root / LIVE_SITE_RELATIVE
    publication = Path(tempfile.mkdtemp(prefix=".restyle-site-", dir=repository_root))
    new_site = publication / "new-site"
    site_backup_ready = False
    site_installed = False
    rollback_errors: list[str] = []
    try:
        shutil.copytree(stage / LIVE_SITE_RELATIVE, new_site)
        for record in selected:
            for field in ("file", "poster"):
                relative = record[field]
                destination = safe_path(repository_root, relative)
                backup = backup_live_file(destination, backup_root, repository_root)
                changed.append((destination, backup))
                atomic_copy(stage / relative, destination)
        archive = safe_path(repository_root, LIVE_ARCHIVE_RELATIVE.as_posix())
        changed.append((archive, backup_live_file(archive, backup_root, repository_root)))
        atomic_copy(stage / LIVE_ARCHIVE_RELATIVE, archive)
        validate_generated_outputs(live_records, repository_root)
        validate_zip_archive(archive, live_records)

        if live_site.exists():
            site_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(live_site, site_backup)
            site_backup_ready = True
        if live_site.exists():
            from replace_ai_batch import remove_live_site

            remove_live_site(repository_root)
        new_site.rename(live_site)
        site_installed = True
        validate_staged_site(live_records, repository_root)
        ensure_source_hashes_unchanged(selected, repository_root, expected_source_hashes)
    except Exception as error:
        if site_installed and live_site.exists():
            try:
                from replace_ai_batch import remove_live_site

                remove_live_site(repository_root)
            except Exception as rollback_error:
                rollback_errors.append(f"live site removal: {rollback_error}")
        if site_backup_ready and not live_site.exists():
            try:
                shutil.copytree(site_backup, live_site)
            except Exception as rollback_error:
                rollback_errors.append(f"live site restore: {rollback_error}")
        for path, backup in reversed(changed):
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_copy(backup, path)
            except Exception as rollback_error:
                rollback_errors.append(f"file restore {path}: {rollback_error}")
        try:
            if publication.exists():
                remove_publication(repository_root, publication)
        except Exception as rollback_error:
            rollback_errors.append(f"temporary publication cleanup: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                f"Restyle failed and rollback was incomplete; recovery files retained at {run_directory}: "
                + "; ".join(rollback_errors)
            ) from error
        raise
    else:
        remove_publication(repository_root, publication)


def ensure_source_hashes_unchanged(
    selected: list[dict[str, Any]],
    repository_root: Path,
    expected_hashes: dict[str, str],
) -> None:
    for record in selected:
        source = safe_path(repository_root, f"assets/source/{record['id']}.png")
        if not source.is_file() or sha256_file(source) != expected_hashes[record["id"]]:
            raise RuntimeError(f"Source PNG changed during build: {source}")


def restyle(arguments: argparse.Namespace) -> Path | None:
    repository_root = arguments.repo_root.expanduser().resolve()
    manifest_path = resolve_file(arguments.manifest, "Manifest")
    font_path = resolve_file(arguments.font, "Caption font")
    selected = read_selected_manifest(manifest_path)
    live_records = read_live_records(repository_root)
    validate_repository_inputs(repository_root, live_records)
    source_paths = validate_selection(selected, live_records, repository_root)
    load_font(font_path)
    manifest_hash = sha256_file(repository_root / LIVE_MANIFEST_RELATIVE)
    expected_snapshot = snapshot(
        repository_root,
        [
            LIVE_MANIFEST_RELATIVE.as_posix(),
            LIVE_ARCHIVE_RELATIVE.as_posix(),
            LIVE_SITE_RELATIVE.as_posix(),
            *STATIC_SITE_FILES,
            *asset_paths(live_records),
            *(f"assets/source/{record['id']}.png" for record in selected),
        ],
    )
    if arguments.check_only:
        return None

    run_directory = unique_run_directory(arguments.originals_root.expanduser().resolve())
    stage = run_directory / "repository-stage"
    stage.mkdir()
    copy_existing_stage(repository_root, stage, live_records)
    hashes = source_hashes(source_paths)
    save_outputs(selected, load_tiles(selected, source_paths), run_directory, stage, font_path, FRAME_COUNT)
    package_stage(stage)
    validate_staged_site(live_records, stage)
    validate_generated_outputs(selected, run_directory)
    for identifier, expected_hash in hashes.items():
        source = source_paths[identifier]
        if not source.is_file() or sha256_file(source) != expected_hash:
            raise RuntimeError(f"Source PNG changed during build: {source}")
    if sha256_file(repository_root / LIVE_MANIFEST_RELATIVE) != manifest_hash:
        raise RuntimeError("Live manifest changed during build")
    if sha256_file(stage / LIVE_MANIFEST_RELATIVE) != manifest_hash:
        raise RuntimeError("Staged manifest differs from the live manifest")
    deploy(selected, live_records, stage, run_directory, repository_root, expected_snapshot, hashes)
    return run_directory


def main() -> int:
    arguments = parse_args()
    run_directory = restyle(arguments)
    if run_directory is None:
        print("Restyle preflight passed; no files were written")
        return 0
    repository_root = arguments.repo_root.expanduser().resolve()
    print(f"Restyled {len(read_selected_manifest(arguments.manifest))} duck GIFs and posters")
    print(f"Run directory: {run_directory}")
    print(f"ZIP: {repository_root / LIVE_ARCHIVE_RELATIVE}")
    print(f"Site: {repository_root / LIVE_SITE_RELATIVE}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(f"error: {error}") from error
