// The background worker sends events to the server. Content scripts can't do this themselves
// because the shopping site's cross-origin rules would block the request.
importScripts("config.js"); // defines API, the server address
const log = (...a) => console.log("[Thinking of You]", ...a);

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type !== "track") return;
  chrome.storage.local.get(["token", "enabled"]).then(async ({ token, enabled }) => {
    if (!token || enabled === false) {
      log("not signed in, or tracking is paused in the popup");
      return reply({ ok: false });
    }
    try {
      const r = await fetch(API + "/events", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify(msg.payload),
      });
      log("server replied", r.status, await r.json().catch(() => null));
      if (r.status === 401) {
        await chrome.storage.local.remove(["token", "name"]);
        log("your login expired, please sign in again from the popup");
      }
      reply({ ok: r.ok });
    } catch (err) {
      log("could not reach the server:", err.message);
      reply({ ok: false });
    }
  });
  return true; // keep the message channel open for the async reply
});