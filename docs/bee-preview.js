/* Minimal Beefree JSON -> HTML renderer, only for a quick visual preview.
   The real rendering happens inside Newsman after import. */
(function (root) {
  const css = (o) => Object.entries(o || {})
    .filter(([k, v]) => typeof v === "string" || typeof v === "number")
    .map(([k, v]) => `${k}:${v}`).join(";");
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pad = (s = {}) => ["top", "right", "bottom", "left"].map((k) => s["padding-" + k] || "0").join(" ");
  const hideMergeTags = (h) => String(h || "")
    .replace(/<code[^>]*data-bee-preview-value="([^"]*)"[^>]*>.*?<\/code>/g, "$1");

  function module(m, ctx) {
    const t = m.type.replace("mailup-bee-newsletter-modules-", "");
    const d = m.descriptor || {};
    const wrap = (inner, extra = "") => `<div style="padding:${pad(d.style)};${extra}">${inner}</div>`;
    if (t === "text" || t === "paragraph" || t === "heading") {
      const tx = d[t] || {};
      const st = tx.style || {};
      const link = (tx.computedStyle || {}).linkColor || ctx.linkColor;
      return wrap(`<div class="bp-text" style="${css(st)}; --bp-link:${link}">${hideMergeTags(tx.html || tx.text)}</div>`);
    }
    if (t === "image") {
      const im = d.image || {};
      const cs = d.computedStyle || {};
      const w = cs.width && /fixedwidth|autowidth/.test(cs.class || "") ? `max-width:${cs.width};` : "";
      const rad = (d.style || {})["border-radius"];
      let img = `<img src="${esc(im.src)}" alt="${esc(im.alt)}" style="display:block;width:100%;${w}height:auto;margin:0 auto;${rad ? "border-radius:" + rad : ""}">`;
      if (im.href) img = `<a href="${esc(im.href)}" target="_blank">${img}</a>`;
      return wrap(img, "text-align:center");
    }
    if (t === "button") {
      const b = d.button || {};
      const st = Object.assign({}, b.style);
      const label = (b.label || "").replace(/<\/?(div|p)[^>]*>/g, "");
      return wrap(`<a href="${esc(b.href || "#")}" target="_blank" style="display:inline-block;text-decoration:none;box-sizing:border-box;${css(st)}">${label}</a>`,
        `text-align:${(d.style || {})["text-align"] || "center"}`);
    }
    if (t === "divider") {
      const dv = (d.divider || {}).style || {};
      return wrap(`<div style="border-top:${dv["border-top"] || "1px solid #ddd"};width:${dv.width || "100%"};height:${dv.height || "0"};margin:0 auto"></div>`);
    }
    if (t === "social") {
      const icons = ((d.iconsList || {}).icons || []).map((i) =>
        `<a href="${esc(i.image.href)}" target="_blank" title="${esc(i.image.title)}" style="display:inline-block;margin:0 5px"><img src="${esc(i.image.src)}" width="${(d.computedStyle || {}).iconsDefaultWidth || 32}" alt="${esc(i.image.alt)}"></a>`).join("");
      return wrap(icons, `text-align:${(d.style || {})["text-align"] || "center"}`);
    }
    if (t === "html") return wrap((d.html || {}).html || "");
    if (t === "form") {
      const f = d.form || {}, st = f.style || {}, btn = st.buttons || {}, fld = st.fields || {};
      const fields = (f.structure || {}).fields || {};
      const rows = ((f.structure || {}).layout || []).map((row) => row
        .map((k) => fields[k]).filter((x) => x && !x.removeFromLayout));
      const box = (o, keys) => keys.filter((k) => o[k]).map((k) => `${k}:${o[k]}`).join(";");
      const fs = (d.style || {})["font-size"] || "14px";
      const lab = st.labels || {};
      const pads = ["padding-top", "padding-right", "padding-bottom", "padding-left"];
      const borders = ["border-top", "border-right", "border-bottom", "border-left"];
      const html = rows.filter((r) => r.length).map((r) => `<div style="display:flex;gap:8px;margin:6px 0">${r.map((x) => {
        if (x.type === "submit") return `<button style="flex:1;cursor:pointer;font:inherit;font-size:${fs};background:${btn.backgroundColor};color:${btn.color};border-radius:${btn["border-radius"]};font-weight:${btn["font-weight"] || "bold"};letter-spacing:${btn["letter-spacing"] || "0"};line-height:${btn["line-height"] || "normal"};${box(btn, borders)};${box(btn, pads)}">${esc(x.attributes.value || "Trimite")}</button>`;
        if (x.type === "checkbox") return `<label style="display:flex;gap:8px;align-items:flex-start;font-size:${fs};line-height:${lab["line-height"] || "1.5"};color:${lab.color || "inherit"};text-align:left;flex:1"><input type="checkbox" style="margin:${lab["line-height"] === "200%" ? "7px" : "3px"} 0 0;flex:none"><span>${(x.label || "").replace(/\[([^\]]+)\]\(([^)]+)\)/g, `<a href="$2" target="_blank" style="color:${lab.color || "inherit"};text-decoration:underline">$1</a>`)}</span></label>`;
        return `<input placeholder="${esc((x.attributes || {}).placeholder || x.label)}" style="flex:1;min-width:0;font:inherit;font-size:${fs};line-height:200%;background:${fld.backgroundColor};color:${fld.color || "inherit"};border-radius:${fld["border-radius"]};outline:none;${box(fld, borders)};${box(fld, pads)}">`;
      }).join("")}</div>`).join("");
      return wrap(html);
    }
    return "";
  }

  function render(bee) {
    const page = bee.page || bee;
    const body = page.body || {};
    const content = body.content || {};
    const width = (content.computedStyle || {}).messageWidth || "650px";
    const ctx = { linkColor: (content.computedStyle || {}).linkColor || "#0068A5" };
    const rows = (page.rows || []).map((r) => {
      const rs = (r.content || {}).style || {};
      const cols = (r.columns || []).map((c) =>
        `<div class="bp-col" style="flex:${c["grid-columns"] || 12};min-width:0;${css(c.style)}">${(c.modules || []).map((m) => module(m, ctx)).join("")}</div>`).join("");
      return `<div style="${css((r.container || {}).style)}"><div class="bp-row${((r.content || {}).computedStyle || {}).rowColStackOnMobile === false ? "" : " bp-stack"}" style="max-width:${width};margin:0 auto;display:flex;${css(rs)};width:auto">${cols}</div></div>`;
    }).join("");
    const fonts = (body.webFonts || []).filter((f) => f.url).map((f) => `<link rel="stylesheet" href="${esc(f.url)}">`).join("");
    return fonts + `<div class="bp" style="${css((body.container || {}).style)};${css(content.style)};padding:10px 0">
      <style>.bp p{margin:0}.bp input[type=checkbox]{width:auto!important}.bp .bp-text a{color:var(--bp-link)}.bp img{border:0}
      @media (max-width:620px){.bp .bp-stack{flex-direction:column}}</style>${rows}</div>`;
  }

  root.BeePreview = { render };
})(typeof window !== "undefined" ? window : globalThis);
