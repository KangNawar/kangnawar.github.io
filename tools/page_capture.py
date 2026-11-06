#!/usr/bin/env python3
"""Turn a captured shop page into a draft batch for review. Nothing runs on its own.

For shops whose prices live on their website rather than in a printed catalogue
(IKEA, Informa, AZKO, brand stores, marketplaces). Two kinds of input:

  harga-<site>-<date>.json   from the "Ambil harga" bookmarklet (see /infoadmin/).
                             Best option: it reads the page as the browser shows it,
                             so prices loaded by JavaScript are included.
  page.html / page.mhtml     a page saved with Ctrl+S. Only the structured
                             schema.org data inside it is read (product pages
                             usually have it; listing pages often don't).

Run:  python tools/page_capture.py inbox/ikea-2026-11/harga-ikea.co.id-2026-11-07.json [--store ikea]
      [--out inbox/ikea-2026-11/batch.json] [--valid-until 2026-11-30]

The draft has one item per product card with a price. Price and strikethrough
price, link and badge % are filled in; brand, size and category are TODO when
they can't be read. Check every item against the page, fix the TODOs, delete
what you don't want, then run tools/batch_import.py on it as usual.

Printing a page to PDF also works as evidence (treat it like a catalogue), but
links are lost and pages that load as you scroll print only what was loaded.
"""
from __future__ import annotations

import argparse
import email
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from form_inbox import guess_store  # noqa: E402
from kn_data import REPO_ROOT  # noqa: E402

TODO = "TODO"
PRICE_RE = re.compile(r"Rp\.?\s?(\d{1,3}(?:[.,]\d{3})+|\d+)(?:,\d{2})?(?!\d)", re.I)
BADGE_RE = re.compile(r"(?:-|hemat\s*|diskon\s*|disc\.?\s*)?(\d{1,2})\s?%", re.I)
SIZE_RE = re.compile(
    r"(?<![\w.,])(?:(\d+)\s?x\s?)?(\d+(?:[.,]\d+)?)\s?(kg|gr|g|ml|l|liter|pcs|pc|lembar|sheet|s)(?![a-z])", re.I)
# Lines in a product card that are labels, not the product name
NOISE = re.compile(
    r"^(baru|new|terlaris|best ?seller|harga\b[^\d]*|promo|sale|diskon|"
    r"tambah(kan)? ke (keranjang|troli)|beli|add to (cart|bag)|lihat|stok|tersedia|habis|gratis ongkir|"
    r"ikea family|member|[\d.,]+\s*(rb|jt|k)?\+?\s*(terjual|sold|ulasan|review)|\(?\d+\)?|[\d.]+\s*/\s*5|[★♡♥].*)$", re.I)


def rupiah(text: str) -> int:
    return int(re.sub(r"[.,]", "", text))


def prices_in(text: str) -> list[int]:
    return [rupiah(m.group(1)) for m in PRICE_RE.finditer(text)]


def size_in(text: str) -> str | None:
    """'Rak buku, 80x28 cm' -> None; 'Detergen 1,8 kg' -> '1.8kg'; 'Tisu 2 x 200 lembar' -> '2x200lembar'"""
    for m in SIZE_RE.finditer(text):
        pack, amount, unit = m.group(1), m.group(2).replace(",", "."), m.group(3).lower()
        unit = {"gr": "g", "liter": "l", "pc": "pcs", "sheet": "lembar"}.get(unit, unit)
        return f"{pack}x{amount}{unit}" if pack else f"{amount}{unit}"
    return None


def card_item(card: dict) -> tuple[dict | None, str]:
    """One bookmarklet card -> (draft item, reason if skipped)."""
    text = card.get("text", "")
    prices = [p for p in prices_in(text) if p > 0]
    if not prices:
        return None, "Tidak ada harga"
    struck = [p for t in card.get("struck", []) for p in prices_in(t)]
    notes = []
    if struck:
        was = max(struck)
        rest = [p for p in prices if p != was] or prices
        price = min(rest)
    elif len(set(prices)) >= 2:
        price, was = min(prices), max(prices)
        notes.append("CHECK: dua harga di kartu, yang besar dianggap harga coret")
    else:
        price, was = prices[0], None
    if len(set(prices)) > 2:
        notes.append(f"CHECK: {len(set(prices))} harga di kartu ({', '.join(map(str, sorted(set(prices))))})")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    words = [ln for ln in lines if not PRICE_RE.search(ln) and not NOISE.match(ln.strip())
             and not re.fullmatch(r"[-\d\s%.,/]+", ln.strip()) and len(ln) > 1]
    name = ", ".join(words[:2]) or card.get("img_alt") or ""
    if not name:
        return None, "Nama produk tidak terbaca"

    item = {
        "as_captured": " | ".join(lines)[:300],
        "brand": TODO, "name": name, "size": size_in(" ".join(words)) or TODO, "cat": TODO,
        "price": price,
    }
    if was and was > price:
        item["was"] = was
        badge = BADGE_RE.search(text)
        if badge:
            item["badge"] = int(badge.group(1))
    else:
        item["promo"] = "regular"
    if card.get("href"):
        item["url"] = card["href"]
    if notes:
        item["check"] = "; ".join(notes)
    return item, ""


