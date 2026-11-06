import json
import unittest

from helpers import TempRepo

import form_inbox


class FormInboxTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.csv = self.repo.root / "kiriman.csv"
        self.rows = ["Timestamp,Nama produk,Harga,Foto label harga,Link produk",
                     "07/11/2026 1:23:45,Wardah Hydra Rose 50ml,\"Rp 45.000\",https://drive.google.com/x,https://shopee.co.id/abc",
                     "08/11/2026 9:00:00,Rinso 1.295 kg,26900,https://drive.google.com/y,"]
        self.csv.write_text("\n".join(self.rows), encoding="utf-8")

    def tearDown(self):
        self.repo.cleanup()

    def batch(self):
        out = next((self.repo.root / "inbox").glob("form-*/batch.json"))
        return json.loads(out.read_text())

    def test_new_rows_become_draft_items(self):
        self.assertEqual(form_inbox.main([str(self.csv), "--root", str(self.repo.root)]), 0)
        items = self.batch()["items"]
        self.assertEqual([i["price"] for i in items], [45000, 26900])
        self.assertEqual((items[0]["store"], items[0]["channel"], items[0]["seen_on"]), ("shopee", "online", "2026-11-07"))
        self.assertEqual(items[0]["url"], "https://shopee.co.id/abc")
        self.assertEqual(items[1]["store"], "TODO")
        self.assertEqual(items[0]["brand"], "TODO")

    def test_second_run_only_takes_new_rows(self):
        form_inbox.main([str(self.csv), "--root", str(self.repo.root)])
        self.csv.write_text("\n".join(self.rows + ["09/11/2026 8:00:00,Kentang 1 kg,22000,,"]), encoding="utf-8")
        for f in (self.repo.root / "inbox").glob("form-*/batch.json"):
            f.unlink()
        form_inbox.main([str(self.csv), "--root", str(self.repo.root)])
        items = self.batch()["items"]
        self.assertEqual([i["as_submitted"] for i in items], ["Kentang 1 kg"])


if __name__ == "__main__":
    unittest.main()
