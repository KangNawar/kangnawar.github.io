#!/usr/bin/env python3
"""Make images small enough for the repo: WebP, max side, size cap, no metadata.

Examples
  python tools/image_prep.py inbox/*.jpg --out public/img/evidence/2026
  python tools/image_prep.py flyer.jpg --crop 120,340,600,500 --name 2026-11-06_indomaret_x --out public/img/evidence/2026
  python tools/image_prep.py photo.png --out public/img/products --thumb 320

- Fixes phone rotation, flattens transparency onto white, strips EXIF/GPS.
- Lowers quality step by step, then shrinks, until the file fits --max-kb.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "image"


def flatten(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def encode(img: Image.Image, max_side: int, max_kb: int, start_q: int = 80, min_q: int = 40) -> tuple[bytes, int, tuple]:
    """Return (webp bytes, quality used, size). Shrinks until it fits max_kb."""
    side = max_side
    while True:
        work = img.copy()
        work.thumbnail((side, side), Image.LANCZOS)
        for q in range(start_q, min_q - 1, -5):
            buf = io.BytesIO()
            work.save(buf, "WEBP", quality=q, method=6)  # no exif= argument -> metadata dropped
            if buf.tell() <= max_kb * 1024:
                return buf.getvalue(), q, work.size
        if side <= 160:
            return buf.getvalue(), min_q, work.size  # tiny but still too big: give up gracefully
        side = int(side * 0.85)


def process(src: Path, out_dir: Path, name: str | None, max_side: int, max_kb: int,
            crop: tuple | None, thumb: int | None) -> list[tuple[Path, int, tuple, int]]:
    with Image.open(src) as im:
        img = flatten(im)
    if crop:
        x, y, w, h = crop
        img = img.crop((x, y, x + w, y + h))
    stem = name or slugify(src.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    data, q, size = encode(img, max_side, max_kb)
    target = out_dir / f"{stem}.webp"
    target.write_bytes(data)
    written.append((target, len(data), size, q))
    if thumb:
        data, q, size = encode(img, thumb, max(8, max_kb // 4))
        t = out_dir / f"{stem}.thumb.webp"
        t.write_bytes(data)
        written.append((t, len(data), size, q))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="image files or folders")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--name", help="output name (single input only), without extension")
    ap.add_argument("--max-side", type=int, default=800)
    ap.add_argument("--max-kb", type=int, default=60)
    ap.add_argument("--crop", help="x,y,width,height in source pixels (after rotation)")
    ap.add_argument("--thumb", type=int, help="also write a <name>.thumb.webp of this max side")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for item in args.inputs:
        p = Path(item)
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED) if p.is_dir() else [p]
    if args.name and len(files) != 1:
        ap.error("--name needs exactly one input")
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    if crop and len(crop) != 4:
        ap.error("--crop needs x,y,width,height")

    total_in = total_out = 0
    failures = 0
    for f in files:
        try:
            results = process(f, Path(args.out), args.name, args.max_side, args.max_kb, crop, args.thumb)
        except Exception as exc:  # keep going through a batch
            failures += 1
            print(f"FAIL {f}: {exc}", file=sys.stderr)
            continue
        total_in += f.stat().st_size
        for path, n, size, q in results:
            total_out += n
            flag = "" if n <= args.max_kb * 1024 else "  (still over limit)"
            print(f"{f.name:<40} -> {path.name:<44} {n/1024:6.1f} KB  {size[0]}x{size[1]}  q{q}{flag}")
    if files:
        print(f"\n{len(files) - failures} images: {total_in/1048576:.1f} MB -> {total_out/1048576:.2f} MB"
              + (f", {failures} failed" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
