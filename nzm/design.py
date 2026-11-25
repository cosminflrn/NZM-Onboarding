"""Modern email design: Beefree JSON builders, email layouts and an HTML renderer.

Every email is described once as Beefree JSON (what the Newsman editor opens)
and rendered from that same JSON to email-safe HTML (what is stored/sent), so
the two never drift apart.
"""
import copy
import html as htmlmod
import re
import uuid

WIDTH = 640
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
INK = "#18181b"        # main text
MUTED = "#52525b"      # secondary text
SUBTLE = "#71717a"     # footer text
LINE = "#e4e4e7"       # hairlines
PAGE_BG = "#f4f4f5"    # outside the email card
WHITE = "#ffffff"
ICON_SET = "https://app-rsrc.getbee.io/public/resources/social-networks-icon-sets/circle-dark-gray/{net}@2x.png"
PLACEHOLDER_IMG = "https://img.newsmanapp.com/i/b/901bd24ca743a8d7ea7d611c3e43c36e/28118/placeholder400x300.png"
SOCIAL_NAMES = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube",
                "linkedin": "LinkedIn", "pinterest": "Pinterest", "twitter": "X"}


def uid():
    return str(uuid.uuid4())


def esc(s):
    return htmlmod.escape(str(s or ""), quote=True)


def pad(t, r=None, b=None, l=None):
    r = t if r is None else r
    b = t if b is None else b
    l = r if l is None else l
    return {"padding-top": f"{t}px", "padding-right": f"{r}px", "padding-bottom": f"{b}px", "padding-left": f"{l}px"}


# ====================================================================== text helpers

def para(inner, size=16, color=INK, align="center", lh=1.6, weight=None, spacing=None, mb=0):
    lhpx = int(round(size * lh))
    st = f"font-size:{size}px;line-height:{lhpx}px;text-align:{align};word-break:break-word;"
    if mb:
        st += f"margin-bottom:{mb}px;"
    span = f"font-size:{size}px;line-height:{lhpx}px;color:{color};"
    if spacing:
        span += f"letter-spacing:{spacing};"
    body = f'<span style="{span}" data-mce-style="{span}">{inner}</span>'
    if weight == "bold":
        body = f"<strong>{body}</strong>"
    return f'<p style="{st}" data-mce-style="{st}">{body}</p>'


def wrap(paras, lh_px=21):
    st = f"font-size:14px;line-height:{lh_px}px;font-family:inherit;"
    return f'<div class="txtTinyMce-wrapper" style="{st}" data-mce-style="{st}">{"".join(paras)}</div>'


def link(text, url, color, underline=True, weight=None):
    st = f"color:{color};text-decoration:{'underline' if underline else 'none'};"
    if weight:
        st += f"font-weight:{weight};"
    return f'<a href="{esc(url)}" target="_blank" rel="noopener" style="{st}">{text}</a>'


def nl2br(text):
    return "<br/>".join(esc(x) for x in str(text or "").split("\n"))


MERGE_YEAR = ('<code spellcheck="false" data-bee-type="mergetag" data-bee-code="" data-bee-name="##current_year##" '
              'data-bee-preview-value="2026" data-bee-value="##current_year##"><q>no-content</q></code>')


# ====================================================================== modules

def m_text(html, padding=None, color=INK, link_color=None, lh="160%"):
    return {
        "type": "mailup-bee-newsletter-modules-text", "locked": False, "uuid": uid(),
        "descriptor": {
            "text": {"html": html, "style": {"color": color, "font-family": "inherit", "line-height": lh},
                     "computedStyle": {"linkColor": link_color or color}},
            "style": padding or pad(10, 24),
            "computedStyle": {"hideContentOnMobile": False},
        },
    }


def m_image(src, width, height, display_width, href="", alt="", padding=None, dynamic=None, full=False):
    img = {"alt": alt, "href": href, "prefix": "", "src": src, "target": "_blank",
           "width": f"{int(width)}px", "height": f"{int(height)}px"}
    if dynamic:
        img["dynamicSrc"] = dynamic
    cls = "center autowidth fullwidth" if full else "center fixedwidth"
    return {
        "type": "mailup-bee-newsletter-modules-image", "locked": False, "uuid": uid(),
        "descriptor": {
            "image": img,
            "style": {"width": "100%", **(padding or pad(0))},
            "computedStyle": {"class": cls, "width": f"{int(display_width)}px", "hideContentOnMobile": False},
        },
    }


