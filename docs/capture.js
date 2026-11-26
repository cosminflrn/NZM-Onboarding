// NewsMAN Onboarding – the bookmark button.
// Runs on the client's site, in the team member's own browser (like a normal visit), collects the
// home page, a few useful pages and the images the generator needs, and hands them to the app.
// The page builds the bookmark (javascript: link) from this file; nothing here is loaded from outside.
(async () => {
  const APP = "https://cosminflrn.github.io";
  const app = window.open(APP + "/NZM-Onboarding/#capture", "nzm_onboarding");
  const note = document.createElement("div");
  note.style.cssText = "position:fixed;z-index:2147483647;right:16px;bottom:16px;background:#111;color:#fff;" +
    "font:14px/1.4 system-ui,sans-serif;padding:12px 16px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.3)";
  note.textContent = "NewsMAN Onboarding: preiau pagina…";
  document.body.appendChild(note);

  const items = {};
  let budget = 7e6;
  const abs = (u) => { try { return new URL(u, location.href).href.split("#")[0]; } catch (e) { return ""; } };
  const same = (u) => { try { return new URL(u).host.replace(/^www\./, "") === location.host.replace(/^www\./, ""); } catch (e) { return false; } };
  const getText = async (u, accept) => {
    if (!u || items[u]) return;
    try {
      const r = await fetch(u, { credentials: "include", headers: accept ? { Accept: accept } : {} });
      if (!r.ok) return;
      const t = await r.text();
      if (t.length > 2e6 || (budget -= t.length) < 0) return;
      items[u] = { type: r.headers.get("content-type") || "", final: r.url, text: t };
    } catch (e) { /* not reachable from here: the generator simply skips it */ }
  };
  const getImage = async (u) => {
    if (!u || items[u] || /^data:/.test(u)) return;
    try {
      const r = await fetch(u, { credentials: same(u) ? "include" : "omit" });
      if (!r.ok) return;
      const b = await r.blob();
      if (b.size > 3e6 || (budget -= b.size * 1.37) < 0) return;
      const b64 = await new Promise((ok) => { const f = new FileReader(); f.onload = () => ok(String(f.result).split(",")[1] || ""); f.readAsDataURL(b); });
      items[u] = { type: b.type, final: r.url, b64 };
    } catch (e) { /* cross-site image without CORS: the generator fetches it itself */ }
  };

  // 1) the page exactly as the visitor sees it (scripts already ran)
  items[location.href.split("#")[0]] = { type: "text/html", final: location.href, text: "<!DOCTYPE html>" + document.documentElement.outerHTML };

  // 2) pages the generator looks for: contact, terms, privacy, cart, about + product feeds and sitemaps
  const want = /contact|termen|condi|confiden|privac|gdpr|cookie|despre|about|cos|cart|basket/i;
  const links = [...document.querySelectorAll("a[href]")].map((a) => abs(a.getAttribute("href")))
    .filter((u, i, all) => u && same(u) && all.indexOf(u) === i && want.test(u)).slice(0, 14);
  // the first short links of the page are usually the main menu
  const home = location.href.split("#")[0];
  [...document.querySelectorAll("a[href]")].filter((a) => { const t = (a.textContent || "").trim(); return t.length >= 2 && t.length <= 28; })
    .map((a) => abs(a.getAttribute("href"))).filter((u) => u && same(u) && u !== home && links.indexOf(u) < 0)
    .filter((u, i, all) => all.indexOf(u) === i).slice(0, 8).forEach((u) => links.push(u));
  const feeds = ["/sitemap.xml", "/sitemap_index.xml", "/product-sitemap.xml", "/robots.txt",
    "/products.json?limit=12", "/wp-json/wc/store/v1/products?per_page=12", "/wp-json/wc/store/products?per_page=12"]
    .map((p) => location.origin + p);
  await Promise.all(links.map((u) => getText(u)).concat(feeds.map((u) => getText(u, "application/json,text/xml,*/*"))));

  // 3) images: logo candidates, icons, share image and the first pictures on the page
  const imgs = [];
  const add = (u) => { u = abs(u); if (u && imgs.indexOf(u) < 0) imgs.push(u); };
  document.querySelectorAll("img").forEach((im, i) => {
    const hint = (im.getAttribute("src") + " " + im.alt + " " + im.className + " " + im.id + " " + (im.closest("header,[class*=logo],[id*=logo]") ? "logo" : "")).toLowerCase();
    if (hint.includes("logo") || i < 40) {
      ["src", "data-src", "data-lazy-src", "data-original"].forEach((k) => im.getAttribute(k) && add(im.getAttribute(k)));
      if (im.currentSrc) add(im.currentSrc);
    }
  });
  document.querySelectorAll('link[rel*="icon"],meta[property="og:image"],meta[name="og:image"]').forEach((el) => add(el.href || el.content));
  document.querySelectorAll("svg image[href]").forEach((el) => add(el.getAttribute("href")));
  for (let i = 0; i < imgs.length; i += 6) await Promise.all(imgs.slice(i, i + 6).map(getImage));

  const data = { type: "nzm-capture", url: location.href.split("#")[0], items };
  const n = Object.keys(items).length;
  let delivered = false;
  const send = () => { try { if (app && !app.closed) app.postMessage(data, APP); } catch (e) {} };
  window.addEventListener("message", (e) => {
    if (e.origin !== APP) return;
    if (e.data === "nzm-ready") send();
    if (e.data === "nzm-received") { delivered = true; note.textContent = `NewsMAN Onboarding: gata, ${n} elemente trimise. Poți închide acest tab.`; }
  });
  send();
  note.textContent = `NewsMAN Onboarding: ${n} elemente preluate, le trimit…`;
  setTimeout(() => {
    if (delivered) return;
    // the site blocks the link between windows: save a file to upload in the app instead
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: "application/json" }));
    a.download = "newsman-" + location.host.replace(/^www\./, "") + ".json";
    document.body.appendChild(a); a.click();
    note.textContent = "NewsMAN Onboarding: am salvat un fișier. Încarcă-l în aplicație cu „Încarcă pagina salvată”.";
  }, 8000);
})();
