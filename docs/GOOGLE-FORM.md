# Google Form: "Kirim harga ke Kang Nawar"

The form is for people without GitHub. Answers land in a Google Sheet; a daily
GitHub Action (Phase 3) turns new rows into a pull request using the same
`tools/batch_import.py` as catalogues, so a maintainer reviews every submission.

Build it at forms.google.com while signed in as the Kang Nawar Google account.
Question titles are what visitors see (Bahasa Indonesia). The **column** is the
`batch.json` field each answer feeds. Keep titles stable once live: the import
script finds columns by title.

## Settings (gear icon)

- Responses: **Collect email addresses: Do not collect.**
- Responses: **Limit to 1 response: off.** Allow response editing: off.
- Presentation: **Show link to submit another response: on.**
- Confirmation message: *Terima kasih! Harga akan diperiksa dulu, lalu muncul di
  kangnawar.github.io pada pembaruan berikutnya.*
- Responses tab, then **Link to Sheets**: create a new spreadsheet "Kang Nawar kiriman".

The photo upload question makes Google ask visitors to sign in. That is a fair trade:
most Android users already are, and it deters spam. Uploaded photos go to the form
owner's Drive and stay private.

## Section 1: Produk

| # | Question title | Type | Required | Column | Help text / options |
|---|---|---|---|---|---|
| 1 | Merek | Short answer | Yes | `brand` | Contoh: Wardah, Rinso. Untuk sayur, buah, daging curah: *Tanpa merek* |
| 2 | Nama produk | Short answer | Yes | `name` | Tanpa merek dan ukuran. Contoh: *Detergen Bubuk Anti Noda* |
| 3 | Varian | Short answer | No | `variant` | Aroma, rasa atau warna. Boleh dikosongkan |
| 4 | Ukuran | Short answer | Yes | `size` | Contoh: *50 ml*, *1,5 kg*, *isi 10*, *6 x 100 ml*. Untuk barang curah tulis *curah* |
| 5 | Kategori | Dropdown | Yes | `cat` (category only) | Produk Segar, Perawatan Wajah, Perawatan Tubuh & Rambut, Kosmetik, Kesehatan, Ibu & Bayi, Makanan & Minuman, Sembako & Bumbu, Kebutuhan Rumah, Lainnya |

## Section 2: Toko

| # | Question title | Type | Required | Column | Help text / options |
|---|---|---|---|---|---|
| 6 | Toko | Multiple choice with **Other** | Yes | `store` | Indomaret, Alfamart, Alfamidi, Super Indo, Hypermart, Transmart, Lotte Mart, Guardian, Watsons, Century, Kimia Farma, Apotek K-24, Sociolla, Astro, Shopee, Tokopedia, TikTok Shop, Lazada, Blibli |
| 7 | Dilihat di | Multiple choice | Yes | `channel` | *Di toko (rak/label harga)* → offline, *Di aplikasi atau situs* → online |
| 8 | Kota | Short answer | No | `city` | Untuk harga di toko. Contoh: *Bandung* |
| 9 | Nama penjual (kalau online) | Short answer | No | `seller` | Contoh: *Wardah Official Store* |
| 10 | Tanggal dilihat | Date | Yes | `seen_on` | |

## Section 3: Harga

| # | Question title | Type | Required | Column | Help text / options |
|---|---|---|---|---|---|
| 11 | Harga yang dibayar (Rp) | Short answer, validation **Number > 0** | Yes | `price` | Angka saja tanpa titik. Contoh: *23900* |
| 12 | Untuk berapa barang? | Short answer, validation **Whole number ≥ 1** | Yes | `qty` | Biasanya *1*. "2 seharga" = 2, "Beli 2 Gratis 1" = 3 |
| 13 | Harga coret / harga normal di label (Rp) | Short answer, validation **Number > 0** | No | `was` | Harga untuk **satu** barang. Kosongkan kalau tidak ada |
| 14 | Jenis promo | Multiple choice | Yes | `promo` | Tidak ada promo (harga biasa) → regular; Diskon → diskon; Harga spesial → harga-spesial; Beli X gratis Y → beli-x-gratis-y; Paket / 2 seharga → bundling; Tebus murah (minimal belanja) → tebus-murah; Harga member → harga-member; Cashback → cashback; Voucher / kode promo → voucher; Flash sale → flash-sale; Dapat hadiah barang lain → hadiah |
| 15 | Tulisan promo di label | Short answer | No | `label` (+ `badge` if it contains a %) | Contoh: *Diskon 25%*, *2 seharga 14.900* |
| 16 | Promo berlaku sampai | Date | No | `valid_until` | |
| 17 | Syarat promo | Checkboxes | No | `member`, `min_purchase` | Khusus member; Ada minimal belanja; Harus bayar pakai e-wallet/kartu tertentu |
| 18 | Minimal belanja (Rp) | Short answer, validation **Number** | No | `min_purchase` | Hanya kalau ada minimal belanja |

## Section 4: Bukti

| # | Question title | Type | Required | Column | Help text / options |
|---|---|---|---|---|---|
| 19 | Foto label harga atau tangkapan layar | File upload: **Images only, max 3 files, 10 MB** | Yes | evidence (stays in Drive) | Label dan ukuran terbaca jelas. Jangan ada wajah orang atau nomor kartu |
| 20 | Link produk (kalau online) | Short answer, validation **URL** | No | `source.url` | |
| 21 | Nama panggilan untuk dicantumkan | Short answer | No | `contributor` | Boleh dikosongkan. Jangan email atau nomor HP |
| 22 | Persetujuan | Checkboxes | Yes | - | *Saya mengizinkan harga ini dipublikasikan di Kang Nawar.* |

## After the form exists

1. Send the public form link (the "Send" button, link icon, shorten URL). It goes in
   `src/lib/site.ts` as `SUBMIT_FORM_URL`, and the "Tambah harga" page shows a button.
2. For the daily import (Phase 3) the GitHub Action reads the sheet privately with a
   Google service account; the sheet is **never** published publicly, because it holds
   raw submissions:
   - Google Cloud console: create a project, enable the **Google Sheets API**,
     create a **service account**, add a JSON key.
   - Share the response sheet with the service account's email as **Viewer**.
   - GitHub repo, Settings, Secrets and variables, Actions: add secrets
     `GOOGLE_SERVICE_ACCOUNT` (the JSON key) and `KIRIMAN_SHEET_ID` (the long id in
     the sheet URL).
   The Action then: reads rows newer than the last import, writes a batch, runs
   `batch_import.py` (duplicate hints included), validates, and opens one pull request
   per day listing each row with a link to its photo in Drive for the reviewer.
