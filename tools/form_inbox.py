#!/usr/bin/env python3
"""Turn new Google Form responses into a draft batch for review. Nothing runs on its own.

1. In the response Sheet: File > Download > Comma-separated values (.csv)
2. python tools/form_inbox.py "Kang Nawar kiriman.csv"
3. Open the batch it writes (inbox/form-<date>/batch.json), fill in the TODO
   fields from the photo and link (brand, size, category, store), delete rows
   you don't want, then run tools/batch_import.py on it as usual.

The form has four questions: product name, price, photo, product link. Columns
are found by their titles (any title containing "produk"/"product"/"nama",
"harga"/"price", "foto"/"photo", "link"/"url"). The script remembers how many
rows it has handled in inbox/form-state.json, so each run only picks up new
responses. Use --all to start over.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kn_data import REPO_ROOT  # noqa: E402

TODO = "TODO"


def find_col(headers: list[str], *words: str) -> int | None:
    for i, h in enumerate(headers):
        if any(w in h.lower() for w in words):
            return i
    return None


def parse_price(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text.split(",")[0])  # "Rp 23.900,00" -> 23900
    return int(digits) if digits else None


def parse_timestamp(text: str, dayfirst: bool) -> str | None:
    """Google Sheets writes '07/11/2026 1:23:45' (Indonesian locale) or '11/7/2026 1:23:45' (US)."""
    m = re.match(r"(\d{1,4})[/-](\d{1,2})[/-](\d{2,4})", text.strip())
    if not m:
        return None
    a, b, c = (int(x) for x in m.groups())
    if a > 31:                       # 2026-11-07
        y, mo, d = a, b, c
    elif dayfirst:
        d, mo, y = a, b, c
    else:
        mo, d, y = a, b, c
    try:
        return date(y if y > 99 else 2000 + y, mo, d).isoformat()
    except ValueError:
        return None


def guess_store(url: str) -> tuple[str, str]:
    """(store id, channel) from a product link, TODO if unknown."""
    hosts = {"shopee": "shopee", "tokopedia": "tokopedia", "tiktok": "tiktok-shop", "lazada": "lazada",
             "blibli": "blibli", "astronauts": "astro", "klikindomaret": "indomaret", "alfagift": "alfamart",
             "sociolla": "sociolla", "watsons": "watsons", "guardian": "guardian", "superindo": "superindo",
             "ikea": "ikea", "informa": "informa", "azko": "azko"}
    for key, store in hosts.items():
        if key in url.lower():
            return store, "online"
    return TODO, TODO


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="responses downloaded from the Sheet as CSV")
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--all", action="store_true", help="ignore the remembered position and take every row")
    ap.add_argument("--us-dates", action="store_true", help="timestamps are month/day (US locale sheet)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    state_path = root / "inbox" / "form-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() and not args.all else {"rows_done": 0}

    with open(args.csv, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        print("The CSV is empty.")
        return 1
    headers, data = rows[0], rows[1:]
    col = {
        "time": find_col(headers, "timestamp", "stempel", "waktu"),
        "name": find_col(headers, "produk", "product", "nama"),
        "price": find_col(headers, "harga", "price"),
        "photo": find_col(headers, "foto", "photo", "gambar"),
        "link": find_col(headers, "link", "url", "tautan"),
    }
    if col["name"] is None or col["price"] is None:
        print(f"Could not find the product name and price columns in: {headers}")
        return 1

    new = data[state["rows_done"]:]
    if not new:
        print(f"No new responses ({len(data)} rows, all handled before).")
        return 0

    get = lambda r, k: (r[col[k]].strip() if col[k] is not None and col[k] < len(r) else "")  # noqa: E731
    items, skipped = [], []
    for n, r in enumerate(new, start=state["rows_done"] + 2):  # +2 = sheet row number (header is row 1)
        name, price = get(r, "name"), parse_price(get(r, "price"))
        if not name or not price:
            skipped.append({"row": n, "text": f"{name} {get(r, 'price')}".strip(), "reason": "No product name or price"})
            continue
        link, photo = get(r, "link"), get(r, "photo")
        store, channel = guess_store(link)
        seen = parse_timestamp(get(r, "time"), dayfirst=not args.us_dates) or date.today().isoformat()
        item = {
            "row": n,
            "as_submitted": name,
            "brand": TODO, "name": name, "size": TODO, "cat": TODO,
            "store": store, "channel": channel, "seen_on": seen,
            "price": price,
            "promo": "regular",
            "source_type": "link" if link else "photo",
        }
        if link:
            item["url"] = link
        if photo:
            item["photo"] = photo  # Drive link, private: for the reviewer only, not imported
        items.append(item)

    today = date.today().isoformat()
    out_dir = root / "inbox" / f"form-{today}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "batch.json"
    batch = {
        "batch": f"form-{today}",
        "description": f"Kiriman formulir, baris {state['rows_done'] + 2}-{len(data) + 1}",
        "defaults": {"store": TODO, "channel": "offline", "seen_on": today, "source_type": "photo",
                     "contributor": "Formulir"},
        "items": items,
        "skipped": skipped,
    }
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"rows_done": len(data), "updated": datetime.now().isoformat(timespec="seconds")}) + "\n")

    print(f"{len(items)} new responses -> {out}")
    for it in items:
        print(f"  row {it['row']:>4}  Rp{it['price']:>9,}  {it['store']:<10} {it['as_submitted'][:50]}".replace(",", "."))
    if skipped:
        print(f"  {len(skipped)} rows skipped (no name or price)")
    print("\nNext: open the batch, replace every TODO (brand, size, cat, store), set \"promo\" if the photo shows one,")
    print("delete rows you don't want, then:  python tools/batch_import.py " + str(out.relative_to(root)) + " --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
