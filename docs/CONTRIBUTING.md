# Adding and reviewing data

## Recording a price sighting

One sighting = one product, one store, one day, one price. Needed:

1. **Product**: brand, name, variant, size (e.g. 50 ml). If it is new, a
   `data/products/<id>.json` file is created, with an id like `brand-name-variant-50ml`.
2. **Store** and **channel**: offline (shelf) or online (app/marketplace).
   Online: also the seller name, e.g. "Wardah Official Store".
3. **Price paid** in whole rupiah, and **quantity** received for that price.
4. **Claimed normal price** (the strikethrough or "harga normal" on the tag), if shown.
5. **Promo** type and the label as printed, and the end date if shown.
6. **Evidence**: a photo, screenshot or link.

Regular prices with no promo are welcome. They are what exposes fake discounts.

### Privacy

Contributor credit is a name or handle only. Never an email, phone number, or a
photo that shows people, receipts with card numbers, or home addresses.
`tools/validate.py` rejects anything that looks like an email or phone number.

## Importing a catalogue, flyer or screenshots

1. Put the files in `inbox/<store>-<year>-<edition>/` (inbox/ is never committed).
2. Ask Claude to read them and write `inbox/<batch>/batch.json`: one entry per product,
   plus a `skipped` list with a reason for anything left out (several sizes under one
   "Harga Mulai" price, no size printed, outside our categories).
3. Read through `batch.json` and fix anything wrong. It is plain JSON; the format is
   described at the top of `tools/batch_import.py`.
4. `python tools/batch_import.py inbox/<batch>/batch.json --dry-run`, then without `--dry-run`.
5. `python tools/validate.py` and `python tools/pricing.py`. The pricing summary also lists
   promos whose badge % is higher than the strikethrough price supports.
6. Commit and push (or open a pull request).

## Images

Always run `python tools/image_prep.py <files> --out <folder>` first:
WebP, max 800 px, max 60 KB, metadata (including GPS) stripped.
Crop the evidence to the price tag and product; the whole flyer is not needed.

## Review checklist (maintainers)

- CI is green (`tools/validate.py` and the tests).
- The photo shows the product, the size and the price claimed.
- The product is not a duplicate under another id (search brand + size).
- Nothing personal is visible in the photo.
- Merge. The site rebuilds once a day.
