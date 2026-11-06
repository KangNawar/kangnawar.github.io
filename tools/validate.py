#!/usr/bin/env python3
"""Check every Kang Nawar data file. CI runs this on each pull request.

Run:  python tools/validate.py [--root DIR] [--strict]

Errors (exit code 1) block a merge. Warnings are printed for the reviewer.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kn_data import REPO_ROOT, load, read_json  # noqa: E402


class Report:
    def __init__(self, root: Path):
        self.root = root
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def _rel(self, path) -> str:
        try:
            return str(Path(path).relative_to(self.root))
        except ValueError:
            return str(path)

    def error(self, path, msg):
        self.errors.append(f"{self._rel(path)}: {msg}")

    def warn(self, path, msg):
        self.warnings.append(f"{self._rel(path)}: {msg}")


def schema(ds, name):
    return Draft202012Validator(read_json(ds.schema_dir / f"{name}.schema.json"), format_checker=FormatChecker())


def check_schema(validator, record, path, rep):
    for err in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in err.path) or "(root)"
        rep.error(path, f"{where}: {err.message}")


def check_image(ds, rel_path: str, path, rep, max_kb: int) -> Path | None:
    img = ds.public_dir / rel_path
    if not img.exists():
        rep.error(path, f"image not found: public/{rel_path}")
        return None
    head = img.read_bytes()[:12]
    if not (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        rep.error(path, f"image is not WebP: public/{rel_path} (run tools/image_prep.py)")
    kb = img.stat().st_size / 1024
    if kb > max_kb:
        rep.error(path, f"image is {kb:.0f} KB, limit {max_kb} KB: public/{rel_path}")
    return img


def validate(root: Path | str = REPO_ROOT, today: date | None = None) -> Report:
    ds = load(root)
    rep = Report(Path(root))
    today = today or date.today()

    for path, msg in ds.unreadable:
        rep.error(path, f"not valid JSON: {msg}")

    # Reference lists
    for name, sch, value in [
        ("data/categories.json", "categories", ds.categories),
        ("data/stores.json", "store", ds.stores),
        ("data/promo-types.json", "promo-types", ds.promo_types),
        ("data/rules.json", "rules", ds.rules),
    ]:
        check_schema(schema(ds, sch), value, ds.root / name, rep)

    def dupes(items, label, path):
        seen = set()
        for i in items:
            if i in seen:
                rep.error(path, f"duplicate {label} id '{i}'")
            seen.add(i)

    dupes([c["id"] for c in ds.categories], "category", ds.data_dir / "categories.json")
    for c in ds.categories:
        dupes([s["id"] for s in c.get("subcategories", [])], f"subcategory in {c['id']}", ds.data_dir / "categories.json")
    dupes([s["id"] for s in ds.stores], "store", ds.data_dir / "stores.json")
    dupes([p["id"] for p in ds.promo_types], "promo type", ds.data_dir / "promo-types.json")

    cats = {c["id"]: {s["id"] for s in c.get("subcategories", [])} for c in ds.categories}
    inactive = {c["id"] for c in ds.categories if c.get("active") is False}
    stores = ds.store_map()
    promo_ids = {p["id"] for p in ds.promo_types}
    max_kb = ds.rules.get("max_image_kb", 60)
    referenced_images: set[Path] = set()

    # Products
    pv = schema(ds, "product")
    for pid, (path, p) in ds.products.items():
        check_schema(pv, p, path, rep)
        if p.get("id") != pid:
            rep.error(path, f"id '{p.get('id')}' must match the filename '{pid}'")
        cat, sub = p.get("category"), p.get("subcategory")
        if cat not in cats:
            rep.error(path, f"unknown category '{cat}'")
        elif sub not in cats[cat]:
            rep.error(path, f"unknown subcategory '{sub}' in category '{cat}'")
        elif cat in inactive:
            rep.warn(path, f"category '{cat}' is inactive (hidden on the site)")
        if p.get("image"):
            img = check_image(ds, p["image"], path, rep, ds.rules.get("max_product_image_kb", 20))
            if img:
                referenced_images.add(img.resolve())

    # Observations
    ov = schema(ds, "observation")
    fingerprints: dict[tuple, Path] = {}
    obs_counts: dict[str, int] = {}
    for path, o in ds.observations:
        n_before = len(rep.errors)
        check_schema(ov, o, path, rep)
        if len(rep.errors) > n_before:
            continue  # cross-checks below assume the shape is right

        if o["id"] != path.stem:
            rep.error(path, f"id '{o['id']}' must match the filename '{path.stem}'")
        seen = date.fromisoformat(o["seen_on"])
        expected_dir = f"{seen:%Y}/{seen:%m}"
        if path.parent.relative_to(ds.data_dir / "observations").as_posix() != expected_dir:
            rep.error(path, f"must be stored in data/observations/{expected_dir}/ (from seen_on)")
        prefix = f"{o['seen_on']}_{o['store']}_{o['product']}"
        if not re.fullmatch(re.escape(prefix) + r"(-[0-9]+)?", o["id"]):
            rep.error(path, f"id must be '{prefix}' (add -2, -3 ... for repeats)")

        pid = o["product"]
        obs_counts[pid] = obs_counts.get(pid, 0) + 1
        if pid not in ds.products:
            rep.error(path, f"unknown product '{pid}' (add data/products/{pid}.json)")
        store = stores.get(o["store"])
        if store is None:
            rep.error(path, f"unknown store '{o['store']}'")
        elif o["channel"] not in store["channels"]:
            rep.error(path, f"store '{o['store']}' has no '{o['channel']}' channel")

        if seen > today + timedelta(days=1):
            rep.error(path, f"seen_on {o['seen_on']} is in the future")
        vf, vu = o.get("valid_from"), o.get("valid_until")
        if vf and vu and vf > vu:
            rep.error(path, "valid_from is after valid_until")
        if vu and vu < o["seen_on"]:
            rep.warn(path, "valid_until is before seen_on")

        promo = o.get("promo")
        claimed = o.get("claimed_normal_price")
        if promo:
            if promo["type"] not in promo_ids:
                rep.error(path, f"unknown promo type '{promo['type']}'")
            if promo.get("cashback", 0) >= o["price"]:
                rep.error(path, "cashback is not smaller than the price")
            if not vu:
                rep.warn(path, f"promo without valid_until: expires {ds.rules.get('default_expiry_days', 14)} days after seen_on")
        basis = o.get("price_basis")
        product = ds.products.get(pid, (None, None))[1]
        if basis and product and basis["unit"] != product["size"]["unit"]:
            rep.error(path, f"price_basis unit '{basis['unit']}' differs from the product unit '{product['size']['unit']}'")
        if basis and product and not product.get("loose"):
            rep.warn(path, "price_basis on a product not marked loose")
        if promo and promo.get("claimed_pct") and claimed is None:
            rep.warn(path, "badge % recorded without the strikethrough price: it cannot be checked")
        if o.get("quantity", 1) > 1 and not promo:
            rep.warn(path, "quantity > 1 without a promo: is this a bundle?")
        if claimed is not None and claimed * o.get("quantity", 1) <= o["price"]:
            rep.warn(path, "claimed normal price is not higher than the price paid")
        if o["channel"] == "online" and o["source"]["type"] == "photo" and not o["source"].get("image"):
            rep.warn(path, "online sighting with no link or screenshot")
        if o["source"]["type"] == "report" and not o.get("notes"):
            rep.warn(path, "report without evidence: add notes saying where the price was seen")
        if o["source"]["type"] == "link" and not o["source"].get("url"):
            rep.error(path, "source type 'link' needs a url")
        contributor = o["source"].get("contributor", "")
        if re.search(r"@|\+?62\d{6,}|\b08\d{7,}", contributor):
            rep.error(path, "contributor looks like an email or phone number: use a name or handle")
        if o["source"].get("image"):
            img = check_image(ds, o["source"]["image"], path, rep, max_kb)
            if img:
                referenced_images.add(img.resolve())

        fp = (pid, o["store"], o["channel"], o["seen_on"], o["price"], o.get("quantity", 1), o.get("seller"))
        if fp in fingerprints:
            rep.error(path, f"duplicate of {fingerprints[fp].name}")
        else:
            fingerprints[fp] = path

    for pid, (path, _) in ds.products.items():
        if pid not in obs_counts:
            rep.warn(path, "product has no observations yet")

    img_root = ds.public_dir / "img"
    if img_root.exists():
        for img in img_root.rglob("*"):
            if img.is_file() and img.name != ".gitkeep" and img.resolve() not in referenced_images:
                rep.warn(img, "image is not used by any data file")
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)

    rep = validate(args.root)
    ds = load(args.root)
    for w in rep.warnings:
        print(f"WARN  {w}")
    for e in rep.errors:
        print(f"ERROR {e}")
    print(f"\n{len(ds.products)} products, {len(ds.observations)} observations: "
          f"{len(rep.errors)} errors, {len(rep.warnings)} warnings")
    failed = rep.errors or (args.strict and rep.warnings)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
