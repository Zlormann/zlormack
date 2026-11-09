#!/usr/bin/env python3
"""Met à jour le site GitHub Pages à partir de la galerie publiée (l'artifact Claude).

Deux commandes :
  needs --src DOSSIER --repo DEPOT   liste les fichiers de la galerie qu'il faut encore lire
                                     (wallpapers et images absents du dépôt), un chemin par ligne.
  build --src DOSSIER --repo DEPOT   fabrique le site dans DEPOT : index.html complet, index.json,
                                     wallpapers, images des cartes, logo. Supprime les jours sortis de index.json.

DOSSIER contient les fichiers lus depuis la galerie, avec leur chemin publié
(page.html.txt, index.json, logo.png, img/..., wallpapers/AAAA-MM-JJ/...).

Sécurité : seuls les fichiers cités par index.json ou par la page sont copiés. Jamais de cartes en haute
définition ni de lots de concours : ils ne sont pas dans la galerie et ce script ne les connaît pas.
"""
import argparse
import json
import os
import re
import shutil
import sys

BASE_URL = "https://zlormann.github.io/zlormack/"
TITLE = "Zlormack Gaming : wallpapers gratuits et cartes à collectionner"
DESC = ("Un wallpaper gratuit chaque jour pour PC et mobile, et les cartes à collectionner Zlormack : "
        "niveaux, packs mensuels, concours de Noël.")
RESET = ("<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);"
         "padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}"
         "body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}"
         "img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>")
MAX_BYTES = 5 * 1024 * 1024
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def safe(rel):
    return bool(rel) and not rel.startswith("/") and ".." not in rel.split("/")


def referenced(index, page):
    files = []
    for d in index.get("days", []):
        files += list((d.get("files") or {}).values())
    imgs = sorted(set(re.findall(r'(?:src|href)="(img/[^"]+)"', page)))
    return files + imgs + ["logo.png"]


def load(src):
    with open(os.path.join(src, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    return index, read(os.path.join(src, "page.html.txt"))


def cmd_needs(a):
    index, page = load(a.src)
    need = set()
    for rel in referenced(index, page):
        if not safe(rel):
            continue
        if os.path.exists(os.path.join(a.src, rel)) or os.path.exists(os.path.join(a.repo, rel)):
            continue
        need.add(rel)
    print("\n".join(sorted(need)))


def full_document(page):
    """Transforme le fragment publié (title, link, style, puis contenu) en document HTML complet."""
    end = page.find("</style>")
    if end < 0:
        sys.exit("page.html.txt : balise </style> introuvable")
    end += len("</style>")
    head, body = page[:end], page[end:]
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
    head = re.sub(r'<meta name="claude:[^>]*>\s*', "", head)
    body = body.replace("document.title = 'Zlormack Gaming';",
                        "document.title = %s;" % json.dumps(TITLE, ensure_ascii=False))
    seo = "\n".join([
        '<title>%s</title>' % TITLE,
        '<meta name="description" content="%s">' % DESC,
        '<meta name="theme-color" content="#060a07">',
        '<link rel="canonical" href="%s">' % BASE_URL,
        '<link rel="icon" type="image/png" href="favicon.png">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Zlormack Gaming">',
        '<meta property="og:locale" content="fr_FR">',
        '<meta property="og:title" content="%s">' % TITLE,
        '<meta property="og:description" content="%s">' % DESC,
        '<meta property="og:url" content="%s">' % BASE_URL,
        '<meta property="og:image" content="%sog.jpg">' % BASE_URL,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])
    return ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + seo + "\n" + RESET + "\n" + head.strip() + "\n</head>\n<body>" + body.rstrip() + "\n</html>\n")


def make_extras(repo, latest_pc):
    from PIL import Image
    logo = os.path.join(repo, "logo.png")
    fav = os.path.join(repo, "favicon.png")
    if not os.path.exists(fav) and os.path.exists(logo):
        im = Image.open(logo).convert("RGBA")
        im.thumbnail((128, 128), Image.LANCZOS)
        im.save(fav, optimize=True)
    og = os.path.join(repo, "og.jpg")
    if not os.path.exists(og) and latest_pc and os.path.exists(latest_pc):
        im = Image.open(latest_pc).convert("RGB")
        w, h = im.size
        scale = max(1200 / w, 630 / h)
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        l, t = (im.width - 1200) // 2, (im.height - 630) // 2
        im.crop((l, t, l + 1200, t + 630)).save(og, quality=88, optimize=True)


def cmd_build(a):
    index, page = load(a.src)
    wanted = referenced(index, page)
    for rel in wanted:                       # tout vérifier avant de toucher au dépôt
        if not safe(rel):
            sys.exit("chemin refusé : " + rel)
        s, r = os.path.join(a.src, rel), os.path.join(a.repo, rel)
        p = s if os.path.exists(s) else (r if os.path.exists(r) else None)
        if p is None:
            sys.exit("fichier manquant : " + rel)
        if os.path.getsize(p) > MAX_BYTES:
            sys.exit("fichier trop gros : " + rel)
    updated, removed = [], []
    for rel in wanted:
        s, r = os.path.join(a.src, rel), os.path.join(a.repo, rel)
        if os.path.exists(s):
            os.makedirs(os.path.dirname(r) or ".", exist_ok=True)
            shutil.copyfile(s, r)
            updated.append(rel)
    shutil.copyfile(os.path.join(a.src, "index.json"), os.path.join(a.repo, "index.json"))
    keep = {d.get("date") for d in index.get("days", [])}
    wall = os.path.join(a.repo, "wallpapers")
    if os.path.isdir(wall):
        for d in sorted(os.listdir(wall)):
            if DATE_RE.match(d) and d not in keep:
                shutil.rmtree(os.path.join(wall, d))
                removed.append("wallpapers/" + d)
    days = index.get("days", [])
    latest = None
    if days:
        latest_files = (days[0].get("files") or {})
        latest = os.path.join(a.repo, latest_files.get("pcSigned", ""))
    make_extras(a.repo, latest)
    with open(os.path.join(a.repo, "index.html"), "w", encoding="utf-8") as f:
        f.write(full_document(page))
    for name, text in ((".nojekyll", ""), ("robots.txt", "User-agent: *\nAllow: /\n")):
        p = os.path.join(a.repo, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps({"jours": sorted(keep), "fichiers_copies": len(updated), "supprimes": removed},
                     ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("needs", cmd_needs), ("build", cmd_build)):
        s = sub.add_parser(name)
        s.add_argument("--src", required=True)
        s.add_argument("--repo", required=True)
        s.set_defaults(fn=fn)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
