const $ = (id) => document.getElementById(id);
const say = (text, ok = false) => { $("msg").textContent = text; $("msg").style.color = ok ? "#14907F" : "#D6336C"; };

async function show() {
  const { token, name, enabled } = await chrome.storage.local.get(["token", "name", "enabled"]);
  $("login").hidden = !!token;
  $("main").hidden = !token;
  if (token) {
    $("who").textContent = name || "you";
    $("toggle").checked = enabled !== false;
  }
}

$("loginBtn").onclick = async () => {
  $("err").textContent = "";
  try {
    const r = await fetch(API + "/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: $("email").value.trim(), password: $("pw").value }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Sign-in failed");
    await chrome.storage.local.set({ token: data.token, name: data.name, enabled: true });
    $("pw").value = "";
    show();
  } catch (e) {
    $("err").textContent = /fetch/i.test(e.message) ? "Can't reach the server. Is it running?" : e.message;
  }
};

// Save whatever page you're on (any store). It's your click, so it works beyond the tracked stores.
$("addPage").onclick = async () => {
  say("");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !/^https?:/.test(tab.url || "")) return say("Open a product page first.");
  let info;
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["reader.js"] });
    const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => window.__toyReadPage() });
    info = res.result;
  } catch {
    return say("Chrome won't let me read this page.");
  }
  if (!info || !info.title) return say("Couldn't find a product on this page.");
  const { token } = await chrome.storage.local.get("token");
  try {
    const r = await fetch(API + "/items", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({
        title: info.title.slice(0, 500), description: (info.description || "").slice(0, 5000),
        price: info.price, url: info.url, image_url: info.image || "", private: $("priv").checked,
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (r.ok) return say("Added to your list ✓", true);
    if (r.status === 401) { await chrome.storage.local.remove(["token", "name"]); show(); return; }
    say(Array.isArray(data.detail) ? "This page's details didn't look right." : data.detail || "Couldn't add it.");
  } catch {
    say("Can't reach the server.");
  }
};

$("toggle").onchange = (e) => chrome.storage.local.set({ enabled: e.target.checked });
$("logout").onclick = async () => {
  const { token } = await chrome.storage.local.get("token");
  if (token) fetch(API + "/logout", { method: "POST", headers: { Authorization: "Bearer " + token } }).catch(() => {});
  await chrome.storage.local.remove(["token", "name"]);
  show();
};
show();