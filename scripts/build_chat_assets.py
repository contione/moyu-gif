"""Build captioned 640px chat attachments and compact emoji for the entire library."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageSequence

from build_emoji_assets import content_box, convert as convert_emoji
from build_gifs import unique_run_directory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_SIZE = 640


def convert_chat(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(image)]
        durations = [frame.info.get("duration", 80) for frame in ImageSequence.Iterator(image)]
    left, top, right, bottom = content_box(frames)
    side = right - left
    output = []
    for frame in frames:
        canvas = Image.new("RGB", (side, side), "white")
        crop = (max(0, left), max(0, top), min(frame.width, right), min(frame.height, bottom))
        canvas.paste(frame.crop(crop), (crop[0] - left, crop[1] - top))
        canvas = canvas.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS)
        output.append(canvas)
    palette_samples = Image.new("RGB", (160, 160 * len(output)), "white")
    for index, frame in enumerate(output):
        palette_samples.paste(frame.resize((160, 160)), (0, index * 160))
    palette = palette_samples.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    output = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in output]
    destination.parent.mkdir(parents=True, exist_ok=True)
    output[0].save(destination, save_all=True, append_images=output[1:], duration=durations, loop=0, disposal=1, optimize=True)
    with Image.open(destination) as result:
        if result.size != (OUTPUT_SIZE, OUTPUT_SIZE) or result.n_frames < 2 or result.info.get("loop") != 0:
            raise RuntimeError(f"Invalid chat GIF: {destination}")
    if destination.stat().st_size > 8 * 1024 * 1024:
        raise RuntimeError(f"Chat GIF exceeds 8 MB: {destination}")


def main() -> None:
    manifest = ROOT / "data/gifs.json"
    records = json.loads(manifest.read_text(encoding="utf-8"))
    originals = unique_run_directory(Path.home() / "Pictures" / "AI")
    for record in records:
        identifier = record["id"]
        if not re.fullmatch(r"[a-z0-9-]+", identifier) or record["file"] != f"assets/gifs/{identifier}.gif":
            raise ValueError(f"Unsafe asset: {identifier}")
        source = ROOT / record["file"]
        for field, folder, converter in (("chat", "chat", convert_chat), ("emoji", "emojis", convert_emoji)):
            relative = f"assets/{folder}/{identifier}.gif"
            original = originals / relative
            original.parent.mkdir(parents=True, exist_ok=True)
            if field == "emoji":
                converter(source, original, remove_subtitle="纯文字" not in record.get("tags", []))
            else:
                converter(source, original)
            destination = ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
            record[field] = relative
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(records)} large chat GIFs and emoji; originals: {originals}")


if __name__ == "__main__":
    main()
