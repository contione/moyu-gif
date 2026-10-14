"""Import a maintained animated GIF into the manifest and distribution archive."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from build_gifs import ALLOWED_CATEGORIES, map_asset_path, unique_run_directory


MAX_GIF_SIZE_BYTES = 8 * 1024 * 1024
MIN_GIF_DIMENSION = 16
MAX_GIF_DIMENSION = 2048
MAX_GIF_PIXELS = 4_194_304
MANIFEST_FIELDS = {"id", "title", "category", "tags", "file", "poster", "motion"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="Source animated GIF")
    parser.add_argument("--title", required=True, help="Manifest title")
    parser.add_argument("--category", required=True, choices=sorted(ALLOWED_CATEGORIES), help="Manifest category")
    parser.add_argument("--tags", required=True, help="Comma-separated search tags")
    parser.add_argument("--id", required=True, help="Lowercase slug used for output filenames")
    parser.add_argument("--motion", default="原始动效", help="Motion description for the manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repository_root / "data" / "gifs.json",
        help="Manifest JSON path",
    )
    parser.add_argument("--repo-root", type=Path, default=repository_root, help="Repository root")
    parser.add_argument(
        "--originals-root",
        type=Path,
        default=Path.home() / "Pictures" / "AI",
        help="Root for immutable original outputs",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    raise RuntimeError(message)


def parse_tags(raw_tags: str) -> list[str]:
    tags = [tag.strip() for tag in raw_tags.split(",")]
    if not tags or any(not tag for tag in tags):
        fail("--tags must contain non-empty comma-separated values")
    if len(set(tags)) != len(tags):
        fail("--tags must not contain duplicates")
    return tags


def validate_slug(value: str) -> str:
    if not SLUG_PATTERN.fullmatch(value):
        fail("--id must be a lowercase slug using letters, numbers, and single hyphens")
    return value


def validate_gif(source_path: Path) -> Image.Image:
    if source_path.suffix.lower() != ".gif":
        fail("--file must have a .gif extension")
    try:
        file_size = source_path.stat().st_size
    except FileNotFoundError as error:
        raise RuntimeError(f"GIF not found: {source_path}") from error
    if file_size >= MAX_GIF_SIZE_BYTES:
        fail("GIF file must be smaller than 8 MB")
    try:
        image = Image.open(source_path)
    except OSError as error:
        raise RuntimeError(f"Unable to open GIF: {source_path}") from error
    if image.format != "GIF" or not image.is_animated or image.n_frames < 2:
        fail("GIF must contain at least two actual frames")
    width, height = image.size
    if (
        width < MIN_GIF_DIMENSION
        or height < MIN_GIF_DIMENSION
        or width > MAX_GIF_DIMENSION
        or height > MAX_GIF_DIMENSION
        or width * height > MAX_GIF_PIXELS
    ):
        fail("GIF dimensions are outside the supported range")
    frame_hashes = set()
    for frame_index in range(image.n_frames):
        image.seek(frame_index)
        frame_hashes.add(hash(image.convert("RGBA").tobytes()))
    if len(frame_hashes) < 2:
        fail("GIF frames must contain actual visual changes")
    image.seek(0)
    return image


def read_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        fail(f"Manifest not found: {manifest_path}")
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Manifest is not valid JSON: {manifest_path}: {error}") from error
    if not isinstance(records, list):
        fail("Manifest must be a JSON array")
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or set(record) != MANIFEST_FIELDS:
            fail(f"Manifest record {index} has an unexpected field set")
    return records


def ensure_safe_target(repository_root: Path, relative_path: PurePosixPath) -> Path:
    target = map_asset_path(repository_root, relative_path)
    if target.exists():
        fail(f"Refusing to overwrite existing file: {target}")
    return target


def write_manifest(manifest_path: Path, records: list[dict[str, Any]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_name(f".{manifest_path.name}.tmp")
    try:
        temporary_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(manifest_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def update_archive(repository_root: Path, records: list[dict[str, Any]]) -> Path:
    gif_root = repository_root / "assets" / "gifs"
    attribution_path = repository_root / "ATTRIBUTION.md"
    archive_path = repository_root / "assets" / "moyu-gifs.zip"
    if not attribution_path.is_file():
        fail(f"Required attribution file not found: {attribution_path}")
    gif_paths = [map_asset_path(repository_root, PurePosixPath(record["file"])) for record in records]
    if not gif_paths:
        fail(f"No GIFs found under: {gif_root}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_file_descriptor, temporary_path_text = tempfile.mkstemp(
        prefix=".moyu-gifs-",
        suffix=".zip",
        dir=archive_path.parent,
    )
    os.close(temporary_file_descriptor)
    temporary_path = Path(temporary_path_text)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for gif_path in gif_paths:
                archive.write(gif_path, f"gifs/{gif_path.name}")
            archive.write(attribution_path, "ATTRIBUTION.md")
        temporary_path.replace(archive_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return archive_path


def main() -> int:
    arguments = parse_args()
    source_path = arguments.file.resolve()
    validate_slug(arguments.id)
    title = arguments.title.strip()
    if not title:
        fail("--title must not be empty")
    if not arguments.motion.strip():
        fail("--motion must not be empty")
    tags = parse_tags(arguments.tags)
    source_image = validate_gif(source_path)
    records = read_manifest(arguments.manifest)
    if any(record["id"] == arguments.id for record in records):
        fail(f"Manifest already contains id: {arguments.id}")

    gif_relative_path = PurePosixPath("assets", "gifs", f"{arguments.id}.gif")
    poster_relative_path = PurePosixPath("assets", "posters", f"{arguments.id}.webp")
    target_gif = ensure_safe_target(arguments.repo_root, gif_relative_path)
    target_poster = ensure_safe_target(arguments.repo_root, poster_relative_path)
    archive_path = arguments.repo_root / "assets" / "moyu-gifs.zip"
    attribution_path = arguments.repo_root / "ATTRIBUTION.md"
    if not attribution_path.is_file():
        fail(f"Required attribution file not found: {attribution_path}")

    run_directory = unique_run_directory(arguments.originals_root)
    original_gif = map_asset_path(run_directory, gif_relative_path)
    original_poster = map_asset_path(run_directory, poster_relative_path)
    original_gif.parent.mkdir(parents=True, exist_ok=True)
    original_poster.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, original_gif)
    poster = Image.new("RGBA", source_image.size, "white")
    poster.alpha_composite(source_image.convert("RGBA"))
    poster.convert("RGB").save(original_poster, format="WEBP", quality=88, method=6)
    source_image.close()

    target_gif.parent.mkdir(parents=True, exist_ok=True)
    target_poster.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_gif, target_gif)
    shutil.copy2(original_poster, target_poster)

    records.append(
        {
            "id": arguments.id,
            "title": title,
            "category": arguments.category,
            "tags": tags,
            "file": gif_relative_path.as_posix(),
            "poster": poster_relative_path.as_posix(),
            "motion": arguments.motion.strip(),
        }
    )
    write_manifest(arguments.manifest, records)
    archive_path = update_archive(arguments.repo_root, records)
    print(f"Imported: {target_gif}")
    print(f"Poster: {target_poster}")
    print(f"Originals: {run_directory}")
    print(f"Manifest records: {len(records)}")
    print(f"Archive: {archive_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        raise SystemExit(f"error: {error}")
