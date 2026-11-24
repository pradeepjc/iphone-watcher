// iPhone Duo 256GB Night Sky (unlocked) watcher — runs inside a Chrome tab on apple.com.
// Read-only: only checks availability. Never adds to bag or buys.
(() => {
  if (window.__duoWatcher) { console.log("Watcher already running."); return; }
  const PART = "MK1F4LL/A", ZIP = "55340";
  const STORES = { R022: "Rosedale (Roseville)", R007: "Mall of America", R054: "Southdale (Edina)", R183: "Ridgedale (Minnetonka)" };
  // ntfy topic is a secret. Set it once on apple.com with:
  //   localStorage.duoNtfyTopic = "your-topic-name"
  const TOPIC = (localStorage.getItem("duoNtfyTopic") || "").trim();
  if (!TOPIC) { console.log('No ntfy topic. Run: localStorage.duoNtfyTopic = "your-topic-name"  then paste this script again.'); return; }
  const NTFY = "https://ntfy.sh/" + TOPIC;
  const BAG = "https://www.apple.com/shop/bag";
  const URL = "/shop/fulfillment-messages?fae=true&pl=true&mts.0=regular&mts.1=compact&cppart=UNLOCKED/US&parts.0=" +
              encodeURIComponent(PART).replace("%2F", "/") + "&searchNearby=true&location=" + ZIP;
  const RUN_MS = 72 * 3600e3, MAX_DAYS = 7, REPEAT = 3, REPEAT_GAP = 120e3, FAIL_ALERT = 10;
  const end = Date.now() + RUN_MS;
  const episode = {}; let fails = 0, problemAt = 0, checks = 0, hbDay = null, timer = null;
  const ts = () => new Date().toLocaleTimeString();
  const log = (...a) => console.log("%c[duo " + ts() + "]", "color:#0a7", ...a);

  async function ntfy(title, msg, priority = "default", tags = "", click = "") {
    try {
      const h = { Title: title, Priority: priority };
      if (tags) h.Tags = tags; if (click) h.Click = click;
      const r = await fetch(NTFY, { method: "POST", body: msg, headers: h });
      if (!r.ok) log("ntfy HTTP", r.status);
    } catch (e) { log("ntfy FAILED (blocked?)", e.message); }
  }
  function beep() {
    try { const c = new AudioContext(); [0, .4, .8].forEach(t => { const o = c.createOscillator(); o.frequency.value = 880;
      o.connect(c.destination); o.start(c.currentTime + t); o.stop(c.currentTime + t + .25); }); } catch (e) {}
  }

  // Renew Apple's bot-shield cookies by briefly opening the store page in a small window.
  // Requires Chrome to allow pop-ups for apple.com.
  let lastRefresh = Date.now(), popupWarned = false;
  function refreshSession() {
    return new Promise(resolve => {
      const w = window.open(location.pathname + "?r=" + Date.now(), "duoRefresh", "width=420,height=320,left=0,top=0");
      if (!w) {
        log("POPUP BLOCKED - allow pop-ups for apple.com so the session can refresh");
        if (!popupWarned) { popupWarned = true; ntfy("iPhone watcher: pop-ups blocked", "Allow pop-ups for apple.com in Chrome so the watcher can renew its session.", "high", "warning"); }
        lastRefresh = Date.now(); return resolve();
      }
      setTimeout(() => { try { w.close(); } catch (e) {} lastRefresh = Date.now(); log("session refreshed (window)"); resolve(); }, 12000);
    });
  }
  async function getAvail() {
    return fetch(URL, { credentials: "include", headers: { accept: "*/*" } });
  }

  function parse(j) {
    const c = j.body.content, stores = {};
    for (const s of c.pickupMessage.stores) if (STORES[s.storeNumber]) {
      const p = s.partsAvailability[PART]; stores[s.storeNumber] = [p.pickupDisplay, p.pickupSearchQuote];
    }
    if (!Object.keys(stores).length) throw new Error("no MSP stores in response");
    const reg = ((c.deliveryMessage || {})[PART] || {}).regular || {};
    let date = null;
    for (const o of reg.deliveryOptionMessages || []) {
      const s = o.encodedUpperDateString; if (!s) continue;
      const d = new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8));
      if (!date || d < date) date = d;
    }
    return { stores, date, zip: (reg.address || {}).postalCode, buyable: (reg.buyability || {}).isBuyable };
  }

  async function check() {
    checks++;
    let r;
    try {
      let res = await getAvail();
      if (res.status === 541) {
        log("541 - refreshing session and retrying");
        await refreshSession();
        res = await getAvail();
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      r = parse(await res.json());
    } catch (e) {
      fails++; log("CHECK FAILED", e.message, "consecutive:", fails);
      if (fails >= FAIL_ALERT && Date.now() - problemAt > 2 * 3600e3) {
        problemAt = Date.now();
        ntfy("iPhone watcher PROBLEM", fails + " checks failed in a row (" + e.message + "). Check the Chrome tab.", "high", "warning");
      }
      return;
    }
    if (problemAt) { ntfy("iPhone watcher recovered", "Checks are working again.", "default", "white_check_mark"); problemAt = 0; }
    fails = 0;
    const hits = [];
    for (const [n, [disp, q]] of Object.entries(r.stores)) if (disp === "available") hits.push([n, STORES[n] + " pickup: " + q]);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    if (r.date && (r.date - today) / 864e5 <= MAX_DAYS && r.buyable !== false)
      hits.push(["delivery", "Delivery to " + (r.zip || ZIP) + " by " + r.date.toDateString()]);
    log("ok", Object.entries(r.stores).map(([n, [d]]) => n + "=" + d).join(" "),
        "| delivery", r.date ? r.date.toDateString() : "-", "to", r.zip);
    const keys = new Set(hits.map(h => h[0]));
    for (const k of Object.keys(episode)) if (!keys.has(k)) { log("stock gone:", k); delete episode[k]; }
    for (const [k, text] of hits) {
      const ep = episode[k] = episode[k] || { n: 0, last: 0 };
      if (ep.n < REPEAT && Date.now() - ep.last >= REPEAT_GAP) {
        ep.n++; ep.last = Date.now();
        log("%cALERT " + ep.n + "/" + REPEAT + ": " + text, "color:red;font-weight:bold");
        ntfy("iPhone Duo AVAILABLE", text + ". Tap to open bag and buy now.", "urgent", "rotating_light", BAG);
        beep(); document.title = "IN STOCK - " + text;
      }
    }
    const now = new Date();
    if (now.getHours() === 8 && hbDay !== now.toDateString()) {
      hbDay = now.toDateString();
      ntfy("iPhone watcher: still watching", checks + " checks so far. Ends " + new Date(end).toLocaleString() + ".", "low", "eyes");
    }
  }

  async function loop() {
    if (Date.now() >= end) { log("Finished 72h run."); ntfy("iPhone watcher stopped", "72-hour run finished after " + checks + " checks.", "default", "stop_sign"); return; }
    if (Date.now() - lastRefresh > 20 * 60e3) await refreshSession();
    await check();
    timer = setTimeout(loop, 45e3 + Math.random() * 30e3);
  }

  window.__duoWatcher = { stop() { clearTimeout(timer); delete window.__duoWatcher; log("Stopped."); ntfy("iPhone watcher stopped", "Stopped manually.", "default", "stop_sign"); } };
  log("Started. Runs until", new Date(end).toLocaleString(), "— to stop: __duoWatcher.stop()");
  ntfy("iPhone watcher started (Chrome)", "Watching 4 MSP stores + delivery to " + ZIP + " until " + new Date(end).toLocaleString() + ".", "default", "eyes");
  loop();
})();
