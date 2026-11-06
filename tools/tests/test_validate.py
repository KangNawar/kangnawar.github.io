import json
import unittest
from datetime import date

from PIL import Image

from helpers import TempRepo

import validate

TODAY = date(2026, 11, 6)


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.product("p-ok")
        self.repo.obs("p-ok", "guardian", "2026-10-01", 40000)

    def tearDown(self):
        self.repo.cleanup()

    def errors(self):
        return validate.validate(self.repo.root, TODAY).errors

    def assertErrorLike(self, needle):
        errs = self.errors()
        self.assertTrue(any(needle in e for e in errs), f"no error containing {needle!r} in {errs}")

    def test_clean_data_passes(self):
        self.assertEqual(self.errors(), [])

    def test_real_reference_data_passes(self):
        rep = validate.validate(validate.REPO_ROOT, TODAY)
        self.assertEqual(rep.errors, [])

    def test_unknown_store(self):
        self.repo.obs("p-ok", "toko-hantu", "2026-10-02", 40000)
        self.assertErrorLike("unknown store 'toko-hantu'")

    def test_unknown_product(self):
        self.repo.obs("p-missing", "guardian", "2026-10-02", 40000)
        self.assertErrorLike("unknown product 'p-missing'")

    def test_wrong_channel(self):
        self.repo.obs("p-ok", "shopee", "2026-10-02", 40000, channel="offline")
        self.assertErrorLike("has no 'offline' channel")

    def test_wrong_folder(self):
        rec = self.repo.obs("p-ok", "guardian", "2026-10-03", 40000)
        src = self.repo.root / "data/observations/2026/10" / f"{rec['id']}.json"
        dst = self.repo.root / "data/observations/2026/09" / src.name
        dst.parent.mkdir(parents=True)
        src.rename(dst)
        self.assertErrorLike("must be stored in data/observations/2026/10/")

    def test_price_must_be_whole_rupiah(self):
        self.repo.obs("p-ok", "guardian", "2026-10-04", 39999.5)
        self.assertErrorLike("price")

    def test_unknown_subcategory(self):
        self.repo.product("p-bad", subcategory="obeng")
        self.assertErrorLike("unknown subcategory 'obeng'")

    def test_duplicate_sighting(self):
        self.repo.obs("p-ok", "guardian", "2026-10-01", 40000, suffix="-2")
        self.assertErrorLike("duplicate of")

    def test_contributor_privacy(self):
        self.repo.obs("p-ok", "guardian", "2026-10-05", 40000,
                      source={"type": "photo", "contributor": "budi@example.com"})
        self.assertErrorLike("looks like an email or phone")

    def test_future_date(self):
        self.repo.obs("p-ok", "guardian", "2026-12-25", 40000)
        self.assertErrorLike("in the future")

    def test_bad_json(self):
        p = self.repo.root / "data/products/p-broken.json"
        p.write_text("{ not json", encoding="utf-8")
        self.assertErrorLike("not valid JSON")

    def test_image_rules(self):
        img_dir = self.repo.root / "public/img/products"
        img_dir.mkdir(parents=True)
        Image.new("RGB", (40, 40), "white").save(img_dir / "p-img.webp", "WEBP")
        self.repo.product("p-img", image="img/products/p-img.webp")
        self.assertEqual(self.errors(), [])
        # A PNG renamed to .webp is caught
        Image.new("RGB", (40, 40), "white").save(img_dir / "p-img.webp", "PNG")
        self.assertErrorLike("not WebP")

    def test_oversized_image(self):
        import os
        img_dir = self.repo.root / "public/img/products"
        img_dir.mkdir(parents=True)
        Image.frombytes("RGB", (900, 900), os.urandom(900 * 900 * 3)).save(
            img_dir / "p-big.webp", "WEBP", quality=100)
        self.repo.product("p-big", image="img/products/p-big.webp")
        self.assertErrorLike("limit 20 KB")


if __name__ == "__main__":
    unittest.main()
