"""English version of everything the generator writes (emails, forms, thank-you and confirmation pages).

The generator composes Romanian; for an English client the finished pages go through `tr`, which swaps
each Romanian phrase for its English one. Texts typed by the team in "Editează" stay exactly as typed.
"""
import json
import re

LANGS = ("ro", "en")


def lang_of(brand):
    """The language chosen in the app, or (Automat) the one detected on the site."""
    lang = ((brand or {}).get("options") or {}).get("lang") or "auto"
    if lang in LANGS:
        return lang
    det = (brand or {}).get("lang_detected")
    return det if det in LANGS else "ro"


def _and(s):
    return s.replace(" și ", " and ")


# phrases with a brand / page name inside (checked first)
PATTERNS = [
    (r"Bine ai venit în comunitatea (.+?)!", lambda m: f"Welcome to the {m[1]} community!"),
    (r"Bine ai venit la (.+?)!", lambda m: f"Welcome to {m[1]}!"),
    (r"De acum ești primul care află noutățile (.+?)\. Îți scriem doar când avem ceva cu adevărat util sau interesant pentru tine\.",
     lambda m: f"From now on you'll be the first to hear what's new at {m[1]}. We only write when we have something truly useful or interesting for you."),
    (r"Vei afla primul ce e nou la (.+?), plus sfaturi și informații utile, fără mesaje inutile\.",
     lambda m: f"You'll be the first to know what's new at {m[1]}, plus useful tips, with no pointless messages."),
    (r"Îți vom scrie din când în când cu noutăți de la (.+?) și lucruri care chiar merită citite\.",
     lambda m: f"We'll write now and then with news from {m[1]} and things truly worth reading."),
    (r"De acum primești noutățile (.+?) direct pe email, doar atunci când avem ceva bun de spus\.",
     lambda m: f"From now on you'll get {m[1]} news by email, only when we have something good to say."),
    (r"Află primul de produsele noi și de ofertele (.+?)\.", lambda m: f"Be the first to hear about new products and offers from {m[1]}."),
    (r"Primește ofertele (.+?) înaintea tuturor\.", lambda m: f"Get {m[1]} offers before anyone else."),
    (r"Primește noutățile (.+?) direct pe email\.", lambda m: f"Get {m[1]} news straight to your inbox."),
    (r"Află primul ce e nou la (.+?)\.", lambda m: f"Be the first to know what's new at {m[1]}."),
    (r"Fii primul care află noutățile și ofertele (.+?)\.", lambda m: f"Be the first to hear about news and offers from {m[1]}."),
    (r"Fii primul care află noutățile (.+?)\.", lambda m: f"Be the first to hear what's new at {m[1]}."),
    (r"La (.+?) găsești (.+?)\.", lambda m: f"At {m[1]} you'll find {_and(m[2])}."),
    (r"Urmărește (.+?) pe (.+?) pentru noutăți, culise și idei, în fiecare zi\.",
     lambda m: f"Follow {m[1]} on {_and(m[2])} for news, behind-the-scenes and ideas, every day."),
    (r"Pe site-ul (.+?) găsești tot ce ai nevoie, explicat simplu\.",
     lambda m: f"On the {m[1]} website you'll find everything you need, explained simply."),
    (r"Vrei să afli mai multe despre (.+?) sau ai nevoie de ajutor să alegi\? Scrie-ne și îți răspundem cât de repede putem\.",
     lambda m: f"Want to know more about {m[1]} or need help choosing? Write to us and we'll reply as soon as we can."),
    (r"Îți aducem pe scurt cele mai noi lucruri de la (.+?)\.", lambda m: f"Here's a quick round-up of what's new at {m[1]}."),
    (r"Află tot ce trebuie să știi despre (.+?) – pe scurt, direct pe site-ul nostru\.",
     lambda m: f"Everything you need to know about {m[1]} – in short, right on our website."),
    (r"(\]\([^)]*\)|</a>)\s*abonării", lambda m: m[1]),  # "[terms](link) abonării" -> "[terms](link)"
]

