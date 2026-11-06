// Build-time data access. Everything here runs in Node during `astro build`.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const read = (p: string) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf-8'));

export type Size = { amount: number; unit: 'ml' | 'g' | 'pcs' | 'sheet' };
export interface Product {
  id: string; brand: string; name: string; variant?: string; size: Size;
  pack_count?: number; loose?: boolean; category: string; subcategory: string; image?: string;
}
export interface RawObs {
  id: string; product: string; store: string; seller?: string; channel: 'offline' | 'online'; city?: string;
  price: number; quantity?: number; claimed_normal_price?: number; price_basis?: Size;
  promo?: { type: string; label?: string; cashback?: number; min_purchase?: number; member_only?: boolean; payment_method?: string; claimed_pct?: number };
  seen_on: string; valid_from?: string; valid_until?: string;
  source: { type: string; url?: string; image?: string; contributor?: string }; notes?: string;
}
export interface Computed {
  id: string; product: string; store: string; channel: string; seen_on: string; is_promo: boolean;
  effective_pack_price: number; unit_price: number; unit_label: string;
  market_unit_price: number | null; market_stores: string[]; market_count: number; vs_market_pct: number | null;
  claimed_discount_pct: number | null; badge_pct: number | null; badge_gap_pct: number | null;
  cheaper_elsewhere: { id: string; store: string; channel: string; seen_on: string; unit_price: number; saving_pct: number } | null;
  verdict: string; verdict_label: string; expires_on: string | null; expired: boolean;
}
export interface Store { id: string; name: string; type: string; channels: string[] }
export interface Sub { id: string; name: string; unit: string }
export interface Category { id: string; name: string; active?: boolean; subcategories: Sub[] }
export interface PromoType { id: string; name: string; description: string }

export interface Sighting extends Computed {
  raw: RawObs; productData: Product; storeData: Store; promoName?: string;
}

function loadDir<T>(dir: string): T[] {
  const abs = path.join(ROOT, dir);
  if (!fs.existsSync(abs)) return [];
  const out: T[] = [];
  for (const entry of fs.readdirSync(abs, { withFileTypes: true, recursive: true } as any) as any[]) {
    if (entry.isFile() && entry.name.endsWith('.json')) {
      const parent = entry.parentPath ?? entry.path;
      out.push(JSON.parse(fs.readFileSync(path.join(parent, entry.name), 'utf-8')));
    }
  }
  return out;
}

let cache: ReturnType<typeof build> | null = null;

function build() {
  const categories: Category[] = read('data/categories.json');
  const stores: Store[] = read('data/stores.json');
  const promoTypes: PromoType[] = read('data/promo-types.json');
  const products = new Map(loadDir<Product>('data/products').map((p) => [p.id, p]));
  const raws = new Map(loadDir<RawObs>('data/observations').map((o) => [o.id, o]));
  const computedFile = path.join(ROOT, 'build/computed.json');
  if (!fs.existsSync(computedFile)) {
    throw new Error('build/computed.json is missing. Run `npm run data` (python tools/pricing.py) first.');
  }
  const computed = JSON.parse(fs.readFileSync(computedFile, 'utf-8'));
  const storeMap = new Map(stores.map((s) => [s.id, s]));
  const promoMap = new Map(promoTypes.map((p) => [p.id, p.name]));

  const sightings: Sighting[] = (computed.observations as Computed[])
    .filter((c) => raws.has(c.id) && products.has(c.product))
    .map((c) => {
      const raw = raws.get(c.id)!;
      return {
        ...c, raw, productData: products.get(c.product)!, storeData: storeMap.get(c.store)!,
        promoName: raw.promo ? promoMap.get(raw.promo.type) : undefined,
      };
    });

  const byProduct = new Map<string, Sighting[]>();
  for (const s of sightings) {
    if (!byProduct.has(s.product)) byProduct.set(s.product, []);
    byProduct.get(s.product)!.push(s);
  }
  for (const list of byProduct.values()) list.sort((a, b) => b.seen_on.localeCompare(a.seen_on));

  return {
    generatedOn: computed.generated_on as string,
    categories, stores, storeMap, promoTypes, products, sightings, byProduct,
    activeCategories: categories.filter((c) => c.active !== false),
  };
}

export function db() {
  return (cache ??= build());
}

export function activePromos() {
  return db().sightings.filter((s) => s.is_promo && !s.expired);
}

export function categoryOf(p: Product) {
  const c = db().categories.find((c) => c.id === p.category)!;
  return { category: c, sub: c.subcategories.find((s) => s.id === p.subcategory)! };
}
