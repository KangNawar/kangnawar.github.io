# Adding and reviewing data (maintainer notes)

Data only enters through the maintainer. The public way to send a price is the
Google Form on https://kangnawar.github.io/panduan/; issues and pull requests on
GitHub are not used for data. The Indonesian version of these notes is the unlinked
page https://kangnawar.github.io/infoadmin/. The Google Form and how its responses
are imported (by hand, with `tools/form_inbox.py`) is in `docs/GOOGLE-FORM.md`.
Prices from shop websites (IKEA and others) come in through the "Ambil harga"
bookmarklet and `tools/page_capture.py`.

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
3. Read through `batch.json` and fix anything wrong. One product = brand + line + size;
   scents and flavours the brand prices the same are merged. Use `pid` to point an item
   at an existing product. It is plain JSON; the format is
   described at the top of `tools/batch_import.py`.
4. `python tools/batch_import.py inbox/<batch>/batch.json --dry-run`, then without `--dry-run`.
5. `python tools/validate.py` and `python tools/pricing.py`. The pricing summary also lists
   promos whose badge % is higher than the strikethrough price supports.
6. Commit and push (or open a pull request).

## Images

Product photos: your own photos only, never catalogue or brand images.
`python tools/image_prep.py photo.jpg --out public/img/products --name <product-id> --max-side 400 --max-kb 20`
then add `"image": "img/products/<product-id>.webp"` to the product file.
Catalogue pages and submission photos are evidence and stay out of the repo
(in `inbox/` or the form's Drive); observations reference them as text in `source.document`.

## Review checklist (maintainers)

- CI is green (`tools/validate.py` and the tests).
- The photo shows the product, the size and the price claimed.
- The product is not a duplicate under another id (search brand + size).
- Nothing personal is visible in the photo.
- Merge. The site rebuilds on push.
