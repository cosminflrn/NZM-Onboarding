"""Email content: per-client texts and the layouts of every email we generate."""
import base64
import copy
import json
import re
import time

from . import design as D

FORM_TYPES = ("popup", "embed")
SITE_TYPES = ("ecommerce", "non-ecommerce")
SHOP_PLATFORMS = {"shopify", "woocommerce", "gomag", "merchantpro", "prestashop", "magento", "opencart"}


# ====================================================================== switches

def site_type(brand):
    opt = (brand.get("options") or {}).get("site_type") or "auto"
    if opt in SITE_TYPES:
        return opt
    if brand.get("site_type") in SITE_TYPES:
        return brand["site_type"]
    return "ecommerce" if detect_ecommerce(brand) else "non-ecommerce"


def detect_ecommerce(brand):
    if brand.get("platform") in SHOP_PLATFORMS:
        return True
    if any(not p.get("placeholder") for p in brand.get("products") or []):
        return True
    return bool((brand.get("links") or {}).get("cart_found"))


def form_type(brand):
    opt = (brand.get("options") or {}).get("form_type") or "popup"
    return opt if opt in FORM_TYPES else "popup"


# ====================================================================== texts

def _title(label):
    label = (label or "").strip()
    return label[:1].upper() + label[1:].lower() if label.isupper() else label


