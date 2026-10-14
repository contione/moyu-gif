"""Validate and safely deploy a batch of 24 AI-generated PNG illustrations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

try:
    from build_gifs import (
        ASSET_COUNT,
        DEFAULT_FONT,
        MAX_FILE_SIZE_BYTES,
        OUTPUT_HEIGHT,
        OUTPUT_WIDTH,
        load_font,
        map_asset_path,
        read_manifest,
        relative_asset_path,
        save_outputs,
        unique_run_directory,
    )
except ImportError as error:
    raise SystemExit(f"error: unable to import build_gifs.py: {error}") from error


ID_PATTERN = re.compile(r"[a-z0-9-]+")
MAX_SOURCE_DIMENSION = 4096
MAX_SOURCE_PIXELS = 16 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
LIVE_MANIFEST_RELATIVE = Path("data/gifs.json")
LIVE_ARCHIVE_RELATIVE = Path("assets/moyu-gifs.zip")
LIVE_SITE_RELATIVE = Path("_site")
STATIC_SITE_FILES = ("index.html", "styles.css", "app.js", "favicon.svg", ".nojekyll", "ATTRIBUTION.md")


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, type=Path, help="Directory containing one {id}.png per manifest record")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repository_root / "content" / "ai-batch-01.json",
        help="Batch manifest JSON, default: content/ai-batch-01.json",
    )
    parser.add_argument("--check-only", action="store_true", help="Validate inputs without writing any files")
    parser.add_argument("--repo-root", type=Path, default=repository_root, help="Repository root receiving the replacement")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT, help="Caption font, default: Windows msyhbd.ttc")
    parser.add_argument(
        "--originals-root",
        type=Path,
        default=Path.home() / "Pictures" / "AI",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def resolve_existing_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError(f"{label} not found: {path}")
    return resolved


def read_exact_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    try:
        records = read_manifest(manifest_path)
    except RuntimeError:
        raise
    if len(records) != ASSET_COUNT:
        raise RuntimeError(f"Manifest must contain exactly {ASSET_COUNT} records")

    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        record_id = record["id"]
        if not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
            raise RuntimeError(f"Manifest record {index} has an unsafe id: {record_id!r}")
        if record_id in seen_ids:
            raise RuntimeError(f"Manifest contains duplicate id: {record_id}")
        seen_ids.add(record_id)
        expected_file = f"assets/gifs/{record_id}.gif"
        expected_poster = f"assets/posters/{record_id}.webp"
        if record["file"] != expected_file or record["poster"] != expected_poster:
            raise RuntimeError(f"Manifest record {index} must use asset paths derived from its id")
    return records


def read_live_manifest(repository_root: Path) -> list[dict[str, Any]]:
    live_manifest = repository_root / LIVE_MANIFEST_RELATIVE
    if not live_manifest.is_file():
        return []
    try:
        return read_manifest(live_manifest)
    except RuntimeError as error:
        raise RuntimeError(f"Current live manifest is invalid: {error}") from error


def validate_new_ids(records: Iterable[dict[str, Any]], old_records: Iterable[dict[str, Any]]) -> None:
    old_ids = {record["id"] for record in old_records}
    reused_ids = sorted(record["id"] for record in records if record["id"] in old_ids)
    if reused_ids:
        raise RuntimeError(f"New manifest reuses existing ids: {', '.join(reused_ids)}")


def safe_image_path(images_dir: Path, record_id: str) -> Path:
    root = images_dir.resolve()
    candidate = images_dir / f"{record_id}.png"
    try:
        candidate.resolve().relative_to(root)
    except ValueError as error:
        raise RuntimeError(f"Image path escapes --images-dir: {candidate}") from error
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_image(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Missing PNG: {path.name}")
    if path.stat().st_size > MAX_SOURCE_FILE_BYTES:
        raise RuntimeError(f"PNG is too large: {path.name}")
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise RuntimeError(f"Not a PNG: {path.name}")
            if image.width < 256 or image.height < 256:
                raise RuntimeError(f"PNG must be at least 256x256: {path.name} ({image.width}x{image.height})")
            if max(image.width, image.height) > MAX_SOURCE_DIMENSION or image.width * image.height > MAX_SOURCE_PIXELS:
                raise RuntimeError(f"PNG dimensions are unsafe: {path.name} ({image.width}x{image.height})")
            image.verify()
    except RuntimeError:
        raise
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise RuntimeError(f"Unable to validate PNG: {path.name}: {error}") from error
    return sha256_file(path)


def validate_sources(records: list[dict[str, Any]], images_dir: Path) -> dict[str, Path]:
    if not images_dir.is_dir():
        raise RuntimeError(f"Images directory not found: {images_dir}")
    source_paths: dict[str, Path] = {}
    missing: list[str] = []
    for record in records:
        path = safe_image_path(images_dir, record["id"])
        if not path.is_file():
            missing.append(path.name)
        else:
            source_paths[record["id"]] = path
    if missing:
        raise RuntimeError(f"Missing PNG files: {', '.join(missing)}")

    hashes: dict[str, list[str]] = {}
    errors: list[str] = []
    for record in records:
        path = source_paths[record["id"]]
        try:
            file_hash = validate_source_image(path)
        except RuntimeError as error:
            errors.append(str(error))
            continue
        hashes.setdefault(file_hash, []).append(path.name)
    duplicates = [", ".join(names) for names in hashes.values() if len(names) > 1]
    if duplicates:
        errors.append(f"Duplicate PNG SHA256 content: {'; '.join(duplicates)}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return source_paths


def validate_motion_strings(records: list[dict[str, Any]], old_records: list[dict[str, Any]]) -> None:
    supported_motions = {record["motion"] for record in old_records}
    if not supported_motions:
        return
    unsupported = sorted({record["motion"] for record in records if record["motion"] not in supported_motions})
    if unsupported:
        raise RuntimeError(f"Manifest contains unsupported motion strings: {', '.join(unsupported)}")


def validate_generated_outputs(records: list[dict[str, Any]], run_directory: Path) -> None:
    for record in records:
        gif_path = map_asset_path(run_directory, relative_asset_path(record["file"]))
        poster_path = map_asset_path(run_directory, relative_asset_path(record["poster"]))
        if not gif_path.is_file() or not poster_path.is_file():
            raise RuntimeError(f"Generated output missing for {record['id']}")
        if gif_path.stat().st_size >= MAX_FILE_SIZE_BYTES:
            raise RuntimeError(f"Generated GIF exceeds 2 MB: {gif_path}")
        try:
            with Image.open(gif_path) as gif:
                if gif.format != "GIF" or gif.n_frames < 2 or gif.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
                    raise RuntimeError(f"Invalid animation output: {gif_path}")
                frame_hashes: set[str] = set()
                for frame_index in range(gif.n_frames):
                    gif.seek(frame_index)
                    frame_hashes.add(hashlib.sha256(gif.convert("RGB").tobytes()).hexdigest())
                if len(frame_hashes) < 2:
                    raise RuntimeError(f"Animation frames are identical: {gif_path}")
            with Image.open(poster_path) as poster:
                if poster.format != "WEBP" or poster.size != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
                    raise RuntimeError(f"Invalid preview output: {poster_path}")
                poster.verify()
        except RuntimeError:
            raise
        except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise RuntimeError(f"Unable to validate generated output for {record['id']}: {error}") from error


def copy_png_backups(records: list[dict[str, Any]], source_paths: dict[str, Path], run_directory: Path) -> None:
    backup_directory = run_directory / "source-images"
    backup_directory.mkdir(parents=True, exist_ok=True)
    for record in records:
        shutil.copy2(source_paths[record["id"]], backup_directory / f"{record['id']}.png")


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{destination.name}.", dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        shutil.copy2(source, temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def copy_static_site_files(repository_root: Path, stage_repository: Path) -> None:
    for filename in STATIC_SITE_FILES:
        source = repository_root / filename
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"Required static site file not found: {source}")
        destination = stage_repository / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def validate_zip_archive(archive_path: Path, records: list[dict[str, Any]]) -> None:
    expected_members = {f"gifs/{record['id']}.gif" for record in records} | {"ATTRIBUTION.md"}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = set(archive.namelist())
            if members != expected_members:
                raise RuntimeError(f"Invalid ZIP contents: {archive_path}")
            if archive.testzip() is not None:
                raise RuntimeError(f"Corrupt ZIP archive: {archive_path}")
    except RuntimeError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise RuntimeError(f"Unable to validate ZIP archive: {archive_path}: {error}") from error


def validate_staged_site(records: list[dict[str, Any]], stage_repository: Path) -> None:
    validate_generated_outputs(records, stage_repository)
    validate_zip_archive(stage_repository / LIVE_ARCHIVE_RELATIVE, records)
    staged_manifest = read_manifest(stage_repository / LIVE_MANIFEST_RELATIVE)
    if staged_manifest != records:
        raise RuntimeError("Staged manifest does not match the new records")

    site_directory = stage_repository / LIVE_SITE_RELATIVE
    for filename in (*STATIC_SITE_FILES, "data/gifs.json", "assets/moyu-gifs.zip"):
        if not (site_directory / filename).is_file():
            raise RuntimeError(f"Static site file missing from stage: {site_directory / filename}")
    validate_generated_outputs(records, site_directory)
    validate_zip_archive(site_directory / LIVE_ARCHIVE_RELATIVE, records)
    if sha256_file(stage_repository / LIVE_ARCHIVE_RELATIVE) != sha256_file(site_directory / LIVE_ARCHIVE_RELATIVE):
        raise RuntimeError("Staged site ZIP does not match the staged ZIP")
    if read_manifest(site_directory / LIVE_MANIFEST_RELATIVE) != records:
        raise RuntimeError("Staged site manifest does not match the new records")


def snapshot_source_hashes(source_paths: dict[str, Path]) -> dict[str, str]:
    return {record_id: sha256_file(path) for record_id, path in source_paths.items()}


def ensure_sources_unchanged(source_paths: dict[str, Path], expected_hashes: dict[str, str]) -> None:
    changed = []
    for record_id, path in source_paths.items():
        if not path.is_file() or sha256_file(path) != expected_hashes[record_id]:
            changed.append(path.name)
    if changed:
        raise RuntimeError(f"Source PNG changed during build: {', '.join(changed)}")


def ensure_new_asset_targets_absent(records: list[dict[str, Any]], repository_root: Path) -> None:
    conflicts = []
    for record in records:
        for field in ("file", "poster"):
            path = map_asset_path(repository_root, relative_asset_path(record[field]))
            if path.exists() or path.is_symlink():
                conflicts.append(path)
    if conflicts:
        raise RuntimeError(f"Refusing to overwrite existing new assets: {', '.join(str(path) for path in conflicts)}")


def backup_live_file(path: Path, backup_root: Path, repository_root: Path) -> Path | None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing to overwrite symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError(f"Expected live file: {path}")
    backup_path = backup_root / path.relative_to(repository_root)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def restore_live_file(path: Path, backup_path: Path | None) -> None:
    if backup_path is None:
        path.unlink(missing_ok=True)
    else:
        atomic_copy(backup_path, path)


def validate_live_site_target(site_path: Path, repository_root: Path) -> None:
    if site_path.is_symlink():
        raise RuntimeError(f"Refusing to remove symlink: {site_path}")
    expected = (repository_root.resolve() / LIVE_SITE_RELATIVE).resolve()
    if site_path.resolve(strict=False) != expected:
        raise RuntimeError(f"Unsafe live site path: {site_path}")


def remove_live_site(repository_root: Path) -> None:
    site_path = repository_root / LIVE_SITE_RELATIVE
    validate_live_site_target(site_path, repository_root)
    if site_path.exists():
        if not site_path.is_dir():
            raise RuntimeError(f"Expected live site directory: {site_path}")
        shutil.rmtree(site_path)


def deploy_staged_outputs(records: list[dict[str, Any]], run_directory: Path, repository_root: Path) -> None:
    stage_repository = run_directory / "repository-stage"
    backup_root = run_directory / "live-backup"
    changed_files: list[tuple[Path, Path | None]] = []
    installed_assets: list[Path] = []
    live_site = repository_root / LIVE_SITE_RELATIVE
    site_backup = backup_root / LIVE_SITE_RELATIVE
    backup_ready = False
    site_copy_started = False

    try:
        ensure_new_asset_targets_absent(records, repository_root)
        for record in records:
            for field in ("file", "poster"):
                relative_path = relative_asset_path(record[field])
                source = map_asset_path(stage_repository, relative_path)
                destination = map_asset_path(repository_root, relative_path)
                atomic_copy(source, destination)
                installed_assets.append(destination)

        archive_path = repository_root / LIVE_ARCHIVE_RELATIVE
        changed_files.append((archive_path, backup_live_file(archive_path, backup_root, repository_root)))
        atomic_copy(stage_repository / LIVE_ARCHIVE_RELATIVE, archive_path)
        validate_generated_outputs(records, repository_root)
        validate_zip_archive(archive_path, records)

        live_manifest = repository_root / LIVE_MANIFEST_RELATIVE
        changed_files.append((live_manifest, backup_live_file(live_manifest, backup_root, repository_root)))
        write_live_manifest(records, repository_root)

        if live_site.is_symlink():
            raise RuntimeError(f"Refusing to replace symlink: {live_site}")
        if live_site.exists() and not live_site.is_dir():
            raise RuntimeError(f"Expected live site directory: {live_site}")
        if live_site.exists():
            if site_backup.exists() or site_backup.is_symlink():
                raise RuntimeError(f"Live site backup already exists: {site_backup}")
            site_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(live_site, site_backup)
            backup_ready = True
        site_copy_started = True
        if backup_ready:
            remove_live_site(repository_root)
        shutil.copytree(stage_repository / LIVE_SITE_RELATIVE, live_site)
    except Exception as error:
        rollback_errors: list[str] = []
        if live_site.exists() and site_copy_started:
            try:
                remove_live_site(repository_root)
            except Exception as rollback_error:
                rollback_errors.append(f"live site removal: {rollback_error}")
        if backup_ready and not live_site.exists() and not live_site.is_symlink():
            try:
                shutil.copytree(site_backup, live_site)
            except Exception as rollback_error:
                rollback_errors.append(f"live site restore: {rollback_error}")
        elif backup_ready and (live_site.exists() or live_site.is_symlink()):
            rollback_errors.append(f"live site restore skipped because target still exists: {live_site}")
        for path, backup_path in reversed(changed_files):
            try:
                restore_live_file(path, backup_path)
            except Exception as rollback_error:
                rollback_errors.append(f"file restore {path}: {rollback_error}")
        for path in installed_assets:
            try:
                path.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(f"asset removal {path}: {rollback_error}")
        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise RuntimeError(f"Deployment failed and rollback was incomplete: {details}") from error
        raise


def write_live_manifest(records: list[dict[str, Any]], repository_root: Path) -> Path:
    live_manifest = repository_root / LIVE_MANIFEST_RELATIVE
    live_manifest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=live_manifest.parent, delete=False) as temporary:
        json.dump(records, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(live_manifest)
    finally:
        temporary_path.unlink(missing_ok=True)
    return live_manifest


def cleanup_old_assets(old_records: list[dict[str, Any]], new_records: list[dict[str, Any]], repository_root: Path) -> None:
    new_paths = {record[field] for record in new_records for field in ("file", "poster")}
    for record in old_records:
        for field, directory in (("file", "gifs"), ("poster", "posters")):
            value = record[field]
            relative_path = relative_asset_path(value)
            if value in new_paths or relative_path.parts[:2] != ("assets", directory) or len(relative_path.parts) != 3:
                continue
            candidate = map_asset_path(repository_root, relative_path)
            if candidate.is_file() and not candidate.is_symlink():
                candidate.unlink()


def rebuild_site(repository_root: Path) -> None:
    import package_site

    package_site.ROOT = repository_root.resolve()
    package_site.main()


def check_inputs(records: list[dict[str, Any]], old_records: list[dict[str, Any]], images_dir: Path, font_path: Path) -> dict[str, Path]:
    validate_new_ids(records, old_records)
    validate_motion_strings(records, old_records)
    load_font(font_path)
    return validate_sources(records, images_dir)


def replace_batch(arguments: argparse.Namespace) -> Path | None:
    repository_root = arguments.repo_root.expanduser().resolve()
    manifest_path = resolve_existing_path(arguments.manifest, "Manifest")
    font_path = resolve_existing_path(arguments.font, "Caption font")
    records = read_exact_manifest(manifest_path)
    old_records = read_live_manifest(repository_root)
    source_paths = check_inputs(records, old_records, arguments.images_dir.expanduser(), font_path)
    source_hashes = snapshot_source_hashes(source_paths)
    if arguments.check_only:
        return None

    run_directory = unique_run_directory(arguments.originals_root.expanduser().resolve())
    copy_png_backups(records, source_paths, run_directory)
    stage_repository = run_directory / "repository-stage"
    stage_repository.mkdir(parents=True, exist_ok=True)
    copy_static_site_files(repository_root, stage_repository)
    tiles = []
    for record in records:
        with Image.open(source_paths[record["id"]]) as image:
            tile = Image.new("RGBA", image.size, "white")
            tile.alpha_composite(image.convert("RGBA"))
            tiles.append(tile.convert("RGB"))
    save_outputs(records, tiles, run_directory, stage_repository, font_path, 20)
    write_live_manifest(records, stage_repository)
    rebuild_site(stage_repository)
    validate_staged_site(records, stage_repository)
    ensure_sources_unchanged(source_paths, source_hashes)
    deploy_staged_outputs(records, run_directory, repository_root)
    cleanup_old_assets(old_records, records, repository_root)
    return run_directory


def main() -> int:
    arguments = parse_args()
    run_directory = replace_batch(arguments)
    if arguments.check_only:
        print("Preflight passed; no files were written")
    else:
        print(f"Replaced {ASSET_COUNT} GIFs and posters")
        print(f"Originals and PNG backups: {run_directory}")
        print(f"Repository: {arguments.repo_root.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit(f"error: {error}") from error
