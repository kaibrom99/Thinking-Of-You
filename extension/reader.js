// Reads a product's details from the current page. Shared by the tracker (content.js)
// and the popup's "Add this page" button. Safe to load twice.
(() => {
  if (window.__toyReadPage) return;

  // Where each store's product pages live (keep in sync with catalog.py on the server)
  const PRODUCT_PATH = {
    "amazon.com": /\/(dp|gp\/product)\//, "etsy.com": /\/listing\//, "target.com": /\/p\//,
    "walmart.com": /\/ip\//, "ebay.com": /\/itm\//, "shein.com": /-p-\d+/, "sephora.com": /\/product\//,
    "ulta.com": /\/p\//, "lululemon.com": /\/p\//, "nike.com": /\/t\//, "urbanoutfitters.com": /\/shop\//,
    "asos.com": /\/prd\//, "gymshark.com": /\/products\//, "footlocker.com": /\/product\//,
    "gamestop.com": /\d{5,}\.html$/, "bestbuy.com": /\.p$/, "lego.com": /\/product\//,
    "barnesandnoble.com": /\/w\//, "fivebelow.com": /\/products\//, "depop.com": /\/products\//,
    "poshmark.com": /\/listing\//,
  };

  // Pages on a store's site that are never products (keep in sync with catalog.py)
  const NOT_PRODUCT = /\/(checkout|cart|bag|basket|payment|orders?|login|signin|sign-in|account|wishlist|favorites)(\/|$)/i;
  const NOT_PRODUCT_TITLE = /^\s*(checkout|(shopping |my |your )?(cart|bag|basket)|sign in|log in|login|order (confirmation|summary)|payment)\b/i;

  function isProductPage() {
    const host = location.hostname;
    const site = Object.keys(PRODUCT_PATH).find((d) => host === d || host.endsWith("." + d));
    return !!site && PRODUCT_PATH[site].test(location.pathname) && !NOT_PRODUCT.test(location.pathname);
  }

  // First number in the text, so "$19.99 - $29.99" gives 19.99 and "1,299.00" gives 1299
  const num = (v) => {
    const m = String(v ?? "").match(/\d[\d,]*(\.\d+)?/);
    return m ? parseFloat(m[0].replace(/,/g, "")) : null;
  };
  const meta = (sel) => document.querySelector(sel)?.content?.trim() || "";
  const cleanTitle = (t) => t.replace(/\s*[:|]\s*(Target|Walmart|SHEIN(?: \w+)?|eBay|Etsy)\s*$/i, "").trim();
  const https = (u) => {  // only secure, reasonably short image links are allowed
    try {
      const a = new URL(u, location.href).href;
      return a.startsWith("https://") && a.length <= 2000 ? a : "";
    } catch { return ""; }
  };
  const firstImage = (v) => { v = [].concat(v || [])[0]; return typeof v === "string" ? v : v?.url || ""; };

  function jsonPrice(n) {  // price from offers, price specs, or the first variant's offers
    const offers = [].concat(n.offers || n.hasVariant?.[0]?.offers || []).flatMap((o) => [o, ...[].concat(o?.offers || [])]);
    for (const o of offers) {
      const spec = [].concat(o?.priceSpecification || [])[0];
      const p = num(o?.price ?? o?.lowPrice ?? spec?.price);
      if (p) return p;
    }
    return null;
  }

  // 1) Structured data many stores publish (schema.org Product)
  function fromJsonLd() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      let data;
      try { data = JSON.parse(s.textContent); } catch { continue; }
      for (const n of [].concat(data, data?.["@graph"] || [])) {
        const types = [].concat(n?.["@type"] || []);
        if (!types.includes("Product") && !types.includes("ProductGroup")) continue;
        return { title: n.name, description: n.description, price: jsonPrice(n), image: firstImage(n.image) };
      }
    }
    return null;
  }

  // 2) Amazon doesn't publish that data, so read the page directly
  function fromAmazon() {
    const t = document.querySelector("#productTitle");
    if (!t) return null;
    const img = document.querySelector("#landingImage, #imgBlkFront");
    return { title: t.textContent, price: num(document.querySelector(".a-price .a-offscreen")?.textContent),
             image: img?.getAttribute("data-old-hires") || img?.src || "" };
  }

  // 3) Generic fallback: Open Graph tags
  function fromOpenGraph() {
    const title = meta('meta[property="og:title"]') || document.querySelector("h1")?.textContent || document.title;
    return title ? { title, price: num(meta('meta[property="product:price:amount"]') || meta('meta[property="og:price:amount"]') ||
                                  meta('meta[itemprop="price"]') || meta('meta[name="twitter:data1"]')) } : null;
  }

  // Price fallback: look for a price-looking element on the page, starting nearest the product title
  const OLD = /(^|[\s_-])(was|old|compare|strike\w*|original|msrp|crossed)(?=$|[\s_-])/i;
  const struck = (el) => {  // crossed-out "was" prices don't count
    for (let e = el, i = 0; e && i < 4; e = e.parentElement, i++) {
      if (/^(S|DEL|STRIKE)$/.test(e.tagName) || OLD.test(String(e.className || ""))) return true;
    }
    return false;
  };
  function priceIn(root) {
    const sel = '[itemprop="price"], [data-test*="price" i], [data-testid*="price" i], [class*="price" i], [aria-label*="price" i]';
    for (const el of root.querySelectorAll(sel)) {
      if (struck(el)) continue;
      const attr = el.getAttribute("content");
      const text = (attr || el.textContent || "").trim();
      if (!text || text.length > 40) continue;  // big blocks of text are not just a price
      if (/\$\s?\d/.test(text) || (attr && /^\d/.test(text))) {
        const n = num(text);
        if (n) return n;
      }
    }
    return null;
  }
  function findPrice() {
    for (let el = document.querySelector("h1"), depth = 0; el && depth < 6; el = el.parentElement, depth++) {
      const p = priceIn(el);
      if (p !== null) return p;
    }
    return priceIn(document);
  }

  // The biggest product-looking picture on screen: if the browser can show it, so can we
  function pageImage() {
    let best = "", bestArea = 0;
    for (const img of document.images) {
      const src = img.currentSrc || img.src || "";
      if (!src.startsWith("https://") || /\.svg(\?|$)/i.test(src) || !img.complete || img.naturalWidth < 200) continue;
      const r = img.getBoundingClientRect();
      const ratio = r.width / (r.height || 1);
      if (r.width < 150 || r.height < 150 || ratio < 0.4 || ratio > 2.5 || r.bottom < 0 || r.top > innerHeight * 1.2) continue;
      if (r.width * r.height > bestArea) { best = src; bestArea = r.width * r.height; }
    }
    return best;
  }

  function readPage() {
    const p = fromJsonLd() || fromAmazon() || fromOpenGraph();
    if (!p || !p.title) return null;
    return {
      url: location.href.length <= 2000 ? location.href : location.origin + location.pathname,
      title: cleanTitle(p.title),
      description: (p.description || meta('meta[property="og:description"]') || meta('meta[name="description"]')).trim(),
      price: p.price ?? findPrice(),
      image: https(pageImage()) || https(p.image) || https(meta('meta[property="og:image"]') || meta('meta[name="twitter:image"]')),
    };
  }

  window.__toyIsProductPage = isProductPage;
  window.__toyReadPage = readPage;
  window.__toyReadProduct = () => {
    if (!isProductPage()) return null;
    const p = readPage();
    return p && !NOT_PRODUCT_TITLE.test(p.title) ? p : null;
  };
})();