def _join(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " și " + items[-1]


def clean_description(desc, name):
    """First sentence of the meta description, if it reads like a sentence."""
    d = re.sub(r"\s+", " ", (desc or "")).strip()
    if not d or len(d) < 25 or re.search(r"lorem|ipsum|just another|wordpress|default", d, re.I):
        return ""
    m = re.match(r"(.{25,220}?[.!?])(\s|$)", d)
    d = m.group(1) if m else (d[:200].rsplit(" ", 1)[0] + "…" if len(d) > 200 else d)
    return d


def default_texts(brand, ecom):
    n = brand["name"]
    menu = [m for m in (brand.get("links") or {}).get("menu") or [] if m.get("label")]
    cats = [_title(m["label"]).lower() for m in menu if not re.search(r"reducer|promo|ofert|outlet|sale", m["label"], re.I)][:3]
    desc = clean_description(brand.get("description"), n)
    if ecom:
        about = f"La {n} găsești {_join(cats)}." if cats else ""
        intro = "\n\n".join(x for x in [
            desc or about,
            "De acum ești primul care află de produsele noi, de promoțiile pentru abonați și de ofertele pe care nu vrei să le ratezi.",
        ] if x)
    else:
        intro = "\n\n".join(x for x in [
            desc,
            f"De acum ești primul care află noutățile {n}. Îți scriem doar când avem ceva cu adevărat util sau interesant pentru tine.",
        ] if x)
    return {
        "hero_eyebrow": "Bine ai venit",
        "hero_title": f"Bine ai venit în comunitatea {n}!",
        "hero_subtitle": "Îți mulțumim că te-ai abonat. Ne bucurăm să te avem alături.",
        "intro": intro,
        "cta_label": "Intră în magazin" if ecom else "Vizitează site-ul",
        "products_title": "Am ales câteva produse pentru tine",
        "cards_title": "Ce găsești la noi",
        "discount_note": "Aplică-l la finalizarea comenzii.",
        "form_title": "Abonează-te la newsletter",
        "form_subtitle": f"Fii primul care află noutățile și ofertele {n}." if ecom else f"Fii primul care află noutățile {n}.",
        "news_title": f"Descoperă {n}",
        "news_subtitle": "Am adunat câteva lucruri pe care merită să le vezi.",
        "newsletter_title": f"Noutăți de la {n}",
        "newsletter_subtitle": "Iată ce am pregătit pentru tine în perioada aceasta.",
    }


def texts_for(brand, ecom):
    t = default_texts(brand, ecom)
    for k, v in (brand.get("texts") or {}).items():
        if isinstance(v, str) and v.strip():
            t[k] = v.strip()
    return t


BENEFITS = {
    "ecommerce": [("Oferte pentru abonați", "Promoții trimise întâi pe email."),
                  ("Noutăți în avans", "Afli primul de produsele noi."),
                  ("Idei și inspirație", "Recomandări alese pentru tine.")],
    "non-ecommerce": [("Noutăți", "Afli primul ce pregătim."),
                      ("Sfaturi utile", "Informații alese cu grijă."),
                      ("Fără spam", "Îți scriem doar când contează.")],
}


# ====================================================================== emails

def kit(brand):
    ecom = site_type(brand) == "ecommerce"
    return D.Kit(brand, texts_for(brand, ecom), ecom)


def welcome_email(k):
    t, b = k.t, k.b
    code = (b.get("options") or {}).get("discount_code")
    rows = [k.header(),
            k.hero(t["hero_eyebrow"], t["hero_title"], t["hero_subtitle"]),
            k.banner(),
            k.body(t["intro"], top=36, bottom=12)]
    if code:
        rows.append(k.discount(code, t["discount_note"]))
    if k.ecom:
        rows.append(k.products((b.get("products") or [])[:3], t["products_title"]))
    rows.append(k.cta(t["cta_label"], k.home, top=20, bottom=12))
    rows.append(k.benefits(BENEFITS["ecommerce" if k.ecom else "non-ecommerce"]))
    rows.append(k.help())
    return k.assemble(rows)


def social_email(k):
    """Welcome series #2: follow us (or 'we're here to help' without socials)."""
    b = k.b
    if b.get("socials"):
        nets = [D.SOCIAL_NAMES[n] for n in b["socials"]][:3]
        rows = [k.header(nav=False),
                k.hero("Hai să rămânem în contact", "Ne găsești și pe social media",
                       f"Urmărește {b['name']} pe {D_join(nets)} pentru noutăți, culise și idei, în fiecare zi."),
                k.body("Acolo vezi primul noutățile, părerile celor care ne cunosc deja și răspunsuri rapide la întrebările tale.",
                       top=32, bottom=8),
                k.social_cta(),
                k.help()]
        return k.assemble(rows, social_footer=False), "Hai să ne vedem și pe social media 👋", "Rămâi aproape de noi."
    else:
        rows = [k.header(nav=False),
                k.hero("Suntem aici pentru tine", "Ai o întrebare? Scrie-ne!",
                       "Echipa noastră îți răspunde cu drag la orice întrebare."),
                k.help(),
                k.cta("Vizitează site-ul", k.home, top=8, bottom=36)]
        subject = f"Suntem aici dacă ai nevoie de noi"
    return k.assemble(rows), subject, "Rămâi aproape de noi."


def D_join(items):
    return _join(items)


def news_email(k):
    """Welcome series #3: explore the site (featured sections)."""
    t, b = k.t, k.b
    prods = b.get("products") or []
    rows = [k.header(),
            k.hero("Ghid rapid", t["news_title"], t["news_subtitle"])]
    if k.ecom:
        pick = prods[3:6] if len(prods) >= 6 else prods[:3]
        rows.append(k.products(pick, "Ți-ar putea plăcea"))
        target = (b.get("links") or {}).get("promo") or k.home
        rows.append(k.cta("Vezi toate noutățile", target, top=20, bottom=32))
    else:
        rows.append(k.featured((b.get("links") or {}).get("menu") or [], "Câteva locuri de unde să începi"))
        rows.append(k.cta("Vizitează site-ul", k.home, top=24, bottom=32, outline=True))
    rows.append(k.help())
    return k.assemble(rows), f"Descoperă {b['name']} ✨", "Câteva lucruri pe care merită să le vezi."


def newsletter_email(k):
    """Non-ecommerce draft: a regular newsletter, ready to be edited and sent."""
    t, b = k.t, k.b
    rows = [k.header(nav=False),
            k.hero("Newsletter", t["newsletter_title"], t["newsletter_subtitle"]),
            k.banner(),
            k.body(clean_description(b.get("description"), b["name"]) or
                   "Scrie aici câteva rânduri despre noutățile pe care vrei să le împărtășești.", top=36, bottom=8),
            k.cards((b.get("links") or {}).get("menu") or [], t["cards_title"]),
            k.cta(t["cta_label"], k.home, top=24, bottom=32),
            k.help()]
    return k.assemble(rows)


def cart_email(k, n, condition):
    """Abandoned cart #1-3. `condition` is the Newsman NZCart repeat block."""
    b = k.b
    code = (b.get("options") or {}).get("discount_code")
    cart = (b.get("links") or {}).get("cart") or k.home
    if n == 1:
        hero = ("Coșul tău", "Ai uitat ceva în coș?", "Am păstrat produsele pentru tine. Le găsești mai jos.")
        subject, pre = "Ai uitat ceva în coș? 🛒", "Produsele tale te așteaptă."
    elif n == 2 and code:
        hero = ("Un mic cadou", "Finalizează comanda cu reducere", "Ți-am pregătit un cod special pentru produsele din coș.")
        subject, pre = "Un mic cadou pentru coșul tău 🎁", "Folosește codul tău la finalizarea comenzii."
    elif n == 2:
        hero = ("Coșul tău", "Produsele tale te așteaptă", "Stocurile sunt limitate, așa că îți recomandăm să finalizezi comanda cât mai curând.")
        subject, pre = "Produsele tale te așteaptă în coș", "Stocurile sunt limitate."
    else:
        hero = ("Ultima amintire", "Coșul tău expiră curând", "Produsele sunt încă rezervate pentru tine, dar nu pentru mult timp.")
        subject, pre = "Ultima amintire: coșul tău te așteaptă", "Finalizează comanda cât produsele sunt pe stoc."
    rows = [k.header(nav=False), k.hero(*hero)]
    if n >= 2 and code:
        rows.append(k.discount(code, "Aplică-l la finalizarea comenzii."))
    rows.append(k.heading("Produsele din coșul tău", top=32, bottom=8))
    rows.append(cart_products_row(k, condition))
    rows.append(k.cta("Finalizează comanda", cart, top=24, bottom=36))
    rows.append(k.help())
    return k.assemble(rows), subject, pre


def cart_products_row(k, condition):
    img = D.m_image(D.PLACEHOLDER_IMG, 400, 300, 160, href="{{url}}", alt="{{name}}", dynamic="{{img}}",
                    padding=D.pad(8, 8, 8, 16))
    name = D.m_text(D.wrap([D.para(D.link("{{name}}", "{{url}}", D.INK, underline=False), 16, D.INK, align="left",
                                   weight="bold", lh=1.4)]), padding=D.pad(16, 16, 4, 8), link_color=D.INK)
    btn = D.m_button("Vezi produsul", "{{url}}", "transparent", D.INK, border=f"1px solid {D.LINE}", size=13,
                     px=16, py=8, weight="600", align="left", padding=D.pad(4, 16, 12, 8))
    return D.row([[img], [name, btn]], bg=D.WHITE, grid=[4, 8], col_pad=D.pad(4, 16, 4, 16), condition=condition)


# ====================================================================== workflow export helpers

def _draft_payload(draft, bee, subject, title):
    html = D.render_html(bee, title)
    js = json.dumps(bee, ensure_ascii=False, separators=(",", ":"))
    draft["params"]["json"] = js
    draft["params"]["txt_editor"] = ('<div style="display: none" id="beefree_contents_json">'
                                     + base64.b64encode(js.encode("utf-8")).decode() + "</div>")
    if "background_color" in draft["params"]:
        draft["params"]["background_color"] = D.PAGE_BG
    draft["html"] = html
    draft["text"] = D.render_text(html)
    draft["automation_subject"] = subject


def _set_actions(data, draft_id, subject, preheader, brand):
    opts = brand.get("options") or {}
    for trig in data["triggers"].values():
        for act in trig.get("actions", []) + trig.get("actions_no", []):
            if act.get("action_type") != "send_email":
                continue
            act["from_name"] = opts.get("sender_name") or brand["name"]
            if opts.get("sender_email"):
                act["from_email"] = opts["sender_email"]
            if act.get("draft_id") == draft_id:
                act["subject"] = subject
                act["preheader"] = preheader


def _find_condition(tpl):
    for d in tpl["data"]["draft_meta"]["meta"].values():
        for r in json.loads(d["params"]["json"])["page"]["rows"]:
            cond = r.get("container", {}).get("displayCondition")
            if cond and "NZCart" in json.dumps(cond):
                return cond
    return {"before": "{{#each NZCart.products}}", "after": "{{/each}}", "type": "nzcart_products",
            "label": "Listare produse din coș", "description": "Conținutul va fi repetat pentru fiecare produs din coș"}


def build_cart_automation(brand, tpl):
    doc = copy.deepcopy(tpl)
    data = doc["data"]
    k = kit(brand)
    cond = _find_condition(tpl)
    data["workflow"]["name"] = f'{brand["name"]} - Coș abandonat'
    for n, (did, draft) in enumerate(sorted(data["draft_meta"]["meta"].items(), key=lambda x: x[1]["trigger_id"]), 1):
        bee, subject, pre = cart_email(k, min(n, 3), cond)
        _draft_payload(draft, bee, subject, subject)
        _set_actions(data, did, subject, pre, brand)
    doc["exported_at"] = int(time.time())
    return doc


def build_welcome_automation(brand, tpl):
    doc = copy.deepcopy(tpl)
    data = doc["data"]
    k = kit(brand)
    data["workflow"]["name"] = f'{brand["name"]} - Bun venit'
    builders = [lambda: (welcome_email(k), f"Bine ai venit la {brand['name']}! 👋", "Ne bucurăm că ești aici."),
                lambda: social_email(k),
                lambda: news_email(k)]
    for n, (did, draft) in enumerate(sorted(data["draft_meta"]["meta"].items(), key=lambda x: x[1]["trigger_id"])):
        bee, subject, pre = builders[min(n, 2)]()
        _draft_payload(draft, bee, subject, subject)
        _set_actions(data, did, subject, pre, brand)
    doc["exported_at"] = int(time.time())
    return doc


def build_newsletter(brand, tpl):
    """Draft: welcome newsletter with products (ecommerce) or a regular newsletter (non-ecommerce)."""
    doc = copy.deepcopy(tpl)
    k = kit(brand)
    doc["data"] = welcome_email(k) if k.ecom else newsletter_email(k)
    doc["exported_at"] = int(time.time())
    return doc
