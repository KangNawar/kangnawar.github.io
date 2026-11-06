#!/usr/bin/env python3
"""Turn a reviewed extraction batch into product + observation files.

Run:  python tools/batch_import.py inbox/<batch>/batch.json [--dry-run] [--root DIR]

A batch is what the extraction step (Claude reading a catalogue, flyer or
screenshots) produces. It is plain JSON so it can be checked and corrected
by hand before import. Shape:

{
  "batch": "superindo-2026-45",
  "defaults": {"store": "superindo", "channel": "offline", "city": "...",
               "seen_on": "2026-11-06", "valid_from": "...", "valid_until": "...",
               "source_type": "catalogue", "contributor": "Kang Nawar",
               "document": "Katalog Super Indo Ed. 45"},   # + ", hal. <page>" per item
  "items": [ {item}, ... ],
  "skipped": [ {"page": 1, "text": "...", "reason": "..."} ]
}

Item keys
  page          page number (links the evidence image)
  brand, name   as printed; brand "Tanpa Merek" for unbranded fresh food
  variant       optional, e.g. "Semua rasa" or "Plain, Swiss Choco"
  size          "105g", "1.45kg", "1500ml", "1l", "10pcs", "18x34g", "24x600ml"
  loose         true for goods sold by weight; product size becomes 1000 g
  per           loose goods: what the price buys, e.g. "100g" (default "100g")
  cat           "category/subcategory"
  price         rupiah paid (for `qty` packs)
  qty           packs received for `price` ("2 seharga" -> 2, "Beli 2 Gratis 1" -> 3)
  was           strikethrough price for ONE pack (or per `per` for loose goods)
  promo         promo type id; default: "diskon" if badge, "harga-spesial" if `was`, else none
  badge         % printed on the badge ("Diskon 25%" -> 25)
  label         promo text as printed
  member, min_purchase, valid_from, valid_until, notes
  store, channel, seen_on, url, source_type   per-item overrides of the defaults
  pid           use an EXISTING product id. Same brand + line + size = same product,
                whatever the scent or flavour; check the duplicate hints this tool prints.

Catalogue pages stay in inbox/ as private evidence; only a text reference
("Katalog Super Indo Ed. 45, hal. 3") goes into the data.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from image_prep import slugify  # noqa: E402
from kn_data import REPO_ROOT, read_json  # noqa: E402

UNBRANDED = "Tanpa Merek"
SIZE_RE = re.compile(r"^(?:(\d+)\s*x\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|gr|l|ml|pcs|s|sheet|lembar)$", re.I)


def parse_size(text: str) -> tuple[float, str, int]:
    """'18x34g' -> (34, 'g', 18); '1.45kg' -> (1450, 'g', 1); '10pcs' -> (10, 'pcs', 1)"""
    m = SIZE_RE.match(text.strip().replace(" ", ""))
    if not m:
        raise ValueError(f"cannot read size '{text}'")
    pack = int(m.group(1)) if m.group(1) else 1
    amount = float(m.group(2).replace(",", "."))
    unit = m.group(3).lower()
    if unit == "kg":
        amount, unit = amount * 1000, "g"
    elif unit == "gr":
        unit = "g"
    elif unit == "l":
        amount, unit = amount * 1000, "ml"
    elif unit == "s":
        unit = "pcs"
    elif unit == "lembar":
        unit = "sheet"
    amount = round(amount, 3)
    return (int(amount) if amount == int(amount) else amount), unit, pack


def size_token(amount, unit, pack) -> str:
    unit_tok = {"sheet": "lembar"}.get(unit, unit)
    amt = str(amount).replace(".", "-")
    return f"{pack}x{amt}{unit_tok}" if pack > 1 else f"{amt}{unit_tok}"


def build_product(item: dict) -> dict:
    cat, sub = item["cat"].split("/")
    if item.get("loose"):
        amount, unit, pack = 1000, parse_size(item.get("per", "100g"))[1], 1
        tail = "curah"
    else:
        amount, unit, pack = parse_size(item["size"])
        tail = size_token(amount, unit, pack)
    brand = item["brand"]
    parts = ([] if brand == UNBRANDED else [brand]) + [item["name"], tail]
    pid = item.get("pid") or slugify(" ".join(parts))[:120].strip("-")
    product = {"id": pid, "brand": brand, "name": item["name"]}
    if item.get("variant"):
        product["variant"] = item["variant"]
    product["size"] = {"amount": amount, "unit": unit}
    if pack > 1:
        product["pack_count"] = pack
    if item.get("loose"):
        product["loose"] = True
    product["category"], product["subcategory"] = cat, sub
    return product


def build_observation(item: dict, product: dict, d: dict, document: str | None) -> dict:
    obs = {"id": None, "product": product["id"], "store": item.get("store", d["store"]),
           "channel": item.get("channel", d["channel"])}
    city = item.get("city", d.get("city"))
    if city and obs["channel"] == "offline":
        obs["city"] = city
    obs["price"] = int(item["price"])
    if item.get("qty", 1) > 1:
        obs["quantity"] = int(item["qty"])
    if item.get("was"):
        obs["claimed_normal_price"] = int(item["was"])
    if item.get("loose"):
        amount, unit, _ = parse_size(item.get("per", "100g"))
        obs["price_basis"] = {"amount": amount, "unit": unit}

    ptype = item.get("promo")
    if ptype is None:
        ptype = "diskon" if item.get("badge") else ("harga-spesial" if item.get("was") else None)
    if ptype and ptype != "regular":
        promo = {"type": ptype}
        for key, out in [("label", "label"), ("badge", "claimed_pct"), ("min_purchase", "min_purchase")]:
            if item.get(key) is not None:
                promo[out] = item[key]
        if item.get("member"):
            promo["member_only"] = True
        obs["promo"] = promo

    obs["seen_on"] = item.get("seen_on", d["seen_on"])
    is_promo = "promo" in obs
    for key in ("valid_from", "valid_until"):
        value = item.get(key, d.get(key) if is_promo else None)
        if value:
            obs[key] = value
    source = {"type": item.get("source_type", d.get("source_type", "catalogue"))}
    if document:
        source["document"] = document
    if item.get("url"):
        source["url"] = item["url"]
    if d.get("contributor"):
        source["contributor"] = d["contributor"]
    obs["source"] = source
    notes = "; ".join(n for n in [item.get("notes")] if n)
    if notes:
        obs["notes"] = notes[:280]
    return obs


def _words(text: str) -> set[str]:
    return {w for w in slugify(text).split("-") if len(w) > 2}


def similar_products(new: dict, existing: dict) -> list[str]:
    """Existing products that are probably the same thing (frugal rule: one product per
    brand + line + size, variants merged). Same brand, same size and half the name words."""
    out = []
    nw = _words(new["name"])
    for pid, old in existing.items():
        if old.get("brand", "").lower() != new["brand"].lower():
            continue
        same_size = (old["size"] == new["size"] and old.get("pack_count", 1) == new.get("pack_count", 1)) \
            or (old.get("loose") and new.get("loose"))
        if not same_size:
            continue
        ow = _words(old["name"])
        if nw and ow and len(nw & ow) / min(len(nw), len(ow)) >= 0.5:
            out.append(pid)
    return out


def write_json(path: Path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(batch_path: Path, root: Path, dry_run: bool) -> int:
    batch = read_json(batch_path)
    d = batch["defaults"]
    existing_products = {p.stem: read_json(p) for p in (root / "data" / "products").glob("*.json")}
    hints = []

    def document_for(item):
        doc = d.get("document")
        if doc and item.get("page"):
            return f"{doc}, hal. {item['page']}"
        return doc

    products_dir = root / "data" / "products"
    new_products = reused = 0
    used_ids: set[str] = set()
    observations = []
    problems = []
    for n, item in enumerate(batch["items"], 1):
        try:
            product = build_product(item)
        except (ValueError, KeyError) as exc:
            problems.append(f"item {n} ({item.get('name')}): {exc}")
            continue
        ppath = products_dir / f"{product['id']}.json"
        if ppath.exists():
            existing = read_json(ppath)
            if existing["size"] != product["size"] or existing.get("pack_count", 1) != product.get("pack_count", 1):
                problems.append(f"item {n}: product {product['id']} exists with a different size")
                continue
            reused += 1
        elif product["id"] not in used_ids:
            new_products += 1
            for other in similar_products(product, existing_products):
                hints.append(f"item {n}: new '{product['id']}' looks like existing '{other}'. "
                             f"Same product? Set \"pid\": \"{other}\" in the batch.")
            if not dry_run:
                write_json(ppath, product)
        used_ids.add(product["id"])

        obs = build_observation(item, product, d, document_for(item))
        base = f"{obs['seen_on']}_{obs['store']}_{product['id']}"
        oid, k = base, 1
        obs_dir = root / "data" / "observations" / obs["seen_on"][:4] / obs["seen_on"][5:7]
        while oid in {o["id"] for o in observations} or (obs_dir / f"{oid}.json").exists():
            k += 1
            oid = f"{base}-{k}"
        obs["id"] = oid
        observations.append(obs)
        if not dry_run:
            write_json(obs_dir / f"{oid}.json", obs)

    print(f"\n{batch['batch']}: {len(observations)} observations, {new_products} new products, "
          f"{reused} existing products, {len(batch.get('skipped', []))} skipped in extraction")
    for h in hints:
        print(f"CHECK   {h}")
    for p in problems:
        print(f"PROBLEM {p}")
    if dry_run:
        print("(dry run: nothing written)")
    return 1 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("batch", help="path to batch.json")
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    return run(Path(args.batch), Path(args.root), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
