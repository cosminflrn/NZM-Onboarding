# NZM Onboarding

Dai linkul unui site, primești 3 fișiere gata de importat în contul Newsman al clientului:

| Fișier | Ce e | Unde se importă |
|---|---|---|
| `…__1-Pop-up-abonare.json` | formular pop-up + pagina de mulțumire + emailul și pagina de confirmare | Formulare → import |
| `…__2-Welcome.json` | template de welcome cu 3 produse reale de pe site | Newslettere / Template-uri → import |
| `…__3-Automatizare-cos-abandonat.json` | automatizarea de coș abandonat (3 emailuri) | Automatizări → import |

## Cum se folosește

Totul se face din pagina **https://cosminflrn.github.io/NZM-Onboarding/**:

1. Pagina merge pentru oricine are linkul, fără cont sau token, după ce se configurează o dată intermediarul Cloudflare ([worker/README.md](worker/README.md)). Fără intermediar, pagina cere fiecărui utilizator un token GitHub.
2. Pui linkul site-ului (opțional: nume brand, cod discount, email expeditor) → **Generează**. Vezi progresul în pagină.
3. În 1–2 minute clientul apare în listă: **Previzualizare**, descărcare **.zip** sau fișier cu fișier.
4. Importi fișierele în Newsman. **Deschide fiecare email o dată în editor și dă Save**, ca Newsman să regenereze HTML-ul din design.

### Corecturi

**✏ Editează** pe un client deschide un formular cu tot ce s-a extras (logo – și upload, banner, culori, telefon, email, social, linkuri, meniu, produse, discount, expeditor). La salvare fișierele se regenerează automat, fără să mai citească site-ul. **↻ Recitește site** pornește de la zero.

Câmpuri utile în `brand.json`:
- `logo.url`, `logo.display_width` – logo-ul și lățimea lui în email (px)
- `banner.url` – bannerul găsit pe site; în welcome se folosește doar dacă pui `options.use_site_banner: true` (implicit rămâne imaginea „Bine ai venit”)
- `colors.accent` (butoane, bare), `colors.dark` (header/footer, text), `colors.light` (fundaluri deschise), `colors.muted`
- `contact.phone`, `contact.email`, `socials.*`, `links.*` (`cart`, `terms`, `privacy`, `menu`…)
- `products` – cele 3 produse din welcome (`name`, `url`, `image`, `price`)
- `options.discount_code`, `options.sender_email`, `options.sender_name`

## Ce citește de pe site

- **Nume** – `og:site_name`, schema.org, titlul paginii
- **Logo** – schema.org, imagini/SVG cu „logo” din header; SVG și WebP sunt convertite în PNG (emailurile nu afișează SVG)
- **Banner** – primul slide / hero; WebP/AVIF sunt convertite în JPG
- **Culori** – culoarea de brand din logo, `theme-color`, variabile CSS și stilul butoanelor; dacă e prea deschisă pentru text alb pe buton, e închisă puțin
- **Telefon, email** – linkuri `tel:`/`mailto:`, apoi textul paginii și pagina de Contact
- **Social** – Facebook, Instagram, TikTok, YouTube, LinkedIn, Pinterest, X
- **Linkuri** – meniul principal (+ Reduceri dacă există), coș, termeni, confidențialitate, contact
- **Produse** – Shopify (`/products.json`), WooCommerce (Store API), schema.org Product de pe paginile de produs, sitemap. Sunt alese 3 la întâmplare (aceleași la regenerare); imaginile sunt puse pe fundal pătrat ca să se alinieze.

## Ce se modifică în template-uri

- **Pop-up:** plicul → logo, culorile butonului/textului, linkul de termeni din checkbox, iconițele social din pagina de mulțumire, numele formularului.
- **Welcome:** logo, meniu cu linkuri reale, banner (+ titlul „Bine ai venit!” scris ca text), blocul de discount → rând de 3 produse (discountul rămâne doar dacă ai dat un cod), telefon/email, social, copyright, culori.
- **Coș abandonat:** doar emailurile; fără cod de discount, blocurile cu cod și imaginile de discount sunt scoase, iar subiectele emailurilor 2–3 devin fără discount; – logo, culori, social, telefon, linkurile „#” (Finalizează comanda → coș, Termeni, Confidențialitate), footer, `CODDISCOUNT` (dacă ai dat cod), expeditor. Pașii automatizării rămân neatinși.

Imaginile convertite sunt găzduite pe GitHub Pages (`docs/clients/<site>/assets/`); restul sunt luate direct de pe site-ul clientului. Dacă vrei să nu depinzi de ele, încarcă-le în managerul de imagini Newsman.

## Schimbarea template-urilor de bază

Template-urile sunt în `templates/` (exporturi Newsman). Poți pune exporturi noi peste ele, cu condiția să păstrezi „placeholderele” pe care le recunoaște generatorul (sunt listate la începutul `nzm/generate.py`):
imaginile de logo/banner (după numele fișierului), culorile `#030000`, `#fb2324`, `#f4f1ef`, `#efe9e6`, `#8f7d5e`, `#ef4136`, `#47433c`, telefoanele `0700 000 000` / `072000000`, `Siteulmeu.ro 2022`, `CODDISCOUNT`, linkurile `#` și `example.com`. La un push în `templates/` toți clienții se regenerează.

## Rulare locală

```bash
pip install -r requirements.txt
python -m nzm scrape https://magazin.ro --discount BUN10
python -m nzm regen docs/clients/magazin-ro/brand.json
```

## Configurare inițială (o singură dată)

- **Settings → Pages →** Source: *Deploy from a branch*, Branch: `main`, folder `/docs`.
- **Settings → Actions → General → Workflow permissions:** *Read and write*.
- Intermediarul Cloudflare: vezi [worker/README.md](worker/README.md).
