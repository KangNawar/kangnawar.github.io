// "Ambil harga" bookmarklet. Source of the button on /infoadmin/.
//
// Run it on a shop page AFTER the products have loaded (scroll to the bottom
// first on pages that load more as you scroll). It saves one JSON file with
// what the browser shows: every product card that has a "Rp" price and a link,
// plus any schema.org Product data the page carries. Nothing is sent anywhere.
// Then: python tools/page_capture.py <file> --store <id>
//
// Keep it plain ES2017 and free of // comments inside code lines: the build
// strips comment lines and joins the rest into one javascript: URL.
(() => {
  const PRICE = /Rp\s?\d/;
  const clean = (t) => (t || '').replace(/ /g, ' ').split('\n').map((l) => l.trim()).filter(Boolean).join('\n');
  const hrefOf = (a) => {
    const h = a.getAttribute('href') || '';
    if (!h || h.startsWith('#') || h.startsWith('javascript:')) return '';
    try { return new URL(h, location.href).href.split('#')[0]; } catch (e) { return ''; }
  };
  const linksIn = (el) => {
    const set = new Set();
    const up = el.closest('a[href]');
    if (up && hrefOf(up)) set.add(hrefOf(up));
    el.querySelectorAll('a[href]').forEach((a) => { const h = hrefOf(a); if (h) set.add(h); });
    return set;
  };
  const priced = (el) => PRICE.test(el.innerText || '') && linksIn(el).size >= 1;
  const isCard = (el) => {
    const text = el.innerText || '';
    if (text.length > 700 || !PRICE.test(text)) return false;
    const links = linksIn(el);
    if (links.size < 1 || links.size > 3) return false;
    const parts = Array.from(el.children).filter(priced).map((c) => Array.from(linksIn(c)).sort().join(' '));
    return new Set(parts).size < 2;
  };
  const candidates = Array.from(document.body.querySelectorAll('*')).filter((el) => {
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'svg', 'HEAD'].includes(el.tagName)) return false;
    if (!(el.textContent || '').includes('Rp')) return false;
    if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return false;
    return isCard(el);
  });
  const set = new Set(candidates);
  const cards = [];
  const seen = new Set();
  for (const el of candidates) {
    if (el.parentElement && set.has(el.parentElement)) continue;
    const links = Array.from(linksIn(el));
    const text = clean(el.innerText);
    const key = links[0] + '|' + text;
    if (seen.has(key)) continue;
    seen.add(key);
    const img = el.querySelector('img[alt]');
    const struck = Array.from(el.querySelectorAll('s, del, strike, [style*="line-through"], [class*="strike"], [class*="previous"], [class*="old-price"], [class*="was"]'))
      .map((n) => clean(n.innerText)).filter((t) => PRICE.test(t));
    cards.push({ text, href: links[0], img_alt: img ? img.getAttribute('alt') : '', struck });
  }
  const jsonld = [];
  document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    try { jsonld.push(JSON.parse(s.textContent)); } catch (e) {}
  });
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const day = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
  const out = { kind: 'kangnawar-capture', version: 1, url: location.href, title: document.title, captured_on: day, captured_at: now.toISOString(), cards, jsonld };
  const blob = new Blob([JSON.stringify(out, null, 1)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'harga-' + location.hostname.replace(/^www\./, '') + '-' + day + '.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  alert('Kang Nawar: ' + cards.length + ' produk berharga tersimpan' + (jsonld.length ? ' (+ data terstruktur)' : '') + '.');
})();
