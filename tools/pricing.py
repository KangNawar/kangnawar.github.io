#!/usr/bin/env python3
"""Unit prices and market comparisons for every price observation.

Run:  python tools/pricing.py [--root DIR] [--today YYYY-MM-DD] [--out build/computed.json]

The question Kang Nawar answers is "is this cheaper than elsewhere?", so a promo
is compared with the MARKET PRICE: what OTHER stores charged for the same product
recently, per unit. The store's own strikethrough price is shown as the store's
claim, never as the yardstick. Rules: docs/VERDICTS.md, thresholds: data/rules.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kn_data import REPO_ROOT, load  # noqa: E402

ELSEWHERE = "lebih-murah-di-tempat-lain"
REAL = "hemat-beneran"
MARKET = "sesuai-harga-pasar"
ABOVE = "di-atas-harga-pasar"
NO_COMPARE = "belum-ada-pembanding"
REGULAR = "harga-reguler"  # not a promo: no verdict, but it is part of other products' market price

VERDICT_LABELS = {
    ELSEWHERE: "Lebih murah di tempat lain",
    REAL: "Hemat beneran",
    MARKET: "Sesuai harga pasar",
    ABOVE: "Di atas harga pasar",
    NO_COMPARE: "Belum ada pembanding",
    REGULAR: "Harga reguler",
}


def unit_basis(product: dict) -> tuple[float, str]:
    """(multiplier, label). Loose goods per kg, other weights/volumes per 100, counts per item."""
    unit = product["size"]["unit"]
    if product.get("loose") and unit == "g":
        return 1000.0, "per kg"
    if unit in ("ml", "g"):
        return 100.0, f"per 100 {unit}"
    return 1.0, "per pcs" if unit == "pcs" else "per lembar"


def units_per_pack(product: dict) -> float:
    return product["size"]["amount"] * product.get("pack_count", 1)


def units_priced(obs: dict, product: dict) -> float:
    """Amount the price buys: the pack, or the price_basis for loose goods ('Rp/100gr')."""
    basis = obs.get("price_basis")
    return basis["amount"] if basis else units_per_pack(product)


def effective_pack_price(obs: dict) -> float:
    """Rupiah per sellable pack after promo and guaranteed cashback."""
    cashback = (obs.get("promo") or {}).get("cashback", 0)
    return (obs["price"] - cashback) / obs.get("quantity", 1)


def unit_price(obs: dict, product: dict) -> float:
    basis, _ = unit_basis(product)
    return effective_pack_price(obs) / units_priced(obs, product) * basis


def claimed_unit_price(obs: dict, product: dict) -> float | None:
    if "claimed_normal_price" not in obs:
        return None
    basis, _ = unit_basis(product)
    return obs["claimed_normal_price"] / units_priced(obs, product) * basis


def is_promo(obs: dict) -> bool:
    return "promo" in obs or "claimed_normal_price" in obs


def pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 1)


def evaluate(obs: dict, product: dict, siblings: list[dict], rules: dict, today: date) -> dict:
    """Comparison for one observation. `siblings` = all OTHER observations of the same product."""
    seen = date.fromisoformat(obs["seen_on"])
    up = unit_price(obs, product)
    claimed_up = claimed_unit_price(obs, product)
    _, unit_label = unit_basis(product)

    # Market: other stores, from `market_window_days` before to `elsewhere_window_days` after.
    lo = seen - timedelta(days=rules["market_window_days"])
    hi = seen + timedelta(days=rules["elsewhere_window_days"])
    market_obs = [s for s in siblings
                  if s["store"] != obs["store"] and lo <= date.fromisoformat(s["seen_on"]) <= hi]
    market_prices = [unit_price(s, product) for s in market_obs]
    market = statistics.median(market_prices) if market_prices else None

    near = [s for s in market_obs
            if abs((date.fromisoformat(s["seen_on"]) - seen).days) <= rules["elsewhere_window_days"]]
    cheaper = None
    if near:
        best = min(near, key=lambda s: unit_price(s, product))
        if unit_price(best, product) < up * (1 - rules["elsewhere_margin_pct"] / 100):
            cheaper = best

    vs_market = None if market is None else 1 - up / market
    claimed_discount = None if claimed_up is None else 1 - up / claimed_up

    badge_pct = (obs.get("promo") or {}).get("claimed_pct")
    badge_gap = None
    if badge_pct is not None and claimed_discount is not None:
        gap = badge_pct - claimed_discount * 100
        if gap > rules.get("badge_tolerance_pct", 3):
            badge_gap = round(gap, 1)

    if not is_promo(obs):
        verdict = REGULAR
    elif cheaper is not None:
        verdict = ELSEWHERE
    elif market is None or len(market_obs) < rules["min_market_sightings"]:
        verdict = NO_COMPARE
    elif vs_market >= rules["real_deal_pct"] / 100:
        verdict = REAL
    elif vs_market <= -rules["pricier_pct"] / 100:
        verdict = ABOVE
    else:
        verdict = MARKET

    expires_on = None
    if is_promo(obs):
        expires_on = obs.get("valid_until") or (seen + timedelta(days=rules["default_expiry_days"])).isoformat()

    return {
        "id": obs["id"],
        "product": obs["product"],
        "store": obs["store"],
        "channel": obs["channel"],
        "seen_on": obs["seen_on"],
        "is_promo": is_promo(obs),
        "effective_pack_price": round(effective_pack_price(obs)),
        "unit_price": round(up, 2),
        "unit_label": unit_label,
        "market_unit_price": None if market is None else round(market, 2),
        "market_stores": sorted({s["store"] for s in market_obs}),
        "market_count": len(market_obs),
        "vs_market_pct": pct(vs_market),
        "claimed_discount_pct": pct(claimed_discount),
        "badge_pct": badge_pct,
        "badge_gap_pct": badge_gap,
        "cheaper_elsewhere": None if cheaper is None else {
            "id": cheaper["id"],
            "store": cheaper["store"],
            "channel": cheaper["channel"],
            "seen_on": cheaper["seen_on"],
            "unit_price": round(unit_price(cheaper, product), 2),
            "saving_pct": pct(1 - unit_price(cheaper, product) / up),
        },
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "expires_on": expires_on,
        "expired": expires_on is not None and date.fromisoformat(expires_on) < today,
    }


def compute(ds, today: date | None = None) -> dict:
    today = today or date.today()
    rules = ds.rules
    by_product: dict[str, list[dict]] = {}
    for _, obs in ds.observations:
        by_product.setdefault(obs["product"], []).append(obs)

    results, summaries = [], {}
    for pid, items in by_product.items():
        if pid not in ds.products:
            continue  # validate.py reports this
        product = ds.products[pid][1]
        for obs in items:
            siblings = [o for o in items if o is not obs]
            results.append(evaluate(obs, product, siblings, rules, today))

        recent_cut = today - timedelta(days=rules["market_window_days"])
        recent = [o for o in items if date.fromisoformat(o["seen_on"]) >= recent_cut]
        prices = [unit_price(o, product) for o in recent]
        summaries[pid] = {
            "observations": len(items),
            "stores": sorted({o["store"] for o in items}),
            "last_seen": max(o["seen_on"] for o in items),
            "lowest_unit_price_recent": round(min(prices), 2) if prices else None,
            "unit_label": unit_basis(product)[1],
        }

    results.sort(key=lambda r: (r["seen_on"], r["id"]), reverse=True)
    return {
        "generated_on": today.isoformat(),
        "rules": rules,
        "verdict_labels": VERDICT_LABELS,
        "products": summaries,
        "observations": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repo root holding data/ (default: this repo)")
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (for expiry)")
    ap.add_argument("--out", default=None, help="output file (default: <root>/build/computed.json)")
    args = ap.parse_args(argv)

    ds = load(args.root)
    today = date.fromisoformat(args.today) if args.today else None
    out = Path(args.out) if args.out else Path(args.root) / "build" / "computed.json"
    data = compute(ds, today)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    counts: dict[str, int] = {}
    for r in data["observations"]:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"{len(data['observations'])} observations, {len(data['products'])} products -> {out}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {VERDICT_LABELS[k]:<28} {v}")
    for r in data["observations"]:
        if r["cheaper_elsewhere"]:
            c = r["cheaper_elsewhere"]
            print(f"  cheaper elsewhere: {r['product']} at {r['store']} -> {c['store']} ({c['saving_pct']}% less)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
