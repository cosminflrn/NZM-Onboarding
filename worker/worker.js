// NewsMAN Onboarding – intermediar Cloudflare Worker.
// Ține tokenul GitHub ca secret și lasă pagina să facă DOAR operațiile de care are nevoie:
// pornește generarea, urmărește progresul, citește fișierele generate, salvează editări în docs/clients/.
//
// Variabile (Worker → Settings → Variables and Secrets):
//   GITHUB_TOKEN   (Secret)  token fine-grained: Actions R/W + Contents R/W, doar pe repo-ul NZM-Onboarding
//   REPO           (Text)    cosminflrn/NZM-Onboarding
//   ALLOWED_ORIGIN (Text)    https://cosminflrn.github.io   (opțional; implicit oricine)
//   APP_USER       (Text)    utilizatorul cerut în pagină
//   APP_PASSWORD   (Secret)  parola cerută în pagină
//   BRAND_API_TOKEN      (Secret)  token-ul „normal” de la Brandfetch NewsMAN (opțional: fără el, varianta Brandfetch e oprită)
//   BRAND_WEBHOOK_SECRET (Secret)  secretul cu care Brandfetch NewsMAN semnează webhook-ul
//   BRAND_API_URL        (Text)    implicit https://brandfetch.newsman.eu/api/brand
//   BRAND_INSTANCE       (Text)    implicit cosmin

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type,Accept,X-NZM-Auth",
      "Access-Control-Max-Age": "86400",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });

    const url = new URL(req.url);
    // public pictures made by the generator (e.g. a white logo set on its brand colour), served from the site's files
    const pic = url.pathname.match(/^\/img\/([a-z0-9-]+)\/([a-z0-9-]+\.(png|jpg))$/);
    if (pic && req.method === "GET") {
      const owner = String(env.REPO || "").split("/")[0].toLowerCase();
      const name = String(env.REPO || "").split("/")[1] || "";
      const r = await fetch(`https://${owner}.github.io/${name}/clients/${pic[1]}/assets/${pic[2]}`, { cf: { cacheTtl: 86400 } });
      if (!r.ok) return new Response("not found", { status: 404 });
      return new Response(r.body, { headers: {
        "Content-Type": pic[3] === "png" ? "image/png" : "image/jpeg",
        "Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*" } });
    }
    const authed = await checkAuth(req, env);
    if (url.pathname === "/login") {
      return new Response(JSON.stringify({ ok: authed }), {
        status: authed ? 200 : 401, headers: { ...cors, "Content-Type": "application/json" },
      });
    }
    // NewsMAN Brandfetch posts its results here (signed); stored as inbox/bf-<job>.json for the generator
    if (url.pathname === "/brandfetchwebhook" && req.method === "POST") return brandWebhook(req, env);
    // the page asks for a site's brand: cached result right away, otherwise a job whose result comes by webhook
    if (url.pathname === "/bf/start" && req.method === "POST") {
      if (!authed) return deny(cors, "utilizator sau parolă greșite", 401);
      return brandStart(req, env, cors);
    }
    if (url.pathname.startsWith("/gh/") && !authed) return deny(cors, "utilizator sau parolă greșite", 401);
    if (!url.pathname.startsWith("/gh/")) {
      return new Response(JSON.stringify({ ok: true, repo: env.REPO, token: !!env.GITHUB_TOKEN, brandfetch: !!(env.BRAND_API_TOKEN && env.BRAND_WEBHOOK_SECRET) }), {
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    const path = url.pathname.slice(3); // /repos/owner/repo/...
    const repo = "/repos/" + String(env.REPO || "").toLowerCase();
    const lower = path.toLowerCase();
    if (!lower.startsWith(repo)) return deny(cors);
    const rest = path.slice(repo.length);

    const rules = {
      GET: /^(|\/actions\/workflows\/onboarding\.yml\/runs|\/actions\/runs\/\d+(\/jobs)?|\/check-runs\/\d+\/annotations|\/contents\/docs\/clients\/[\w.\/-]+)$/,
      POST: /^\/actions\/workflows\/onboarding\.yml\/dispatches$/,
      PUT: /^\/contents\/(docs\/clients\/[a-z0-9-]+\/(brand\.json|assets\/[\w.-]+)|inbox\/[a-z0-9]{4,12}\.json)$/,
    };
    if (!rules[req.method] || !rules[req.method].test(rest) || rest.includes("..")) return deny(cors);

    const body = req.method === "GET" ? undefined : await req.text();
    if (body && body.length > 20_000_000) return deny(cors, "prea mare");

    const gh = await fetch("https://api.github.com" + path + url.search, {
      method: req.method,
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: req.headers.get("Accept") || "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nzm-onboarding-proxy",
        "Content-Type": "application/json",
      },
      body,
    });
    const headers = new Headers(cors);
    const ct = gh.headers.get("content-type");
    if (ct) headers.set("Content-Type", ct);
    headers.set("Cache-Control", "no-store");
    return new Response(gh.body, { status: gh.status, headers });
  },
};

