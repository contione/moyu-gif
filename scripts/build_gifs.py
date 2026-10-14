"""Build captioned reaction GIFs from a 6 x 4 illustration sheet."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageDraw, ImageFont


SHEET_COLUMNS = 6
SHEET_ROWS = 4
ASSET_COUNT = SHEET_COLUMNS * SHEET_ROWS
OUTPUT_WIDTH = 320
OUTPUT_HEIGHT = 320
CHARACTER_AREA_HEIGHT = 246
CAPTION_AREA_HEIGHT = OUTPUT_HEIGHT - CHARACTER_AREA_HEIGHT
FRAME_DURATION_MS = 80
DEFAULT_FRAMES = 20
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
WHITE = (255, 255, 255)
WHITE_THRESHOLD = 24
DEFAULT_FONT = Path(r"C:\Windows\Fonts\msyhbd.ttc")
ALLOWED_CATEGORIES = {"打工日常", "情绪发疯", "快乐吃瓜", "社交必备"}
REQUIRED_FIELDS = {"id", "title", "category", "tags", "file", "poster", "motion"}


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", required=True, type=Path, help="6-column by 4-row illustration sheet")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repository_root / "data" / "gifs.json",
        help="GIF manifest JSON path",
    )
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT, help="Caption font, default: Windows msyhbd.ttc")
    parser.add_argument(
        "--originals-root",
        type=Path,
        default=Path.home() / "Pictures" / "AI",
        help="Root for immutable original outputs",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repository_root,
        help="Repository root receiving copied assets",
    )
    parser.add_argument(
        "--frames",
        type=int,
        choices=(16, 20),
        default=DEFAULT_FRAMES,
        help="Frames per GIF (16 or 20)",
    )
    return parser.parse_args()


def read_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"Manifest not found: {manifest_path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Manifest is not valid JSON: {manifest_path}: {error}") from error

    if not isinstance(records, list) or len(records) < ASSET_COUNT:
        raise RuntimeError(f"Manifest must be a JSON array with at least {ASSET_COUNT} records")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_posters: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict) or set(record) != REQUIRED_FIELDS:
            raise RuntimeError(f"Manifest record {index} must contain exactly: {sorted(REQUIRED_FIELDS)}")
        record_id = record["id"]
        if not isinstance(record_id, str) or not record_id or record_id in seen_ids:
            raise RuntimeError(f"Manifest record {index} has an invalid or duplicate id")
        seen_ids.add(record_id)
        if not isinstance(record["title"], str) or not record["title"]:
            raise RuntimeError(f"Manifest record {index} has an empty title")
        if record["category"] not in ALLOWED_CATEGORIES:
            raise RuntimeError(f"Manifest record {index} uses an unsupported category")
        if not isinstance(record["tags"], list) or not all(isinstance(tag, str) and tag for tag in record["tags"]):
            raise RuntimeError(f"Manifest record {index} tags must be a non-empty string array")
        if not isinstance(record["motion"], str) or not record["motion"]:
            raise RuntimeError(f"Manifest record {index} has an empty motion description")
        for field_name, expected_directory, expected_suffix, seen_paths in (
            ("file", "gifs", ".gif", seen_files),
            ("poster", "posters", ".webp", seen_posters),
        ):
            asset_path = relative_asset_path(record[field_name])
            if (
                asset_path.is_absolute()
                or len(asset_path.parts) != 3
                or asset_path.parts[0] != "assets"
                or asset_path.parts[1] != expected_directory
                or asset_path.suffix.lower() != expected_suffix
            ):
                raise RuntimeError(f"Manifest record {index} has an invalid {field_name} path")
            normalized_path = asset_path.as_posix()
            if normalized_path in seen_paths:
                raise RuntimeError(f"Manifest contains duplicate {field_name} paths")
            seen_paths.add(normalized_path)
    return records


def relative_asset_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeError(f"Asset path must use safe POSIX separators: {value!r}")
    asset_path = PurePosixPath(value)
    if asset_path.is_absolute() or any(part in {"", ".", ".."} for part in asset_path.parts):
        raise RuntimeError(f"Asset path must stay relative: {value!r}")
    if asset_path.as_posix() != value:
        raise RuntimeError(f"Asset path must be normalized POSIX text: {value!r}")
    return asset_path


def map_asset_path(root: Path, relative_path: PurePosixPath) -> Path:
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        raise RuntimeError(f"Asset path must be a normalized relative path: {relative_path}")
    root_resolved = root.resolve()
    candidate = root.joinpath(*relative_path.parts)
    try:
        candidate.resolve().relative_to(root_resolved)
    except ValueError as error:
        raise RuntimeError(f"Asset path escapes root: {relative_path}") from error
    return candidate


def load_font(font_path: Path) -> ImageFont.FreeTypeFont:
    if not font_path.is_file():
        raise RuntimeError(f"Caption font not found: {font_path}. Pass an installed font with --font.")
    try:
        return ImageFont.truetype(str(font_path), 48, index=0)
    except OSError as error:
        raise RuntimeError(f"Unable to load caption font: {font_path}") from error


def crop_sheet(sheet_path: Path) -> list[Image.Image]:
    try:
        sheet = Image.open(sheet_path).convert("RGB")
    except FileNotFoundError as error:
        raise RuntimeError(f"Sheet not found: {sheet_path}") from error
    except OSError as error:
        raise RuntimeError(f"Unable to open sheet: {sheet_path}") from error

    if sheet.width < SHEET_COLUMNS or sheet.height < SHEET_ROWS:
        raise RuntimeError("Sheet must contain at least a 6 x 4 pixel grid")
    if sheet.width % SHEET_COLUMNS or sheet.height % SHEET_ROWS:
        raise RuntimeError("Sheet width and height must divide evenly into exactly 6 columns and 4 rows")

    tile_width = sheet.width // SHEET_COLUMNS
    tile_height = sheet.height // SHEET_ROWS
    return [
        sheet.crop(
            (
                column * tile_width,
                row * tile_height,
                (column + 1) * tile_width,
                (row + 1) * tile_height,
            )
        )
        for row in range(SHEET_ROWS)
        for column in range(SHEET_COLUMNS)
    ]


def remove_edge_white(tile: Image.Image) -> Image.Image:
    """Make only edge-connected near-white pixels transparent."""
    working = tile.convert("RGB")
    marker = (255, 0, 255)
    edge_seeds = {(x, 0) for x in range(working.width)}
    edge_seeds.update((x, working.height - 1) for x in range(working.width))
    edge_seeds.update((0, y) for y in range(working.height))
    edge_seeds.update((working.width - 1, y) for y in range(working.height))
    for seed in edge_seeds:
        if working.getpixel(seed) != marker:
            ImageDraw.floodfill(working, seed, marker, thresh=WHITE_THRESHOLD)

    raw_pixels = working.tobytes()
    alpha_bytes = bytes(
        0
        if raw_pixels[index] == marker[0]
        and raw_pixels[index + 1] == marker[1]
        and raw_pixels[index + 2] == marker[2]
        else 255
        for index in range(0, len(raw_pixels), 3)
    )
    alpha = Image.frombytes("L", working.size, alpha_bytes)
    bounding_box = alpha.getbbox()
    if bounding_box is None:
        return tile.convert("RGBA")

    padding = max(4, round(min(tile.size) * 0.02))
    left = max(0, bounding_box[0] - padding)
    top = max(0, bounding_box[1] - padding)
    right = min(tile.width, bounding_box[2] + padding)
    bottom = min(tile.height, bounding_box[3] + padding)
    foreground = tile.convert("RGBA").crop((left, top, right, bottom))
    foreground.putalpha(alpha.crop((left, top, right, bottom)))
    return foreground


def prepare_character(tile: Image.Image) -> Image.Image:
    character = remove_edge_white(tile)
    character.thumbnail((220, 178), Image.Resampling.LANCZOS)
    return character


def oscillation(frame_index: int, frame_count: int, cycles: float = 1.0) -> float:
    return math.sin(2 * math.pi * cycles * frame_index / frame_count)


def animate_character(character: Image.Image, motion: str, frame_index: int, frame_count: int) -> tuple[Image.Image, int, int]:
    phase = oscillation(frame_index, frame_count)
    transformed = character
    horizontal_offset = 0
    vertical_offset = 0

    if "跑开" in motion:
        horizontal_offset = round(52 * frame_index / (frame_count - 1))
    elif "慢移" in motion:
        horizontal_offset = round(20 * phase)
    elif "靠近" in motion:
        horizontal_offset = round(18 * (1 - frame_index / (frame_count - 1)))
    elif "探头" in motion:
        horizontal_offset = round(12 * phase)
    elif "摇晃" in motion:
        horizontal_offset = round(10 * phase)
    elif "震动" in motion or "颤抖" in motion:
        horizontal_offset = round((7 if "剧烈" in motion else 3) * phase)
    elif "旋转" in motion or "摇头" in motion or "打转" in motion:
        horizontal_offset = round(4 * phase)

    if "弹跳" in motion or "跳舞" in motion or "鼓掌" in motion:
        vertical_offset = round(-12 * abs(phase))
    elif "下坠" in motion or "下沉" in motion:
        vertical_offset = round(15 * frame_index / (frame_count - 1))
    elif "漂浮" in motion:
        vertical_offset = round(8 * phase)
    elif "点头" in motion:
        vertical_offset = round(6 * phase)

    if "摇头" in motion or "旋转" in motion or "打转" in motion or "鞠躬" in motion:
        angle = 16 * phase if "打转" in motion else 10 * phase
        transformed = character.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    elif "融化" in motion:
        scale = 1.0 - 0.16 * max(0.0, frame_index / (frame_count - 1))
        transformed = character.resize(
            (character.width, max(1, round(character.height * scale))),
            Image.Resampling.BICUBIC,
        )

    return transformed, horizontal_offset, vertical_offset


def draw_star(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, radius: int, fill: tuple[int, int, int, int]) -> None:
    points = []
    for point_index in range(10):
        angle = -math.pi / 2 + point_index * math.pi / 5
        point_radius = radius if point_index % 2 == 0 else radius // 2
        points.append((center_x + round(math.cos(angle) * point_radius), center_y + round(math.sin(angle) * point_radius)))
    draw.polygon(points, fill=fill)


def draw_heart(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, size: int, fill: tuple[int, int, int, int]) -> None:
    draw.ellipse((center_x - size, center_y - size // 2, center_x, center_y + size // 2), fill=fill)
    draw.ellipse((center_x, center_y - size // 2, center_x + size, center_y + size // 2), fill=fill)
    draw.polygon(
        [(center_x - size, center_y), (center_x + size, center_y), (center_x, center_y + size * 2)],
        fill=fill,
    )


def draw_motion_overlay(
    canvas: Image.Image,
    motion: str,
    frame_index: int,
    frame_count: int,
    character_box: tuple[int, int, int, int],
) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    left, top, right, bottom = character_box
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    phase = oscillation(frame_index, frame_count)

    if "闪动" in motion or "亮点" in motion or "闪光" in motion:
        draw_star(draw, min(306, right + 14), max(18, top + 18), 8, (255, 199, 0, 220))
        draw_star(draw, max(14, left - 14), min(228, bottom - 12), 5, (255, 125, 36, 220))
    if "惊叹号" in motion:
        draw.text((center_x + 84, max(18, top + 4)), "!", fill=(230, 57, 45, 240), anchor="mm", stroke_width=1)
    if "对勾" in motion:
        draw.line((right - 4, top + 20, right + 8, top + 32, right + 28, top + 4), fill=(43, 160, 85, 230), width=5, joint="curve")
    if "汗滴" in motion:
        drop_x = min(303, right + 9)
        drop_y = min(230, top + 38 + round(8 * phase))
        draw.ellipse((drop_x - 4, drop_y - 8, drop_x + 4, drop_y + 3), fill=(73, 166, 230, 210))
        draw.polygon([(drop_x - 4, drop_y), (drop_x + 4, drop_y), (drop_x, drop_y - 10)], fill=(73, 166, 230, 210))
    if "爆炸线" in motion:
        for line_index in range(8):
            angle = 2 * math.pi * line_index / 8
            start_radius = max(right - left, bottom - top) // 2 + 7
            end_radius = start_radius + 14
            draw.line(
                (
                    center_x + round(math.cos(angle) * start_radius),
                    center_y + round(math.sin(angle) * start_radius),
                    center_x + round(math.cos(angle) * end_radius),
                    center_y + round(math.sin(angle) * end_radius),
                ),
                fill=(239, 91, 55, 200),
                width=3,
            )
    if "残影" in motion or "速度线" in motion or "键盘线" in motion or "警报线" in motion:
        line_color = (120, 120, 120, 145) if "残影" in motion else (227, 91, 62, 170)
        for line_index in range(3):
            line_y = min(236, top + 30 + line_index * 18)
            draw.line((max(8, left - 38), line_y, max(14, left - 6), line_y), fill=line_color, width=3)
    if "爆米花" in motion:
        for offset_x, offset_y in ((-30, -36), (20, -48), (48, -20)):
            pop_x = max(10, min(310, center_x + offset_x))
            pop_y = max(15, min(232, center_y + offset_y + round(8 * phase)))
            draw.ellipse((pop_x - 5, pop_y - 5, pop_x + 5, pop_y + 5), fill=(255, 221, 104, 230))
    if "烟雾" in motion or "蒸汽" in motion:
        smoke_color = (150, 150, 150, 120)
        for offset_x, offset_y in ((-18, -42), (2, -57), (22, -44)):
            smoke_x = max(10, min(310, center_x + offset_x + round(5 * phase)))
            smoke_y = max(18, center_y + offset_y)
            draw.ellipse((smoke_x - 8, smoke_y - 6, smoke_x + 8, smoke_y + 6), outline=smoke_color, width=3)
    if "心形" in motion or "心形飘起" in motion:
        heart_y = max(18, top - 12 - round(20 * (frame_index / frame_count)))
        draw_heart(draw, min(304, right + 13), heart_y, 6, (236, 82, 116, 220))
    if "问号" in motion:
        draw.text((max(16, left - 18), max(20, top + 10)), "?", fill=(102, 75, 185, 230), anchor="mm", stroke_width=1)
    if "气泡" in motion:
        bubble_left = min(242, max(12, right - 10))
        bubble_top = max(12, top - 36)
        draw.rounded_rectangle((bubble_left, bubble_top, min(310, bubble_left + 58), bubble_top + 28), radius=9, fill=(255, 255, 255, 235), outline=(50, 50, 50, 180), width=2)
        draw.ellipse((bubble_left + 13, bubble_top + 11, bubble_left + 17, bubble_top + 15), fill=(50, 50, 50, 210))
        draw.ellipse((bubble_left + 27, bubble_top + 11, bubble_left + 31, bubble_top + 15), fill=(50, 50, 50, 210))
        draw.ellipse((bubble_left + 41, bubble_top + 11, bubble_left + 45, bubble_top + 15), fill=(50, 50, 50, 210))
    if "彩带" in motion:
        draw.arc((max(6, left - 20), max(12, top - 20), min(316, right + 24), min(240, bottom + 30)), 200, 330, fill=(75, 151, 218, 220), width=4)
        draw.arc((max(6, left - 10), max(12, top - 20), min(316, right + 34), min(240, bottom + 30)), 205, 335, fill=(241, 105, 104, 220), width=4)


def fit_caption_font(title: str, font_path: Path) -> ImageFont.FreeTypeFont:
    for size in range(50, 19, -2):
        font = ImageFont.truetype(str(font_path), size, index=0)
        bounds = font.getbbox(title)
        if bounds[2] - bounds[0] <= OUTPUT_WIDTH - 28 and bounds[3] - bounds[1] <= CAPTION_AREA_HEIGHT - 14:
            return font
    return ImageFont.truetype(str(font_path), 20, index=0)


def build_frame(
    character: Image.Image,
    title: str,
    motion: str,
    frame_index: int,
    frame_count: int,
    caption_font: ImageFont.FreeTypeFont,
) -> Image.Image:
    transformed, horizontal_offset, vertical_offset = animate_character(character, motion, frame_index, frame_count)
    max_x = OUTPUT_WIDTH - transformed.width
    max_y = CHARACTER_AREA_HEIGHT - transformed.height
    base_x = max(0, max_x // 2)
    base_y = max(0, max_y // 2)
    character_x = max(0, min(max_x, base_x + horizontal_offset))
    character_y = max(0, min(max_y, base_y + vertical_offset))

    top_area = Image.new("RGBA", (OUTPUT_WIDTH, CHARACTER_AREA_HEIGHT), WHITE + (255,))
    top_area.alpha_composite(transformed, (character_x, character_y))
    draw_motion_overlay(
        top_area,
        motion,
        frame_index,
        frame_count,
        (character_x, character_y, character_x + transformed.width, character_y + transformed.height),
    )

    frame = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), WHITE)
    frame.paste(top_area.convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(frame)
    draw.text(
        (OUTPUT_WIDTH // 2, CHARACTER_AREA_HEIGHT + CAPTION_AREA_HEIGHT // 2),
        title,
        font=caption_font,
        fill=(0, 0, 0),
        anchor="mm",
    )
    return frame


def unique_run_directory(originals_root: Path) -> Path:
    originals_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    candidate = originals_root / timestamp
    suffix = 1
    while candidate.exists():
        candidate = originals_root / f"{timestamp}-{suffix:02d}"
        suffix += 1
    (candidate / "assets" / "gifs").mkdir(parents=True)
    (candidate / "assets" / "posters").mkdir(parents=True)
    return candidate


def quantize_gif_frames(frames: list[Image.Image]) -> list[Image.Image]:
    palette_source = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT * len(frames)), WHITE)
    for frame_index, frame in enumerate(frames):
        palette_source.paste(frame, (0, frame_index * OUTPUT_HEIGHT))
    palette = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    return [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]


def save_outputs(
    records: list[dict[str, Any]],
    tiles: list[Image.Image],
    run_directory: Path,
    repository_root: Path,
    font_path: Path,
    frame_count: int,
) -> None:
    prepared_characters = [prepare_character(tile) for tile in tiles]
    for record, character in zip(records, prepared_characters):
        caption_font = fit_caption_font(record["title"], font_path)
        frames = [
            build_frame(character, record["title"], record["motion"], frame_index, frame_count, caption_font)
            for frame_index in range(frame_count)
        ]
        gif_relative_path = relative_asset_path(record["file"])
        poster_relative_path = relative_asset_path(record["poster"])
        original_gif = map_asset_path(run_directory, gif_relative_path)
        original_poster = map_asset_path(run_directory, poster_relative_path)
        original_gif.parent.mkdir(parents=True, exist_ok=True)
        original_poster.parent.mkdir(parents=True, exist_ok=True)
        gif_frames = quantize_gif_frames(frames)
        gif_frames[0].save(
            original_gif,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=FRAME_DURATION_MS,
            loop=0,
            disposal=2,
            optimize=False,
            colors=256,
        )
        frames[0].save(original_poster, format="WEBP", quality=88, method=6)
        file_size = original_gif.stat().st_size
        if file_size >= MAX_FILE_SIZE_BYTES:
            raise RuntimeError(f"Generated GIF exceeds 2 MB: {original_gif} ({file_size} bytes)")

    for record in records:
        for field_name in ("file", "poster"):
            relative_path = relative_asset_path(record[field_name])
            source = run_directory / relative_path
            destination = map_asset_path(repository_root, relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def main() -> int:
    arguments = parse_args()
    records = read_manifest(arguments.manifest)
    sheet_records = records[:ASSET_COUNT]
    load_font(arguments.font)
    tiles = crop_sheet(arguments.sheet)
    run_directory = unique_run_directory(arguments.originals_root)
    save_outputs(sheet_records, tiles, run_directory, arguments.repo_root, arguments.font, arguments.frames)
    print(f"Built {len(sheet_records)} GIFs and posters")
    print(f"Originals: {run_directory}")
    print(f"Repository assets: {arguments.repo_root / 'assets'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        raise SystemExit(f"error: {error}")
