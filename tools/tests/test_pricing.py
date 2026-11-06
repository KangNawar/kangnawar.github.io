import unittest
from datetime import date

from helpers import TempRepo

import pricing
from kn_data import load

TODAY = date(2026, 11, 7)
PROMO = {"type": "diskon"}


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def result(self, oid):
        out = pricing.compute(load(self.repo.root), TODAY)
        return next(r for r in out["observations"] if r["id"] == oid)

    def test_kentang_cheaper_at_astro(self):
        """The user's example: Super Indo promo Rp2.390/100 g vs Astro Rp22.410/kg."""
        r = self.repo
        r.product("kentang-curah", amount=1000, unit="g", loose=True)
        si = r.obs("kentang-curah", "superindo", "2026-11-06", 2390, claimed_normal_price=2790,
                   price_basis={"amount": 100, "unit": "g"}, promo={"type": "diskon", "claimed_pct": 25})
        r.obs("kentang-curah", "astro", "2026-11-07", 22410, channel="online")
        res = self.result(si["id"])
        self.assertEqual(res["unit_label"], "per kg")
        self.assertEqual(res["unit_price"], 23900.0)
        self.assertEqual(res["verdict"], pricing.ELSEWHERE)
        self.assertEqual(res["cheaper_elsewhere"]["store"], "astro")
        self.assertEqual(res["cheaper_elsewhere"]["unit_price"], 22410.0)
        self.assertEqual(res["cheaper_elsewhere"]["saving_pct"], 6.2)
        self.assertEqual(res["claimed_discount_pct"], 14.3)   # the store's own claim, shown but not judged
        self.assertEqual(res["badge_gap_pct"], 10.7)

    def test_no_other_store_means_no_comparison(self):
        r = self.repo
        r.product("p-alone")
        r.obs("p-alone", "guardian", "2026-10-20", 50000)  # same store's regular price is not "market"
        o = r.obs("p-alone", "guardian", "2026-11-01", 40000, claimed_normal_price=60000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.NO_COMPARE)

    def test_real_deal_vs_market(self):
        r = self.repo
        r.product("p-real")
        r.obs("p-real", "watsons", "2026-10-20", 50000)
        r.obs("p-real", "shopee", "2026-10-25", 52000, channel="online")
        o = r.obs("p-real", "guardian", "2026-11-01", 44000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.REAL)
        self.assertEqual(res["market_unit_price"], 102000.0)
        self.assertEqual(res["vs_market_pct"], 13.7)

    def test_market_price(self):
        r = self.repo
        r.product("p-mkt")
        r.obs("p-mkt", "watsons", "2026-10-20", 50000)
        o = r.obs("p-mkt", "guardian", "2026-11-01", 49000, claimed_normal_price=70000, promo=PROMO)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.MARKET)
        self.assertEqual(res["claimed_discount_pct"], 30.0)  # claims 30% but it is just the market price

    def test_above_market_when_cheaper_store_is_old(self):
        r = self.repo
        r.product("p-above")
        r.obs("p-above", "watsons", "2026-10-10", 40000)  # 22 days before: market, but not "now"
        o = r.obs("p-above", "guardian", "2026-11-01", 46000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.ABOVE)

    def test_small_difference_is_not_cheaper_elsewhere(self):
        r = self.repo
        r.product("p-margin")
        r.obs("p-margin", "shopee", "2026-11-02", 44000, channel="online")  # ~2% cheaper
        o = r.obs("p-margin", "watsons", "2026-11-01", 45000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.MARKET)

    def test_old_market_prices_ignored(self):
        r = self.repo
        r.product("p-old")
        r.obs("p-old", "watsons", "2026-08-01", 30000)  # > 30 days before
        o = r.obs("p-old", "guardian", "2026-11-01", 40000, promo=PROMO)
        self.assertEqual(self.result(o["id"])["verdict"], pricing.NO_COMPARE)

    def test_regular_sighting_gets_no_verdict_but_shows_cheaper_store(self):
        r = self.repo
        r.product("p-reg")
        r.obs("p-reg", "shopee", "2026-11-02", 30000, channel="online")
        o = r.obs("p-reg", "guardian", "2026-11-01", 40000)
        res = self.result(o["id"])
        self.assertEqual(res["verdict"], pricing.REGULAR)
        self.assertEqual(res["cheaper_elsewhere"]["store"], "shopee")


class UnitPriceTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def res(self, oid):
        out = pricing.compute(load(self.repo.root), TODAY)
        return next(r for r in out["observations"] if r["id"] == oid)

    def test_buy_2_get_1(self):
        self.repo.product("p-b2g1", amount=50)
        o = self.repo.obs("p-b2g1", "indomaret", "2026-10-01", 100000, quantity=3,
                          promo={"type": "beli-x-gratis-y", "label": "Beli 2 Gratis 1"})
        r = self.res(o["id"])
        self.assertEqual((r["unit_price"], r["unit_label"]), (66666.67, "per 100 ml"))

    def test_cashback_and_pack_count(self):
        self.repo.product("p-pack", amount=50, pack_count=3)
        o = self.repo.obs("p-pack", "shopee", "2026-10-01", 95000, channel="online",
                          promo={"type": "cashback", "cashback": 5000})
        self.assertEqual(self.res(o["id"])["unit_price"], 60000.0)

    def test_pieces_compare_per_item(self):
        self.repo.product("p-pcs", amount=10, unit="pcs")
        o = self.repo.obs("p-pcs", "alfamart", "2026-10-01", 25000)
        r = self.res(o["id"])
        self.assertEqual((r["unit_price"], r["unit_label"]), (2500.0, "per pcs"))

    def test_default_expiry(self):
        self.repo.product("p-exp")
        o = self.repo.obs("p-exp", "guardian", "2026-10-01", 40000, promo=PROMO)
        r = self.res(o["id"])
        self.assertEqual(r["expires_on"], "2026-10-15")
        self.assertTrue(r["expired"])

    def test_honest_badge_not_flagged(self):
        self.repo.product("p-badge")
        o = self.repo.obs("p-badge", "superindo", "2026-11-06", 17000, claimed_normal_price=20000,
                          promo={"type": "diskon", "claimed_pct": 15})
        self.assertIsNone(self.res(o["id"])["badge_gap_pct"])


if __name__ == "__main__":
    unittest.main()
