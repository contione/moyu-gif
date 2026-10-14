import concurrent.futures
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source"
BASE = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/"
PAIRS = [
    ("1F431", "1F4BB"), ("1F438", "2753"), ("1F439", "2705"),
    ("1F9AB", "1F4BC"), ("1F47B", "1F4A7"), ("1F43C", "1F4A5"),
    ("1F986", "1F37F"), ("1F436", "1F44D"), ("1F431", "1FAB4"),
    ("1F438", "1F4B8"), ("1F439", "2328"), ("1F9AB", "1F60E"),
    ("1F43C", "1F525"), ("1F986", "1F926"), ("1F431", "2728"),
    ("1F438", "1F44F"), ("1F47B", "1F50B"), ("1F436", "1F4A8"),
    ("1F439", "2615"), ("1F9AB", "1F6CB"), ("1F986", "1F4AC"),
    ("1F431", "1F64F"), ("1F43C", "1F381"), ("1F438", "1F389"),
]


def download(code):
    target = SOURCE / f"{code}.png"
    if not target.exists():
        request = Request(f"{BASE}{code}.png", headers={"User-Agent": "moyu-gif"})
        with urlopen(request, timeout=45) as response:
            target.write_bytes(response.read())
    with Image.open(target) as image:
        image.verify()
    return code


def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    codes = sorted({code for pair in PAIRS for code in pair})
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(download, codes))
    sheet = Image.new("RGB", (1536, 1024), "white")
    for index, (character, prop) in enumerate(PAIRS):
        tile = Image.new("RGBA", (256, 256), "white")
        with Image.open(SOURCE / f"{character}.png") as image:
            image = image.convert("RGBA")
            image = image.crop(image.getbbox()).resize((184, 184), Image.Resampling.LANCZOS)
            tile.alpha_composite(image, (22, 28))
        with Image.open(SOURCE / f"{prop}.png") as image:
            image = image.convert("RGBA")
            image = image.crop(image.getbbox())
            image.thumbnail((106, 106), Image.Resampling.LANCZOS)
            tile.alpha_composite(image, (144, 144))
        sheet.paste(tile.convert("RGB"), ((index % 6) * 256, (index // 6) * 256))
    archive = Path.home() / "Pictures" / "AI" / f"moyu-source-{datetime.now():%Y%m%d-%H%M%S-%f}"
    archive.mkdir(parents=True, exist_ok=False)
    path = archive / "openmoji-sheet.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
