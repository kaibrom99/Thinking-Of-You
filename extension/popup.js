const $ = (id) => document.getElementById(id);

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

$("toggle").onchange = (e) => chrome.storage.local.set({ enabled: e.target.checked });
$("logout").onclick = async () => {
  const { token } = await chrome.storage.local.get("token");
  if (token) fetch(API + "/logout", { method: "POST", headers: { Authorization: "Bearer " + token } }).catch(() => {});
  await chrome.storage.local.remove(["token", "name"]);
  show();
};
show();