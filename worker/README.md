# Intermediar Cloudflare (o singură dată, ~10 minute, gratuit)

Ca pagina să meargă pentru colegi fără token GitHub, tokenul stă aici, ca secret. Pagina cere un utilizator și o parolă comune; fără ele nu se poate porni nimic.
Intermediarul permite doar: pornirea generării, urmărirea ei, citirea fișierelor generate și salvarea editărilor în `docs/clients/`. Nu poate modifica codul și nu poate șterge nimic.

1. **Token GitHub:** https://github.com/settings/personal-access-tokens/new
   - Repository access: *Only select repositories* → `NZM-Onboarding`
   - Permissions: **Actions: Read and write**, **Contents: Read and write**
   - Generate token și copiază-l.
2. **Cloudflare:** cont gratuit pe https://dash.cloudflare.com → **Workers & Pages → Create → Create Worker** (Hello World) → nume `nzm-onboarding` → **Deploy**.
3. **Edit code** → șterge tot, lipește conținutul din `worker/worker.js` → **Deploy**.
4. Worker → **Settings → Variables and Secrets → Add**:
   - `GITHUB_TOKEN` = tokenul de la pasul 1 (tip **Secret**)
   - `REPO` = `cosminflrn/NZM-Onboarding`
   - `ALLOWED_ORIGIN` = `https://cosminflrn.github.io`
   - `APP_USER` = utilizatorul comun (tip **Text**)
   - `APP_PASSWORD` = parola comună (tip **Secret** — nu o pune niciodată în repo)
   → **Deploy**.
5. Copiază adresa workerului (ex. `https://nzm-onboarding.<cont>.workers.dev`) și pune-o în `docs/config.js`:
   ```js
   window.NZM_PROXY = "https://nzm-onboarding.<cont>.workers.dev";
   ```
   Deschide adresa workerului în browser: trebuie să vezi `{"ok":true,...,"token":true}`.

Când expiră tokenul, faci unul nou și îl înlocuiești doar la pasul 4.
