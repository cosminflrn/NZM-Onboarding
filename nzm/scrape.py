"""Extract brand data (logo, banner, colors, contact, socials, links, products) from a shop."""
import json
import random
import re
from collections import defaultdict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import colors as C
from . import images as I
from .net import Fetcher, absolute, same_site

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"^https?://(www\.|m\.|web\.)?(facebook|fb)\.(com|me)/(?!sharer|share|dialog|plugins|tr\b|tr\?|login|policy)[^?#]+", re.I),
    "instagram": re.compile(r"^https?://(www\.)?instagram\.com/(?!p/|explore|accounts|share)[^?#]+", re.I),
    "tiktok": re.compile(r"^https?://(www\.)?tiktok\.com/@[^?#]+", re.I),
    "youtube": re.compile(r"^https?://(www\.)?youtube\.com/(channel/|c/|user/|@)[^?#]+", re.I),
    "linkedin": re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/(company|in|school)/[^?#]+", re.I),
    "pinterest": re.compile(r"^https?://([a-z]{2,3}\.)?pinterest\.[a-z.]+/(?!pin/create)[^?#]+", re.I),
    "twitter": re.compile(r"^https?://(www\.)?(twitter|x)\.com/(?!intent|share|home)[^?#]+", re.I),
}

PAY_BADGE_RE = re.compile(
    r"apple.?pay|google.?pay|\bgpay|samsung.?pay|visa|master.?card|maestro|paypal|netopia|mobilpay|euplatesc|payu|"
    r"stripe|revolut|klarna|tbi|anpc|\bsal\b|\bsol\b|trustpilot|trusted|gpec|ecommerce.?europe|"
    r"fan.?courier|sameday|cargus|\bdpd\b|\bgls\b|easybox|google.?play|app.?store", re.I)
BAD_IMG_WORDS = re.compile(
    r"anpc|\bsal\b|sal-|sol-|\bsol\b|netopia|mobilpay|visa|mastercard|maestro|payu|euplatesc|stripe|paypal|gls|fan-?courier|"
    r"sameday|cargus|dpd|trusted|badge|google-?play|app-?store|ecommerce-?europe|gpec|placeholder|loader|spinner|flag|"
    r"lazy|blank|pixel|spacer|icon-|/icons?/|payment|card", re.I)

FRAMEWORK_DEFAULTS = {  # colors present on many sites that are rarely the brand
    "#007bff", "#0d6efd", "#17a2b8", "#28a745", "#198754", "#dc3545", "#ffc107", "#6c757d", "#0dcaf0",
    "#96588a", "#7f54b3", "#720eec", "#cf2e2e", "#ff6900", "#fcb900", "#7bdcb5", "#00d084", "#8ed1fc",
    "#0693e3", "#9b51e0", "#f78da7", "#abb8c3", "#2271b1", "#135e96", "#3858e9", "#1e73be", "#0073aa",
    "#4285f4", "#1877f2", "#3b5998", "#1da1f2", "#e4405f", "#25d366", "#ff0000", "#00ff00", "#0000ff",
}

PROMO_RE = re.compile(r"reducer|promo|ofert|outlet|sale\b|lichidar|black ?friday|discount|campani|clearance", re.I)
TERMS_RE = re.compile(r"termen|condi[tț]i|terms|tc\b", re.I)
PRIVACY_RE = re.compile(r"confiden[tț]ialitat|privacy|gdpr|prelucrarea datelor|protec[tț]ia datelor|cookie", re.I)
CONTACT_RE = re.compile(r"^contact|contacteaz|contact\b", re.I)
CART_HREF_RE = re.compile(r"/(cart|cos|cosul|cos-de-cumparaturi|cos-cumparaturi|basket|shopping-cart|checkout/cart|cosul-meu)(/|\?|$|\.html)", re.I)
# seasonal / dated campaign pages go stale (e.g. a "Black Friday" page from 2012)
SEASONAL_RE = re.compile(r"black.?friday|cyber.?monday|cr[aă]ciun|pa[sș]te|valentine|\b20\d\d\b", re.I)
MENU_SKIP_RE = re.compile(
    r"cont|account|login|logare|autentific|inregistr|register|cos\b|co[sș]ul|cart|wishlist|favorit|caut|search|contact|"
    r"blog|despre|about|track|urmar|retur|faq|intrebari|ajutor|help|livrare|termen|confiden|gdpr|anpc|newsletter|compar|"
    r"magazin(e)?\b|store locator|limba|lang|lei\b|ron\b|eur\b", re.I)
PRODUCT_HREF_RE = re.compile(r"/(produs|produse|product|products|p|item|shop)/[^/]+|-p\d+|/\d{3,}[-/]|-\d{3,}\.html$|\.html$|/pd/", re.I)
NOT_PRODUCT_HREF_RE = re.compile(r"categor|/collections/[^/]+/?$|/c/|/brand|/blog|/tag/|/pagina|/page/|/cont\b|/contul|/account|/cart\b|/cos\b|/checkout|/wishlist|/compare|/search|\?|#", re.I)


def soup_of(html):
    return BeautifulSoup(html or "", "html.parser")


def text_of(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def classes_chain(el, depth=4):
    """class+id strings of an element and some ancestors (lowercase)."""
    parts = []
    cur = el
    for _ in range(depth):
        if cur is None or not getattr(cur, "attrs", None) and cur.name is None:
            break
        if getattr(cur, "attrs", None):
            parts.append(" ".join(cur.get("class", []) if isinstance(cur.get("class"), list) else [str(cur.get("class", ""))]))
            parts.append(str(cur.get("id", "")))
        cur = cur.parent
    return " ".join(parts).lower()


def in_tag(el, names, depth=12):
    cur = el.parent
    for _ in range(depth):
        if cur is None:
            return False
        if cur.name in names:
            return True
        if cur.name in ("main", "body", "html"):
            return False  # page-wide classes ("has-app-install-banner-header") say nothing about the element
        cls = " ".join(cur.get("class", [])) if cur.get("class") else ""
        ident = cur.get("id", "") or ""
        for n in names:
            if re.search(rf"(^|[\s_-]){n}([\s_-]|$)", f"{cls} {ident}".lower()):
                return True
        cur = cur.parent
    return False


def best_from_srcset(srcset):
    best, best_w = None, -1
    for part in (srcset or "").split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1:
            m = re.match(r"(\d+)(w|x)", bits[1])
            if m:
                w = int(m.group(1)) * (1000 if m.group(2) == "x" else 1)
        if w > best_w:
            best, best_w = bits[0], w
    return best


def img_url(tag, base):
    for attr in ("data-src", "data-ng-src", "ng-src", "data-lazy-src", "data-original", "data-lazy", "data-srcset", "srcset", "src"):
        v = tag.get(attr)
        if not v or v.startswith("data:"):
            continue
        if "srcset" in attr or ("," in v and " " in v.strip()):
            v = best_from_srcset(v)
        u = absolute(base, v)
        if u:
            return u
    return None


# ----------------------------------------------------------------- JSON-LD

def jsonld_items(soup):
    items = []
    for s in soup.find_all("script", type=lambda t: t and "ld+json" in t):
        raw = s.string or s.get_text() or ""
        raw = re.sub(r"[\x00-\x1f]", " ", raw)
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                items.append(d)
                for k in ("@graph", "itemListElement", "mainEntity", "item"):
                    if k in d:
                        stack.append(d[k])
    return items


def ld_type(d):
    t = d.get("@type", "")
    return [x.lower() for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)]


