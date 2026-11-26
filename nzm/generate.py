"""Apply a brand profile (brand.json) to the NewsMAN export templates.

Every template is a NewsMAN export (popup form, welcome template, abandoned-cart
workflow). Each one stores the Beefree design as JSON (sometimes JSON inside a
string, sometimes base64) and, for forms/automations, the rendered HTML too.
We change the JSON structurally and patch the HTML with the same values so the
two stay in sync.
"""
import base64
import copy
import html as htmlmod
import json
import os
import re
import time
import uuid

from . import colors as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")

# ---------------------------------------------------------------- placeholders
# Unique pieces of image URLs used as placeholders in the templates (host may
# be img.newsmanapp.com or img.nzmt.eu, so we only match the tail).
LOGO_IDS = [
    "544ada38-b525-4694-bc73-853fa2bd152f.png",         # welcome header logo
    "logo-pic.png",                                     # automation footer logo
    "fc1cb082-8538-419c-84f1-909d114a2075.png",         # automation email #1 header
    "icon-mail-address-envelope-message-364245.jpg",   # popup / confirm envelope
    "db7111db-970a-44b8-9257-0240470198c7.jpg",         # embedded form: confirmation email header
]
BANNER_IDS = ["bine-ai-venit.png"]
PRODUCT_PLACEHOLDER_IMG = "https://img.newsmanapp.com/i/b/901bd24ca743a8d7ea7d611c3e43c36e/28118/placeholder400x300.png"

COLOR_ROLES = {
    "welcome": {"#030000": "dark", "#fb2324": "accent", "#f4f1ef": "light"},
    "automation": {"#fb2324": "accent", "#ff0000": "accent", "#ff0030": "accent", "#efe9e6": "light", "#8f7d5e": "muted"},
    "form": {"#ef4136": "accent", "#47433c": "dark"},
    "embed": {"#a60400": "accent", "#3aaee0": "accent"},
}
# texts of the pop-up template that become per-client texts
FORM_TEXTS = {"Abonează-te!": "form_title", "Și rămâi la curent cu toate noutățile.": "form_subtitle"}

PHONE_PLACEHOLDERS = ["0700 000 000", "072000000"]
SOCIAL_NAMES = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube",
                "linkedin": "LinkedIn", "pinterest": "Pinterest", "twitter": "X"}
DISCOUNT_PLACEHOLDER = "CODDISCOUNT"


def use_site_banner(brand):
    return bool((brand.get("options") or {}).get("use_site_banner"))


def esc(s):
    return htmlmod.escape(s or "", quote=True)


def new_uuid():
    return str(uuid.uuid4())


# ================================================================ string pass

