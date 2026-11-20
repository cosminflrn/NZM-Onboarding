"""CLI.

  python -m nzm scrape https://magazin.ro [--discount COD] [--sender-email x@y.ro] [--sender-name "Brand"]
  python -m nzm regen docs/clients/magazin-ro/brand.json
  python -m nzm regen-all
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
import zipfile

from . import generate as G
from .scrape import Scraper

ROOT = G.ROOT
CLIENTS = os.path.join(ROOT, "docs", "clients")


def write_report(brand, out_dir, files):
    L, ct = brand["links"], brand["contact"]
    lines = [f"# {brand['name']} ({brand['domain']})", "",
             f"Generat: {brand.get('generated_at', '')}  ·  Platformă: {brand.get('platform')}", "",
             "## Ce am găsit", "",
             f"- **Logo:** {(brand.get('logo') or {}).get('url') or '— (placeholder)'}",
             f"- **Banner:** {(brand.get('banner') or {}).get('url') or '— (imaginea generică)'}",
             f"- **Culori:** accent `{brand['colors']['accent']}` · închis `{brand['colors']['dark']}` · deschis `{brand['colors']['light']}`",
             f"- **Telefon:** {ct.get('phone') or '—'}",
             f"- **Email:** {ct.get('email') or '—'}",
             f"- **Social:** {', '.join(f'[{k}]({v})' for k, v in brand['socials'].items()) or '—'}",
             f"- **Meniu:** {', '.join(f'[{m['label']}]({m['url']})' for m in L.get('menu') or []) or '—'}",
             f"- **Coș:** {L.get('cart')} · **Termeni:** {L.get('terms') or '—'} · **Confidențialitate:** {L.get('privacy') or '—'}",
             f"- **Produse:** " + (", ".join(f"[{p['name']}]({p['url']})" for p in brand.get("products") or []) or "— (placeholder)"),
             f"- **Cod discount:** {brand['options'].get('discount_code') or '— (welcome fără discount; în automatizare rămâne CODDISCOUNT)'}",
             f"- **Expeditor automatizare:** {brand['options'].get('sender_name')} <{brand['options'].get('sender_email') or 'neschimbat'}>",
             "", "## De verificat", ""]
    lines += [f"- {w}" for w in brand.get("warnings") or []] or ["- nimic special"]
    lines += ["", "## Fișiere", ""] + [f"- `{f}`" for f in files]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def finish(brand, out_dir):
    files = G.generate(brand, out_dir)
    with open(os.path.join(out_dir, "brand.json"), "w", encoding="utf-8") as f:
        json.dump(brand, f, ensure_ascii=False, indent=2)
    write_report(brand, out_dir, files)
    zpath = os.path.join(out_dir, f"{brand['slug']}__newsman-import.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in files + ["report.md"]:
            z.write(os.path.join(out_dir, fn), fn)
    update_index()
    return files


def update_index():
    items = []
    for bj in sorted(glob.glob(os.path.join(CLIENTS, "*", "brand.json"))):
        with open(bj, encoding="utf-8") as f:
            b = json.load(f)
        folder = os.path.dirname(bj)
        items.append({
            "slug": b["slug"], "name": b["name"], "domain": b["domain"], "url": b["url"],
            "generated_at": b.get("generated_at"), "logo": (b.get("logo") or {}).get("url"),
            "colors": {k: b["colors"][k] for k in ("accent", "dark", "light")},
            "warnings": b.get("warnings", []),
            "products": len([p for p in b.get("products") or []]),
            "files": sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.json")) + glob.glob(os.path.join(folder, "*.zip"))
                            if not p.endswith("brand.json")),
        })
    items.sort(key=lambda x: x.get("generated_at") or "", reverse=True)
    with open(os.path.join(CLIENTS, "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def cmd_scrape(a):
    tmp = os.path.join(CLIENTS, "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    public_root = (a.public_base or os.environ.get("NZM_PUBLIC_BASE", "")).rstrip("/")
    # slug is only known after redirects, so scrape into _tmp then move
    probe = Scraper(a.url, tmp, "")
    brand = probe.run()
    slug = brand["slug"]
    out_dir = os.path.join(CLIENTS, slug)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    shutil.move(tmp, out_dir)
    base = f"{public_root}/clients/{slug}" if public_root else ""
    # rewrite relative asset urls to public ones
    raw = json.dumps(brand, ensure_ascii=False)
    raw = re.sub(r'"assets/', f'"{base}/assets/' if base else '"assets/', raw)
    brand = json.loads(raw)
    brand["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if a.discount:
        brand["options"]["discount_code"] = a.discount.strip()
    if a.sender_email:
        brand["options"]["sender_email"] = a.sender_email.strip()
    if a.sender_name:
        brand["options"]["sender_name"] = a.sender_name.strip()
    if a.name:
        brand["name"] = a.name.strip()
        brand["options"]["sender_name"] = a.sender_name or brand["name"]
    files = finish(brand, out_dir)
    print(json.dumps({"slug": slug, "name": brand["name"], "files": files, "warnings": brand["warnings"]}, ensure_ascii=False))
    if a.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"slug={slug}\nname={brand['name']}\n")


def cmd_regen(a):
    with open(a.brand, encoding="utf-8") as f:
        brand = json.load(f)
    brand["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out_dir = os.path.dirname(os.path.abspath(a.brand))
    for old in glob.glob(os.path.join(out_dir, "*__*.json")) + glob.glob(os.path.join(out_dir, "*.zip")):
        os.remove(old)
    print(finish(brand, out_dir))


def cmd_regen_all(a):
    for bj in glob.glob(os.path.join(CLIENTS, "*", "brand.json")):
        cmd_regen(argparse.Namespace(brand=bj))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nzm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scrape")
    s.add_argument("url")
    s.add_argument("--discount", default="")
    s.add_argument("--sender-email", default="")
    s.add_argument("--sender-name", default="")
    s.add_argument("--name", default="", help="numele brandului (suprascrie ce se găsește pe site)")
    s.add_argument("--public-base", default="", help="ex. https://user.github.io/repo")
    s.add_argument("--github-output", action="store_true")
    s.set_defaults(fn=cmd_scrape)
    r = sub.add_parser("regen")
    r.add_argument("brand")
    r.set_defaults(fn=cmd_regen)
    ra = sub.add_parser("regen-all")
    ra.set_defaults(fn=cmd_regen_all)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