def m_button(label, href, bg, color=WHITE, border=None, size=16, padding=None, align="center", radius="999px",
             px=28, py=12, weight="700"):
    border = border or "0px solid transparent"
    st = f"word-break:break-word;"
    return {
        "type": "mailup-bee-newsletter-modules-button", "locked": False, "uuid": uid(),
        "descriptor": {
            "button": {
                "label": f'<div class="txtTinyMce-wrapper"><p style="{st}" data-mce-style="{st}"><strong>{esc(label)}</strong></p></div>',
                "href": href, "target": "_blank",
                "style": {"background-color": bg, "border-top": border, "border-right": border, "border-bottom": border,
                          "border-left": border, "border-radius": radius, "color": color, "direction": "ltr",
                          "font-family": "inherit", "font-size": f"{size}px", "font-weight": weight, "line-height": "150%",
                          "max-width": "100%", "padding-top": f"{py}px", "padding-bottom": f"{py}px",
                          "padding-left": f"{px}px", "padding-right": f"{px}px", "width": "auto"},
            },
            "style": {**(padding or pad(8, 24)), "text-align": align},
            "computedStyle": {"height": int(size * 1.5 + 2 * py), "width": int(len(label) * size * 0.6 + 2 * px),
                              "hideContentOnMobile": False},
        },
    }


def m_divider(color=LINE, width="100%", thickness=1, padding=None, height=None, style="solid"):
    dv = {"border-top": f"{thickness}px {style} {color}", "width": width}
    if height is not None:
        dv = {"border-top": "0px solid transparent", "width": "100%", "height": f"{height}px"}
    return {
        "type": "mailup-bee-newsletter-modules-divider", "locked": False, "uuid": uid(),
        "descriptor": {"divider": {"style": dv}, "style": padding or pad(8, 24),
                       "computedStyle": {"align": "center", "hideContentOnMobile": False}},
    }


def m_spacer(h):
    return m_divider(height=h, padding=pad(0))


def m_social(socials, padding=None):
    icons = []
    for net, url in socials.items():
        nice = SOCIAL_NAMES.get(net, net.title())
        icons.append({"id": uid(), "type": "follow", "name": net, "text": "",
                      "image": {"alt": nice, "title": nice, "href": url, "prefix": "", "target": "_blank",
                                "src": ICON_SET.format(net=net)}})
    n = max(1, len(icons))
    return {
        "type": "mailup-bee-newsletter-modules-social", "locked": False, "uuid": uid(),
        "descriptor": {
            "iconsList": {"icons": icons},
            "style": {**(padding or pad(8, 24)), "text-align": "center"},
            "computedStyle": {"iconsDefaultWidth": 32, "padding": "0 6px 0 6px", "width": n * 44, "height": 48,
                              "hideContentOnMobile": False},
        },
    }