def ld_image(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    return v if isinstance(v, str) else None


def ld_price(d):
    offers = d.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if not isinstance(offers, dict):
        return None, None
    price = offers.get("price") or offers.get("lowPrice")
    if price is None and isinstance(offers.get("priceSpecification"), dict):
        price = offers["priceSpecification"].get("price")
    if isinstance(offers.get("offers"), list) and price is None and offers["offers"]:
        price = offers["offers"][0].get("price")
    return price, offers.get("priceCurrency")


def fmt_price(price, currency=None, domain=""):
    try:
        p = float(str(price).replace(" ", "").replace(",", ".")) if not isinstance(price, (int, float)) else float(price)
    except (TypeError, ValueError):
        return str(price) if price else ""
    s = f"{p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    cur = (currency or "").upper()
    if cur in ("RON", "LEI") or (not cur and domain.endswith(".ro")):
        return f"{s} lei"
    if cur == "EUR":
        return f"{s} €"
    # other currencies: written the international way ($6.00, £12.50, 1,200.00 CHF)
    intl = f"{p:,.2f}"
    sym = {"USD": "$", "GBP": "£", "CAD": "CA$", "AUD": "A$"}.get(cur)
    return f"{sym}{intl}" if sym else f"{intl} {cur}".strip()


LEAD_SKIP_RE = re.compile(r"cookie|gdpr|termeni|confiden|copyright|©|abon|newsletter|javascript|browser|"
                          r"toate drepturile|all rights|privacy|log ?in|autentific|co[șs]ul|cart|\bpre[tț]\b.*lei", re.I)


def page_lead(soup):
    """The first real sentence(s) a section page says about itself (its intro, not menus, cookies or footers)."""
    main = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
    if not main.find("p") or len(main.get_text(" ", strip=True)) < 200:
        main = soup.body or soup
    for p in main.find_all("p"):
        if in_tag(p, ["header", "nav", "footer", "aside", "form"]):
            continue
        t = re.sub(r"\s+", " ", p.get_text(" ")).strip()
        if len(t) < 50 or LEAD_SKIP_RE.search(t) or t.count("|") > 1:
            continue
        sents = []
        for x in re.findall(r"[^.!?]+[.!?]", t) or [t]:
            # "dvs.", "etc.", "nr." end a word, not the sentence
            if sents and re.search(r"\b(dvs|dv|etc|nr|str|ex|ș\.a|sf|dl|dna|art|pag|vs|e\.g|i\.e)\.$", sents[-1], re.I):
                sents[-1] += x
            else:
                sents.append(x)
        out = ""
        for x in sents:
            if len(out) + len(x) > 170:
                break
            out += x
        out = out.strip()
        if 40 <= len(out) <= 170:
            return out
    return None


def amount(text):
    """'4.999,99 Lei' / '1,299.99' / '43.00' -> 4999.99 / 1299.99 / 43.0 (None if no number)."""
    t = re.sub(r"[^\d.,]", "", text or "")
    if not t:
        return None
    m = re.search(r"[.,](\d{2})$", t)
    whole, dec = (t[:m.start()], m.group(1)) if m else (t, "00")
    try:
        return float(re.sub(r"[.,]", "", whole) + "." + dec)
    except ValueError:
        return None


PRICE_TEXT_RE = re.compile(r"\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})?\s?(?:lei|ron|€|eur)\b|(?:€|\$|£)\s?\d+(?:[.,]\d{2})?", re.I)

# ----------------------------------------------------------------- main class

CHALLENGE_RE = re.compile(
    r"un moment,? v[ăa] rog|one moment,? please|just a moment|checking (your|if the site connection|the site connection)"
    r"|attention required|please wait while|verifying you are human|ddos protection|security check|access denied"
    r"|bot verification|enable javascript and cookies", re.I)


def is_challenge(soup):
    """Anti-bot interstitials (Cloudflare, Imunify360, Sucuri, SiteGround…): a title like 'One moment, please'
    and almost no real content."""
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")
    text = " ".join(soup.get_text(" ").split())
    if CHALLENGE_RE.search(title):
        return True
    return len(text) < 600 and bool(CHALLENGE_RE.search(text)) and len(soup.find_all("a", href=True)) < 5


class Scraper:
    def __init__(self, url, out_dir, public_base="", seed=None, fetcher=None, hints=None):
        if not re.match(r"^https?://", url):
            url = "https://" + url
        self.start_url = url
        self.hints = hints or {}   # brand data from NewsMAN Brandfetch: preferred over what the page suggests
        self.f = fetcher or Fetcher()
        self.assets = I.AssetStore(out_dir, public_base)
        self.warnings = []
        self.seed = seed

    # -- helpers
    def page(self, url):
        final, html, ctype = self.f.get(url)
        if not html or ("html" not in (ctype or "") and "<html" not in html[:2000].lower()):
            return final, None
        return final, soup_of(html)

    def image(self, url):
        if not url:
            return None, None
        if url.startswith("inline-svg:"):
            return I.load(url[len("inline-svg:"):].encode("utf-8"), "image/svg+xml")
        _, data, ctype = self.f.get(url, binary=True)
        im, fmt = I.load(data, ctype)
        if im is None and url.startswith("http") and "wsrv.nl" not in url:
            # the site refuses GitHub's servers: the same picture through the public image service
            from urllib.parse import quote
            _, data, ctype = self.f.get("https://wsrv.nl/?url=" + quote(url, safe=""), binary=True)
            im, fmt = I.load(data, ctype)
        return im, fmt

    # -- run
    def run(self):
        final, soup = self.page(self.start_url)
        if soup is None:
            if any(x.split(" ")[0] in ("401", "403", "406", "429", "503") for x in self.f.log):
                raise RuntimeError(f"{self.start_url} nu permite citirea automată de pe serverele GitHub "
                                   "(răspuns 403 de la firewall-ul site-ului).")
            raise RuntimeError(f"Nu am putut deschide {self.start_url} ({'; '.join(self.f.log[-3:])})")
        if is_challenge(soup):
            # the site answered with an anti-bot "please wait" page instead of itself: never build a client from it
            raise RuntimeError(f"{self.start_url} a răspuns cu o pagină anti-bot („un moment, vă rog”) în loc de site. "
                               "Folosește „Preia din browser”.")
        p = urlparse(final)
        self.base = f"{p.scheme}://{p.netloc}/"
        # relative links/images resolve against the page itself (or its <base href>), not the domain root:
        # sites living in a sub-folder (e.g. /p/ro/) would otherwise lose logo, links and pictures
        base_tag = soup.find("base", href=True)
        self.ref = urljoin(final, base_tag["href"]) if base_tag else final
        self.home = final.split("#")[0].split("?")[0]
        self.domain = p.netloc.lower().removeprefix("www.")
        self.html = str(soup)
        self.soup = soup
        self.rng = random.Random(self.seed if self.seed is not None else self.domain)
        self.ld = jsonld_items(soup)
        self.platform = self.detect_platform()

        brand = {
            "url": self.home,
            "domain": self.domain,
            "slug": re.sub(r"[^a-z0-9]+", "-", self.domain).strip("-"),
            "platform": self.platform,
        }
        brand["name"] = self.site_name()
        brand["description"] = self.description()
        links = self.links()
        contact = self.contact(links)
        brand["contact"] = contact
        brand["socials"] = self.socials()
        brand["links"] = links
        logo, logo_colors = self.logo()
        brand["logo"] = logo
        brand["banner"] = self.banner(logo)
        self.banner_src = (brand["banner"] or {}).get("source_url")
        brand["colors"] = self.colors(logo_colors)
        self.apply_hints(brand)
        brand["products"] = self.products(6)
        brand["options"] = {"discount_code": "", "sender_email": contact.get("email") or "", "sender_name": brand["name"],
                            "form_type": "popup", "site_type": "auto"}
        from .emails import detect_ecommerce
        page_text = " ".join(self.soup.get_text(" ").split())
        brand["shop_signals"] = {
            "prices": len(PRICE_TEXT_RE.findall(page_text)),
            "add_to_cart": len(re.findall(r"adaug[ăa] [îi]n co[șs]|add to (cart|bag|basket)|cump[ăa]r[ăa] acum|buy now", page_text, re.I)),
        }
        brand["site_type"] = "ecommerce" if detect_ecommerce(brand) else "non-ecommerce"
        brand["lang_detected"] = self.detect_lang()
        if brand["site_type"] == "non-ecommerce" and getattr(self, "regular_menu", None):
            links["menu"] = self.regular_menu  # a presentation site: its sections, not a "discounts" shortcut
        self.section_images(links.get("menu") or [], logo)
        if brand["site_type"] == "ecommerce" and not brand["products"]:
            self.warnings.append("Produse: nu am găsit produse pe site; în emailuri rămân produse placeholder.")
        brand["warnings"] = self.warnings
        brand["fetch_log"] = self.f.log[-20:]
        return brand

    def apply_hints(self, brand):
        """NewsMAN Brandfetch results win over our own guesses for identity (name, colours, banner, links)."""
        h = self.hints
        if not h:
            return
        # a page title ("Website sitebuilder") is not a brand name: take it only when it names the domain
        root = re.sub(r"[^a-z0-9]", "", self.domain.split(".")[0])
        name = re.split(r"\s+[-–—|:·]\s+", h.get("name") or "")[0].strip()   # "eMAG.ro - Căutarea…" -> "eMAG.ro"
        if name and root and root in re.sub(r"[^a-z0-9]", "", name.lower()):
            brand["name"] = name
        if h.get("description"):
            # an English description in a Romanian email reads wrong: only when its language matches the site's
            d = h["description"]
            english = re.search(r"\b(the|and|your|with|our|you)\b", d, re.I) and not re.search("[ăâîșțşţ]", d, re.I)
            if bool(english) == (self.detect_lang() == "en"):
                brand["description"] = d
            elif brand.get("description") == d:
                brand["description"] = None
        if h.get("accent"):
            pal = C.palette(h["accent"], h.get("dark"))
            brand["colors"].update(pal)
        for key in ("privacy", "terms", "contact"):
            if h.get(key):
                brand["links"][key] = h[key]
        for net, u in (h.get("socials") or {}).items():
            if u:
                brand["socials"][net] = u
        # a banner is a wide picture, not a sidebar widget or a pop-up graphic
        if h.get("banner") and not re.search(r"widget|subscribe|newsletter|popup|pop-up|sidebar|side-|icon|badge|logo",
                                             h["banner"], re.I):
            im, _ = self.image(h["banner"])
            if im is not None and im.width >= 500 and im.width >= im.height * 1.6:
                brand["banner"] = {"url": h["banner"], "source_url": h["banner"], "width": im.width, "height": im.height}
                self.banner_src = h["banner"]
                self.warnings = [w for w in self.warnings if not w.startswith("Banner:")]
        self.warnings.insert(0, "Brand preluat din brand fetch NewsMAN (logo, culori, banner, linkuri); produsele și meniul din site.")

    # -- platform
    def detect_lang(self):
        """Romanian or English for the emails: the page's declared language first, then its words."""
        soup = self.soup
        html_tag = soup.find("html")
        declared = ((html_tag.get("lang") if html_tag else "") or "").strip().lower()[:2]
        if not declared:
            m = soup.find("meta", property="og:locale") or soup.find("meta", attrs={"http-equiv": re.compile("content-language", re.I)})
            declared = ((m.get("content") if m else "") or "").strip().lower()[:2]
        text = " ".join(soup.get_text(" ").split()).lower()[:20000]
        ro = len(re.findall(r"[ăâîșțşţ]", text)) + 3 * len(re.findall(r"\b(și|pentru|este|sunt|despre|acasă|coș|produse|livrare|contul)\b", text))
        en = 3 * len(re.findall(r"\b(the|and|for|with|your|our|you|about|home|cart|shipping|account)\b", text))
        if declared == "ro" or (not declared and ro >= en):
            return "ro"
        if declared == "en":
            # a Romanian site with a careless template lang="en" still reads Romanian
            return "ro" if ro > 2 * en and ro > 30 else "en"
        return "en" if declared or en > ro else "ro"  # any other language: English is the safer choice

    def detect_platform(self):
        h = self.html.lower()
        if "cdn.shopify.com" in h or "shopify.theme" in h:
            return "shopify"
        if "woocommerce" in h or "wp-content/plugins/woocommerce" in h:
            return "woocommerce"
        if "gomag" in h:
            return "gomag"
        if "merchantpro" in h:
            return "merchantpro"
        if "prestashop" in h:
            return "prestashop"
        if re.search(r"magento|/static/(version\d+/)?frontend/|[\"'/]mage/(cookies|requirejs|apply)|mage-init", h):
            return "magento"
        if "route=product" in h or "catalog/view/theme" in h:
            return "opencart"
        if "wp-content" in h:
            return "wordpress"
        return "necunoscut"

    # -- name
    def site_name(self):
        m = self.soup.find("meta", property="og:site_name")
        if m and m.get("content", "").strip():
            return m["content"].strip()
        for d in self.ld:
            if set(ld_type(d)) & {"organization", "store", "onlinestore", "website", "localbusiness"} and isinstance(d.get("name"), str):
                return d["name"].strip()
        title = text_of(self.soup.title)
        if title:
            parts = [x.strip() for x in re.split(r"\s[|\-–—:]\s", title) if x.strip()]
            if parts:
                short = min(parts, key=len)
                if len(short) <= 40:
                    return short
        return self.domain.split(".")[0].capitalize()

    # -- description
    def description(self):
        for attrs in ({"name": "description"}, {"property": "og:description"}):
            m = self.soup.find("meta", attrs=attrs)
            if m and (m.get("content") or "").strip():
                return re.sub(r"\s+", " ", m["content"]).strip()
        for d in self.ld:
            if isinstance(d.get("description"), str) and set(ld_type(d)) & {"organization", "store", "website", "localbusiness"}:
                return d["description"].strip()
        return ""

    # -- links
    def all_links(self, soup=None):
        soup = soup or self.soup
        out = []
        for a in soup.find_all("a", href=True):
            out.append((a, a["href"].strip(), text_of(a)))
        return out

    def links(self):
        res = {"home": self.home, "cart": None, "terms": None, "privacy": None, "contact": None, "promo": None, "menu": []}
        for a, href, txt in self.all_links():
            u = absolute(self.ref, href)
            if not u or not same_site(u, self.base):
                continue
            label = (txt or a.get("title") or "").strip()
            if not res["cart"] and CART_HREF_RE.search(urlparse(u).path + ("?" + urlparse(u).query if urlparse(u).query else "")):
                res["cart"] = u
            if not res["terms"] and TERMS_RE.search(label) and not PRIVACY_RE.search(label):
                res["terms"] = u
            if not res["privacy"] and PRIVACY_RE.search(label) and "cookie" not in label.lower():
                res["privacy"] = u
            if not res["contact"] and (CONTACT_RE.search(label) or re.search(r"/contact", u, re.I)):
                res["contact"] = u
            if not res["promo"] and PROMO_RE.search(label) and len(label) < 40 and not SEASONAL_RE.search(label + " " + u):
                res["promo"] = u
        res["cart_found"] = bool(res["cart"])
        if not res["cart"]:
            res["cart"] = {
                "shopify": urljoin(self.base, "/cart"),
                "woocommerce": urljoin(self.base, "/cos/") if self.domain.endswith(".ro") else urljoin(self.base, "/cart/"),
                "gomag": urljoin(self.base, "/cos-de-cumparaturi"),
                "opencart": urljoin(self.base, "/index.php?route=checkout/cart"),
                "magento": urljoin(self.base, "/checkout/cart/"),
                "prestashop": urljoin(self.base, "/cos?action=show") if self.domain.endswith(".ro") else urljoin(self.base, "/cart?action=show"),
            }.get(self.platform, self.base)
            if self.platform in ("shopify", "woocommerce", "gomag", "opencart", "magento", "prestashop"):
                self.warnings.append("Link coș: nu l-am găsit explicit pe site, am folosit adresa standard a platformei — verifică-l.")
        if not res["privacy"]:
            for a, href, txt in self.all_links():
                u = absolute(self.ref, href)
                if u and same_site(u, self.base) and PRIVACY_RE.search(txt or ""):
                    res["privacy"] = u
                    break
        res["menu"] = self.menu(res.get("promo"))
        return res

    def menu(self, promo):
        containers = []
        for sel in ["header nav", "nav", "header", "[class*=menu]", "[id*=menu]", "[class*=nav]"]:
            containers.extend(self.soup.select(sel))
        seen, items = set(), []
        for cont in containers:
            if in_tag(cont, ["footer"]):
                continue
            for a in cont.find_all("a", href=True):
                label = re.sub(r"^[\s→›»>\-–•·|]+|[\s→›»>\-–•·|]+$", "", text_of(a))
                u = absolute(self.ref, a["href"])
                if not u or not same_site(u, self.base) or urlparse(u).path in ("", "/"):
                    continue
                if urlparse(u).path.rstrip("/") == urlparse(self.home).path.rstrip("/"):
                    continue  # the home page itself (site living in a sub-folder)
                if not (2 <= len(label) <= 28) or MENU_SKIP_RE.search(label) or re.fullmatch(r"[\d\s.,]+", label):
                    continue
                if "_" in label or re.search(r"^(acas[aă]|home|prima pagin[aă]|start)$", label, re.I):
                    continue  # internal page names ("ACASĂ_SSL") and links back home
                if SEASONAL_RE.search(label + " " + u):
                    continue  # seasonal / dated campaign pages go stale (e.g. a Black Friday page from 2012)
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append({"label": label.upper(), "url": u})
            if len(items) >= 3:
                break
        promo_item = None
        if promo:
            promo_item = next((i for i in items if i["url"] == promo), None)
            if not promo_item:
                promo_item = {"label": "REDUCERI", "url": promo}
                for a, href, txt in self.all_links():
                    if absolute(self.ref, href) == promo and txt and len(txt) <= 28:
                        promo_item["label"] = txt.upper()
                        break
        self.regular_menu = [i for i in items if i is not promo_item][:3]
        regular = self.regular_menu[: (2 if promo_item else 3)]
        result = regular + ([promo_item] if promo_item else [])
        if not result:
            self.warnings.append("Meniu: nu am găsit linkuri de meniu; am pus doar HOME.")
        return result

    # -- contact
    def contact(self, links):
        res = {"phone": None, "phone_href": None, "email": None}
        pages = [self.soup]
        if links.get("contact"):
            _, cs = self.page(links["contact"])
            if cs is not None:
                pages.append(cs)
        for soup in pages:
            for a in soup.find_all("a", href=True):
                h = a["href"].strip()
                if not res["phone"] and h.lower().startswith("tel:"):
                    num = re.sub(r"[^\d+]", "", h[4:])
                    if len(re.sub(r"\D", "", num)) >= 9:
                        txt = text_of(a)
                        m_num = re.search(r"\+?[\d][\d\s.\-()]{7,}\d", txt)
                        same = m_num and re.sub(r"\D", "", m_num.group(0)) == re.sub(r"\D", "", num)
                        res["phone"] = m_num.group(0).strip() if same else num
                        res["phone_href"] = "tel:" + num
                if not res["email"] and h.lower().startswith("mailto:"):
                    em = h[7:].split("?")[0].strip()
                    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", em, re.I):
                        res["email"] = em
            if res["phone"] and res["email"]:
                break
        if not res["phone"] or not res["email"]:
            for soup in pages:
                txt = text_of(soup.body or soup)
                if not res["phone"]:
                    m = re.search(r"(?<!\d)(?:\+?40[\s.]?|0)(?:7\d{2}|[23]\d{2})[\s.\-]?\d{3}[\s.\-]?\d{3}(?!\d)", txt)
                    if m:
                        res["phone"] = m.group(0).strip()
                        res["phone_href"] = "tel:" + re.sub(r"[^\d+]", "", m.group(0))
                if not res["email"]:
                    for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", txt):
                        em = m.group(0)
                        if not re.search(r"example|sentry|wixpress|\.(png|jpg|webp|gif|svg)$|@\dx", em, re.I):
                            res["email"] = em
                            break
        if not res["phone"]:
            self.warnings.append("Telefon: nu am găsit niciun număr pe site.")
        if not res["email"]:
            self.warnings.append("Email: nu am găsit nicio adresă de contact pe site.")
        return res

    # -- socials
    def socials(self):
        found = {}
        links = self.all_links()
        # prefer links in footer/header, then anywhere
        links.sort(key=lambda t: 0 if in_tag(t[0], ["footer", "header"]) else 1)
        for a, href, _ in links:
            href = href.split("?")[0].rstrip("/")
            for net, pat in SOCIAL_PATTERNS.items():
                if net not in found and pat.match(href):
                    found[net] = href
        for d in self.ld:
            for s in d.get("sameAs", []) if isinstance(d.get("sameAs"), list) else []:
                for net, pat in SOCIAL_PATTERNS.items():
                    if net not in found and isinstance(s, str) and pat.match(s):
                        found[net] = s.rstrip("/")
        if not found:
            self.warnings.append("Social media: nu am găsit niciun profil.")
        order = ["facebook", "instagram", "tiktok", "youtube", "linkedin", "pinterest", "twitter"]
        return {k: found[k] for k in order if k in found}

    # -- logo
    def logo_candidates(self):
        cands = []
        for d in self.ld:
            if set(ld_type(d)) & {"organization", "store", "onlinestore", "localbusiness", "brand"}:
                u = ld_image(d.get("logo"))
                if u:
                    cands.append((70, absolute(self.ref, u), "json-ld"))
        imgs = self.soup.find_all("img")
        total = max(1, len(imgs))
        for idx, img in enumerate(imgs):
            u = img_url(img, self.ref)
            if not u:
                continue
            chain = classes_chain(img, 4) + " " + (img.get("alt") or "").lower() + " " + u.lower().split("/")[-1]
            score = 0
            if "logo" in chain:
                score = 60
            elif img.find_parent(class_=re.compile(r"navbar-brand|site-branding|brand", re.I)):
                score = 50
            elif img.find_parent("a", href=re.compile(r"^(/|%s/?)$" % re.escape(self.base.rstrip("/")))) and in_tag(img, ["header"]):
                score = 50
            if not score:
                continue
            if in_tag(img, ["header"]):
                score += 15
            # the brand mark links home and is named after the site ("eMAG" on emag.ro): beats other logos nearby
            home = img.find_parent("a", href=re.compile(r"^(/|%s/?)$" % re.escape(self.base.rstrip("/"))))
            root = re.sub(r"[^a-z0-9]", "", self.domain.split(".")[0])
            if home is not None:
                score += 20
            if root and root in re.sub(r"[^a-z0-9]", "", (img.get("alt") or "").lower()):
                score += 10
            if idx < total * 0.25:
                score += 10
            if in_tag(img, ["footer"]):
                score -= 30
            if BAD_IMG_WORDS.search(u) or re.search(r"partener|partner|brands?/", u, re.I):
                score -= 40
            if PAY_BADGE_RE.search(chain + " " + u):
                continue  # Apple Pay, Visa, ANPC… sit in "payment-logos" blocks but are never the brand
            if re.search(r"logos\b", chain) and not re.search(r"(?<![a-z])logo(?!s)", chain):
                score -= 30  # "partner-logos", "payment-logos": a strip of other brands' logos
            cands.append((score, u, "img"))
        for svg in self.soup.find_all("svg"):
            chain = classes_chain(svg, 4)
            if "logo" in chain and len(str(svg)) > 120:
                score = 55 + (15 if in_tag(svg, ["header"]) else 0) - (30 if in_tag(svg, ["footer"]) else 0)
                markup = str(svg)
                if "xmlns" not in markup[:200]:
                    markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
                cands.append((score, "inline-svg:" + markup, "inline-svg"))
        for el in self.soup.find_all(attrs={"data-nzm-logo": True}):  # logo drawn from a style sheet (seen by the browser)
            cands.append((80, absolute(self.ref, el["data-nzm-logo"]), "css-bg"))
        og = self.soup.find("meta", property="og:image")
        if og and "logo" in (og.get("content") or "").lower():
            cands.append((40, absolute(self.ref, og["content"]), "og:image"))
        for rel in ("apple-touch-icon", "icon"):
            for l in self.soup.find_all("link", rel=lambda r: r and rel in (r if isinstance(r, list) else [r])):
                cands.append((10, absolute(self.ref, l.get("href")), rel))
        cands = [c for c in cands if c[1]]
        cands.sort(key=lambda c: -c[0])
        return cands

    def logo(self):
        tried = set()
        hinted = [(999, u, "brandfetch") for u in self.hints.get("logos") or []]
        for score, url, src in hinted + list(self.logo_candidates()):
            if url in tried:
                continue
            tried.add(url)
            im, fmt = self.image(url)
            if im is None or im.width < 40:
                continue
            orig_size = im.size
            im = I.trim_transparent(im)
            dom = I.dominant_colors(im)
            # white logos (made for dark headers) are invisible on white emails
            light_logo = not dom or all(C.luminance(c) > 0.7 for c, _ in dom[:2])
            recolored = False
            light_parts = False
            if not light_logo and im.mode in ("RGBA", "LA", "P"):
                # transparent logo with white text next to coloured parts: needs a dark header to stay readable
                px = [p for p in im.convert("RGBA").resize((80, max(1, int(80 * im.height / im.width)))).getdata() if p[3] > 200]
                light_parts = bool(px) and sum(1 for r, g, b, a in px if r > 225 and g > 225 and b > 225) > 0.2 * len(px)
            if light_logo and im.mode in ("RGBA", "LA", "P"):
                # white logo made for a dark header: paint it dark so it shows on white emails
                rgba = im.convert("RGBA")
                dark = I.Image.new("RGBA", rgba.size, (34, 34, 34, 255))
                dark.putalpha(rgba.split()[-1])
                im = dark
                recolored = True
                self.warnings.append("Logo: logo-ul de pe site e alb; l-am colorat închis ca să se vadă pe fundal alb — verifică.")
            elif light_logo:
                self.warnings.append(f"Logo: logo-ul găsit ({url[:80]}) pare alb; verifică dacă se vede pe fundal alb.")
            # email-safe: keep original if PNG/JPG/GIF and not SVG, otherwise host a PNG
            if fmt in I.EMAIL_SAFE and not recolored and not url.startswith("inline-svg:") and im.size == orig_size:
                public = url
            else:
                im2 = im.copy()
                if im2.width > 600:
                    im2.thumbnail((600, 600))
                public = self.assets.save(im2, "logo", "PNG")
            w, h = im.size
            disp_w = min(200, w, int(round(70 * w / h)) if h else 200)
            disp_w = max(disp_w, min(120, w))
            return ({"url": public, "source_url": url if not url.startswith("inline-svg:") else "inline-svg",
                     "width": w, "height": h, "display_width": disp_w, "found_by": src, "recolored": recolored, "light_parts": light_parts},
                    dom)
        self.warnings.append("Logo: nu am găsit logo-ul — am păstrat placeholderul din template.")
        return None, []

    # -- pictures
    def page_images(self, soup, base):
        """Candidate content pictures of a page, best first (og:image, <img>, lazy-load attributes, CSS urls)."""
        cands = []
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            cands.append(absolute(base, og["content"]))
        main = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
        if main is not soup.body and not main.find("img") and len(main.get_text(" ", strip=True)) < 300:
            main = soup.body or soup  # an empty <main> (content built around it): look at the whole page
        for el in main.find_all(True):
            if el.name in ("header", "footer", "nav") or in_tag(el, ["header", "footer", "nav"], depth=6):
                continue
            if el.name == "img":
                u = img_url(el, base)
                if u:
                    cands.append(u)
            for attr in ("data-bg", "data-background", "data-bg-image", "data-background-image", "data-lazy-background"):
                if el.get(attr):
                    cands.append(absolute(base, el[attr].strip()))
            st = el.get("style") or ""
            for m in re.finditer(r"url\(['\"]?([^'\")]+)", st):
                cands.append(absolute(base, m.group(1)))
        out, seen = [], set()
        for u in cands:
            if not u or u in seen or not re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", u, re.I):
                continue
            seen.add(u)
            if BAD_IMG_WORDS.search(u) or re.search(r"logo|favicon|icon|avatar", u, re.I):
                continue
            # WordPress-style sized copies ("-768x512.jpg"): big ones are fine, small thumbnails are skipped
            size = re.search(r"-(\d{2,4})x(\d{2,4})\.[a-z]+(\?|$)", u, re.I)
            if size and int(size.group(1)) < 500:
                continue
            out.append(u)
        return out

    def good_image(self, u, min_w=300, min_h=180):
        """A real photo: big enough, sane ratio, not a logo/icon (transparent or few-colour graphics)."""
        if re.search(r"booking|tripadvisor|google|facebook|instagram|whatsapp|badge|award|sigla|brand", u, re.I):
            return False
        im, fmt = self.image(u)
        if im is None or im.width < min_w or im.height < min_h or not (0.5 <= im.width / im.height <= 3.5):
            return False
        small = im.convert("RGBA")
        small.thumbnail((64, 64))
        px = list(small.getdata())
        if sum(1 for p in px if p[3] < 200) > len(px) * 0.05:
            return False  # cut-out graphic / logo
        if len({(r // 16, g // 16, b // 16) for r, g, b, a in px}) < 40:
            return False  # flat graphic, not a photo
        return True

    # -- one picture per menu section (used by non-ecommerce emails)
    def section_images(self, menu, logo):
        used = {(self.banner_src or "")}
        pool = None
        for item in menu[:3]:
            final, soup = self.page(item["url"])
            cands = self.page_images(soup, final)[:12] if soup is not None else []
            pick = next((u for u in cands if u not in used and self.good_image(u)), None)
            item["image_from"] = "page" if pick else "home"
            if soup is not None:
                m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
                d = re.sub(r"\s+", " ", (m.get("content") if m else "") or "").strip()
                sent = re.match(r"(.{20,150}?[.!?])(\s|$)", d)
                if sent:
                    item["desc"] = sent.group(1)
                lead = page_lead(soup)
                if lead:
                    item["lead"] = lead
            if not pick:
                # pictures loaded by JavaScript are invisible to us: borrow one from the homepage
                if pool is None:
                    pool = [u for u in self.page_images(self.soup, self.ref)[:20] if self.good_image(u, 500, 300)]
                pick = next((u for u in pool if u not in used), None)
            if pick:
                used.add(pick)
                item["image"] = pick
                im, _ = self.image(pick)   # its size decides how it is cropped later (portraits keep their top)
                if im is not None:
                    item["img_w"], item["img_h"] = im.size

    # -- banner
    def banner(self, logo):
        cands = []
        hero_re = re.compile(r"slide|slider|swiper|carousel|hero|banner|owl|slick|revslider|masthead|jumbotron|cover", re.I)
        order = 0
        for img in self.soup.find_all("img"):
            order += 1
            if in_tag(img, ["footer"]):
                continue
            chain = classes_chain(img, 6)
            if not hero_re.search(chain):
                continue
            u = img_url(img, self.ref)
            if u and not BAD_IMG_WORDS.search(u) and "logo" not in u.lower():
                cands.append((60 - min(order, 40) * 0.5, u))
        for pic in self.soup.find_all("source", srcset=True):
            if hero_re.search(classes_chain(pic, 6)):
                u = absolute(self.ref, best_from_srcset(pic["srcset"]))
                if u:
                    cands.append((58, u))
        # pictures set as backgrounds (inline or measured in the browser): the first slider on the page wins
        bg_order = 0
        for el in self.soup.find_all(lambda t: t.has_attr("data-bg") or re.search(
                r"background(-image)?\s*:[^;]*url\(", t.get("style") or "", re.I)):
            if not hero_re.search(classes_chain(el, 4)):
                continue
            bg_order += 1
            m = re.search(r"url\(['\"]?([^'\")]+)", el.get("style") or "")
            u = el.get("data-bg") or (m.group(1) if m else None)
            if u:
                cands.append((57 - min(bg_order, 40) * 0.2, absolute(self.ref, u)))
        og = self.soup.find("meta", property="og:image")
        if og and og.get("content") and "logo" not in og["content"].lower():
            cands.append((40, absolute(self.ref, og["content"])))
        for i, u in enumerate(self.page_images(self.soup, self.ref)[:6]):
            cands.append((30 - i, u))
        cands.sort(key=lambda c: -c[0])
        seen = set()
        for _, u in cands:
            if not u or u in seen or (logo and u == logo.get("source_url")):
                continue
            seen.add(u)
            if len(seen) > 8:
                break
            im, fmt = self.image(u)
            if im is None or im.width < 500:
                continue
            ratio = im.width / max(1, im.height)
            if ratio < 0.9 or ratio > 5:
                continue
            if fmt in I.EMAIL_SAFE:
                public = u
            else:
                im2 = im.convert("RGB")
                if im2.width > 1300:
                    im2.thumbnail((1300, 1300))
                public = self.assets.save(im2, "banner", "JPEG")
            return {"url": public, "source_url": u, "width": im.width, "height": im.height}
        self.warnings.append("Banner: nu am găsit un banner potrivit pe site — emailurile au doar blocul colorat de sus.")
        return None

    # -- colors
    def stylesheets(self):
        css = []
        for st in self.soup.find_all("style"):
            css.append(st.get_text())
        links = []
        for l in self.soup.find_all("link", href=True):
            rel = l.get("rel") or []
            rel = rel if isinstance(rel, list) else [rel]
            if "stylesheet" in [r.lower() for r in rel] or (l.get("as") == "style"):
                u = absolute(self.ref, l["href"])
                if u and not re.search(r"fonts\.googleapis|font-awesome|fontawesome|icons?\.css|jquery-ui|swiper|slick|owl\.|animate|aos\.css", u, re.I):
                    links.append(u)
        # site stylesheets first
        links.sort(key=lambda u: (0 if same_site(u, self.base) else 1, 1 if re.search(r"plugin|vendor|lib|bootstrap|wp-includes|block-library", u) else 0))
        for u in links[:8]:
            _, text, _ = self.f.get(u)
            if text and len(text) < 3_000_000:
                css.append(text)
        inline = " ".join(el.get("style", "") for el in self.soup.find_all(style=True))
        css.append(inline)
        return css

    def colors(self, logo_colors):
        scores = defaultdict(float)
        darks = defaultdict(float)
        seen_on_screen = self.soup.find("meta", attrs={"name": "nzm-colors"})  # colours measured in the browser
        if seen_on_screen:
            for i, part in enumerate((seen_on_screen.get("content") or "").split(",")):
                h = C.norm_hex(part.split(":")[0])
                if h:
                    # measured on the real page: worth more than anything guessed from style sheets
                    scores[h] += (40, 14, 8)[i] if i < 3 else 4
        meta = self.soup.find("meta", attrs={"name": "theme-color"})
        if meta and C.norm_hex(meta.get("content")):
            scores[C.norm_hex(meta["content"])] += 8
        tile = self.soup.find("meta", attrs={"name": "msapplication-TileColor"})
        if tile and C.norm_hex(tile.get("content")):
            scores[C.norm_hex(tile["content"])] += 3
        for css in self.stylesheets():
            for m in re.finditer(r"--([\w-]+)\s*:\s*([^;}{]+)", css):
                name, val = m.group(1).lower(), m.group(2)
                if name.startswith("wp--preset"):
                    continue
                if re.search(r"primary|brand|accent|main|theme|secondary|highlight|button|btn|link", name):
                    for c in C.find_colors(val):
                        scores[c] += 5 if "secondary" not in name else 2
            for m in re.finditer(r"([^{}]{1,400})\{([^{}]{1,3000})\}", css):
                sel, body = m.group(1).lower(), m.group(2)
                bgs = re.findall(r"background(?:-color)?\s*:\s*([^;]+)", body)
                fg = re.findall(r"(?<![-\w])color\s*:\s*([^;]+)", body)
                if re.search(r"btn|button|add.?to.?cart|addtocart|cta|primary|buy|checkout|badge|label-sale|onsale|price|promo|discount", sel):
                    for v in bgs:
                        for c in C.find_colors(v):
                            scores[c] += 4
                    for v in fg:
                        for c in C.find_colors(v):
                            scores[c] += 1.5
                if re.search(r"header|footer|top-?bar|navbar|nav\b|menu", sel):
                    for v in bgs:
                        for c in C.find_colors(v):
                            if C.is_dark(c):
                                darks[c] += 3
                            else:
                                scores[c] += 1.5
                if re.search(r"(^|,|\s)(body|html|h1|h2|h3|p)(\s|,|$|:)", sel):
                    for v in fg:
                        for c in C.find_colors(v):
                            if C.is_dark(c):
                                darks[c] += 2
            for c in C.find_colors(css):
                scores[c] += 0.15
        total_logo = sum(n for _, n in logo_colors) or 1
        for c, n in logo_colors:
            if C.is_brandish(c):
                scores[c] += 14 * n / total_logo + 4
            elif C.is_dark(c):
                darks[c] += 4 * n / total_logo
        # merge similar colors, keep brandish ones
        merged = []
        for c, s in sorted(scores.items(), key=lambda x: -x[1]):
            if not C.is_brandish(c):
                continue
            if c in FRAMEWORK_DEFAULTS:
                s *= 0.3
            for item in merged:
                if C.similar(item[0], c, 36):
                    item[1] += s
                    break
            else:
                merged.append([c, s])
        # boost colors present in the logo
        for item in merged:
            if any(C.similar(item[0], lc, 50) for lc, _ in logo_colors):
                item[1] *= 1.5
        merged.sort(key=lambda x: -x[1])
        accent = merged[0][0] if merged else None
        if not accent:
            self.warnings.append("Culori: nu am găsit o culoare de brand clară — am folosit o culoare implicită; verifică.")
        dark = max(darks.items(), key=lambda x: x[1])[0] if darks else None
        pal = C.palette(accent, dark)
        pal["candidates"] = [c for c, _ in merged[:6]]
        pal["logo_colors"] = [c for c, _ in logo_colors]
        return pal

    # -- products
    def products(self, want=3):
        found = []
        try:
            if self.platform == "shopify":
                found = self.products_shopify()
            elif self.platform in ("woocommerce", "wordpress"):
                found = self.products_woo()
        except Exception as e:  # never fail the whole run because of products
            self.f.log.append(f"products api error: {e}")
        if len(found) < want:
            found += self.products_generic(want * 3)
        uniq, seen = [], set()
        for p in found:
            if p.get("name") and p.get("image") and p.get("url") and p["url"] not in seen:
                seen.add(p["url"])
                uniq.append(p)
        self.rng.shuffle(uniq)
        out = []
        for p in uniq:
            im, fmt = self.image(p["image"])
            if im is None or im.width < 150:
                continue
            p["source_image"] = p["image"]
            ratio = im.width / max(1, im.height)
            # keep the shop's own image when an email client can show it as is;
            # only convert/square (and host) WebP/AVIF or very tall/wide images
            if not (fmt in ("JPEG", "PNG") and 0.8 <= ratio <= 1.25):
                p["image"] = self.assets.save(I.square(im, 600), "product", "JPEG")
            out.append(p)
            if len(out) >= want:
                break
        if 0 < len(out) < 3:
            self.warnings.append(f"Produse: am găsit doar {len(out)} din 3; restul rămân placeholder.")
        return out

    def products_shopify(self):
        data = self.f.json(urljoin(self.base, "/products.json?limit=60"))
        cur = None
        m = re.search(r'Shopify\.currency\s*=\s*\{"active":"(\w+)"', self.html)
        if m:
            cur = m.group(1)
        out = []
        for p in (data or {}).get("products", []):
            imgs = p.get("images") or []
            var = (p.get("variants") or [{}])[0]
            if not imgs or not var.get("available", True):
                continue
            out.append({"name": p.get("title"), "url": urljoin(self.base, f"/products/{p.get('handle')}"),
                        "image": imgs[0].get("src"), "price": fmt_price(var.get("price"), cur, self.domain)})
        return out

    def products_woo(self):
        data = self.f.json(urljoin(self.base, "/wp-json/wc/store/v1/products?per_page=40"))
        out = []
        for p in data if isinstance(data, list) else []:
            imgs = p.get("images") or []
            pr = p.get("prices") or {}
            price = None
            if pr.get("price"):
                price = int(pr["price"]) / (10 ** int(pr.get("currency_minor_unit", 2)))
            if not imgs or p.get("is_in_stock") is False:
                continue
            out.append({"name": re.sub(r"<[^>]+>", "", p.get("name", "")), "url": p.get("permalink"),
                        "image": imgs[0].get("src"), "price": fmt_price(price, pr.get("currency_code"), self.domain) if price else ""})
        return out

    def product_from_page(self, url):
        final, soup = self.page(url)
        if soup is None:
            return None
        for d in jsonld_items(soup):
            if "product" in ld_type(d) and d.get("name"):
                price, cur = ld_price(d)
                img = ld_image(d.get("image"))
                if img:
                    return {"name": str(d["name"]).strip(), "url": d.get("url") if isinstance(d.get("url"), str) and d["url"].startswith("http") else final,
                            "image": absolute(final, img), "price": fmt_price(price, cur, self.domain) if price else ""}

        def meta(*names):
            for n in names:
                m = soup.find("meta", property=n) or soup.find("meta", attrs={"name": n}) or soup.find(attrs={"itemprop": n})
                if m and (m.get("content") or "").strip():
                    return m["content"].strip()
            return None
        is_product = (meta("og:type") or "").lower().startswith("product") or meta("product:price:amount", "og:price:amount", "price")
        if is_product and meta("og:title") and meta("og:image"):
            price = meta("product:price:amount", "og:price:amount", "price")
            cur = meta("product:price:currency", "og:price:currency", "priceCurrency")
            return {"name": meta("og:title"), "url": final, "image": absolute(final, meta("og:image")),
                    "price": fmt_price(price, cur, self.domain) if price else ""}
        return None

    def products_from_cards(self, limit):
        out, seen = [], set()
        for a in self.soup.find_all("a", href=True):
            img = a.find("img")
            u = absolute(self.ref, a["href"])
            if not img or not u or not same_site(u, self.base):
                continue
            u = u.split("#")[0]
            if u in seen or NOT_PRODUCT_HREF_RE.search(u.split("?")[0]):  # tracking params (?p=1) are fine
                continue
            if in_tag(a, ["header", "nav", "footer"]):
                continue
            box, price = a, None
            for _ in range(5):  # the card around the picture link
                txt = " ".join(box.get_text(" ").split())
                txt = re.sub(r"(\d)\s*([.,])\s+(\d{2})\b", r"\1\2\3", txt)  # "114 , 99 Lei" (decimal mark in its own tag)
                txt = re.sub(r"(\d)\s+([.,]\d{2})\b", r"\1\2", txt)  # "43 .00 lei" (decimals in their own tag)
                # "1.299<sup>99</sup> Lei": small raised decimals right after the amount
                txt = re.sub(r"(\d)\s+(\d{2})\s*(lei|ron)\b", r"\1,\2 \3", txt, flags=re.I)
                # installment amounts ("12 rate x 50,01 lei/lună") are not the price
                found = [x.group(0) for x in PRICE_TEXT_RE.finditer(txt)
                         if not re.search(r"\brat[ae]\b|lun[aă]|/lun|month|/mo\b|installment|pre[tț]\s*/|/\s*(kg|l|buc|spalare|sp[ăa]lare|bucat)|per unit|unitar",
                                          txt[max(0, x.start() - 30):x.end() + 15], re.I)]
                if found and len(txt) < 900:   # big shops' cards also carry ratings, badges, delivery estimates
                    # an old (crossed-out / recommended) price often comes first: the price paid is the lowest
                    price = min(found, key=lambda x: amount(x) or 1e12)
                    break
                if not box.parent or box.parent.name in ("body", "html"):
                    break
                box = box.parent
            if not price:
                continue
            # the shop's own "price you pay" element, when it marks one, beats any other amount in the card
            main, up = None, box
            for _ in range(3):   # the price block can sit next to the part holding the picture
                main = up.find(class_=re.compile(r"new-price|sale-price|special-price|price--sale|current-price|final-price|price-new", re.I))
                if main or not up.parent or len(up.parent.get_text(" ")) > 1500:
                    break
                up = up.parent
            if main:
                mt = " ".join(main.get_text(" ").split())
                mt = re.sub(r"(\d)\s*([.,])\s+(\d{2})\b", r"\1\2\3", mt)
                mt = re.sub(r"(\d)\s+(\d{2})\s*(lei|ron)\b", r"\1,\2 \3", mt, flags=re.I)
                mm = PRICE_TEXT_RE.search(mt)
                if mm:
                    price = mm.group(0)
            name = (img.get("alt") or a.get("title") or a.get("aria-label") or "").strip()
            if len(name) < 4:
                # the card's title: another link to the same product, or its heading
                path = u.split("?")[0]
                same = [" ".join(x.get_text(" ").split()) for x in box.find_all("a", href=True)
                        if x is not a and (absolute(self.ref, x["href"]) or "").split("?")[0] == path]
                heads = [" ".join(x.get_text(" ").split()) for x in box.find_all(["h2", "h3", "h4"])]
                name = next((t for t in same + heads if 4 <= len(t) <= 160 and not PRICE_TEXT_RE.search(t)), "")
            if len(name) < 4:
                texts = [" ".join(x.get_text(" ").split()) for x in box.find_all(["a", "h2", "h3", "h4", "p", "span"])]
                texts = [t for t in texts if 4 <= len(t) <= 120 and not PRICE_TEXT_RE.search(t)]
                name = max(texts, key=len) if texts else ""
            src = img_url(img, self.ref)
            if not name or not src or BAD_IMG_WORDS.search(src):
                continue
            seen.add(u)
            # a machine-readable amount when the shop gives one (content="43.00"), else the text
            tag = box.find(attrs={"content": re.compile(r"^\d+(\.\d+)?$")}, class_=re.compile(r"pric|pret|suma|amount", re.I)) \
                or box.find(attrs={"itemprop": "price"})
            cur = "EUR" if "€" in price or "eur" in price.lower() else ("USD" if "$" in price else ("GBP" if "£" in price else "RON"))
            num = tag.get("content") if tag else amount(price)
            out.append({"name": name, "url": u, "image": src, "price": fmt_price(num, cur, self.domain) if num else ""})
            if len(out) >= limit:
                break
        return out

    def products_generic(self, limit):
        out = []
        # 1. products described on the homepage itself
        for d in self.ld:
            if "product" in ld_type(d) and d.get("name") and ld_image(d.get("image")) and isinstance(d.get("url"), str):
                price, cur = ld_price(d)
                out.append({"name": d["name"], "url": absolute(self.ref, d["url"]), "image": absolute(self.ref, ld_image(d["image"])),
                            "price": fmt_price(price, cur, self.domain) if price else ""})
        if len(out) >= 3:
            return out
        # 2. product cards on the homepage: picture, name and price together (works for custom shops too)
        out += self.products_from_cards(limit)
        if len(out) >= 3:
            return out
        # 3. product-looking links on the homepage
        scored = {}
        for a, href, txt in self.all_links():
            u = absolute(self.ref, href)
            if not u or not same_site(u, self.base) or NOT_PRODUCT_HREF_RE.search(u) or urlparse(u).path in ("", "/"):
                continue
            s = 0
            if "product" in classes_chain(a, 5) or "produs" in classes_chain(a, 5):
                s += 3
            if PRODUCT_HREF_RE.search(urlparse(u).path):
                s += 2
            if a.find("img"):
                s += 1
            if in_tag(a, ["header", "nav", "footer", "menu"]):
                s -= 3
            if s >= 3:
                scored[u.split("#")[0]] = max(s, scored.get(u, 0))
        urls = list(scored)
        self.rng.shuffle(urls)
        # 3. sitemap fallback
        if len(urls) < 4:
            urls += self.sitemap_products(30)
        tried = 0
        for u in urls:
            if len(out) >= limit or tried >= 10:
                break
            tried += 1
            p = self.product_from_page(u)
            if p:
                out.append(p)
        return out

    def sitemap_products(self, n):
        maps = []
        _, robots, _ = self.f.get(urljoin(self.base, "/robots.txt"))
        if robots:
            maps += re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
        maps += [urljoin(self.base, "/sitemap.xml"), urljoin(self.base, "/sitemap_index.xml")]
        product_urls = []
        visited = 0
        queue = list(dict.fromkeys(maps))
        while queue and visited < 6 and len(product_urls) < 200:
            sm = queue.pop(0)
            visited += 1
            _, xml, _ = self.f.get(sm)
            if not xml or "<loc" not in xml:
                continue
            locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml)
            if "<sitemapindex" in xml:
                prod = [l for l in locs if re.search(r"product|produs", l, re.I)]
                queue = prod[:2] + queue
                continue
            if re.search(r"product|produs", sm, re.I):
                product_urls += locs
            else:
                product_urls += [l for l in locs if PRODUCT_HREF_RE.search(urlparse(l).path) and not NOT_PRODUCT_HREF_RE.search(l)]
        self.rng.shuffle(product_urls)
        return product_urls[:n]
