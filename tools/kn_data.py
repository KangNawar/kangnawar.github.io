"""Shared loader for Kang Nawar data files.

Layout (relative to the repo root):
  data/categories.json, data/stores.json, data/promo-types.json, data/rules.json
  data/products/<product-id>.json
  data/observations/<YYYY>/<MM>/<observation-id>.json
  public/img/...
  schemas/*.schema.json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class Dataset:
    root: Path
    categories: list = field(default_factory=list)
    stores: list = field(default_factory=list)
    promo_types: list = field(default_factory=list)
    rules: dict = field(default_factory=dict)
    # id -> (path, record)
    products: dict = field(default_factory=dict)
    # list of (path, record)
    observations: list = field(default_factory=list)
    # (path, error message) for files that are not valid JSON at all
    unreadable: list = field(default_factory=list)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def public_dir(self) -> Path:
        return self.root / "public"

    @property
    def schema_dir(self) -> Path:
        # Schemas always come from the real repo, so tests can use a temp data root.
        return REPO_ROOT / "schemas"

    def store_map(self) -> dict:
        return {s["id"]: s for s in self.stores}

    def category_map(self) -> dict:
        return {c["id"]: c for c in self.categories}


def _try_read(path: Path, ds: Dataset):
    try:
        return read_json(path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        ds.unreadable.append((path, str(exc)))
        return None


def load(root: Path | str = REPO_ROOT) -> Dataset:
    root = Path(root)
    ds = Dataset(root=root)
    d = ds.data_dir
    for attr, name, default in [
        ("categories", "categories.json", []),
        ("stores", "stores.json", []),
        ("promo_types", "promo-types.json", []),
        ("rules", "rules.json", {}),
    ]:
        p = d / name
        value = _try_read(p, ds) if p.exists() else default
        setattr(ds, attr, value if value is not None else default)

    for p in sorted((d / "products").glob("*.json")):
        rec = _try_read(p, ds)
        if rec is not None:
            ds.products[p.stem] = (p, rec)

    for p in sorted((d / "observations").glob("**/*.json")):
        rec = _try_read(p, ds)
        if rec is not None:
            ds.observations.append((p, rec))
    return ds
