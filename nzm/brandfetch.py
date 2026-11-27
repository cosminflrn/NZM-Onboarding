"""NewsMAN Brandfetch (the brand service built by a colleague, to be part of NewsMAN).

The Cloudflare Worker asks the service for a site's brand; the service posts the result back to the
Worker's /brandfetchwebhook, which stores it as inbox/bf-<job_id>.json. Here that result becomes
"hints" for the scraper: identity (name, logo, colours, banner, links) comes from Brandfetch, while
products, menu and the rest still come from the site itself.
"""
import html
import json


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("status") not in (None, "completed", "done", "ok", "success"):
        raise RuntimeError(f"brand fetch NewsMAN nu a putut citi site-ul ({data.get('status')}: "
                           f"{data.get('error') or data.get('message') or 'fără detalii'})")
    return data


def _src(entry):
    for f in entry.get("formats") or []:
        if str(f.get("src", "")).startswith("http"):
            return f["src"]
    return entry.get("src") if str(entry.get("src", "")).startswith("http") else None


def hints(data):
    b = data.get("branding") or {}
    logos = b.get("logos") or []
    # "dark" logos are drawn in dark colours (made for light backgrounds, like our white emails): try them first
    order = sorted(logos, key=lambda l: {"dark": 0, None: 1, "light": 2}.get(l.get("theme"), 1))
    colors = {c.get("type"): c.get("hex") for c in b.get("colors") or [] if c.get("hex")}
    banner = next((_src(i) for i in b.get("images") or [] if i.get("type") == "banner" and _src(i)), None)
    links = b.get("links") or {}
    return {
        "name": (b.get("name") or "").strip() or None,
        "description": (b.get("description") or b.get("longDescription") or "").strip() or None,
        "logos": [u for u in (_src(l) for l in order) if u],
        "accent": colors.get("accent") or colors.get("brand") or colors.get("primary"),
        "dark": colors.get("dark"),
        "banner": banner,
        "privacy": links.get("privacyPolicy"),
        "terms": links.get("termsAndConditions"),
        "contact": links.get("contact"),
        "socials": {k: v for k, v in (b.get("social") or {}).items() if str(v).startswith("http")},
    }


def stand_in_page(url, data, h):
    """When the site itself can't be read, a small page made of the Brandfetch data lets the generator
    still build the client (no products/menu then, only the brand)."""
    b = data.get("branding") or {}
    e = lambda x: html.escape(x or "", quote=True)
    links = "".join(f'<a href="{e(u)}">{e(t)}</a>' for u, t in (
        (h.get("privacy"), "Politica de confidențialitate"), (h.get("terms"), "Termeni și condiții"),
        (h.get("contact"), "Contact")) if u)
    socials = "".join(f'<a href="{e(u)}">{e(k)}</a>' for k, u in (h.get("socials") or {}).items())
    logo = f'<a href="/" class="logo"><img src="{e(h["logos"][0])}" alt="{e(h.get("name"))}"></a>' if h.get("logos") else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{e(h.get("name") or b.get("domain"))}</title>'
            f'<meta name="description" content="{e(h.get("description"))}">'
            f'<meta property="og:site_name" content="{e(h.get("name"))}"></head>'
            f'<body><header>{logo}</header><main></main><footer>{links}{socials}</footer></body></html>')
