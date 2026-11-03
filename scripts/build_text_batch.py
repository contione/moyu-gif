"""Build centered, code-only developer GIFs without an image-generation service."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_emoji_assets import convert as convert_emoji
from build_gifs import ALLOWED_CATEGORIES, unique_run_directory

ROOT = Path(__file__).resolve().parents[1]
SIZE = 640
FRAME_COUNT = 20
CODE_FONT = Path("C:/Windows/Fonts/consolab.ttf")
EFFECTS = {"cursor", "bounce", "stamp", "shake", "drift"}


def render_frames(design: dict, code_font: Path) -> list[Image.Image]:
    font = ImageFont.truetype(str(code_font), 300)
    glyphs = []
    for line in design["lines"]:
        bounds = font.getbbox(line, stroke_width=3)
        glyph = Image.new("RGBA", (bounds[2] - bounds[0], bounds[3] - bounds[1]), (255, 255, 255, 0))
        ImageDraw.Draw(glyph).text((-bounds[0], -bounds[1]), line, font=font, fill=design["color"], stroke_width=3)
        glyphs.append(glyph.crop(glyph.getbbox()))
    gap = 28
    ink = Image.new("RGBA", (max(glyph.width for glyph in glyphs), sum(glyph.height for glyph in glyphs) + gap * (len(glyphs) - 1)), (255, 255, 255, 0))
    offset = 0
    for glyph in glyphs:
        ink.alpha_composite(glyph, ((ink.width - glyph.width) // 2, offset))
        offset += glyph.height + gap
    scale = min(584 / ink.width, 520 / ink.height)
    width = round(ink.width * scale)
    height = round(ink.height * scale)
    if len(glyphs) == 1:
        height = min(420, round(height * 1.55))
    ink = ink.resize((width, height), Image.Resampling.LANCZOS)
    frames = []
    for index in range(FRAME_COUNT):
        phase = 2 * math.pi * index / FRAME_COUNT
        horizontal = round(3 * math.sin(phase * 2)) if design["effect"] == "shake" else 0
        vertical = round(4 * math.sin(phase)) if design["effect"] in {"bounce", "drift", "cursor"} else 0
        if design["effect"] == "stamp" and index < 4:
            vertical = -6 + index * 2
        canvas = Image.new("RGB", (SIZE, SIZE), "white")
        canvas.paste(ink, ((SIZE - width) // 2 + horizontal, (SIZE - height) // 2 + vertical), ink)
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
    parser.add_argument("--replace", action="store_true", help="Replace only existing batch IDs; preserve backups")
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
        if arguments.replace and identifier not in identifiers:
            raise ValueError(f"Cannot replace unknown ID: {identifier}")
        if not arguments.replace and identifier in identifiers:
            raise ValueError(f"ID already exists: {identifier}")
        record = {"id": identifier, "title": " ".join(design["lines"]) + " · " + design["caption"], "category": design["category"], "tags": ["纯文字", "程序员", "代码梗", *design["tags"]], "motion": f"文字 {design['effect']} + 阅读停顿"}
        for field, directory, suffix in (("file", "gifs", "gif"), ("poster", "posters", "webp"), ("chat", "chat", "gif"), ("emoji", "emojis", "gif")):
            record[field] = f"assets/{directory}/{identifier}.{suffix}"
            if (ROOT / record[field]).exists() and not arguments.replace:
                raise ValueError(f"Output already exists: {record[field]}")
        records.append(record)
    ImageFont.truetype(str(arguments.code_font), 48)
    outputs = (ROOT / "content/dev-text-01.json", ROOT / "content/dev-text-01-generation.json")
    if not arguments.replace and any(path.exists() for path in outputs):
        raise ValueError("Batch metadata already exists; refusing to overwrite")
    if arguments.check_only:
        print(f"Text batch preflight passed: {len(records)} designs")
        return
    originals = unique_run_directory(Path.home() / "Pictures" / "AI")
    if arguments.replace:
        for record in records:
            for field in ("file", "poster", "chat", "emoji"):
                source = ROOT / record[field]
                destination = originals / "previous" / record[field]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        for source in (*outputs, live_path):
            destination = originals / "previous" / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    provenance = []
    for design, record in zip(designs, records):
        frames = render_frames(design, arguments.code_font)
        original = originals / record["file"]
        save_animation(frames, original)
        poster = originals / record["poster"]
        poster.parent.mkdir(parents=True, exist_ok=True)
        frames[10].save(poster, format="WEBP", quality=95, method=6)
        chat = originals / record["chat"]
        chat.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, chat)
        convert_emoji(original, originals / record["emoji"], remove_subtitle=False)
        source = originals / f"{record['id']}.png"
        frames[10].save(source)
        provenance.append({"id": record["id"], "files": {field: hashlib.sha256((originals / record[field]).read_bytes()).hexdigest() for field in ("file", "poster", "chat", "emoji")}})
    if live_path.read_bytes() != previous_bytes:
        raise RuntimeError("Live manifest changed during generation; exports retained without publishing")
    for record in records:
        for field in ("file", "poster", "chat", "emoji"):
            destination = ROOT / record[field]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if arguments.replace:
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                with temporary.open("xb") as target, (originals / record[field]).open("rb") as source:
                    shutil.copyfileobj(source, target)
                temporary.replace(destination)
            else:
                with destination.open("xb") as target, (originals / record[field]).open("rb") as source:
                    shutil.copyfileobj(source, target)
    report = {"mode": "local-text-typesetting", "new_ai_artwork": False, "fonts": [arguments.code_font.name], "layout": "centered-code-only-large-type", "design_sha256": hashlib.sha256(arguments.manifest.read_bytes()).hexdigest(), "items": provenance}
    outputs[0].write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs[1].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replacements = {record["id"]: record for record in records}
    merged = [replacements.get(record["id"], record) for record in live] if arguments.replace else live + records
    live_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(records)} text GIFs; originals and previous versions: {originals}")


if __name__ == "__main__":
    main()
