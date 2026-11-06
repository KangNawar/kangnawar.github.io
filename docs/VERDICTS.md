# How comparisons work

Kang Nawar answers one question: **is this cheaper than elsewhere?**
Every promo is compared with the **market price**: what *other* stores charged for
the same product recently. The store's own strikethrough price is shown as the
store's claim, but it is never the yardstick. The tone is a friendly tip
("di Astro lebih murah"), not an accusation.

Computed by `tools/pricing.py`; thresholds in `data/rules.json`.

## 1. One product, many variants

A product is **brand + line + size**. Scents, flavours and colours that the brand
prices the same are the same product (Rinso Anti Noda 1,295 g is one product whatever
the fragrance). A different size is a different product. When importing, the tools
warn when a new item looks like an existing one.

## 2. Everything is compared per unit

```
effective pack price = (price paid - guaranteed cashback) / packs received
unit price           = effective pack price / amount bought x basis
```

Basis: **per kg** for loose goods (curah), **per 100 ml / 100 g** for packaged goods,
**per item / sheet** for counts. Super Indo's kentang at Rp2.390 per 100 g is
Rp23.900 per kg, so it can be compared with Astro's Rp22.410 per kg.

## 3. Market price

The market price of a sighting is the median unit price of the same product at
**other stores**, online or offline, from **30 days before to 14 days after** it.
The same store's own earlier prices do not count as "market".

## 4. The verdict

Checked in this order; the first that applies wins.

| Verdict | When |
| --- | --- |
| **Lebih murah di tempat lain** | Another store had it more than **3%** cheaper per unit within **14 days**. The site names the store and its price. |
| **Belum ada pembanding** | No other store's price in the window yet. |
| **Hemat beneran** | At least **10%** below the market price. |
| **Di atas harga pasar** | At least **10%** above the market price. |
| **Sesuai harga pasar** | Within 10% of the market price, whatever the label says. |

Regular sightings (no promo) get no verdict ("Harga reguler"), but they are part of
other stores' market price and they also show "lebih murah di ..." when relevant.

## 5. The store's own label

Shown quietly on the product page only: the discount the store claims against its
strikethrough price, and, if the printed badge % is more than 3 points higher than
that arithmetic, a neutral note. It does not affect the verdict.

## 6. Expiry

A promo expires on its `valid_until`, or 14 days after it was seen. Expired promos
leave the home page but stay in price history and keep counting as market prices.
