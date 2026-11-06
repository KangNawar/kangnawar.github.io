import { db, categoryOf } from '../lib/data';
import { productName, ukuran } from '../lib/format';

export function GET() {
  const { products, byProduct } = db();
  const index = [...products.values()].map((p) => {
    const { category, sub } = categoryOf(p);
    const latest = byProduct.get(p.id)?.[0];
    return {
      id: p.id,
      n: productName(p),
      s: ukuran(p),
      v: p.variant ?? '',
      c: `${category.name}, ${sub.name}`,
      t: latest?.storeData.name ?? '',
      p: latest?.raw.price ?? null,
    };
  });
  return new Response(JSON.stringify(index), { headers: { 'Content-Type': 'application/json' } });
}