# fixed phrases, longest first so a short one never cuts into a longer one
PHRASES = {
    # --- welcome series / newsletter
    "Îți mulțumim că te-ai abonat. Ne bucurăm să te avem alături.": "Thanks for subscribing. We're glad to have you with us.",
    "De acum ești primul care află de produsele noi, de promoțiile pentru abonați și de ofertele pe care nu vrei să le ratezi.":
        "From now on you'll be the first to hear about new products, subscriber-only deals and offers you won't want to miss.",
    "Acolo vezi primul noutățile, părerile celor care ne cunosc deja și răspunsuri rapide la întrebările tale.":
        "That's where you'll see our news first, what people who already know us think, and quick answers to your questions.",
    "Echipa noastră îți răspunde cu drag la orice întrebare.": "Our team is happy to answer any question.",
    "Am adunat câteva lucruri pe care merită să le vezi.": "We've gathered a few things worth a look.",
    "Abonații află primii de produsele noi și primesc ofertele înaintea tuturor.":
        "Subscribers hear about new products first and get offers before anyone else.",
    "Vei primi din când în când noutăți, recomandări alese și oferte doar pentru abonați.":
        "Now and then you'll get news, hand-picked recommendations and subscriber-only offers.",
    "Îți scriem când apar produse noi sau oferte bune, fără să-ți umplem inboxul.":
        "We'll write when there are new products or good offers, without filling your inbox.",
    "Mulțumim pentru încredere. Ne bucurăm că ești aici.": "Thanks for your trust. We're glad you're here.",
    "Ne bucurăm că ți-ai făcut loc pentru noi în inbox.": "We're glad you made room for us in your inbox.",
    "Câteva noutăți pe care am vrut să le afli primul.": "A few things we wanted you to hear first.",
    "Pe scurt, tot ce e nou la noi în ultima vreme.": "In short, everything new with us lately.",
    "Câteva locuri bune de unde să începi.": "A few good places to start.",
    "Iată ce te așteaptă la noi.": "Here's what's waiting for you.",
    "Câteva lucruri pe care merită să le vezi.": "A few things worth a look.",
    "Iată ce am pregătit pentru tine în perioada aceasta.": "Here's what we've prepared for you lately.",
    "Hai să ne vedem și pe social media 👋": "Let's connect on social media 👋",
    "Ne găsești și pe social media": "Find us on social media",
    "Hai să rămânem în contact": "Let's stay in touch",
    "Suntem aici dacă ai nevoie de noi": "We're here if you need us",
    "Suntem aici pentru tine": "We're here for you",
    "Ai o întrebare? Scrie-ne!": "Got a question? Write to us!",
    "Rămâi aproape de noi.": "Stay close.",
    "Ne bucurăm că ești aici.": "We're glad you're here.",
    "Câteva locuri de unde să începi": "A few places to start",
    "Am ales câteva produse pentru tine": "We picked a few products for you",
    "Ce găsești la noi": "What you'll find here",
    "Mai găsești la noi": "More from us",
    "Ți-ar putea plăcea": "You might like",
    "Vezi toate noutățile": "See what's new",
    "Vizitează site-ul": "Visit the website",
    "Intră în magazin": "Shop now",
    "Contactează-ne": "Contact us",
    "Ghid rapid": "Quick guide",
    "Bine ai venit": "Welcome",
    "Noutăți de la ": "News from ",
    "Abonează-te la newsletter": "Subscribe to our newsletter",
    "Aplică-l la finalizarea comenzii.": "Use it at checkout.",
    # benefits / cards
    "Oferte pentru abonați": "Subscriber deals",
    "Promoții trimise întâi pe email.": "Promotions sent to your inbox first.",
    "Noutăți în avans": "Early news",
    "Afli primul de produsele noi.": "Be first to see new products.",
    "Idei și inspirație": "Ideas & inspiration",
    "Recomandări alese pentru tine.": "Picks chosen for you.",
    "Afli primul ce pregătim.": "Be first to see what's coming.",
    "Sfaturi utile": "Useful tips",
    "Informații alese cu grijă.": "Carefully chosen information.",
    "Fără spam": "No spam",
    "Îți scriem doar când contează.": "We only write when it matters.",
    "Răspuns rapid": "Quick reply",
    "Îți scriem înapoi cât de repede putem.": "We write back as soon as we can.",
    "Oameni reali": "Real people",
    "Vorbești direct cu echipa noastră.": "You talk directly to our team.",
    "Fără obligații": "No strings attached",
    "Întreabă orice, oricând.": "Ask anything, anytime.",
    "Comandă simplă": "Easy checkout",
    "Finalizezi în câțiva pași.": "Done in a few steps.",
    "Plată securizată": "Secure payment",
    "Datele tale sunt protejate.": "Your data is protected.",
    "Suntem aici": "We're here",
    "Te ajutăm cu orice întrebare.": "We'll help with any question.",
    "Noutăți": "News",
    # --- abandoned cart
    "Stocurile sunt limitate, așa că îți recomandăm să finalizezi comanda cât mai curând.":
        "Stock is limited, so we recommend completing your order soon.",
    "Produsele sunt încă rezervate pentru tine, dar nu pentru mult timp.": "Your items are still reserved for you, but not for long.",
    "Am păstrat produsele pentru tine. Le găsești mai jos.": "We've saved your items. You'll find them below.",
    "Ți-am pregătit un cod special pentru produsele din coș.": "We've prepared a special code for the items in your cart.",
    "Finalizează comanda cât produsele sunt pe stoc.": "Complete your order while items are in stock.",
    "Folosește codul tău la finalizarea comenzii.": "Use your code at checkout.",
    "Ultima amintire: coșul tău te așteaptă": "Last reminder: your cart is waiting",
    "Un mic cadou pentru coșul tău 🎁": "A little gift for your cart 🎁",
    "Produsele tale te așteaptă în coș": "Your items are waiting in your cart",
    "Produsele tale te așteaptă.": "Your items are waiting.",
    "Produsele tale te așteaptă": "Your items are waiting",
    "Finalizează comanda cu reducere": "Complete your order with a discount",
    "Finalizează comanda": "Complete your order",
    "Ai uitat ceva în coș?": "Did you forget something?",
    "Produsele din coșul tău": "Items in your cart",
    "Coșul tău expiră curând": "Your cart expires soon",
    "Te-ar putea interesa și": "You might also like",
    "Ultima amintire": "Last reminder",
    "Un mic cadou": "A little gift",
    "Coșul tău": "Your cart",
    "Ai nevoie de ajutor la alegere sau o întrebare despre comandă? ": "Need help choosing or have a question about your order? ",
    " și te ajutăm cu drag.": " and we'll gladly help.",
    " sau sună-ne la ": " or call us at ",
    "Scrie-ne la ": "Write to us at ",
    "Sună-ne la ": "Call us at ",
    "Listare produse din coș": "Cart items",
    "Conținutul va fi repetat pentru fiecare produs din coș": "Repeated for every item in the cart",
    " - Coș abandonat": " - Abandoned cart",
    " - Bun venit": " - Welcome",
    # --- shared blocks
    "Ai întrebări? Suntem aici pentru tine.": "Questions? We're here for you.",
    "Primești acest email pentru că te-ai abonat la newsletter. ": "You're receiving this email because you subscribed to our newsletter. ",
    ". Toate drepturile rezervate.": ". All rights reserved.",
    "Termeni și condiții": "Terms & conditions",
    "Confidențialitate": "Privacy",
    "Dezabonare": "Unsubscribe",
    "Vezi online": "View online",
    "Vezi produsul": "View product",
    "CODUL TĂU DE REDUCERE": "YOUR DISCOUNT CODE",
    "Nume produs": "Product name",
    "Descoperă ": "Discover ",
    "Descoperă": "Discover",
    # --- forms, thank-you page, confirmation page and e-mail
    "Pentru a completa procesul de abonare te rugăm să verifici căsuța de email și sa accesezi link-ul din emailul de confirmare.":
        "To complete your subscription, please check your inbox and click the link in the confirmation email.",
    "Abonarea este aproape gata! Mai trebuie doar să îți confirmi emailul. Mulțumim!":
        "Almost done! Just confirm your email address. Thank you!",
    "Abonarea ta a fost confirmată. Îți mulțumim !": "Your subscription is confirmed. Thank you!",
    "Vă rugăm să accesați butonul de mai jos pentru a confirma abonarea dvs. la newsletter-ul:":
        "Please click the button below to confirm your subscription to the newsletter:",
    "Vă rugăm să accesați butonul de mai jos pentru a confirma abonarea dvs la newsletter-ul:":
        "Please click the button below to confirm your subscription to the newsletter:",
    "Nu uitați că pentru o bună funcționare a newsletter-ului, trebuie să adăugați adresa de mail":
        "To make sure our newsletter reaches you, please add",
    "Nu uitați că pentru o bună funcționare a newsletter-ului trebuie să adăugați adresa de mail":
        "To make sure our newsletter reaches you, please add",
    "în lista dvs. de contacte (Address Book).": "to your contacts (Address Book).",
    "Sunteți de acord cu Politica de confidențialitate ?": "Do you agree to the Privacy Policy?",
    "Și rămâi la curent cu toate noutățile.": "And stay up to date with all our news.",
    "Urmărește-ne și pe social media:": "Follow us on social media:",
    "Mulțumim pentru abonare!": "Thanks for subscribing!",
    "Confirm abonarea la newsletter": "Confirm my subscription",
    "termenii și condițiile abonării": "the subscription terms and conditions",
    "termenii și condițiile": "the terms and conditions",
    "Mai este doar un pas !": "Just one more step!",
    "Continuă navigarea": "Continue browsing",
    "Sunt de acord cu ": "I agree to ",
    "Adresă de email": "Email address",
    "Formular abonare": "Subscribe form",
    "Pop-up abonare": "Subscribe pop-up",
    "Vă mulțumim!": "Thank you!",
    "Vă mulțumim,": "Thank you,",
    "Bună ziua,": "Hello,",
    "Bună ziua!": "Hello!",
    "Abonează-te!": "Subscribe!",
    "ABONARE": "SUBSCRIBE",
    "Abonare": "Subscribe",
    "după abonare": "after subscribing",
    # the same sentences split over several tags in the templates
    "Abonarea ta a fost confirmată.": "Your subscription is confirmed.",
    "Îți mulțumim !": "Thank you!",
    "pentru abonare!": "for subscribing!",
    "Mulțumim": "Thanks",
}
# eyebrows are written in capitals ("COȘUL TĂU"): the upper-case form of every short phrase too
PHRASES.update({ro.upper(): en.upper() for ro, en in list(PHRASES.items())
                if len(ro) <= 40 and ro.upper() != ro and ro.upper() not in PHRASES})
