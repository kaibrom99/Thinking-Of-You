// Runs on the allowlisted shopping sites, in the user's own browser. Only product pages are ever reported.
const PRODUCT_PATH = {
  "amazon.com": /\/(dp|gp\/product)\//,
  "etsy.com": /\/listing\//,
  "target.com": /\/p\//,
  "walmart.com": /\/ip\//,
  "ebay.com": /\/itm\//,
  "shein.com": /-p-\d+/,
};

function isProductPage() {
  const host = location.hostname;
  const site = Object.keys(PRODUCT_PATH).find((d) => host === d || host.endsWith("." + d));
  return !!site && PRODUCT_PATH[site].test(location.pathname);
}

// First number in the text, so "$19.99 - $29.99" gives 19.99 and "1,299.00" gives 1299
const num = (v) => {
  const m = String(v ?? "").match(/\d[\d,]*(\.\d+)?/);
  return m ? parseFloat(m[0].replace(/,/g, "")) : null;
};
const meta = (sel) => document.querySelector(sel)?.content?.trim() || "";
const cleanTitle = (t) => t.replace(/\s*[:|]\s*(Target|Walmart|SHEIN(?: \w+)?|eBay|Etsy)\s*$/i, "").trim();

// 1) Structured data many stores publish (schema.org Product)
function fromJsonLd() {
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    let data;
    try { data = JSON.parse(s.textContent); } catch { continue; }
    for (const n of [].concat(data, data?.["@graph"] || [])) {
      if (![].concat(n?.["@type"] || []).includes("Product")) continue;
      const offer = [].concat(n.offers || [])[0] || {};
      return { title: n.name, description: n.description, price: num(offer.price ?? offer.lowPrice) };
    }
  }
  return null;
}

// 2) Amazon doesn't publish that data, so read the page directly
function fromAmazon() {
  const t = document.querySelector("#productTitle");
  if (!t) return null;
  return { title: t.textContent, price: num(document.querySelector(".a-price .a-offscreen")?.textContent) };
}

// 3) Generic fallback: Open Graph title (safe now, since we only get here on product URLs)
function fromOpenGraph() {
  const title = meta('meta[property="og:title"]') || document.querySelector("h1")?.textContent || "";
  return title ? { title, price: num(meta('meta[property="product:price:amount"]') || meta('meta[property="og:price:amount"]')) } : null;
}

// Price fallback for stores that load it after the page (Target, and others using itemprop)
function findPrice() {
  const el = document.querySelector('[data-test="product-price"], [itemprop="price"]');
  return num(el?.getAttribute("content") ?? el?.textContent);
}

function readProduct() {
  if (!isProductPage()) return null;
  const p = fromJsonLd() || fromAmazon() || fromOpenGraph();
  if (!p || !p.title) return null;
  return {
    url: location.href,
    title: cleanTitle(p.title),
    description: (p.description || meta('meta[property="og:description"]') || meta('meta[name="description"]')).trim(),
    price: p.price ?? findPrice(),
  };
}

const log = (...a) => console.log("[Thinking of You]", ...a);

function send(event, product) {
  log("sending", event, product);
  try {
    chrome.runtime.sendMessage({ type: "track", payload: { ...product, event } });
  } catch (e) {
    log("could not send. Refresh this page after reloading the extension:", e.message);
  }
}

// Views: send as soon as the product is known, then once more if the price shows up late
// (the server ignores the repeated view but fills in the missing price)
function sendView(url, tries = 0, sent = false) {
  if (location.href !== url) return; // navigated away while waiting
  const p = readProduct();
  if (p && !sent) {
    send("view", p);
    sent = true;
    if (p.price !== null) return;
  } else if (p && sent && p.price !== null) {
    return send("view", p);
  }
  if (tries < 6) setTimeout(() => sendView(url, tries + 1, sent), 1500);
  else if (!p) log("no product found on this page:", url);
}

let lastUrl = "";
function checkPage() {
  if (location.href === lastUrl) return;
  lastUrl = location.href;
  const url = lastUrl;
  log(isProductPage() ? "product page:" : "not a product page, ignoring:", url);
  setTimeout(() => sendView(url), 1500);
}
checkPage();
setInterval(checkPage, 1500); // catches navigation on sites that don't reload the page

// Add-to-cart: any button or link whose text or id says "add to cart/bag/basket"
const lastCart = {}; // last add-to-cart time per product page
document.addEventListener("click", (e) => {
  const b = e.target.closest('button, input[type="submit"], input[type="button"], a, [role="button"]');
  if (!b) return;
  const label = [b.innerText, b.value, b.getAttribute("aria-label"), b.id, b.name].join(" ");
  if (/add[\s_-]*to[\s_-]*(cart|bag|basket)/i.test(label)) {
    // Some stores need two clicks (open the size picker, then confirm), so count one add per minute per product
    if (Date.now() - (lastCart[location.pathname] || 0) < 60000) return;
    const p = readProduct();
    if (p) { lastCart[location.pathname] = Date.now(); send("cart", p); }
  }
}, true);