# NZM Onboarding

Unealtă internă NewsMAN: pui linkul site-ului unui client și primești fișierele gata de importat în contul lui Newsman. Logo-ul, culorile, banner-ul, linkurile, contactul, rețelele sociale și produsele se iau automat de pe site.

**Pagina:** https://cosminflrn.github.io/NZM-Onboarding/ (utilizator și parolă comune echipei)

![NZM Onboarding](docs/screenshot.png)

## Ce primești (3 fișiere per client)

| Fișier | Magazin online | Site de prezentare |
|---|---|---|
| `…-formular-pop-up/embed.json` | formular + pagină de mulțumire + email de confirmare | la fel |
| `…-automatizare-….json` | coș abandonat (3 emailuri) | bun venit (3 emailuri) |
| `…-newsletter-….json` | bun venit cu produse | newsletter de noutăți |

Se importă în Newsman la Formulare, Automatizări și Newslettere. Comutatoarele din pagină aleg tipul formularului, tipul site-ului și limba (română / engleză). Tipul site-ului și limba se pot și detecta automat.

## Cum se folosește

1. **Generează:** pui linkul (opțional nume brand, cod de reducere, email expeditor) și apeși **Generează**. Durează 1–2 minute.
2. **Previzualizare:** vezi formularul și emailurile, pe desktop sau pe mobil.
3. **Editează:** corectezi texte, logo, banner, culori, contact, produse. Fișierele se regenerează automat.
4. **Descarcă:** descarci fișierele, unul câte unul sau toate. Se pot selecta până la 3 clienți odată, pentru descărcare, recitire sau ștergere.

**Site blocat** (firewall care refuză serverele GitHub): tragi butonul **NZM Onboarding** din pagină în bookmark bar, o singură dată. Apoi îl apeși pe site-ul clientului, iar pagina se preia din browserul tău și generarea pornește singură.

## Cum funcționează

- **GitHub Pages** (`docs/`) găzduiește pagina.
- **GitHub Actions** (`.github/workflows/onboarding.yml`) citește site-ul și generează fișierele, cu codul din `nzm/`. Rezultatele se salvează în `docs/clients/`.
- **Cloudflare Worker** (`worker/`) face legătura între pagină și GitHub. Tokenul GitHub și parola stau doar acolo, ca secrete ([setare](worker/README.md)).
- **Template-urile de bază** sunt exporturi Newsman (`templates/`). Emailurile se construiesc din cod în format Beefree, fără HTML sau cod personalizat.
- **Verificare automată:** înainte de salvare, fiecare fișier e verificat (fără cod, linkuri spre GitHub, texte de exemplu sau variabile necunoscute). Dacă ceva nu e în regulă, generarea se oprește cu eroare și fișierul nu ajunge în istoric.

## Întreținere

- **Token GitHub:** dacă expiră sau îl schimbi, îl faci din nou și îl înlocuiești în Cloudflare, la `GITHUB_TOKEN` (vezi [worker/README.md](worker/README.md)).
- **Template-uri de bază:** le exporți din Newsman și le pui în `templates/` cu aceleași nume. Toți clienții se regenerează automat.
- **Rulare locală:** `pip install -r requirements.txt`, apoi `python -m nzm scrape https://site.ro` sau `python -m nzm regen docs/clients/<client>/brand.json`.
