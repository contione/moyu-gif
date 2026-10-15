"""Build compact, tightly cropped GIFs for Google Chat custom emoji uploads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence


OUTPUT_SIZE = 128
MAX_BYTES = 256 * 1024
WHITE_THRESHOLD = 245


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=root / "content" / "duck-office-01.json")
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def content_box(frames: list[Image.Image]) -> tuple[int, int, int, int]:
    union: tuple[int, int, int, int] | None = None
    for frame in frames:
        rgb = frame.convert("RGB")
        background = Image.new("RGB", rgb.size, "white")
        difference = ImageChops.difference(rgb, background).convert("L")
        mask = difference.point(lambda value: 255 if value > 255 - WHITE_THRESHOLD else 0)
        box = mask.getbbox()
        if box is None:
            raise RuntimeError("Frame contains no visible artwork")
        union = box if union is None else (
            min(union[0], box[0]), min(union[1], box[1]), max(union[2], box[2]), max(union[3], box[3])
        )
    assert union is not None
    left, top, right, bottom = union
    width = right - left
    height = bottom - top
    side = max(width, height)
    padding = max(6, round(side * 0.06))
    side = min(max(side + padding * 2, width, height), frames[0].width, frames[0].height)
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    crop_left = max(0, min(frames[0].width - side, center_x - side // 2))
    crop_top = max(0, min(frames[0].height - side, center_y - side // 2))
    return crop_left, crop_top, crop_left + side, crop_top + side


def make_frame(frame: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    cropped = frame.convert("RGB").crop(box)
    return cropped.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)


def convert(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        frames = [frame.copy().convert("RGB").crop((0, 0, image.width, round(image.height * 0.77))) for frame in ImageSequence.Iterator(image)]
        durations = [frame.info.get("duration", 80) for frame in ImageSequence.Iterator(image)]
    box = content_box(frames)
    output_frames = [make_frame(frame, box).quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for frame in frames]
    destination.parent.mkdir(parents=True, exist_ok=True)
    output_frames[0].save(
        destination,
        format="GIF",
        save_all=True,
        append_images=output_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
        colors=128,
    )
    if destination.stat().st_size >= MAX_BYTES:
        raise RuntimeError(f"Emoji GIF exceeds 256 KB: {destination} ({destination.stat().st_size} bytes)")
    with Image.open(destination) as result:
        if result.size != (OUTPUT_SIZE, OUTPUT_SIZE) or result.n_frames < 2 or result.info.get("loop") != 0:
            raise RuntimeError(f"Invalid emoji GIF: {destination}")


def main() -> int:
    arguments = parse_args()
    root = arguments.repo_root.resolve()
    records = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise RuntimeError("Manifest must be a non-empty array")
    jobs = []
    for record in records:
        identifier = record["id"]
        source = root / record["file"]
        destination = root / "assets" / "emojis" / f"{identifier}.gif"
        if not source.is_file():
            raise RuntimeError(f"Missing source GIF: {source}")
        jobs.append((source, destination))
    if arguments.check_only:
        for _, destination in jobs:
            if not destination.is_file():
                raise RuntimeError(f"Missing emoji GIF: {destination}")
            with Image.open(destination) as image:
                if image.size != (OUTPUT_SIZE, OUTPUT_SIZE) or image.n_frames < 2 or image.info.get("loop") != 0:
                    raise RuntimeError(f"Invalid emoji GIF: {destination}")
            if destination.stat().st_size >= MAX_BYTES:
                raise RuntimeError(f"Emoji GIF exceeds 256 KB: {destination}")
        print(f"Emoji preflight passed: {len(jobs)} files")
        return 0
    for source, destination in jobs:
        convert(source, destination)
    print(f"Built {len(jobs)} compact Google Chat emoji GIFs")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise SystemExit(f"error: {error}") from error
