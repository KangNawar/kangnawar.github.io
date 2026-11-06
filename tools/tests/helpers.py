"""Builds throwaway data roots for tests. All brands and prices here are fictional."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
from kn_data import REPO_ROOT  # noqa: E402


class TempRepo:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="kn-test-"))
        data = self.root / "data"
        (data / "products").mkdir(parents=True)
        (data / "observations").mkdir()
        (self.root / "public" / "img").mkdir(parents=True)
        for name in ["categories.json", "stores.json", "promo-types.json", "rules.json"]:
            shutil.copy(REPO_ROOT / "data" / name, data / name)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def product(self, pid, amount=50, unit="ml", pack_count=1, **extra):
        rec = {"id": pid, "brand": "Contoh", "name": f"Produk {pid}",
               "size": {"amount": amount, "unit": unit},
               "category": "perawatan-wajah", "subcategory": "pelembap"}
        rec.update(extra)
        if pack_count != 1:
            rec["pack_count"] = pack_count
        self._write(self.root / "data" / "products" / f"{pid}.json", rec)
        return rec

    def obs(self, product, store, seen_on, price, channel="offline", suffix="", **extra):
        oid = f"{seen_on}_{store}_{product}{suffix}"
        rec = {"id": oid, "product": product, "store": store, "channel": channel,
               "price": price, "seen_on": seen_on, "source": {"type": "photo"}, **extra}
        y, m = seen_on[:4], seen_on[5:7]
        self._write(self.root / "data" / "observations" / y / m / f"{oid}.json", rec)
        return rec

    @staticmethod
    def _write(path: Path, rec):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
