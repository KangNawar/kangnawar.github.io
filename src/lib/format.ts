const rp = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 });
export const rupiah = (n: number) => `Rp${rp.format(Math.round(n))}`;
export const pct = (n: number) => `${new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(n)}%`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
export function tanggal(iso: string, withYear = false) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]}${withYear ? ' ' + y : ''}`;
}
export function rentang(from?: string, to?: string | null) {
  if (from && to) {
    const sameMonth = from.slice(0, 7) === to.slice(0, 7);
    return sameMonth ? `${Number(from.slice(8))}–${tanggal(to)}` : `${tanggal(from)} – ${tanggal(to)}`;
  }
  return to ? `s.d. ${tanggal(to)}` : '';
}

const UNIT_WORD: Record<string, string> = { ml: 'ml', g: 'g', pcs: 'pcs', sheet: 'lembar' };
export function ukuran(p: { size: { amount: number; unit: string }; pack_count?: number; loose?: boolean }) {
  if (p.loose) return 'curah';
  const amt = new Intl.NumberFormat('id-ID').format(p.size.amount);
  const one = p.size.unit === 'pcs' ? `isi ${amt}` : `${amt} ${UNIT_WORD[p.size.unit]}`;
  return p.pack_count && p.pack_count > 1 ? `${p.pack_count} × ${one}` : one;
}
export function satuan(label: string) {
  return label.replace('per 100 ', '/100 ').replace('per kg', '/kg').replace('per pcs', '/pcs').replace('per lembar', '/lembar');
}
export const productName = (p: { brand: string; name: string }) =>
  p.brand === 'Tanpa Merek' ? p.name : `${p.brand} ${p.name}`;