_ORDERED = sorted(PHRASES.items(), key=lambda kv: -len(kv[0]))
_RX = [(re.compile(p), f) for p, f in PATTERNS]


def _esc_u(s):
    """The same phrase as it appears inside JSON written with \\u escapes (some template fields)."""
    return json.dumps(s, ensure_ascii=True)[1:-1]


def tr_text(s):
    if not isinstance(s, str) or not s or not re.search(r"[a-zA-ZăâîșțĂÂÎȘȚ]", s):
        return s
    for rx, fn in _RX:
        s = rx.sub(fn, s)
    for ro, en in _ORDERED:
        if ro in s:
            if " " in ro.strip():
                s = s.replace(ro, en)
            else:  # single words only as whole words ("Abonare" must not touch "Abonarea")
                s = re.sub(rf"(?<!\w){re.escape(ro)}(?!\w)", en.replace("\\", "\\\\"), s)
        if "\\u" in s:
            esc = _esc_u(ro)
            if esc != ro and esc in s:
                s = s.replace(esc, _esc_u(en))
    return s


def tr(obj, lang):
    """Translate every string inside obj (dicts, lists, tuples) when lang is English."""
    if lang != "en":
        return obj
    if isinstance(obj, str):
        return tr_text(obj)
    if isinstance(obj, dict):
        return {k: tr(v, lang) for k, v in obj.items()}
    if isinstance(obj, list):
        return [tr(v, lang) for v in obj]
    if isinstance(obj, tuple):
        return tuple(tr(v, lang) for v in obj)
    return obj