def row(columns, bg=WHITE, col_pad=None, container_bg="transparent", grid=None, radius=None, condition=None,
        stack=True):
    n = len(columns)
    grid = grid or [12 // n] * n
    cols = []
    for mods, g in zip(columns, grid):
        cols.append({"grid-columns": g, "modules": mods, "uuid": uid(),
                     "style": {"background-color": "transparent", "border-top": "0px solid transparent",
                               "border-right": "0px solid transparent", "border-bottom": "0px solid transparent",
                               "border-left": "0px solid transparent", **(col_pad or pad(0))}})
    content_style = {"background-color": bg, "background-image": "none", "background-position": "top left",
                     "background-repeat": "no-repeat", "color": INK, "width": f"{WIDTH}px"}
    if radius:
        content_style["border-radius"] = radius
    r = {
        "columns": cols,
        "container": {"style": {"background-color": container_bg, "background-image": "none",
                                "background-position": "top left", "background-repeat": "no-repeat"}},
        "content": {"computedStyle": {"hideContentOnDesktop": False, "hideContentOnMobile": False,
                                      "rowColStackOnMobile": stack, "rowReverseColStackOnMobile": False,
                                      "verticalAlign": "top"},
                    "style": content_style},
        "empty": False, "locked": False, "synced": False,
        "type": {1: "one-column-empty", 2: "two-columns-empty", 3: "three-columns-empty"}.get(n, "one-column-empty"),
        "uuid": uid(),
    }
    if condition:
        r["container"]["displayCondition"] = copy.deepcopy(condition)
    return r


def page(rows, link_color, title=""):
    return {
        "page": {
            "body": {
                "container": {"style": {"background-color": PAGE_BG}},
                "content": {"computedStyle": {"linkColor": link_color, "messageBackgroundColor": "transparent",
                                              "messageWidth": f"{WIDTH}px"},
                            "style": {"color": INK, "font-family": FONT}},
                "type": "mailup-bee-page-properties", "webFonts": [],
            },
            "description": "", "rows": rows,
            "template": {"name": "template-base", "type": "basic", "version": "2.0.0"},
            "title": title,
        },
        "comments": {},
    }


# ====================================================================== building blocks

class Kit:
    """Brand-aware blocks shared by all emails."""

    def __init__(self, brand, texts, ecommerce):
        self.b = brand
        self.t = texts
        self.ecom = ecommerce
        c = brand["colors"]
        self.accent = c["accent"]
        self.dark = c["dark"]
        self.tint = c["light"]
        self.L = brand.get("links") or {}
        self.home = self.L.get("home") or brand.get("url")

    # ---- header
    def header(self, nav=True):
        logo = self.b.get("logo") or {}
        mods = [m_spacer(8)]
        if logo.get("url"):
            w = int(logo.get("display_width") or 160)
            ratio = (logo.get("height") or 1) / max(1, logo.get("width") or 1)
            mods.append(m_image(logo["url"], logo.get("width") or w, logo.get("height") or int(w * ratio), w,
                                href=self.home, alt=self.b["name"], padding=pad(20, 24, 12, 24)))
        else:
            mods.append(m_text(wrap([para(esc(self.b["name"]), 22, INK, weight="bold")]), padding=pad(20, 24, 12, 24)))
        items = (self.L.get("menu") or [])[:3] if (nav and self.ecom) else []
        if items:
            sep = f'<span style="color:{LINE};">&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;</span>'
            links = sep.join(link(esc(m["label"]), m["url"], MUTED, underline=False, weight="600") for m in items)
            mods.append(m_text(wrap([para(links, 12, MUTED, spacing="1px", lh=1.5)]), padding=pad(4, 24, 16, 24),
                               color=MUTED, link_color=MUTED))
        else:
            mods.append(m_spacer(6))
        return row([mods], bg=WHITE)

    # ---- hero block in brand color
    def hero(self, eyebrow, title, subtitle, cta=None, cta_url=None):
        mods = [m_spacer(28)]
        if eyebrow:
            mods.append(m_text(wrap([para(esc(eyebrow).upper(), 12, "#ffffff", weight="bold", spacing="2px", lh=1.4)]),
                               padding=pad(0, 40, 8, 40), color="#ffffff"))
        mods.append(m_text(wrap([para(esc(title), 32, "#ffffff", weight="bold", lh=1.2)]),
                           padding=pad(0, 40, 12, 40), color="#ffffff", lh="120%"))
        if subtitle:
            mods.append(m_text(wrap([para(nl2br(subtitle), 17, "#ffffff", lh=1.55)]), padding=pad(0, 48, 8, 48),
                               color="#ffffff"))
        if cta and cta_url:
            mods.append(m_button(cta, cta_url, "#ffffff", self.accent, padding=pad(16, 24, 8, 24)))
        mods.append(m_spacer(28))
        return row([mods], bg=self.accent)

    def banner(self):
        ban = self.b.get("banner") or {}
        if not ban.get("url"):
            return None
        return row([[m_image(ban["url"], ban.get("width") or 1200, ban.get("height") or 600, WIDTH,
                             href=self.home, alt=self.b["name"], full=True)]], bg=WHITE)

    # ---- plain section of text
    def body(self, text, size=17, top=32, bottom=8, align="center", color=INK):
        ps = [para(nl2br(x), size, color, align=align, lh=1.65) for x in str(text).split("\n\n") if x.strip()]
        for i in range(len(ps) - 1):
            ps[i] = ps[i].replace('word-break:break-word;"', 'word-break:break-word;margin-bottom:14px;"', 1)
        return row([[m_text(wrap(ps), padding=pad(top, 40, bottom, 40))]], bg=WHITE)

    def heading(self, text, top=32, bottom=4, sub=None):
        ps = [para(esc(text), 22, INK, weight="bold", lh=1.3)]
        if sub:
            ps.append(para(esc(sub), 15, MUTED, lh=1.5))
        return row([[m_text(wrap(ps), padding=pad(top, 32, bottom, 32))]], bg=WHITE)

    def cta(self, label, url, top=16, bottom=32, outline=False):
        if outline:
            btn = m_button(label, url, "transparent", self.accent, border=f"2px solid {self.accent}",
                           padding=pad(top, 24, bottom, 24))
        else:
            btn = m_button(label, url, self.accent, "#ffffff", padding=pad(top, 24, bottom, 24))
        return row([[btn]], bg=WHITE)

    def discount(self, code, note):
        mods = [
            m_text(wrap([para("CODUL TĂU DE REDUCERE", 12, MUTED, weight="bold", spacing="2px", lh=1.4)]),
                   padding=pad(28, 24, 4, 24), color=MUTED),
            m_text(wrap([para(esc(code), 30, self.accent, weight="bold", spacing="3px", lh=1.3)]),
                   padding=pad(4, 24, 4, 24), color=self.accent),
            m_text(wrap([para(esc(note), 14, MUTED, lh=1.5)]), padding=pad(4, 32, 28, 32), color=MUTED),
        ]
        return [row([[m_spacer(8)]], bg=WHITE),
                row([mods], bg=self.tint, container_bg="transparent", radius="16px"),
                row([[m_spacer(8)]], bg=WHITE)]

    def products(self, products, title):
        prods = list(products or [])[:3]
        while len(prods) < 3:
            prods.append({"name": "Nume produs", "price": "199,00 lei", "url": self.home, "image": PLACEHOLDER_IMG,
                          "placeholder": True})
        cols = []
        for p in prods:
            name = p["name"] if len(p["name"]) <= 55 else p["name"][:52].rstrip() + "…"
            mods = [
                m_image(p["image"], 400 if p.get("placeholder") else 600, 300 if p.get("placeholder") else 600, 176,
                        href=p["url"], alt=name, padding=pad(0, 8, 12, 8)),
                m_text(wrap([para(link(esc(name), p["url"], INK, underline=False), 15, INK, lh=1.4)]),
                       padding=pad(0, 8, 4, 8), link_color=INK),
            ]
            if p.get("price"):
                mods.append(m_text(wrap([para(esc(p["price"]), 16, self.accent, weight="bold", lh=1.4)]),
                                   padding=pad(0, 8, 4, 8), color=self.accent))
            mods.append(m_button("Vezi produsul", p["url"], "transparent", INK, border=f"1px solid {LINE}", size=13,
                                 px=16, py=8, weight="600", padding=pad(6, 8, 8, 8)))
            cols.append(mods)
        return [self.heading(title, top=36, bottom=12),
                row(cols, bg=WHITE, col_pad=pad(0, 8, 8, 8))]

    @staticmethod
    def _label(it):
        lab = it["label"].strip()
        return lab[:1].upper() + lab[1:].lower() if lab.isupper() else lab

    def cards(self, items, title):
        """Non-ecommerce: up to 3 sections/pages of the site as cards (with their picture when found)."""
        items = [i for i in items if i.get("label") and i.get("url")][:3]
        if not items:
            return []
        cols = []
        for it in items:
            mods = []
            if it.get("image"):
                mods.append(m_image(it["image"], 600, 400, 176, href=it["url"], alt=self._label(it),
                                    padding=pad(0, 8, 12, 8)))
            mods += [
                m_text(wrap([para(esc(self._label(it)), 17, INK, weight="bold", lh=1.35)]), padding=pad(4, 12, 4, 12)),
                m_button("Descoperă →", it["url"], "transparent", self.accent, size=14, px=0, py=4, radius="0px",
                         padding=pad(0, 12, 16, 12)),
            ]
            cols.append(mods)
        return [self.heading(title, top=36, bottom=16),
                row(cols, bg=WHITE, col_pad=pad(0, 8, 8, 8))]

    def featured(self, items, intro_title):
        """One section large (picture + title + button), the others as a 2-column row."""
        items = [i for i in items if i.get("label") and i.get("url")][:3]
        if not items:
            return []
        first, rest = items[0], items[1:]
        mods = []
        if first.get("image"):
            mods.append(m_image(first["image"], 600, 400, 560, href=first["url"], alt=self._label(first),
                                padding=pad(0, 40, 16, 40)))
        mods += [m_text(wrap([para(esc(self._label(first)), 22, INK, weight="bold", lh=1.3)]), padding=pad(4, 40, 4, 40)),
                 m_button(f"Descoperă {self._label(first).lower()} →", first["url"], self.accent, "#ffffff", size=15,
                          padding=pad(8, 24, 16, 24))]
        out = [self.heading(intro_title, top=36, bottom=16), row([mods], bg=WHITE)]
        if rest:
            cols = []
            for it in rest:
                cm = []
                if it.get("image"):
                    cm.append(m_image(it["image"], 600, 400, 264, href=it["url"], alt=self._label(it),
                                      padding=pad(0, 8, 12, 8)))
                cm += [m_text(wrap([para(esc(self._label(it)), 17, INK, weight="bold", lh=1.35)]), padding=pad(4, 12, 4, 12)),
                       m_button("Descoperă →", it["url"], "transparent", self.accent, size=14, px=0, py=4, radius="0px",
                                padding=pad(0, 12, 16, 12))]
                cols.append(cm)
            out.append(row(cols, bg=WHITE, col_pad=pad(8, 24, 8, 24)))
        return out

    def benefits(self, items):
        cols = []
        for n, (title, desc) in enumerate(items[:3], 1):
            cols.append([
                m_text(wrap([para(f"0{n}", 22, self.accent, weight="bold", lh=1.2)]), padding=pad(8, 12, 4, 12),
                       color=self.accent),
                m_text(wrap([para(esc(title), 15, INK, weight="bold", lh=1.4)]), padding=pad(0, 12, 2, 12)),
                m_text(wrap([para(esc(desc), 14, MUTED, lh=1.5)]), padding=pad(0, 12, 8, 12), color=MUTED),
            ])
        return [row([[m_divider(LINE, "100%", 1, pad(24, 40, 8, 40))]], bg=WHITE),
                row(cols, bg=WHITE, col_pad=pad(8, 8, 16, 8))]

    def social_cta(self):
        socials = self.b.get("socials") or {}
        if not socials:
            return []
        mods = []
        for net, url in list(socials.items())[:4]:
            mods.append(m_button(f"{SOCIAL_NAMES.get(net, net.title())} →", url, "transparent", INK,
                                 border=f"1px solid {LINE}", size=15, px=24, py=10, weight="600",
                                 padding=pad(4, 24, 4, 24)))
        mods.insert(0, m_spacer(8))
        mods.append(m_spacer(16))
        return [row([mods], bg=WHITE)]

    def help(self):
        ct = self.b.get("contact") or {}
        bits = []
        if ct.get("phone"):
            bits.append(link(esc(ct["phone"]), ct.get("phone_href") or "tel:" + re.sub(r"[^\d+]", "", ct["phone"]),
                             INK, weight="600"))
        if ct.get("email"):
            bits.append(link(esc(ct["email"]), "mailto:" + ct["email"], INK, weight="600"))
        if not bits:
            return None
        ps = [para("Ai întrebări? Suntem aici pentru tine.", 15, MUTED, lh=1.5),
              para(" &nbsp;·&nbsp; ".join(bits), 15, INK, lh=1.6)]
        return row([[m_text(wrap(ps), padding=pad(24, 32, 32, 32), link_color=INK)]], bg=WHITE)

    # ---- footer
    def footer(self, social=True):
        mods = [m_spacer(12)]
        if social and self.b.get("socials"):
            mods.append(m_social(self.b["socials"], padding=pad(12, 24, 8, 24)))
        legal = []
        if self.L.get("terms"):
            legal.append(link("Termeni și condiții", self.L["terms"], SUBTLE))
        if self.L.get("privacy"):
            legal.append(link("Confidențialitate", self.L["privacy"], SUBTLE))
        site = re.sub(r"^https?://(www\.)?", "", self.home or "").rstrip("/")
        legal.append(link(esc(site), self.home, SUBTLE))
        ps = [para(f"© {MERGE_YEAR} {esc(self.b['name'])}. Toate drepturile rezervate.", 13, SUBTLE, lh=1.6),
              para(" &nbsp;·&nbsp; ".join(legal), 13, SUBTLE, lh=1.6),
              para("Primești acest email pentru că te-ai abonat la newsletter. "
                   + link("Dezabonare", "##NEWSMAN:list_unsubscribe##", SUBTLE) + " &nbsp;·&nbsp; "
                   + link("Vezi online", "##NEWSMAN:view_online##", SUBTLE), 12, SUBTLE, lh=1.6)]
        mods.append(m_text(wrap(ps), padding=pad(8, 32, 32, 32), color=SUBTLE, link_color=SUBTLE))
        return row([mods], bg=PAGE_BG)

    def top_gap(self):
        return row([[m_spacer(20)]], bg=PAGE_BG)

    def assemble(self, rows, social_footer=True):
        flat = [self.top_gap()]
        for r in rows:
            if r is None:
                continue
            flat.extend(r if isinstance(r, list) else [r])
        flat.append(self.footer(social_footer))
        return page(flat, self.accent)


# ====================================================================== HTML renderer

RESPONSIVE_CSS = (
    "*{box-sizing:border-box}body{margin:0;padding:0}a[x-apple-data-detectors]{color:inherit!important;"
    "text-decoration:inherit!important}p{line-height:inherit;margin:0}"
    f"@media (max-width:{WIDTH + 20}px){{.row-content{{width:100%!important}}"
    ".stack .column{width:100%!important;display:block!important}.img-full{max-width:100%!important}}"
)


def _style(d, keys=None):
    out = []
    for k, v in (d or {}).items():
        if keys and k not in keys:
            continue
        if isinstance(v, (str, int, float)) and v != "":
            out.append(f"{k}:{v}")
    return ";".join(out)


def _pads(d):
    return ";".join(f"{k}:{d[k]}" for k in ("padding-top", "padding-right", "padding-bottom", "padding-left") if k in d)


def _clean_text_html(h):
    h = re.sub(r'\sdata-mce-style="[^"]*"', "", h)
    h = re.sub(r"<code[^>]*data-bee-value=\"([^\"]*)\"[^>]*>.*?</code>", r"\1", h, flags=re.S)
    h = re.sub(r'<p style="', '<p style="margin:0;', h)
    return h


def render_module(m):
    t = m["type"].replace("mailup-bee-newsletter-modules-", "")
    d = m["descriptor"]
    st = d.get("style", {})
    p = _pads(st)
    if t == "text":
        tx = d["text"]
        s = tx.get("style", {})
        return (f'<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tr>'
                f'<td style="{p}"><div style="font-family:{FONT};color:{s.get("color", INK)};line-height:{s.get("line-height", "150%")}">'
                f'{_clean_text_html(tx["html"])}</div></td></tr></table>')
    if t == "image":
        im = d["image"]
        cs = d.get("computedStyle", {})
        w = int(float(str(cs.get("width", "600")).replace("px", "") or 600))
        src = im.get("dynamicSrc") or im["src"]
        img = (f'<img src="{esc(src)}" alt="{esc(im.get("alt"))}" title="{esc(im.get("alt"))}" width="{w}" '
               f'style="display:block;height:auto;border:0;width:100%;max-width:{w}px">')
        if im.get("href"):
            img = f'<a href="{esc(im["href"])}" target="_blank" style="text-decoration:none">{img}</a>'
        return (f'<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tr>'
                f'<td align="center" style="{p}"><div style="max-width:{w}px">{img}</div></td></tr></table>')
    if t == "button":
        b = d["button"]
        bs = b["style"]
        label = re.sub(r"</?(div|p)[^>]*>", "", b["label"])
        a_style = _style(bs, ["background-color", "color", "font-size", "font-weight", "line-height", "border-radius",
                              "border-top", "border-right", "border-bottom", "border-left", "padding-top",
                              "padding-bottom", "padding-left", "padding-right"])
        align = st.get("text-align", "center")
        return (f'<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tr>'
                f'<td align="{align}" style="{p};text-align:{align}">'
                f'<a href="{esc(b.get("href") or "#")}" target="_blank" style="display:inline-block;text-decoration:none;'
                f'font-family:{FONT};mso-border-alt:none;{a_style}">{label}</a></td></tr></table>')
    if t == "divider":
        dv = d["divider"]["style"]
        if dv.get("height"):
            return f'<div style="height:{dv["height"]};line-height:{dv["height"]};font-size:1px">&#8202;</div>'
        return (f'<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tr><td style="{p}">'
                f'<table border="0" cellpadding="0" cellspacing="0" role="presentation" width="{dv.get("width", "100%")}" align="center">'
                f'<tr><td style="font-size:1px;line-height:1px;border-top:{dv["border-top"]}">&#8202;</td></tr></table>'
                f'</td></tr></table>')
    if t == "social":
        cells = "".join(
            f'<td style="padding:0 6px"><a href="{esc(i["image"]["href"])}" target="_blank">'
            f'<img src="{esc(i["image"]["src"])}" width="32" height="32" alt="{esc(i["image"]["alt"])}" '
            f'title="{esc(i["image"]["title"])}" style="display:block;height:auto;border:0"></a></td>'
            for i in d["iconsList"]["icons"])
        return (f'<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"><tr>'
                f'<td align="center" style="{p}"><table border="0" cellpadding="0" cellspacing="0" role="presentation">'
                f'<tr>{cells}</tr></table></td></tr></table>')
    return ""


def render_html(bee, title=""):
    pg = bee["page"]
    body_bg = pg["body"]["container"]["style"].get("background-color", PAGE_BG)
    rows_html = []
    for i, r in enumerate(pg["rows"], 1):
        cs = r["content"]["style"]
        cols = r["columns"]
        total = sum(c.get("grid-columns", 12) for c in cols) or 12
        tds = []
        for c in cols:
            pct = round(100 * c.get("grid-columns", 12) / total, 4)
            inner = "".join(render_module(m) for m in c["modules"])
            tds.append(f'<td class="column" width="{pct}%" valign="top" style="vertical-align:top;{_pads(c.get("style", {}))}">'
                       f'{inner}</td>')
        radius = f'border-radius:{cs["border-radius"]};' if cs.get("border-radius") else ""
        stack = " stack" if r["content"]["computedStyle"].get("rowColStackOnMobile", True) else ""
        cont_bg = r["container"]["style"].get("background-color", "transparent")
        table = (f'<table class="row row-{i}" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" '
                 f'role="presentation" style="background-color:{cont_bg}"><tr><td>'
                 f'<table class="row-content{stack}" align="center" border="0" cellpadding="0" cellspacing="0" '
                 f'role="presentation" width="{WIDTH}" style="width:{WIDTH}px;margin:0 auto;background-color:{cs.get("background-color", WHITE)};{radius}">'
                 f'<tr>{"".join(tds)}</tr></table></td></tr></table>')
        cond = r["container"].get("displayCondition")
        if cond:
            table = cond.get("before", "") + table + cond.get("after", "")
        rows_html.append(table)
    return ('<!DOCTYPE html><html lang="ro"><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title>'
            '<!--[if mso]><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch><o:AllowPNG/>'
            '</o:OfficeDocumentSettings></xml><![endif]-->'
            f'<style>{RESPONSIVE_CSS}</style></head>'
            f'<body style="margin:0;padding:0;background-color:{body_bg};-webkit-text-size-adjust:none;text-size-adjust:none">'
            f'<table class="nl-container" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" '
            f'style="background-color:{body_bg}"><tr><td>{"".join(rows_html)}</td></tr></table></body></html>')


def render_text(html):
    h = re.sub(r"(?is)<(head|style)[^>]*>.*?</\1>", "", html)
    h = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
               lambda m: f"{re.sub(r'<[^>]+>', '', m.group(2)).strip()} [{m.group(1)}]", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</tr>", "\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    h = htmlmod.unescape(h).replace(" ", "")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in h.split("\n")]
    out, blank = [], False
    for x in lines:
        if x:
            out.append(x)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip() + "\n"