class Patcher:
    """String-level replacements shared by JSON text and rendered HTML."""

    def __init__(self, brand, kind, texts=None):
        self.b = brand
        self.kind = kind
        self.texts = texts or {}
        self.pal = brand["colors"]
        self.links = brand.get("links") or {}
        self.socials = brand.get("socials") or {}
        logo = brand.get("logo") or {}
        self.logo_url = logo.get("url")
        self.logo_w = logo.get("display_width") or 160
        banner = (brand.get("banner") or {}) if use_site_banner(brand) else {}
        self.banner_url = banner.get("url")

    # -- links
    def link_for(self, text):
        t = (text or "").lower()
        L = self.links
        if re.search(r"finaliz|co[sș]|comand", t):
            return L.get("cart") or L.get("home")
        if re.search(r"termen|condi", t):
            return L.get("terms") or L.get("home")
        if re.search(r"confiden|gdpr|privacy", t):
            return L.get("privacy") or L.get("terms") or L.get("home")
        if re.search(r"contact", t):
            return L.get("contact") or L.get("home")
        if re.search(r"ofert|reducer|promo", t):
            return L.get("promo") or L.get("home")
        return L.get("home")

    def fix_hash_links(self, s):
        if 'href="#"' not in s:
            return s
        out, pos = [], 0
        for m in re.finditer(r'href="#"', s):
            out.append(s[pos:m.start()])
            end = s.find("</a>", m.end())
            window = s[m.end(): end if end != -1 else m.end() + 2000]
            txt = re.sub(r"<!--.*?-->", " ", window, flags=re.S)
            txt = htmlmod.unescape(re.sub(r"<[^>]+>", " ", txt.split(">", 1)[-1] if ">" in txt else txt))
            out.append(f'href="{esc(self.link_for(txt))}"')
            pos = m.end()
        out.append(s[pos:])
        return "".join(out)

    # -- images
    def fix_images(self, s):
        if self.logo_url:
            for pid in LOGO_IDS:
                if pid not in s:
                    continue
                # resize <img> tags that show the logo
                def img_tag(m):
                    tag = m.group(0)
                    tag = re.sub(r'\bwidth="\d+(px)?"', f'width="{self.logo_w}"', tag)
                    tag = re.sub(r"max-width:\s*\d+px", f"max-width:{self.logo_w}px", tag)
                    tag = re.sub(r"(?<![-\w])width:\s*\d+px", f"width:{self.logo_w}px", tag)
                    tag = re.sub(r'alt="[^"]*"', f'alt="{esc(self.b["name"])}"', tag)
                    if self.kind == "form" and "margin-bottom" not in tag:
                        tag = re.sub(r'style="', 'style="margin-bottom:20px;', tag, count=1) if 'style="' in tag \
                            else tag.replace("<img", '<img style="margin-bottom:20px"', 1)
                    return tag
                s = re.sub(r"<img\b[^>]*" + re.escape(pid) + r"[^>]*>", img_tag, s)
                s = re.sub(r"https?://[^\s\"'<>()\\]*?/" + re.escape(pid), self.logo_url, s)
        if self.banner_url:
            for pid in BANNER_IDS:
                s = re.sub(r"https?://[^\s\"'<>()\\]*?/" + re.escape(pid), self.banner_url, s)
        return s

    # -- colors
    def fix_colors(self, s):
        for old, role in COLOR_ROLES[self.kind].items():
            s = re.sub(re.escape(old) + r"(?![0-9a-fA-F])", self.pal[role], s, flags=re.I)
        if self.kind == "embed":
            # the embedded form uses black for buttons *and* text: only recolor button backgrounds
            acc = self.pal["accent"]
            s = re.sub(r'("background-color"\s*:\s*")#000000(")', rf"\g<1>{acc}\g<2>", s)
            s = re.sub(r"(background-color:\s*)#000000\b", rf"\g<1>{acc}", s)
            s = re.sub(r'(fillcolor=")#000000(")', rf"\g<1>{acc}\g<2>", s)
        return s

    # -- socials in rendered html
    def fix_social_html(self, s):
        if not self.socials:
            return drop_social_html(s)
        if "social-networks-icon-sets" not in s:
            return s
        cell = (r'(<(td|span)\b[^>]*>)\s*<a href="[^"]*"[^>]*>\s*<img\b[^>]*social-networks-icon-sets/[^/"]+/'
                r'\w+@2x\.png[^>]*>\s*</a>\s*</\2>')
        cell_re = re.compile(cell)
        group_re = re.compile(r"(?:" + cell + r"\s*)+")
        nets = list(self.socials.items())

        def rebuild(m):
            cells = [c.group(0) for c in cell_re.finditer(m.group(0))]
            if not cells:
                return m.group(0)
            first, rest = cells[0], (cells[1] if len(cells) > 1 else cells[0])
            out = []
            for i, (net, url) in enumerate(nets):
                tpl = first if i == 0 else rest
                c = re.sub(r'<a href="[^"]*"', f'<a href="{esc(url)}"', tpl, count=1)
                c = re.sub(r"(social-networks-icon-sets/[^/\"]+/)\w+(@2x\.png)", rf"\g<1>{net}\g<2>", c)
                c = re.sub(r'alt="[^"]*"', f'alt="{SOCIAL_NAMES[net]}"', c)
                c = re.sub(r'title="[^"]*"', f'title="{SOCIAL_NAMES[net]}"', c)
                out.append(c)
            trailing = re.search(r"\s*$", m.group(0)).group(0)
            return "".join(out) + trailing

        s = group_re.sub(rebuild, s)
        n = max(1, len(nets))
        s = re.sub(r'(<table class="social-table" width=")\d+(px")', rf"\g<1>{n * 32 + (n - 1) * 15}\g<2>", s)
        return s

    # -- texts
    def fix_texts(self, s):
        b = self.b
        phone = (b.get("contact") or {}).get("phone")
        if phone:
            for p in PHONE_PLACEHOLDERS:
                s = s.replace(p, esc(phone))
        name = esc(b["name"])
        s = re.sub(r"Siteulmeu\.ro\s*2022", name, s)
        terms = self.links.get("terms") or self.links.get("privacy") or self.links.get("home")
        s = s.replace("(example.com)", f"({terms})").replace('href="example.com"', f'href="{esc(terms)}"')
        s = s.replace("](link)", f"]({terms})").replace('href="link"', f'href="{esc(terms)}"')
        for old, key in FORM_TEXTS.items():
            if self.texts.get(key):
                s = s.replace(old, esc(self.texts[key]))
        code = (b.get("options") or {}).get("discount_code")
        if code:
            s = s.replace(DISCOUNT_PLACEHOLDER, esc(code))
        return s

    def __call__(self, s):
        if not isinstance(s, str) or not s:
            return s
        s = self.fix_images(s)
        s = self.fix_colors(s)
        s = self.fix_social_html(s)
        s = self.fix_texts(s)
        s = self.fix_hash_links(s)
        return s