function deny(cors, msg = "operație nepermisă", status = 403) {
  return new Response(JSON.stringify({ message: msg }), { status, headers: { ...cors, "Content-Type": "application/json" } });
}

// header X-NZM-Auth: base64("user:parola")
async function checkAuth(req, env) {
  if (!env.APP_PASSWORD) return false;
  let given = "";
  try { given = new TextDecoder().decode(Uint8Array.from(atob(req.headers.get("X-NZM-Auth") || ""), (c) => c.charCodeAt(0))); } catch { return false; }
  const expected = `${env.APP_USER || ""}:${env.APP_PASSWORD}`;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(given)), crypto.subtle.digest("SHA-256", enc.encode(expected))]);
  const x = new Uint8Array(a), y = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

// =============================================================== NewsMAN Brandfetch
const json = (obj, status = 200, cors = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json" } });

function siteHost(u) {
  try {
    const h = new URL(/^https?:\/\//i.test(u) ? u : "https://" + u).hostname.toLowerCase().replace(/^www\./, "");
    return /^[a-z0-9.-]+\.[a-z]{2,}$/.test(h) && !/^(localhost|[\d.]+)$/.test(h) ? h : "";
  } catch { return ""; }
}
const usable = (d) => d && !d.error && d.found !== false && !["pending", "processing", "failed", "error", "not_found"].includes(d.status)
  && (d.branding || d.data);

async function brandStart(req, env, cors) {
  if (!env.BRAND_API_TOKEN || !env.BRAND_WEBHOOK_SECRET) return json({ message: "Brandfetch NewsMAN nu e configurat în Cloudflare" }, 503, cors);
  let inp = {};
  try { inp = await req.json(); } catch {}
  const host = siteHost(inp.url || "");
  const rid = String(inp.rid || "");
  if (!host || !/^[a-z0-9]{4,12}$/.test(rid)) return json({ message: "cerere invalidă" }, 400, cors);
  const api = env.BRAND_API_URL || "https://brandfetch.newsman.eu/api/brand";
  const instance = env.BRAND_INSTANCE || "cosmin";
  const auth = { Authorization: `Bearer ${env.BRAND_API_TOKEN}`, Accept: "application/json" };
  const timed = (ms) => AbortSignal.timeout(ms);
  // 1) already known: no need to wait for a webhook
  try {
    const r = await fetch(`${api}?website=${encodeURIComponent(host)}&instance=${encodeURIComponent(instance)}`, { headers: auth, signal: timed(15000) });
    if (r.ok) {
      const d = await r.json();
      if (usable(d)) {
        const path = `inbox/bf-${rid}.json`;
        await ghPut(env, path, JSON.stringify({ ...d, status: d.status || "completed" }), `Brandfetch ${host}`);
        return json({ ready: true, path }, 200, cors);
      }
    }
  } catch {}
  // 2) a job: Brandfetch posts the result to /brandfetchwebhook (the URL allowlisted for this instance)
  const r = await fetch(`${api}/jobs`, {
    method: "POST", headers: { ...auth, "Content-Type": "application/json" }, signal: timed(20000),
    body: JSON.stringify({ website: host, instance, resource_id: rid, list_id: rid }),
  });
  let d = {};
  try { d = await r.json(); } catch {}
  const job = String(d.job_id || d.id || "");
  if (!r.ok || !/^[A-Za-z0-9_-]{4,64}$/.test(job)) return json({ message: `Brandfetch NewsMAN a refuzat cererea (${r.status})` }, 502, cors);
  return json({ ready: false, path: `inbox/bf-${job.replace(/^job-/, "")}.json`, job }, 200, cors);
}

async function hmacHex(secret, text, b64 = false) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text)));
  return b64 ? btoa(String.fromCharCode(...sig)) : [...sig].map((x) => x.toString(16).padStart(2, "0")).join("");
}
function same(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function brandWebhook(req, env) {
  if (!env.BRAND_WEBHOOK_SECRET) return json({ message: "neconfigurat" }, 503);
  const h = (...names) => names.map((n) => req.headers.get(n)).find((v) => v) || "";
  const ts = h("X-Brand-Timestamp", "X-Brandfetch-Timestamp", "X-Webhook-Timestamp").trim();
  const given = h("X-Brand-Signature", "X-Brandfetch-Signature", "X-Webhook-Signature").trim().replace(/^sha256=/i, "");
  const raw = await req.text();   // signature is over the exact bytes received
  if (raw.length > 2_000_000) return json({ message: "prea mare" }, 413);
  if (!/^\d{10,13}$/.test(ts) || !given) return json({ message: "semnătură lipsă" }, 403);
  const secs = ts.length === 13 ? Math.floor(+ts / 1000) : +ts;
  if (Math.abs(Date.now() / 1000 - secs) > 300) return json({ message: "expirat" }, 403);
  // canonical: hex(HMAC(timestamp + "." + body)); the service's migration formats are accepted too
  const okSig = same(await hmacHex(env.BRAND_WEBHOOK_SECRET, `${ts}.${raw}`), given.toLowerCase())
    || same(await hmacHex(env.BRAND_WEBHOOK_SECRET, raw), given.toLowerCase())
    || same(await hmacHex(env.BRAND_WEBHOOK_SECRET, `${ts}.${raw}`, true), given);
  if (!okSig) return json({ message: "semnătură invalidă" }, 403);
  let d;
  try { d = JSON.parse(raw); } catch { return json({ message: "JSON invalid" }, 400); }
  const job = String(d.job_id || d.id || "").replace(/^job-/, "");
  const rid = String(d.resource_id || d.list_id || "");
  if (!/^[A-Za-z0-9_-]{4,64}$/.test(job) || !siteHost(d.website || "")) return json({ message: "date incomplete" }, 422);
  const text = JSON.stringify(d);
  await ghPut(env, `inbox/bf-${job}.json`, text, `Brandfetch ${siteHost(d.website)}`);
  if (/^[a-z0-9]{4,12}$/.test(rid)) await ghPut(env, `inbox/bf-${rid}.json`, text, `Brandfetch ${siteHost(d.website)}`);
  return json({ ok: true });
}

// write (or overwrite: webhooks can be retried) a file in the repo
async function ghPut(env, path, text, message) {
  const base = `https://api.github.com/repos/${env.REPO}/contents/${path}`;
  const headers = { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "nzm-onboarding-proxy", "Content-Type": "application/json" };
  let sha;
  const cur = await fetch(base, { headers });
  if (cur.ok) sha = (await cur.json()).sha;
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  const r = await fetch(base, { method: "PUT", headers, body: JSON.stringify({ message, content: btoa(bin), ...(sha ? { sha } : {}) }) });
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
}
