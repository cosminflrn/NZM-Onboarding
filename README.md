# NZM Onboarding

Dai linkul unui site, primești 3 fișiere gata de importat în contul Newsman al clientului:

| Fișier | Ce e | Unde se importă |
|---|---|---|
| `…__1-Pop-up-abonare.json` | formular pop-up + pagina de mulțumire + emailul și pagina de confirmare | Formulare → import |
| `…__2-Welcome.json` | template de welcome cu 3 produse reale de pe site | Newslettere / Template-uri → import |
| `…__3-Automatizare-cos-abandonat.json` | automatizarea de coș abandonat (3 emailuri) | Automatizări → import |

## Cum se folosește

1. Deschide pagina: **https://cosminflrn.github.io/NZM-Onboarding/**
2. Pune linkul site-ului (opțional: nume brand, cod discount, email expeditor) → **Generează**.
3. Se deschide un issue completat deja → **Create**.
4. În 1–2 minute: clientul apare pe pagină (cu previzualizare) și primești în issue linkul spre `.zip`.
5. Importi fișierele în Newsman. **Deschide fiecare email o dată în editor și dă Save**, ca Newsman să regenereze HTML-ul din design.

Alternativ: tab-ul **Actions → Onboarding → Run workflow**.

### Corecturi

Dacă ceva n-a ieșit bine (logo greșit, culoare, telefon), apasă **✏ Editează date** pe pagină. Se deschide `brand.json` al clientului pe GitHub: modifici valoarea, dai **Commit**, iar fișierele se regenerează automat, fără să mai citească iar site-ul.

Câmpuri utile în `brand.json`:
- `logo.url`, `logo.display_width` – logo-ul și lățimea lui în email (px)
- `banner.url` – bannerul din welcome (`null` = imaginea generică „Bine ai venit”)
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
- **Coș abandonat:** doar emailurile – logo, culori, social, telefon, linkurile „#” (Finalizează comanda → coș, Termeni, Confidențialitate), footer, `CODDISCOUNT` (dacă ai dat cod), expeditor. Pașii automatizării rămân neatinși.

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
- Issue-urile sunt procesate doar dacă sunt deschise de owner/membri/colaboratori ai repo-ului.