def walk_jsonld(node):
    """Yield every schema.org Product in a JSON-LD tree (handles @graph and ItemList)."""
    if isinstance(node, list):
        for n in node:
            yield from walk_jsonld(n)
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Product" in kinds:
            yield node
        for key in ("@graph", "itemListElement", "item", "mainEntity", "hasVariant"):
            if key in node:
                yield from walk_jsonld(node[key])


def jsonld_item(prod: dict, page_url: str) -> dict | None:
    offers = prod.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if offers.get("@type") == "AggregateOffer":
        price = offers.get("lowPrice")
    else:
        price = offers.get("price")
    try:
        price = int(round(float(str(price).replace(",", ""))))
    except (TypeError, ValueError):
        return None
    if offers.get("priceCurrency", "IDR") != "IDR":
        return None
    brand = prod.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    name = str(prod.get("name", "")).strip()
    item = {
        "as_captured": f"schema.org Product: {name}"[:300],
        "brand": brand or TODO, "name": name or TODO,
        "size": size_in(f"{name} {prod.get('description', '')}") or TODO, "cat": TODO,
        "price": price, "promo": "regular",
        "url": prod.get("url") or offers.get("url") or page_url,
    }
    if offers.get("priceValidUntil"):
        item["valid_until"] = str(offers["priceValidUntil"])[:10]
    return item


class _LdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self._in, self.canonical = [], False, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in = True
            self.blocks.append("")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        if tag == "meta" and a.get("property") == "og:url" and not self.canonical:
            self.canonical = a.get("content", "")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = False

    def handle_data(self, data):
        if self._in:
            self.blocks[-1] += data


def read_saved_page(path: Path) -> dict:
    """A Ctrl+S page (.html or .mhtml) -> the same shape the bookmarklet writes."""
    raw = path.read_bytes()
    html, url = None, ""
    if path.suffix.lower() in (".mhtml", ".mht"):
        msg = email.message_from_bytes(raw)
        url = msg.get("Snapshot-Content-Location", "")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                break
    if html is None:
        html = raw.decode("utf-8", "replace")
    p = _LdParser()
    p.feed(html)
    jsonld = []
    for block in p.blocks:
        try:
            jsonld.append(json.loads(block))
        except json.JSONDecodeError:
            pass
    return {"url": url or p.canonical, "captured_on": date.fromtimestamp(path.stat().st_mtime).isoformat(),
            "cards": [], "jsonld": jsonld}


def build_batch(capture: dict, store: str | None, valid_until: str | None) -> dict:
    url = capture.get("url", "")
    host = urlparse(url).hostname or ""
    if not store:
        store, _ = guess_store(url)
    seen = capture.get("captured_on") or date.today().isoformat()
    items, skipped, urls = [], [], set()

    for prod in walk_jsonld(capture.get("jsonld", [])):
        item = jsonld_item(prod, url)
        if item:
            items.append(item)
            urls.add(item["url"])
    for n, card in enumerate(capture.get("cards", []), 1):
        item, reason = card_item(card)
        if item is None:
            skipped.append({"card": n, "text": card.get("text", "")[:120], "reason": reason})
        elif item.get("url") in urls:
            skipped.append({"card": n, "text": item["name"], "reason": "Sudah ada dari data terstruktur"})
        else:
            items.append(item)
            urls.add(item.get("url"))

    defaults = {"store": store, "channel": "online", "seen_on": seen, "source_type": "link",
                "contributor": "Kang Nawar", "document": f"Situs {host or store}, dilihat {seen}"}
    if valid_until:
        defaults["valid_until"] = valid_until
    return {
        "batch": f"{store if store != TODO else 'web'}-web-{seen}",
        "description": f"Dari {url}",
        "defaults": defaults,
        "items": items,
        "skipped": skipped,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", help="bookmarklet .json, or a saved .html / .mhtml page")
    ap.add_argument("--store", help="store id from data/stores.json (guessed from the link if left out)")
    ap.add_argument("--valid-until", help="promo end date shown on the site, YYYY-MM-DD")
    ap.add_argument("--out", help="where to write the draft (default: batch.json next to the capture)")
    ap.add_argument("--root", default=str(REPO_ROOT))
    args = ap.parse_args(argv)

    src = Path(args.capture)
    if src.suffix.lower() == ".json":
        capture = json.loads(src.read_text(encoding="utf-8"))
        if capture.get("kind") != "kangnawar-capture":
            print(f"{src} is not a bookmarklet capture.")
            return 1
    else:
        capture = read_saved_page(src)

    stores = {s["id"] for s in json.loads((Path(args.root) / "data" / "stores.json").read_text(encoding="utf-8"))}
    if args.store and args.store not in stores:
        print(f"Unknown store '{args.store}'. Add it to data/stores.json first.")
        return 1

    batch = build_batch(capture, args.store, args.valid_until)
    out = Path(args.out) if args.out else src.with_name("batch.json")
    if out.exists():
        print(f"{out} already exists. Use --out to write somewhere else.")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    todo = sum(1 for i in batch["items"] if TODO in (i["brand"], i["size"], i["cat"]))
    checks = sum(1 for i in batch["items"] if "check" in i)
    print(f"{out}: {len(batch['items'])} items ({todo} with TODO, {checks} to CHECK), {len(batch['skipped'])} skipped")
    if not batch["items"] and not capture.get("cards"):
        print("No prices found. For pages that load with JavaScript (IKEA, most shops) use the bookmarklet instead.")
    if batch["defaults"]["store"] == TODO:
        print("Store unknown: set defaults.store (or pass --store).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
