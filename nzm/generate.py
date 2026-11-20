"""Apply a brand profile (brand.json) to the Newsman export templates.

Every template is a Newsman export (popup form, welcome template, abandoned-cart
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
]
BANNER_IDS = ["bine-ai-venit.png"]
PRODUCT_PLACEHOLDER_IMG = "https://img.newsmanapp.com/i/b/901bd24ca743a8d7ea7d611c3e43c36e/28118/placeholder400x300.png"

COLOR_ROLES = {
    "welcome": {"#030000": "dark", "#fb2324": "accent", "#f4f1ef": "light"},
    "automation": {"#fb2324": "accent", "#ff0000": "accent", "#ff0030": "accent", "#efe9e6": "light", "#8f7d5e": "muted"},
    "form": {"#ef4136": "accent", "#47433c": "dark"},
}

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

    def __init__(self, brand, kind):
        self.b = brand
        self.kind = kind
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
        return s

    # -- socials in rendered html
    def fix_social_html(self, s):
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


def fix_bee(page, brand, patch):
    """Structural changes valid for every Beefree page."""
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


# -- small builders reused by the welcome email

def p_html(inner, size=14, align="center", line=1.2, extra=""):
    lh = int(round(size * line))
    st = f"font-size:{size}px;line-height:{lh}px;text-align:{align};word-break:break-word;{extra}"
    return f'<p style="{st}" data-mce-style="{st}">{inner}</p>'


def text_wrap(ps, family="inherit"):
    st = f"font-size:12px;line-height:14px;font-family:{family};"
    return f'<div class="txtTinyMce-wrapper" style="{st}" data-mce-style="{st}">{"".join(ps)}</div>'


def make_text(proto, html, color=None, padding=None, link_color=None):
    m = copy.deepcopy(proto)
    m["uuid"] = new_uuid()
    t = m["descriptor"]["text"]
    t["html"] = html
    if color:
        t["style"]["color"] = color
    if link_color:
        t.setdefault("computedStyle", {})["linkColor"] = link_color
    if padding:
        m["descriptor"]["style"].update(padding)
    return m


def make_row(proto_row, modules_per_col):
    r = copy.deepcopy(proto_row)
    r["uuid"] = new_uuid()
    col_proto = r["columns"][0]
    n = len(modules_per_col)
    cols = []
    for mods in modules_per_col:
        c = copy.deepcopy(col_proto)
        c["uuid"] = new_uuid()
        c["grid-columns"] = 12 // n
        c["modules"] = mods
        cols.append(c)
    r["columns"] = cols
    r["type"] = {1: "one-column-empty", 2: "two-columns-empty", 3: "three-columns-empty"}.get(n, "one-column-empty")
    return r


# ================================================================ welcome

def build_welcome(brand, tpl):
    pal = brand["colors"]
    patch = Patcher(brand, "welcome")
    doc = copy.deepcopy(tpl)
    page = doc["data"]
    rows = page["page"]["rows"]

    def find_row(pred):
        for i, r in enumerate(rows):
            for c in r["columns"]:
                for m in c["modules"]:
                    if pred(m):
                        return i, r, m
        return None, None, None

    def has_text(s):
        return lambda m: mtype(m) == "text" and s in m["descriptor"]["text"]["html"]

    text_proto = find_row(has_text("Te rasplatim"))[2]
    image_proto = find_row(lambda m: mtype(m) == "image")[2]
    button_proto = find_row(lambda m: mtype(m) == "button")[2]
    one_col_row = copy.deepcopy(find_row(has_text("Te rasplatim"))[1])
    dark, accent = pal["dark"], pal["accent"]
    L = brand["links"]

    # 1. navigation menu with real links
    i, row, m = find_row(has_text("CATEGORII PRODUSE"))
    if m:
        items = [{"label": "HOME", "url": L["home"]}] + list(L.get("menu") or [])
        while len(items) > 3 and sum(len(x["label"]) for x in items) > 42:
            items.pop(-2 if len(items) > 2 else -1)
        sep = "&nbsp; &nbsp; &nbsp; &nbsp; &nbsp;"
        size = 16 if sum(len(x["label"]) for x in items) < 36 else 14
        links = sep.join(
            f'<a href="{esc(x["url"])}" target="_blank" rel="noopener" style="text-decoration:none;color:{dark};">'
            f'<span style="font-size:{size}px;line-height:{int(size * 1.2)}px;color:{dark};">{esc(x["label"])}</span></a>'
            for x in items)
        m["descriptor"]["text"]["html"] = text_wrap([p_html(links)])
        m["descriptor"]["text"].setdefault("computedStyle", {})["linkColor"] = dark

    # 2. banner: the generic image has "Bine ai venit!" baked in; a site banner
    #    does not, so add the welcome title as text above it.
    if brand.get("banner") and use_site_banner(brand):
        i, row, m = find_row(lambda m: mtype(m) == "image" and "bine-ai-venit" in m["descriptor"]["image"]["src"])
        if row:
            title = make_text(text_proto, text_wrap([
                p_html(f'<strong><span style="font-size:38px;line-height:46px;color:{dark};">Bine ai venit!</span></strong>', 14),
                p_html(f'<span style="font-size:13px;line-height:20px;letter-spacing:3px;color:{dark};">'
                       f'ÎȚI MULȚUMIM CĂ TE-AI ABONAT!</span>', 13),
            ], "'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Geneva, Verdana, sans-serif"),
                padding={"padding-top": "25px", "padding-bottom": "20px"})
            rows.insert(i, make_row(one_col_row, [[title]]))

    # 3. discount block -> products (discount kept only if a code was provided)
    code = (brand.get("options") or {}).get("discount_code")
    i, row, _ = find_row(has_text("Te rasplatim"))
    disc_mods = row["columns"][0]["modules"]
    button = next(x for x in disc_mods if mtype(x) == "button")
    button["descriptor"]["button"]["href"] = L["home"]
    button["descriptor"]["button"]["target"] = "_blank"
    heading = make_text(text_proto, text_wrap([p_html(
        f'<strong><span style="font-size:18px;line-height:22px;color:{dark};">'
        f'Am ales câteva produse care credem că o să-ți placă:</span></strong>')],
        "'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Geneva, Verdana, sans-serif"),
        padding={"padding-top": "20px"})
    product_row = make_row(one_col_row, product_cards(brand, text_proto, image_proto, button_proto))
    if code:
        rows[i + 1:i + 1] = [make_row(one_col_row, [[heading]]), product_row]
    else:
        row["columns"][0]["modules"] = [heading]
        rows[i + 1:i + 1] = [product_row, make_row(one_col_row, [[button]])]

    # 4. thank-you section: links + discount reminder
    i, row, m = find_row(has_text("Click aici"))
    if m:
        target = L.get("promo") or L["home"]
        m["descriptor"]["text"]["html"] = m["descriptor"]["text"]["html"].replace('href="#"', f'href="{esc(target)}"')
    if not code:
        for r in rows:
            for c in r["columns"]:
                c["modules"] = [x for x in c["modules"] if not (mtype(x) == "text" and "Nu uita sa aplici" in x["descriptor"]["text"]["html"])]

    # 5. contact line
    i, row, m = find_row(has_text("Ai nevoie de ajutor"))
    if m:
        ct = brand.get("contact") or {}
        bits = []
        if ct.get("phone"):
            bits.append(f'telefonic: <a href="{esc(ct.get("phone_href") or "tel:" + ct["phone"])}" style="color:{dark};">{esc(ct["phone"])}</a>')
        if ct.get("email"):
            bits.append(f'pe email: <a href="mailto:{esc(ct["email"])}" style="color:{dark};">{esc(ct["email"])}</a>')
        if not bits and L.get("contact"):
            bits.append(f'din <a href="{esc(L["contact"])}" style="color:{dark};">pagina de contact</a>')
        span = f'<span style="font-size:15px;line-height:18px;"><strong><span style="color:{dark};line-height:18px;font-size:15px;">'
        ps = [p_html(span + "Ai nevoie de ajutor? Ne poți contacta</span></strong></span>")]
        if bits:
            ps.append(p_html(span + " sau ".join(bits) + "</span></strong></span>"))
        m["descriptor"]["text"]["html"] = text_wrap(ps)
        m["descriptor"]["text"].setdefault("computedStyle", {})["linkColor"] = dark
        if not brand.get("socials"):
            row["columns"][0]["modules"] = [x for x in row["columns"][0]["modules"] if mtype(x) != "social"]

    # 6. copyright with brand name
    i, row, m = find_row(has_text("COPYRIGHT"))
    if m:
        h = m["descriptor"]["text"]["html"]
        m["descriptor"]["text"]["html"] = h.replace("</code>&nbsp;</span>", f"</code>&nbsp;{esc(brand['name'])}</span>")

    fix_bee(page, brand, patch)
    page = deep_map(page, patch)
    doc["data"] = page
    doc["exported_at"] = int(time.time())
    return doc


def product_cards(brand, text_proto, image_proto, button_proto):
    pal = brand["colors"]
    prods = list(brand.get("products") or [])
    while len(prods) < 3:
        prods.append({"name": "Nume produs", "price": "199,00 lei", "url": brand["links"]["home"],
                      "image": PRODUCT_PLACEHOLDER_IMG, "placeholder": True})
    cols = []
    for p in prods[:3]:
        img = copy.deepcopy(image_proto)
        img["uuid"] = new_uuid()
        is_ph = p.get("placeholder")
        img["descriptor"]["image"].update({"src": p["image"], "href": p["url"], "alt": p["name"],
                                           "width": "400px" if is_ph else "600px",
                                           "height": "300px" if is_ph else "600px", "target": "_blank"})
        img["descriptor"]["computedStyle"] = {"class": "center autowidth", "width": "196px", "hideContentOnMobile": False}
        img["descriptor"]["style"] = {"width": "100%", "padding-top": "10px", "padding-left": "10px",
                                      "padding-right": "10px", "padding-bottom": "5px"}
        name = p["name"] if len(p["name"]) <= 60 else p["name"][:57].rstrip() + "…"
        title = make_text(text_proto, text_wrap([p_html(
            f'<a href="{esc(p["url"])}" target="_blank" rel="noopener" style="text-decoration:none;color:{pal["dark"]};">'
            f'<span style="font-size:14px;line-height:18px;color:{pal["dark"]};">{esc(name)}</span></a>', 14, line=1.3)]),
            padding={"padding-top": "5px", "padding-bottom": "0px"}, link_color=pal["dark"])
        mods = [img, title]
        if p.get("price"):
            mods.append(make_text(text_proto, text_wrap([p_html(
                f'<strong><span style="font-size:16px;line-height:19px;color:{pal["accent"]};">{esc(p["price"])}</span></strong>')]),
                padding={"padding-top": "5px", "padding-bottom": "5px"}))
        btn = copy.deepcopy(button_proto)
        btn["uuid"] = new_uuid()
        b = btn["descriptor"]["button"]
        st = "word-break:break-word;"
        b["label"] = f'<div class="txtTinyMce-wrapper"><p style="{st}" data-mce-style="{st}"><strong>Vezi produsul</strong></p></div>'
        b["href"] = p["url"]
        b["target"] = "_blank"
        b["style"].update({"background-color": pal["accent"], "color": pal["accent_text"], "font-size": "13px",
                           "padding-left": "18px", "padding-right": "18px",
                           **{f"border-{s}": "0px solid transparent" for s in ("top", "right", "bottom", "left")}})
        mods.append(btn)
        cols.append(mods)
    return cols


# ================================================================ automation

def build_automation(brand, tpl):
    patch = Patcher(brand, "automation")
    doc = copy.deepcopy(tpl)
    data = doc["data"]
    opts = brand.get("options") or {}
    data["workflow"]["name"] = f'{brand["name"]} - Coș abandonat'
    for trig in data["triggers"].values():
        for act in trig.get("actions", []) + trig.get("actions_no", []):
            if act.get("action_type") == "send_email":
                if opts.get("sender_email"):
                    act["from_email"] = opts["sender_email"]
                act["from_name"] = opts.get("sender_name") or brand["name"]
    no_code = not opts.get("discount_code")
    if no_code:
        for trig in data["triggers"].values():
            for act in trig.get("actions", []):
                if act.get("action_type") == "send_email" and act.get("subject") in NO_DISCOUNT_SUBJECTS:
                    act["subject"], act["preheader"] = NO_DISCOUNT_SUBJECTS[act["subject"]]
    for draft in data["draft_meta"]["meta"].values():
        params = draft["params"]
        page = json.loads(params["json"])
        if no_code:
            strip_discount(page)
            draft["html"] = strip_discount_html(draft["html"])
            if draft.get("automation_subject") in NO_DISCOUNT_SUBJECTS:
                draft["automation_subject"] = NO_DISCOUNT_SUBJECTS[draft["automation_subject"]][0]
        fix_bee(page, brand, patch)
        page = deep_map(page, patch)
        new_json = json.dumps(page, ensure_ascii=False, separators=(",", ":"))
        params["json"] = new_json
        te = params.get("txt_editor") or ""
        m = re.match(r'(<div style="display: none" id="beefree_contents_json">)([^<]*)(</div>)', te)
        if m:
            rest = patch(te[m.end():])
            params["txt_editor"] = m.group(1) + base64.b64encode(new_json.encode("utf-8")).decode() + m.group(3) + rest
        draft["html"] = patch(draft["html"])
        draft["text"] = patch(draft["text"])
    doc["exported_at"] = int(time.time())
    return doc


NO_DISCOUNT_SUBJECTS = {
    "Ai de la noi 10% discount la finalizarea comenzii!": ("Produsele tale te așteaptă în coș!",
                                                          "Le-am păstrat pentru tine, dar nu știm cât timp mai sunt pe stoc."),
    "Nu uita de reducerea ta!": ("Ultima amintire: coșul tău te așteaptă",
                                 "Finalizează comanda cât produsele sunt încă disponibile."),
}
TOPBAR_TEXT = "Produsele tale te așteaptă!"
REPLACE_TEXTS = [  # (pattern in the discount paragraph, new text)
    (r"Discountul(?:\s|<[^>]+>)*tau(?:\s|<[^>]+>)*expira", "Produsele din coșul tău sunt încă rezervate pentru tine, dar nu pentru mult timp. Finalizează comanda cât sunt pe stoc!"),
    (r"reducere(?:\s|<[^>]+>)*daca", "Stocurile sunt limitate, așa că îți recomandăm să finalizezi comanda cât mai curând."),
]


def _one_paragraph(block_html, text):
    out = re.sub(r"(<p\b[^>]*>).*?(</p>)", rf"\g<1>{text}\g<2>", block_html, count=1, flags=re.S)
    first_end = out.find("</p>") + 4
    return out[:first_end] + re.sub(r"<p\b[^>]*>.*?</p>", "", out[first_end:], flags=re.S)
DISCOUNT_TEXT_RE = re.compile(r"CODDISCOUNT|codul tau|Foloseste\s+codul|Dar stim ca|reducere daca", re.I)
DISCOUNT_IMG_RE = re.compile(r"nu-uita-de-discount|aplica-acum-codul")


def strip_discount(page):
    """Remove the discount code blocks from an automation email (Beefree JSON)."""
    for row in page["page"]["rows"]:
        for col in row["columns"]:
            mods, keep = col["modules"], []
            has_code = any(mtype(m) == "text" and "CODDISCOUNT" in m["descriptor"]["text"]["html"] for m in mods)
            for m in mods:
                t = mtype(m)
                h = m["descriptor"].get("text", {}).get("html", "") if t == "text" else ""
                if t == "text" and re.search(r"\d+%\s*discount", h):
                    m["descriptor"]["text"]["html"] = re.sub(r"(<p\b[^>]*>).*?(</p>)", rf"\g<1><strong>{TOPBAR_TEXT}</strong>\g<2>", h, count=1, flags=re.S)
                    m["descriptor"]["text"]["html"] = re.sub(r"</p>\s*<p\b[^>]*>.*?</p>", "</p>", m["descriptor"]["text"]["html"], flags=re.S)
                    keep.append(m)
                elif t == "text" and any(re.search(pat, h) for pat, _ in REPLACE_TEXTS):
                    new = next(txt for pat, txt in REPLACE_TEXTS if re.search(pat, h))
                    m["descriptor"]["text"]["html"] = _one_paragraph(h, new)
                    keep.append(m)
                elif t == "text" and DISCOUNT_TEXT_RE.search(re.sub(r"<[^>]+>", " ", h)):
                    continue
                elif t == "image" and DISCOUNT_IMG_RE.search(m["descriptor"]["image"].get("src", "")):
                    continue
                elif t == "divider" and has_code and "dotted" in m["descriptor"]["divider"]["style"].get("border-top", ""):
                    continue
                else:
                    keep.append(m)
            col["modules"] = keep
    # the removed discount banner left the greeting glued to the top bar
    for row in page["page"]["rows"]:
        for col in row["columns"]:
            for m in col["modules"]:
                if mtype(m) == "text" and re.search(r">\s*Buna[!,]", m["descriptor"]["text"]["html"]):
                    m["descriptor"]["style"]["padding-top"] = "30px"
                    return


def strip_discount_html(h):
    """Same as strip_discount, on the rendered HTML (flat BEE text/image block tables)."""
    inner = r"(?:(?!<table).)*?"
    def drop(pattern):
        nonlocal h
        h = re.sub(r'<table class="(?:text_block|image_block)[^"]*"' + inner + pattern + inner + r"</table>", "", h, flags=re.S)
    def topbar(m):
        return re.sub(r"(<p\b[^>]*>).*?(</p>)", rf"\g<1><strong>{TOPBAR_TEXT}</strong>\g<2>", m.group(0), count=1, flags=re.S)
    h = re.sub(r'<table class="text_block[^"]*"' + inner + r"\d+%(?:\s|&nbsp;|<[^>]+>)*discount" + inner + r"</table>", topbar, h, flags=re.S)
    for pat, txt in REPLACE_TEXTS:
        h = re.sub(r'<table class="text_block[^"]*"' + inner + pat + inner + r"</table>",
                   lambda m, txt=txt: _one_paragraph(m.group(0), txt), h, flags=re.S)
    def pad_greeting(m):
        td = m.group(1)
        if 'style="' in td:
            td = re.sub(r"padding-top:\s*\d+px;?", "", td)
            td = td.replace('style="', 'style="padding-top:30px;', 1)
        else:
            td = td.replace('class="pad"', 'class="pad" style="padding-top:30px"')
        return td + m.group(2)
    h = re.sub(r'(<td class="pad"[^>]*>)(' + inner + r">\s*Buna[!,])", pad_greeting, h, count=1, flags=re.S)
    nt = r"(?:(?!</table>).)*?"
    h = re.sub(r'<table class="divider_block[^"]*"' + nt + r"<table" + nt + r"dotted #000(?:000)?\b" + nt + r"</table>" + nt + r"</table>",
               "", h, flags=re.S | re.I)
    for pat in [r"CODDISCOUNT", r"Dar stim ca", r"nu-uita-de-discount", r"aplica-acum-codul"]:
        drop(pat)
    return h


# ================================================================ popup form

def build_form(brand, tpl):
    patch = Patcher(brand, "form")
    doc = copy.deepcopy(tpl)
    form = doc["data"]["form"]
    form["form_name"] = f'{brand["name"]} - Pop-up abonare'
    form["pages"]["form"]["form_name"] = form["form_name"]
    json_keys = [("pages", "form", "form_json"), ("pages", "responder", "responder_json"),
                 ("pages", "confirm", "confirm_page_json"), ("template", "confirm_email_json")]
    for path in json_keys:
        holder = form
        for k in path[:-1]:
            holder = holder[k]
        page = json.loads(holder[path[-1]])
        fix_bee(page, brand, patch)
        page = deep_map(page, patch)
        holder[path[-1]] = json.dumps(page, ensure_ascii=False, separators=(",", ":"))
    # the remaining strings (rendered html, labels, modal colors...)
    doc["data"]["form"] = deep_map(form, lambda s: s if s.startswith('{"page"') else patch(s))
    doc["exported_at"] = int(time.time())
    return doc


# ================================================================ entry point

def load_templates(folder=TEMPLATES):
    def rd(n):
        with open(os.path.join(folder, n), encoding="utf-8") as f:
            return json.load(f)
    return {"welcome": rd("welcome.json"), "automation": rd("abandoned_cart.json"), "form": rd("popup.json")}


def generate(brand, out_dir, templates=None):
    templates = templates or load_templates()
    os.makedirs(out_dir, exist_ok=True)
    slug = brand["slug"]
    files = {
        f"{slug}__1-Pop-up-abonare.json": build_form(brand, templates["form"]),
        f"{slug}__2-Welcome.json": build_welcome(brand, templates["welcome"]),
        f"{slug}__3-Automatizare-cos-abandonat.json": build_automation(brand, templates["automation"]),
    }
    for name, doc in files.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent="\t")
    return list(files)