def deep_map(obj, fn):
    if isinstance(obj, dict):
        return {k: deep_map(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_map(v, fn) for v in obj]
    if isinstance(obj, str):
        return fn(obj)
    return obj


# ================================================================ Beefree JSON

def modules(page):
    for row in page["page"]["rows"]:
        for col in row["columns"]:
            for m in col["modules"]:
                yield row, col, m


def mtype(m):
    return m["type"].replace("mailup-bee-newsletter-modules-", "")


SOCIAL_TEXT_RE = re.compile(r"social[ -]?media|urm[ăa]re[șs]te-ne|follow us", re.I)


def drop_social_html(s):
    """No social profiles: remove 'Follow us on social media:', its separator and the empty icons block."""
    if "bee-popup-social" not in s and not SOCIAL_TEXT_RE.search(s):
        return s
    block = r'<div class="bee-popup-block [^"]*bee-popup-{kind}">'
    s = re.sub(block.format(kind="social") + r'\s*<div class="content">(?:(?!</div>).)*</div>\s*</div>', "", s, flags=re.S)
    s = re.sub(block.format(kind="text") + r'\s*<div[^>]*>\s*<p[^>]*>(?:(?!</p>).)*?(?:social media|rm[ăa]re[șs]te-ne)(?:(?!</p>).)*?</p>\s*</div>\s*</div>',
               "", s, flags=re.S | re.I)
    # a separator left as the last block of its column now leads nowhere
    s = re.sub(block.format(kind="divider") + r'\s*<div class="center bee-popup-separator"[^>]*></div>\s*</div>(\s*</div>\s*</div>\s*</div>)',
               r"\1", s)
    return s


def drop_social_modules(page):
    """Same in the editor JSON: social block, the text inviting to it, and the divider right before."""
    for row in page["page"]["rows"]:
        for col in row["columns"]:
            mods = col["modules"]
            keep = []
            for m in mods:
                t = mtype(m)
                if t == "social":
                    continue
                if t in ("text", "paragraph", "heading"):
                    txt = json.dumps(m["descriptor"], ensure_ascii=False)
                    if SOCIAL_TEXT_RE.search(re.sub(r"<[^>]+>", " ", txt)) and len(re.sub(r"<[^>]+>|\\[nt]", "", txt)) < 1500:
                        if keep and mtype(keep[-1]) == "divider":
                            keep.pop()
                        continue
                keep.append(m)
            col["modules"] = keep


def fix_bee(page, brand, patch):
    """Structural changes valid for every Beefree page."""
    if not brand.get("socials"):
        drop_social_modules(page)
    logo = brand.get("logo") or {}
    banner = (brand.get("banner") or {}) if use_site_banner(brand) else {}
    for row, col, m in modules(page):
        t = mtype(m)
        d = m["descriptor"]
        if t == "image":
            src = d["image"].get("src", "")
            if logo.get("url") and any(pid in src for pid in LOGO_IDS):
                d["image"].update({"src": logo["url"], "alt": brand["name"], "href": brand["links"]["home"],
                                   "width": f'{logo["width"]}px', "height": f'{logo["height"]}px', "target": "_blank"})
                cs = d.setdefault("computedStyle", {})
                cs["class"] = "center fixedwidth"
                cs["width"] = f'{logo["display_width"]}px'
                st = d.setdefault("style", {})
                if patch.kind == "form":
                    st["padding-bottom"] = "20px"
                for side in ("top", "bottom", "left", "right"):
                    if st.get(f"padding-{side}", "0px") in ("0px", "0", ""):
                        st[f"padding-{side}"] = "10px"
            elif banner.get("url") and any(pid in src for pid in BANNER_IDS):
                d["image"].update({"src": banner["url"], "alt": brand["name"], "href": brand["links"]["home"],
                                   "width": f'{banner["width"]}px', "height": f'{banner["height"]}px', "target": "_blank"})
        elif t == "social":
            set_social_icons(d, brand.get("socials") or {})
        elif t == "button":
            b = d["button"]
            if patch.kind == "embed" and str(b.get("style", {}).get("background-color", "")).lower() in ("#000000", "#000"):
                b["style"]["background-color"] = brand["colors"]["accent"]
            if not b.get("href") or b.get("href") == "#":
                label = re.sub(r"<[^>]+>", " ", b.get("label", ""))
                b["href"] = patch.link_for(label)
                b["target"] = "_blank"
    return page


def set_social_icons(d, socials):
    icons = d["iconsList"]["icons"]
    if not icons:
        return
    tpl = icons[0]
    capital = tpl["name"][:1].isupper()
    out = []
    for net, url in socials.items():
        ic = copy.deepcopy(tpl)
        ic["id"] = new_uuid()
        nice = SOCIAL_NAMES[net]
        ic["name"] = nice if capital else net
        ic["image"]["src"] = re.sub(r"/\w+@2x\.png$", f"/{net}@2x.png", tpl["image"]["src"])
        ic["image"]["href"] = url
        ic["image"]["prefix"] = ""
        ic["image"]["alt"] = nice
        ic["image"]["title"] = nice
        ic["image"]["target"] = "_blank"
        out.append(ic)
    d["iconsList"]["icons"] = out
    cs = d.get("computedStyle") or {}
    if "width" in cs and out:
        n = len(out)
        cs["width"] = n * 32 + (n - 1) * 15 if isinstance(cs["width"], (int, float)) else cs["width"]


# ================================================================ popup form

def build_form(brand, tpl, kind):
    """kind: 'popup' (pop-up template) or 'embed' (fixed form template)."""
    from . import emails
    texts = emails.texts_for(brand, emails.site_type(brand) == "ecommerce")
    patch = Patcher(brand, "form" if kind == "popup" else "embed", texts)
    doc = copy.deepcopy(tpl)
    form = doc["data"]["form"]
    form["form_name"] = f'{brand["name"]} - ' + ("Pop-up abonare" if kind == "popup" else "Formular abonare")
    form["pages"]["form"]["form_name"] = form["form_name"]
    json_keys = [("pages", "form", "form_json"), ("pages", "responder", "responder_json"),
                 ("pages", "confirm", "confirm_page_json"), ("template", "confirm_email_json")]
    for path in json_keys:
        holder = form
        for k in path[:-1]:
            holder = holder.get(k) or {}
        if path[-1] not in holder:
            continue
        page = json.loads(holder[path[-1]])
        fix_bee(page, brand, patch)
        if path[-1] == "confirm_email_json":
            page["page"]["body"]["container"]["style"]["background-color"] = "#FFFFFF"
        page = deep_map(page, patch)
        holder[path[-1]] = json.dumps(page, ensure_ascii=False, separators=(",", ":"))
    # the remaining strings (rendered html, labels, modal colors...)
    doc["data"]["form"] = deep_map(form, lambda s: s if s.startswith('{"page"') else patch(s))
    doc["exported_at"] = int(time.time())
    from .i18n import lang_of, tr
    doc = tr(doc, lang_of(brand))
    return doc


# ================================================================ entry point

TEMPLATE_FILES = {"popup": "popup.json", "embed": "form_embed.json", "newsletter": "welcome.json",
                  "welcome_auto": "welcome_automation.json", "cart_auto": "abandoned_cart.json"}


def load_templates(folder=TEMPLATES):
    out = {}
    for key, name in TEMPLATE_FILES.items():
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            out[key] = json.load(f)
    return out


WESERV = "https://images.weserv.nl/?url="


def _weserv(src, params):
    from urllib.parse import quote
    return WESERV + quote(src, safe="") + params


def neutral_images(brand):
    """Replace images hosted on our GitHub Pages with an image-CDN URL that points
    to the client's own original file (no trace of this tool in the editor)."""
    b = copy.deepcopy(brand)
    ours = lambda u: isinstance(u, str) and ".github.io/" in u
    logo = b.get("logo") or {}
    src = logo.get("source_url")
    # every picture goes through the image CDN: some sites refuse to show their files on other sites (hotlink protection)
    if not (src and src.startswith("http")) and str(logo.get("url", "")).startswith("http") and not ours(logo.get("url")):
        src = logo["url"]
    if src and src.startswith("http") and WESERV not in str(logo.get("url")):
        recolored = logo["recolored"] if "recolored" in logo else any("colorat închis" in w for w in b.get("warnings") or [])
        logo["url"] = _weserv(src, "&trim=10&w=600&output=png" + ("&filt=negate" if recolored else ""))
    for p in b.get("products") or []:
        # every product image becomes a 600x600 square (white background) so the cards line up
        src = p.get("source_image") if str(p.get("source_image", "")).startswith("http") else p.get("image")
        if isinstance(src, str) and src.startswith("http") and not ours(src) and WESERV not in src:
            p["image"] = _weserv(src, "&w=600&h=600&fit=contain&cbg=white&bg=white&output=jpg&q=85")
    for item in (b.get("links") or {}).get("menu") or []:
        if isinstance(item.get("image"), str) and item["image"].startswith("http") and WESERV not in item["image"]:
            item["image"] = _weserv(item["image"], "&w=600&h=400&fit=cover&a=attention&output=jpg&q=85")
    ban = b.get("banner") or {}
    bsrc = ban.get("source_url") if str(ban.get("source_url", "")).startswith("http") else ban.get("url")
    if isinstance(bsrc, str) and bsrc.startswith("http") and not ours(bsrc) and WESERV not in str(ban.get("url")):
        ban["url"] = _weserv(bsrc, "&w=1300&output=jpg&q=85")
    return b


def _image_ok(url):
    import requests
    try:
        r = requests.get(url, timeout=25, stream=True, headers={"User-Agent": "Mozilla/5.0 NZM-Onboarding image check"})
        ok = r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("image/")
        r.close()
        return ok
    except Exception:
        return False


def verify_images(b):
    """Open every picture the emails will show. One that does not load (hotlink protection, deleted file,
    image CDN refusing it) is left out, so a client never gets a broken-image box. Off with NZM_CHECK_IMAGES=0."""
    if os.environ.get("NZM_CHECK_IMAGES", "1") == "0":
        return b
    from concurrent.futures import ThreadPoolExecutor
    urls = set()
    logo, ban = b.get("logo") or {}, b.get("banner") or {}
    for u in [logo.get("url"), ban.get("url")] + [p.get("image") for p in b.get("products") or []] + \
             [m.get("image") for m in (b.get("links") or {}).get("menu") or []]:
        if isinstance(u, str) and u.startswith("http"):
            urls.add(u)
    if not urls:
        return b
    with ThreadPoolExecutor(8) as ex:
        status = dict(zip(urls, ex.map(_image_ok, urls)))
    # some shops' CDNs refuse the image service but serve the picture to anyone else: use their own link then
    from urllib.parse import parse_qs, urlparse as _up
    direct = {}
    for u, ok in status.items():
        if not ok and WESERV in u:
            src = (parse_qs(_up(u).query).get("url") or [""])[0]
            if src and not src.startswith("http"):
                src = "https://" + src
            if src and re.search(r"\.(jpe?g|png|gif)(\?|$)", src, re.I) and _image_ok(src):
                direct[u] = src
                status[u] = True
    if direct:
        def swap(x):
            return direct.get(x, x)
        if b.get("banner"):
            b["banner"]["url"] = swap(b["banner"]["url"])
        if b.get("logo"):
            b["logo"]["url"] = swap(b["logo"]["url"])
        for p in b.get("products") or []:
            p["image"] = swap(p.get("image"))
        for m in (b.get("links") or {}).get("menu") or []:
            if m.get("image"):
                m["image"] = swap(m["image"])
    if status.get(ban.get("url")) is False:
        b["banner"] = None
    for m in (b.get("links") or {}).get("menu") or []:
        if status.get(m.get("image")) is False:
            m.pop("image", None)
            m["image_from"] = "home"  # becomes a clean text card
    if b.get("products"):
        b["products"] = [p for p in b["products"] if status.get(p.get("image")) is not False]
    if status.get(logo.get("url")) is False and str(logo.get("source_url", "")).startswith("http"):
        logo["url"] = logo["source_url"]  # the image CDN refused it: the site's own file is the last chance
    bad = sorted(u for u, ok in status.items() if not ok)
    if bad:
        print("imagini care nu se încarcă (scoase din emailuri):", *bad, sep="\n  ")
    return b


def generate(brand, out_dir, templates=None):
    from . import emails
    templates = templates or load_templates()
    brand = verify_images(neutral_images(brand))
    os.makedirs(out_dir, exist_ok=True)
    slug = brand["slug"]
    kind = emails.form_type(brand)
    ecom = emails.site_type(brand) == "ecommerce"
    files = {
        f"{slug}-formular-{'pop-up' if kind == 'popup' else 'embed'}.json": build_form(brand, templates[kind], kind),
        f"{slug}-automatizare-{'cos-abandonat' if ecom else 'bun-venit'}.json":
            (emails.build_cart_automation(brand, templates["cart_auto"]) if ecom
             else emails.build_welcome_automation(brand, templates["welcome_auto"])),
        f"{slug}-newsletter-{'bun-venit' if ecom else 'noutati'}.json": emails.build_newsletter(brand, templates["newsletter"]),
    }
    problems = [f"{name}: {p}" for name, doc in files.items() for p in check_output(doc)]
    if problems:  # nothing is saved: a broken file never reaches the history
        raise RuntimeError("Fișierele generate au probleme, nu le salvez: " + "; ".join(problems[:5]))
    for name, doc in files.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent="\t")
    return list(files)


