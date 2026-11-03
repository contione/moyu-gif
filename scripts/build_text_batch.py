"""Append locally typeset developer text GIFs without an image-generation service."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_chat_assets import convert_chat
from build_emoji_assets import convert as convert_emoji
from build_gifs import ALLOWED_CATEGORIES, DEFAULT_FONT, unique_run_directory

ROOT = Path(__file__).resolve().parents[1]
SIZE = 640
FRAME_COUNT = 20
CODE_FONT = Path("C:/Windows/Fonts/consolab.ttf")
EFFECTS = {"cursor", "bounce", "stamp", "shake", "drift"}


def fit_font(lines: list[str], path: Path, maximum: int, width: int) -> ImageFont.FreeTypeFont:
    for size in range(maximum, 19, -2):
        font = ImageFont.truetype(str(path), size)
        if all(font.getbbox(line)[2] - font.getbbox(line)[0] <= width for line in lines):
            return font
    raise ValueError("Text does not fit")


def render_frames(design: dict, code_font: Path, caption_font: Path) -> list[Image.Image]:
    lines = design["lines"]
    font = fit_font(lines, code_font, 246 if len(lines) == 1 else 170, 540)
    caption = design["caption"]
    caption_lines = caption.split("，") if len(caption) > 10 else [caption]
    subtitle_font = fit_font(caption_lines, caption_font, 49, 580)
    frames = []
    for index in range(FRAME_COUNT):
        phase = 2 * math.pi * index / FRAME_COUNT
        horizontal = round(5 * math.sin(phase * 2)) if design["effect"] == "shake" else 0
        vertical = 0
        if design["effect"] == "bounce":
            vertical = round(-12 * max(0, math.sin(phase)))
        elif design["effect"] == "drift":
            vertical = round(6 * math.sin(phase))
        elif design["effect"] == "stamp" and index < 4:
            vertical = -12 + index * 4
        canvas = Image.new("RGB", (SIZE, SIZE), "white")
        draw = ImageDraw.Draw(canvas)
        line_height = 156
        first_y = 258 - (len(lines) - 1) * line_height // 2
        for line_index, line in enumerate(lines):
            draw.text((320 + horizontal, first_y + line_index * line_height + vertical), line, font=font, fill=design["color"], anchor="mm", stroke_width=1)
        if design["effect"] == "cursor":
            cursor_font = ImageFont.truetype(str(code_font), 68)
            draw.text((320, 423), "_" if index < 13 else ".", font=cursor_font, fill=design["color"], anchor="mm")
        subtitle_y = 555 if len(caption_lines) == 1 else 531
        for line_index, line in enumerate(caption_lines):
            draw.text((320, subtitle_y + line_index * 57), line, font=subtitle_font, fill="#20242C", anchor="mm")
        frames.append(canvas)
    return frames


def save_animation(frames: list[Image.Image], destination: Path) -> None:
    sample = Image.new("RGB", (SIZE, SIZE * len(frames)), "white")
    for index, frame in enumerate(frames):
        sample.paste(frame, (0, index * SIZE))
    palette = sample.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
    encoded = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    duration = [90] * len(frames)
    duration[-1] = 650
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded[0].save(destination, save_all=True, append_images=encoded[1:], duration=duration, loop=0, disposal=1, optimize=True)


def validate_designs(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    designs = document.get("items")
    if not isinstance(designs, list) or not designs:
        raise ValueError("Designs must contain a non-empty items array")
    identifiers = set()
    for design in designs:
        identifier = design.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"dev-text-[a-z0-9-]+", identifier) or identifier in identifiers:
            raise ValueError(f"Invalid or duplicate ID: {identifier}")
        identifiers.add(identifier)
        if not isinstance(design.get("lines"), list) or not 1 <= len(design["lines"]) <= 2 or any(not isinstance(line, str) or not line or len(line) > 12 or not line.isascii() for line in design["lines"]):
            raise ValueError(f"Invalid code text: {identifier}")
        if not isinstance(design.get("caption"), str) or not design["caption"] or len(design["caption"]) > 20:
            raise ValueError(f"Invalid caption: {identifier}")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", design.get("color", "")) or design.get("effect") not in EFFECTS:
            raise ValueError(f"Invalid style: {identifier}")
        if design.get("category") not in ALLOWED_CATEGORIES or not isinstance(design.get("tags"), list) or any(not isinstance(tag, str) or not tag for tag in design["tags"]):
            raise ValueError(f"Invalid metadata: {identifier}")
    return designs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--code-font", type=Path, default=CODE_FONT)
    parser.add_argument("--caption-font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    designs = validate_designs(arguments.manifest)
    live_path = ROOT / "data/gifs.json"
    previous_bytes = live_path.read_bytes()
    live = json.loads(previous_bytes)
    identifiers = {record["id"] for record in live}
    records = []
    for design in designs:
        identifier = design["id"]
        if identifier in identifiers:
            raise ValueError(f"ID already exists: {identifier}")
        record = {"id": identifier, "title": " ".join(design["lines"]) + " · " + design["caption"], "category": design["category"], "tags": ["纯文字", "程序员", "代码梗", *design["tags"]], "motion": f"文字 {design['effect']} + 阅读停顿"}
        for field, directory, suffix in (("file", "gifs", "gif"), ("poster", "posters", "webp"), ("chat", "chat", "gif"), ("emoji", "emojis", "gif")):
            record[field] = f"assets/{directory}/{identifier}.{suffix}"
            if (ROOT / record[field]).exists():
                raise ValueError(f"Output already exists: {record[field]}")
        records.append(record)
    for font in (arguments.code_font, arguments.caption_font):
        ImageFont.truetype(str(font), 48)
    outputs = (ROOT / "content/dev-text-01.json", ROOT / "content/dev-text-01-generation.json")
    if any(path.exists() for path in outputs):
        raise ValueError("Batch metadata already exists; refusing to overwrite")
    if arguments.check_only:
        print(f"Text batch preflight passed: {len(records)} designs")
        return
    originals = unique_run_directory(Path.home() / "Pictures" / "AI")
    provenance = []
    for design, record in zip(designs, records):
        frames = render_frames(design, arguments.code_font, arguments.caption_font)
        original = originals / record["file"]
        save_animation(frames, original)
        poster = originals / record["poster"]
        poster.parent.mkdir(parents=True, exist_ok=True)
        frames[10].save(poster, format="WEBP", quality=95, method=6)
        convert_chat(original, originals / record["chat"])
        convert_emoji(original, originals / record["emoji"])
        source = originals / f"{record['id']}.png"
        frames[10].save(source)
        provenance.append({"id": record["id"], "files": {field: hashlib.sha256((originals / record[field]).read_bytes()).hexdigest() for field in ("file", "poster", "chat", "emoji")}})
    if live_path.read_bytes() != previous_bytes:
        raise RuntimeError("Live manifest changed during generation; exports retained without publishing")
    for record in records:
        for field in ("file", "poster", "chat", "emoji"):
            destination = ROOT / record[field]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as target, (originals / record[field]).open("rb") as source:
                shutil.copyfileobj(source, target)
    report = {"mode": "local-text-typesetting", "new_ai_artwork": False, "fonts": [arguments.code_font.name, arguments.caption_font.name], "design_sha256": hashlib.sha256(arguments.manifest.read_bytes()).hexdigest(), "items": provenance}
    outputs[0].write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs[1].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    live_path.write_text(json.dumps(live + records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(records)} text GIFs; originals: {originals}")


if __name__ == "__main__":
    main()
