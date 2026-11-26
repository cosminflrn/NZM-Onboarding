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
    const authed = await checkAuth(req, env);
    if (url.pathname === "/login") {
      return new Response(JSON.stringify({ ok: authed }), {
        status: authed ? 200 : 401, headers: { ...cors, "Content-Type": "application/json" },
      });
    }
    if (url.pathname.startsWith("/gh/") && !authed) return deny(cors, "utilizator sau parolă greșite", 401);
    if (!url.pathname.startsWith("/gh/")) {
      return new Response(JSON.stringify({ ok: true, repo: env.REPO, token: !!env.GITHUB_TOKEN }), {
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
