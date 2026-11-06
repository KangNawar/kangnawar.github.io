import unittest
from datetime import date

from helpers import TempRepo

import pricing
from kn_data import load

TODAY = date(2026, 11, 6)
PROMO = {"type": "diskon"}


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def result(self, oid):
        out = pricing.compute(load(self.repo.root), TODAY)
        return next(r for r in out["observations"] if r["id"] == oid)

    def regulars(self, pid, prices, store="guardian"):
        for i, (day, price) in enumerate(prices):
            self.repo.obs(pid, store, day, price)

    def test_fake_discount(self):
        r = self.repo
        r.product("p-fake")
        self.regulars("p-fake", [("2026-08-01", 50000), ("2026-09-01", 50000)])
        r.obs("p-fake", "watsons", "2026-09-15", 52000)
        o = r.obs("p-fake", "guardian", "2026-10-01", 56000, claimed_normal_price=80000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.FAKE)
        self.assertEqual(res["claimed_discount_pct"], 30.0)
        self.assertEqual(res["real_saving_pct"], -12.0)  # paid MORE than the usual 100k / 100 ml
        self.assertEqual(res["deception_gap_pct"], 42.0)

    def test_real_deal(self):
        r = self.repo
        r.product("p-real")
        self.regulars("p-real", [("2026-08-01", 50000), ("2026-09-01", 50000), ("2026-09-20", 50000)])
        o = r.obs("p-real", "guardian", "2026-10-01", 40000, claimed_normal_price=50000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.REAL)
        self.assertEqual(res["real_saving_pct"], 20.0)
        self.assertEqual(res["deception_gap_pct"], 0.0)

    def test_cheaper_elsewhere_online(self):
        r = self.repo
        r.product("p-else")
        self.regulars("p-else", [("2026-08-01", 50000), ("2026-09-01", 50000)])
        r.obs("p-else", "shopee", "2026-10-05", 40000, channel="online")
        o = r.obs("p-else", "watsons", "2026-10-10", 45000, claimed_normal_price=55000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.ELSEWHERE)
        self.assertEqual(res["cheaper_elsewhere"]["store"], "shopee")
        self.assertEqual(res["cheaper_elsewhere"]["unit_price"], 80000.0)

    def test_elsewhere_ignores_small_differences(self):
        r = self.repo
        r.product("p-margin")
        self.regulars("p-margin", [("2026-08-01", 50000), ("2026-09-01", 50000)])
        r.obs("p-margin", "shopee", "2026-10-05", 44000, channel="online")  # only ~2% cheaper
        o = r.obs("p-margin", "watsons", "2026-10-10", 45000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.NORMAL)

    def test_pricier_than_usual(self):
        r = self.repo
        r.product("p-pricy")
        self.regulars("p-pricy", [("2026-08-01", 50000), ("2026-09-01", 52000)])
        o = r.obs("p-pricy", "guardian", "2026-10-01", 58000, claimed_normal_price=59000,
                  promo={"type": "harga-member", "member_only": True})
        self.assertEqual(self.result(o["id"])["verdict"], pricing.PRICIER)

    def test_normal_price(self):
        r = self.repo
        r.product("p-normal")
        self.regulars("p-normal", [("2026-08-01", 50000), ("2026-09-01", 50000)])
        o = r.obs("p-normal", "guardian", "2026-10-01", 48000, claimed_normal_price=52000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.NORMAL)

    def test_not_enough_data(self):
        r = self.repo
        r.product("p-new")
        o = r.obs("p-new", "guardian", "2026-10-01", 40000, claimed_normal_price=90000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.NO_DATA)
        self.assertEqual(res["claimed_discount_pct"], 55.6)

    def test_old_sightings_outside_window_are_ignored(self):
        r = self.repo
        r.product("p-old")
        self.regulars("p-old", [("2026-01-01", 30000), ("2026-02-01", 30000)])  # > 90 days before
        o = r.obs("p-old", "guardian", "2026-10-01", 40000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.NO_DATA)

    def test_regular_sighting_has_no_verdict(self):
        r = self.repo
        r.product("p-reg")
        o = r.obs("p-reg", "guardian", "2026-10-01", 40000)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.REGULAR)
        self.assertIsNone(res["expires_on"])


class UnitPriceTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def unit(self, oid):
        out = pricing.compute(load(self.repo.root), TODAY)
        return next(r for r in out["observations"] if r["id"] == oid)

    def test_buy_2_get_1(self):
        self.repo.product("p-b2g1", amount=50)
        o = self.repo.obs("p-b2g1", "indomaret", "2026-10-01", 100000, quantity=3,
                          promo={"type": "beli-x-gratis-y", "label": "Beli 2 Gratis 1"})
        res = self.unit(o["id"])
        self.assertEqual(res["unit_price"], 66666.67)
        self.assertEqual(res["unit_label"], "per 100 ml")

    def test_cashback_and_pack_count(self):
        self.repo.product("p-pack", amount=50, pack_count=3)
        o = self.repo.obs("p-pack", "shopee", "2026-10-01", 95000, channel="online",
                          promo={"type": "cashback", "cashback": 5000})
        self.assertEqual(self.unit(o["id"])["unit_price"], 60000.0)  # 90k for 150 ml

    def test_pieces_compare_per_item(self):
        self.repo.product("p-pcs", amount=10, unit="pcs")
        o = self.repo.obs("p-pcs", "alfamart", "2026-10-01", 25000)
        res = self.unit(o["id"])
        self.assertEqual((res["unit_price"], res["unit_label"]), (2500.0, "per pcs"))

    def test_default_expiry(self):
        self.repo.product("p-exp")
        o = self.repo.obs("p-exp", "guardian", "2026-10-01", 40000, promo=PROMO)
        res = self.unit(o["id"])
        self.assertEqual(res["expires_on"], "2026-10-15")
        self.assertTrue(res["expired"])

    def test_valid_until_wins(self):
        self.repo.product("p-vu")
        o = self.repo.obs("p-vu", "guardian", "2026-11-01", 40000, promo=PROMO, valid_until="2026-11-30")
        res = self.unit(o["id"])
        self.assertEqual(res["expires_on"], "2026-11-30")
        self.assertFalse(res["expired"])


if __name__ == "__main__":
    unittest.main()
