import json
import unittest

from helpers import TempRepo

import batch_import
import page_capture

# What the bookmarklet saved from a mock shop page (fictional products and prices).
CAPTURE = {
    "kind": "kangnawar-capture", "version": 1, "url": "https://www.ikea.co.id/in/promo",
    "title": "Promo", "captured_on": "2026-11-07",
    "cards": [
        {"text": "Keranjang Rp 0\nBerandaPromo", "href": "https://www.ikea.co.id/in/keranjang", "img_alt": "", "struck": []},
        {"text": "Harga terbaik baru\nSKOGVIK\nRak buku, putih, 80x28x202 cm\nRp999.000\nHarga sebelumnya Rp 1.299.000\n♡",
         "href": "https://www.ikea.co.id/in/produk/skogvik-10001", "img_alt": "SKOGVIK", "struck": ["Harga sebelumnya Rp 1.299.000"]},
        {"text": "TARNVIK\nKotak penyimpanan dengan tutup, 5 l\nRp49.900\nTambah ke troli",
         "href": "https://www.ikea.co.id/in/produk/tarnvik-10002", "img_alt": "", "struck": []},
        {"text": "Contoh Deterjen Cair Refill 1,8 kg\n-20%\nRp41.000 Rp32.500\n1,2 rb terjual",
         "href": "https://www.ikea.co.id/in/produk/deterjen-10003", "img_alt": "", "struck": ["Rp41.000"]},
    ],
    "jsonld": [{"@context": "https://schema.org", "@type": "Organization", "name": "Toko"}],
}

PRODUCT_PAGE = """<html><head><link rel="canonical" href="https://toko.example/p/123">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product",
"name":"Contoh Sabun Cair 400 ml","brand":{"@type":"Brand","name":"Contoh"},
"offers":{"@type":"Offer","price":"18900","priceCurrency":"IDR","priceValidUntil":"2026-11-30"}}]}</script>
</head><body></body></html>"""


class PageCaptureTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_cards_become_draft_items(self):
        batch = page_capture.build_batch(CAPTURE, None, None)
        self.assertEqual(batch["defaults"]["store"], "ikea")
        items = batch["items"]
        self.assertEqual([i["price"] for i in items], [999000, 49900, 32500])
        self.assertEqual(items[0]["was"], 1299000)
        self.assertEqual(items[0]["name"], "SKOGVIK, Rak buku, putih, 80x28x202 cm")
        self.assertEqual(items[0]["size"], "TODO")
        self.assertEqual(items[1]["promo"], "regular")
        self.assertEqual(items[1]["size"], "5l")
        self.assertEqual((items[2]["was"], items[2]["badge"], items[2]["size"]), (41000, 20, "1.8kg"))
        self.assertEqual(batch["skipped"][0]["card"], 1)

    def test_two_prices_without_strikethrough_are_flagged(self):
        card = {"text": "Contoh Teh 25s\nRp12.000\nRp15.000", "href": "https://x.example/a", "struck": []}
        item, _ = page_capture.card_item(card)
        self.assertEqual((item["price"], item["was"]), (12000, 15000))
        self.assertIn("CHECK", item["check"])

    def test_saved_page_reads_schema_org_product(self):
        page = self.repo.root / "page.html"
        page.write_text(PRODUCT_PAGE, encoding="utf-8")
        batch = page_capture.build_batch(page_capture.read_saved_page(page), "lainnya", None)
        item = batch["items"][0]
        self.assertEqual((item["brand"], item["price"], item["size"]), ("Contoh", 18900, "400ml"))
        self.assertEqual(item["valid_until"], "2026-11-30")
        self.assertEqual(item["url"], "https://toko.example/p/123")

    def test_main_writes_batch_and_import_refuses_todo(self):
        src = self.repo.root / "inbox" / "ikea" / "harga.json"
        src.parent.mkdir(parents=True)
        src.write_text(json.dumps(CAPTURE), encoding="utf-8")
        self.assertEqual(page_capture.main([str(src), "--root", str(self.repo.root)]), 0)
        out = src.with_name("batch.json")
        self.assertTrue(out.exists())
        self.assertEqual(batch_import.run(out, self.repo.root, dry_run=True), 1)
        batch = json.loads(out.read_text())
        batch["items"] = [dict(batch["items"][2], brand="Contoh", cat="kebutuhan-rumah/deterjen")]
        out.write_text(json.dumps(batch), encoding="utf-8")
        self.assertEqual(batch_import.run(out, self.repo.root, dry_run=True), 0)

    def test_unknown_store_is_refused(self):
        src = self.repo.root / "harga.json"
        src.write_text(json.dumps(CAPTURE), encoding="utf-8")
        self.assertEqual(page_capture.main([str(src), "--store", "nope", "--root", str(self.repo.root)]), 1)


if __name__ == "__main__":
    unittest.main()
