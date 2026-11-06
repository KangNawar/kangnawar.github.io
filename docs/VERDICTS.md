# How verdicts work

Every promo on Kang Nawar gets one verdict. It is computed from real price sightings
by `tools/pricing.py`; nobody picks it by hand. Thresholds live in `data/rules.json`
so they can be tuned without touching code.

## 1. Everything is compared per unit

Packs differ, so every price becomes **Rp per 100 ml**, **Rp per 100 g**, or **Rp per item/sheet**.

```
effective pack price = (price paid - guaranteed cashback) / packs received
unit price           = effective pack price / (size x pack_count) x 100   (ml, g)
                     = effective pack price / (size x pack_count)         (pcs, sheet)
```

Example: *Beli 2 Gratis 1* on a 50 ml tube for Rp 100.000 is 3 tubes,
so Rp 33.333 a tube, so **Rp 66.667 per 100 ml**.

## 2. The reference price

For each promo sighting we look at every *other* sighting of the same product,
at any store, online or offline, from **90 days before** to **14 days after** it.
The **reference price** is the median unit price of those sightings.

Regular-price sightings (no promo) are what make this work. Recording "I saw it at
the normal price today" is as useful as recording a sale.

## 3. The verdict

Checked in this order; the first that applies wins.

| Verdict | When |
| --- | --- |
| **Belum cukup data** | Fewer than 3 sightings in the window (including this one). We show the price, no judgement. |
| **Diskon palsu** | The store's claimed "normal" price is more than **15%** above the *highest* price anyone saw in the window. The price was inflated so the discount looks bigger. |
| **Lebih murah di tempat lain** | Another store or channel had it more than **3%** cheaper per unit within **14 days**. |
| **Hemat beneran** | At least **10%** below the reference price. |
| **Lebih mahal dari biasanya** | At least **10%** *above* the reference price, even though it is labelled a promo. |
| **Biasa aja** | Anything else: within 10% of the usual price. |

Sightings without a promo get no verdict ("Harga reguler"); they feed the reference.

## 4. Numbers shown next to a verdict

- **Real saving** = 1 - unit price / reference price. Used for the default sort, *Hemat beneran*.
- **Claimed discount** = 1 - unit price / claimed normal unit price. What the shelf tag says.
- **Deception gap** = claimed discount - real saving. Used for the *Paling menipu* sort.
  A tag saying "30%" on something that is really 12% *more* expensive has a gap of 42 points.

## 5. Expiry

A promo expires on its `valid_until` date, or **14 days** after it was seen if no
end date is known. Expired promos leave the home page but stay in price history.

## 6. Fairness

A verdict is a statement about a store, so every verdict must link to the sightings
it was computed from (date, store, price, photo). Wording on the site is
"menurut data kami" (according to our data). Anyone can report a wrong sighting,
and corrected data changes the verdict on the next daily build.
