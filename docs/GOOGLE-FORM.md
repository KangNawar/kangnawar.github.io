# Google Form: "Kirim harga ke Kang Nawar"

Kept deliberately short. Four questions; everything else (brand, size, store,
category, promo) is worked out by the maintainer from the photo and the link.

| Question | Type | Required |
|---|---|---|
| Nama produk | Short answer | Yes |
| Harga | Short answer | Yes |
| Foto label harga | File upload (images) | Yes |
| Link produk | Short answer | No |

The file upload makes Google ask visitors to sign in; uploaded photos go to the
form owner's Drive and stay private. Responses are linked to a Google Sheet,
which is **never** published to the web.

## Importing responses (manual, only when you choose to)

Nothing syncs automatically.

1. In the response Sheet: **File > Download > Comma-separated values (.csv)**.
2. `python tools/form_inbox.py "path/to/the.csv"`
   - Picks up only rows it has not seen before (it remembers the count in
     `inbox/form-state.json`; `--all` starts over).
   - Writes a draft `inbox/form-<date>/batch.json`: product name and price filled in,
     store guessed from the link (Shopee, Tokopedia, Astro, ...), `TODO` for brand,
     size, category and anything it could not tell. The photo's Drive link is kept
     for you, not imported.
3. Open the draft, look at each photo, replace the `TODO`s, set `"promo"` if the
   photo shows one, delete rows you don't want (spam, unreadable, duplicates).
   Or ask Claude to do this pass with you.
4. `python tools/batch_import.py inbox/form-<date>/batch.json --dry-run`, then for real.
5. `python tools/validate.py`, `python tools/pricing.py`, commit, push.

The site rebuilds on every push to `main`. It does **not** rebuild on a timer;
expired promos hide themselves in the browser, and a rebuild without new data can
be started from GitHub: Actions, "Deploy site", "Run workflow".
