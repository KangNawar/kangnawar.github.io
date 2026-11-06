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
- `tools/`: Python tools: `validate.py`, `pricing.py` (comparisons), `image_prep.py`, `batch_import.py`, `form_inbox.py`, `page_capture.py` (prices from shop websites).
- `public/img/`: product images and evidence crops, WebP, max 60 KB each.

Verdict rules are explained in [docs/VERDICTS.md](docs/VERDICTS.md).
How data is entered and reviewed: [docs/DATA-ENTRY.md](docs/DATA-ENTRY.md).

## Running the site locally

Needs Python 3.10+ and Node 22.

```bash
pip install -r tools/requirements.txt
npm install
npm run dev        # computes verdicts, then serves http://localhost:4321
npm run build      # static site in dist/
```

The site is Astro + Tailwind (`src/`). Pages read `data/` and `build/computed.json`
at build time; the browser only downloads HTML, one CSS file, two fonts and a small
search index. GitHub Actions (`.github/workflows/deploy.yml`) rebuilds on every push
to `main` (or by hand from the Actions tab). There is no timer; expired promos hide
themselves in the browser.

## Local checks

```bash
pip install -r tools/requirements.txt
python tools/validate.py          # check every data file
python tools/pricing.py           # compute unit prices and verdicts -> build/computed.json
python -m unittest discover -s tools/tests
```

## Updating

Only the maintainer changes data: catalogue batches, form responses via
`tools/form_inbox.py` and shop-website captures via `tools/page_capture.py`, all
committed from a local checkout. Pull requests and issues are not used for data;
prices are sent through the form on the site. The deploy workflow runs the tests and
`validate.py` before every build.
