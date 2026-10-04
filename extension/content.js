// Runs on the supported stores, in the user's own browser. Only product pages are ever reported.
// reader.js (loaded first) does the page reading.
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
function sendView(url, tries = 0, sent = null) {
  if (location.href !== url) return; // navigated away while waiting
  const p = window.__toyReadProduct();
  if (p) {
    const price = p.price !== null, image = !!p.image;
    if (!sent || (price && !sent.price) || (image && !sent.image)) {  // send again only when something new turned up
      send("view", p);
      sent = { price: price || !!sent?.price, image: image || !!sent?.image };
    }
    if (sent.price && sent.image) return;
  }
  if (tries < 6) setTimeout(() => sendView(url, tries + 1, sent), 1500);
  else if (!p) log("no product found on this page:", url);
}

let lastUrl = "";
function checkPage() {
  if (location.href === lastUrl) return;
  lastUrl = location.href;
  const url = lastUrl;
  log(window.__toyIsProductPage() ? "product page:" : "not a product page, ignoring:", url);
  setTimeout(() => sendView(url), 1500);
}
checkPage();
setInterval(checkPage, 1500); // catches navigation on sites that don't reload the page

// Add-to-cart: any button or link whose text or id says "add to cart/bag/basket"
const lastCart = {}; // last add-to-cart time per product page
const CART_BUTTON = /add[\s_-]*to[\s_-]*(?:my[\s_-]*|your[\s_-]*)?(cart|bag|basket)|\badd\b[^.]{0,80}?\bto\s+(?:my\s+|your\s+)?(?:cart|bag|basket)\b/i;
function onPress(e) {
  // The clicked element and a few parents, also through shadow DOM (some stores hide their buttons there)
  const path = e.composedPath().filter((n) => n instanceof Element).slice(0, 6);
  const label = path.map((el, i) => {
    const text = (el.innerText || "").trim();
    return [text.length < 60 ? text : "", el.value, el.getAttribute("aria-label"), el.title, el.id, el.name,
            el.getAttribute("data-test"), el.getAttribute("data-testid"), i < 3 ? String(el.className || "") : ""].join(" ");
  }).join(" | ");
  const isCart = CART_BUTTON.test(label);
  if (!isCart && /\b(cart|bag|basket)\b/i.test(label) && label.length < 400) log("button not counted as add-to-cart:", label.trim().slice(0, 200));
  if (isCart) {
    // Some stores need two clicks (open the size picker, then confirm), so count one add per minute per product
    if (Date.now() - (lastCart[location.pathname] || 0) < 60000) return;
    const p = window.__toyReadProduct();
    if (p) { lastCart[location.pathname] = Date.now(); send("cart", p); }
  }
}
document.addEventListener("click", onPress, true);
document.addEventListener("pointerdown", onPress, true);  // some stores swap the button before a click completes