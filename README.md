# Kang Nawar

**Is that sale actually cheaper?** Kang Nawar tracks real prices of everyday products
in Indonesia, offline and online, and gives every promo a verdict, including calling
out fake discounts where the "normal" price was raised before the sale.

Live site: https://kangnawar.github.io (static, hosted on GitHub Pages)

## How it works

- `data/products/*.json`: one file per product (brand, name, size + unit, category).
- `data/observations/YYYY/MM/*.json`: one file per price sighting (store, channel,
  price, the store's claimed normal price, promo mechanism, date, evidence).
- `data/categories.json`, `data/stores.json`, `data/promo-types.json`, `data/rules.json`:
  reference lists and the verdict thresholds.
- `schemas/`: JSON Schemas for all of the above.
- `tools/`: Python tools: `validate.py`, `pricing.py` (verdicts), `image_prep.py`, `batch_import.py`.
- `public/img/`: product images and evidence crops, WebP, max 60 KB each.

Verdict rules are explained in [docs/VERDICTS.md](docs/VERDICTS.md).
How to submit and review data: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Local checks

```bash
pip install -r tools/requirements.txt
python tools/validate.py          # check every data file
python tools/pricing.py           # compute unit prices and verdicts -> build/computed.json
python -m unittest discover -s tools/tests
```

## Updating

Data changes arrive as pull requests (from the submission form or the batch tools),
are checked by CI, merged by a maintainer, and the site rebuilds at most once a day.