ALLOWED_VARS = {"url", "name", "img", "#each NZCart.products", "/each"}
MODULE_TYPES = {"text", "image", "button", "divider", "social", "form", "heading", "paragraph", "properties", "spacer"}


def check_output(doc):
    """Safety net run on every generated file before it is saved (the checks done by hand so far)."""
    out = []
    raw = json.dumps(doc, ensure_ascii=False)
    flat = raw.replace('\\"', '"').replace("\\/", "/")
    for bad, why in ((r"<script", "cod JavaScript"), (r"javascript:", "link javascript:"),
                     (r"\son(?:click|error|load|mouseover)\s*=", "atribut de eveniment"),
                     (r"github\.io|githubusercontent\.com|github\.com/cosminflrn", "link spre GitHub"),
                     (r"example\.com|\(link\)|lorem ipsum", "text de exemplu rămas")):
        if re.search(bad, flat, re.I):
            out.append(why)
    for var in set(re.findall(r"\{\{\s*([^}]+?)\s*\}\}", flat)):
        if var not in ALLOWED_VARS:
            out.append(f"variabilă necunoscută {{{{{var}}}}}")
    types = set(re.findall(r"mailup-bee-[a-z]+-modules?-([a-z-]+)", flat)) | set(re.findall(r"mailup-bee-page-([a-z]+)", flat))
    unknown = types - MODULE_TYPES
    if unknown:
        out.append("module necunoscute: " + ", ".join(sorted(unknown)))
    data = doc.get("data") or {}
    meta = ((data.get("draft_meta") or {}).get("meta") or {}) if isinstance(data, dict) else {}
    for key, d in meta.items():  # automation emails: the hidden editor copy must match the design
        try:
            import base64
            params = d["params"]
            b64 = re.search(r">([A-Za-z0-9+/=]{100,})<", params["txt_editor"]).group(1)
            if json.loads(base64.b64decode(b64)) != json.loads(params["json"]):
                out.append(f"email {key}: copia din editor diferă de design")
        except Exception:
            out.append(f"email {key}: date de editor lipsă")
    for u in re.findall(r'"(?:src|href)"\s*:\s*"([^"]*)"', flat):
        if u and not (u.startswith(("http://", "https://", "mailto:", "tel:", "#", "{{", "[")) or u in ("", "/")):
            out.append(f"link invalid: {u[:60]}")
            break
    return out
