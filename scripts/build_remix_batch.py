"""Append new caption/motion variants using existing, attributed source artwork."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image

from append_ai_batch import read_batch_manifest
from build_gifs import DEFAULT_FONT, save_outputs, unique_run_directory

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    records = read_batch_manifest(args.manifest)
    live_path = ROOT / "data/gifs.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    identifiers = {record["id"] for record in live}
    tiles = []
    provenance = []
    for record in records:
        if record["id"] in identifiers:
            raise ValueError(f"ID already exists: {record['id']}")
        for field in ("file", "poster"):
            if (ROOT / record[field]).exists():
                raise ValueError(f"Output already exists: {record[field]}")
        source = record["source"]
        if not re.fullmatch(r"assets/source/[a-z0-9-]+\.png", source):
            raise ValueError(f"Unsafe source: {source}")
        with Image.open(ROOT / source) as image:
            tiles.append(image.convert("RGB"))
        provenance.append({"id": record["id"], "source": source, "source_sha256": hashlib.sha256((ROOT / source).read_bytes()).hexdigest()})
    originals = unique_run_directory(Path.home() / "Pictures" / "AI")
    save_outputs(records, tiles, originals, ROOT, DEFAULT_FONT, 24)
    live_path.write_text(json.dumps(live + records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"mode": "existing-artwork-caption-and-motion-remix", "new_ai_artwork": False, "frames": 24, "items": provenance}
    for item in report["items"]:
        item["gif_sha256"] = hashlib.sha256((ROOT / f"assets/gifs/{item['id']}.gif").read_bytes()).hexdigest()
    report_path = args.manifest.with_name(args.manifest.stem + "-generation.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(records)} new caption/motion GIFs; originals: {originals}")


if __name__ == "__main__":
    main()
