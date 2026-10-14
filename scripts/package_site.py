import json
import re
import shutil
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def main():
    records = json.loads((ROOT / "data/gifs.json").read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest must be a non-empty array")
    seen = set()
    sources = []
    for record in records:
        identifier = record["id"]
        if not re.fullmatch(r"[a-z0-9-]+", identifier) or identifier in seen:
            raise ValueError(f"Invalid or duplicate id: {identifier}")
        seen.add(identifier)
        if not isinstance(record.get("title"), str) or not record["title"].strip():
            raise ValueError(f"Missing title: {identifier}")
        if not isinstance(record.get("category"), str) or not record["category"].strip():
            raise ValueError(f"Missing category: {identifier}")
        if not isinstance(record.get("tags"), list) or any(not isinstance(tag, str) for tag in record["tags"]):
            raise ValueError(f"Invalid tags: {identifier}")
        for field, pattern in (("file", r"assets/gifs/[a-z0-9-]+\.gif"), ("poster", r"assets/posters/[a-z0-9-]+\.(webp|png|jpg)")):
            relative = record[field]
            if not re.fullmatch(pattern, relative):
                raise ValueError(f"Unsafe asset path: {relative}")
            source = ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(source)
            sources.append(source)
        gif = ROOT / record["file"]
        if gif.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"GIF over 8 MB: {identifier}")
        with Image.open(gif) as image:
            if image.format != "GIF" or image.n_frames < 2:
                raise ValueError(f"Not animated GIF: {identifier}")
            if max(image.size) > 2048:
                raise ValueError(f"GIF too large: {identifier}")
            hashes = set()
            for frame in range(image.n_frames):
                image.seek(frame)
                hashes.add(hash(image.convert("RGB").tobytes()))
            if len(hashes) < 2:
                raise ValueError(f"All frames identical: {identifier}")
        with Image.open(ROOT / record["poster"]) as image:
            image.verify()
    archive = ROOT / "assets/moyu-gifs.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for record in records:
            bundle.write(ROOT / record["file"], f"gifs/{record['id']}.gif")
        bundle.write(ROOT / "ATTRIBUTION.md", "ATTRIBUTION.md")
    target = ROOT / "_site"
    if target.exists():
        if target.resolve() != ROOT.resolve() / "_site" or target.is_symlink():
            raise ValueError("Unsafe build directory")
        shutil.rmtree(target)
    target.mkdir()
    for filename in ("index.html", "styles.css", "app.js", "favicon.svg", ".nojekyll", "ATTRIBUTION.md", "data/gifs.json", "assets/moyu-gifs.zip"):
        sources.append(ROOT / filename)
    for source in sources:
        destination = target / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print(f"Validated {len(records)} animated GIFs, created ZIP and static site: {target}")


if __name__ == "__main__":
    main()
