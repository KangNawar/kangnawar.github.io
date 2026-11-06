import json
import unittest

from helpers import TempRepo

import batch_import
import validate
from datetime import date


class BatchImportTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def run_batch(self, items):
        batch = {"batch": "test-batch", "defaults": {
            "store": "superindo", "channel": "offline", "seen_on": "2026-11-06",
            "valid_from": "2026-11-05", "valid_until": "2026-11-11", "source_type": "catalogue"},
            "items": items}
        path = self.repo.root / "batch.json"
        path.write_text(json.dumps(batch), encoding="utf-8")
        return batch_import.run(path, self.repo.root, dry_run=False)

    def test_ids_sizes_and_validation(self):
        rc = self.run_batch([
            {"brand": "Milo", "name": "3 in 1", "size": "18x34g", "cat": "makanan-minuman/minuman-serbuk",
             "price": 57900, "was": 67990, "badge": 15},
            {"brand": "Tanpa Merek", "name": "Kentang", "loose": True, "cat": "produk-segar/sayur",
             "price": 2390, "was": 2790, "badge": 25},
            {"brand": "Cimory", "name": "Squeeze", "size": "120g", "cat": "makanan-minuman/yogurt-puding",
             "price": 14900, "was": 9990, "qty": 2, "promo": "bundling"},
            {"brand": "So Nice", "name": "Nugget", "size": "450g", "cat": "makanan-minuman/makanan-beku",
             "price": 41990, "promo": "regular"},
        ])
        self.assertEqual(rc, 0)
        products = self.repo.root / "data/products"
        milo = json.loads((products / "milo-3-in-1-18x34g.json").read_text())
        self.assertEqual((milo["size"], milo["pack_count"]), ({"amount": 34, "unit": "g"}, 18))
        self.assertTrue((products / "kentang-curah.json").exists())
        nugget = json.loads((self.repo.root / "data/observations/2026/11/2026-11-06_superindo_so-nice-nugget-450g.json").read_text())
        self.assertNotIn("promo", nugget)
        self.assertNotIn("valid_until", nugget)
        self.assertEqual(validate.validate(self.repo.root, date(2026, 11, 6)).errors, [])

    def test_repeat_sighting_gets_suffix(self):
        item = {"brand": "Kahf", "name": "EDT", "size": "35ml", "cat": "perawatan-tubuh-rambut/parfum",
                "price": 70350, "was": 87890}
        self.run_batch([item, dict(item, price=123100, qty=2, promo="bundling")])
        files = sorted(p.name for p in (self.repo.root / "data/observations/2026/11").iterdir())
        self.assertEqual(files, ["2026-11-06_superindo_kahf-edt-35ml-2.json", "2026-11-06_superindo_kahf-edt-35ml.json"])

    def test_duplicate_hint(self):
        import io, contextlib
        self.repo.product("rinso-detergen-bubuk-anti-noda-1295g", amount=1295, unit="g", brand="Rinso",
                          name="Detergen Bubuk Anti Noda", category="kebutuhan-rumah", subcategory="deterjen")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.run_batch([{"brand": "Rinso", "name": "Anti Noda Detergen Bubuk Rose", "size": "1295g",
                             "cat": "kebutuhan-rumah/deterjen", "price": 26900}])
        self.assertIn("looks like existing 'rinso-detergen-bubuk-anti-noda-1295g'", buf.getvalue())

    def test_bad_size_is_reported(self):
        rc = self.run_batch([{"brand": "X", "name": "Y", "size": "sebungkus", "cat": "sembako/garam", "price": 1000}])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
