# Intermediarul Cloudflare

Leagă pagina de GitHub, ca echipa să folosească unealta doar cu utilizator și parolă, fără token. Tokenul GitHub și parola stau numai aici, ca secrete Cloudflare, niciodată în repo.

Intermediarul permite doar: pornirea generării, a recitirii sau a ștergerii unui client, urmărirea lor, citirea fișierelor generate și salvarea editărilor în `docs/clients/`. Nu poate modifica codul.

## Cum e configurat

- **Worker:** `nzm-onboarding` (Cloudflare → Workers & Pages), legat la acest repo. Root directory `/worker`, deploy command `npx wrangler deploy`, build watch paths `worker/*`. Se republică singur când se schimbă ceva în acest folder.
- **Setări publice:** în `wrangler.toml` (`REPO`, `ALLOWED_ORIGIN`, `APP_USER`).
- **Secrete:** în Cloudflare, la worker → Settings → Variables and Secrets, ambele de tip **Secret**:
  - `GITHUB_TOKEN`: token GitHub *fine-grained*, doar pentru repo-ul `NZM-Onboarding`, cu **Actions** și **Contents** pe *Read and write*;
  - `APP_PASSWORD`: parola comună a echipei.
- **Adresa:** e scrisă în `docs/config.js` (`window.NZM_PROXY`).

## Schimbarea tokenului sau a parolei

1. GitHub → Settings → Developer settings → Fine-grained tokens. Deschide tokenul „NewsMAN Onboarding” → **Regenerate token**, sau fă unul nou cu permisiunile de mai sus.
2. Cloudflare → worker `nzm-onboarding` → Settings → Variables and Secrets. Editează `GITHUB_TOKEN` sau `APP_PASSWORD`, apoi **Deploy**.

Verificare: deschide adresa worker-ului în browser. Trebuie să apară `{"ok":true, … "token":true}`.

## Brand fetch NewsMAN

Pentru comutatorul „Metodă brand fetch” (NewsMAN / Claude) adaugă în Worker → Settings → Variables and Secrets:

| Nume | Tip | Valoare |
|---|---|---|
| `BRAND_API_TOKEN` | Secret | token-ul normal de la brand fetch NewsMAN |
| `BRAND_WEBHOOK_SECRET` | Secret | secretul de semnare a webhook-ului |
| `BRAND_API_URL` | Text (opțional) | implicit `https://brandfetch.newsman.eu/api/brand` |
| `BRAND_INSTANCE` | Text (opțional) | implicit `cosmin` |

Adresa de webhook care trebuie trecută la Brandfetch pentru instanța `cosmin`: `https://<worker>/brandfetchwebhook`.
Comutatorul apare în pagină doar după ce primele două sunt setate.
