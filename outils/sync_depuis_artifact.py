#!/usr/bin/env python3
"""Met à jour le site GitHub Pages à partir de la galerie publiée (l'artifact Claude).

Deux commandes :
  needs --src DOSSIER --repo DEPOT   liste les fichiers de la galerie qu'il faut encore lire
                                     (wallpapers et images absents du dépôt), un chemin par ligne.
  build --src DOSSIER --repo DEPOT   fabrique le site dans DEPOT : index.html complet, index.json,
                                     wallpapers, images des cartes, logo. Supprime les jours sortis de index.json.

DOSSIER contient les fichiers lus depuis la galerie, avec leur chemin publié
(page.html.txt, index.json, logo.png, img/..., wallpapers/AAAA-MM-JJ/...).

Sécurité : seuls les fichiers cités par index.json ou par la page sont copiés, et les images de cartes qui ne
sont plus citées sont supprimées du dépôt. Jamais de cartes payantes en haute définition ni de lots de concours :
ils ne sont pas dans la galerie et ce script ne les connaît pas.

Embargo : tant que la page porte le repère <!--CARTES-ETAT:avant-9-decembre--> et qu'on est avant le 9 décembre 2026
(heure de Paris), le script REFUSE de construire le site si la page cite une image de carte autre que les cartes
gratuites (lune-de-*) et les dos de cartes (dos-niveau*). Il refuse aussi une page déjà « révélée » avant cette date.
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import sys

BASE_URL = "https://zlormann.github.io/zlormack/"
CARTES_URL = BASE_URL + "cartes/"
YOUTUBE_URL = "https://www.youtube.com/@Zlormack"
TITLE = "Wallpapers gaming gratuits, PC et mobile : Zlormack Gaming"
DESC = ("Un fond d'écran gaming gratuit chaque jour pour PC et téléphone : loups, forêts, aurores, villes néon. "
        "Et les cartes à collectionner Zlormack.")
CARTES_TITLE = "Cartes à collectionner Zlormack : loups, niveaux et packs"
CARTES_DESC = ("Cartes à collectionner 100 % numériques : loups en 4 finitions (basique, métal, or, holo), numérotées, "
               "une carte gratuite par pack, nouveau pack le 9 du mois.")
OG_ALT = "Un fond d'écran Zlormack Gaming : ambiance sombre et verte"
# Vérification de propriété (Google Search Console, Bing) : colle ici la valeur « content » de la balise fournie, puis relance la copie.
SITE_VERIFICATION = {"google-site-verification": "CN0ktcLFJPIokkzKyonJzav9Uxg_a5igPrmx530zDlM", "msvalidate.01": ""}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
WEEKDAYS_SHORT = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
RESET = ("<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);"
         "padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}"
         "body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}"
         "img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>")
MAX_BYTES = 5 * 1024 * 1024
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REVEAL_DATE = "2026-12-09"
CARD_DIRS = ("img", "cartes-gratuites")
FREE_OK = re.compile(r"^(img/(lune-de-[a-z0-9-]+|dos-niveau\d)\.webp|cartes-gratuites/lune-de-[a-z0-9-]+-niveau1\.png)$")
STATE_RE = re.compile(r"<!--CARTES-ETAT:([a-z0-9-]+)-->")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def safe(rel):
    return bool(rel) and not rel.startswith("/") and ".." not in rel.split("/")


def referenced(index, page):
    files = []
    for d in index.get("days", []):
        files += list((d.get("files") or {}).values())
    imgs = sorted(set(re.findall(r'(?:src|href)="((?:img|cartes-gratuites)/[^"]+)"', page)))
    return files + imgs + ["logo.png"]


def paris_today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    except Exception:
        return (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).date().isoformat()


def check_embargo(page, wanted):
    """Avant le 9 décembre : aucune carte payante dans le site public. Sort avec une erreur claire sinon."""
    today = os.environ.get("ZLO_TODAY") or paris_today()
    m = STATE_RE.search(page)
    state = m.group(1) if m else ""
    if today >= REVEAL_DATE:
        return
    if state == "apres-9-decembre":
        sys.exit("embargo : la page est déjà révélée (apres-9-decembre) mais nous sommes le %s : rien n'est publié." % today)
    for rel in wanted:
        if rel.split("/")[0] in CARD_DIRS and not FREE_OK.match(rel):
            sys.exit("embargo : la page cite une carte cachée avant le %s : %s. Rien n'est publié." % (REVEAL_DATE, rel))


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


def esc(s):
    return html.escape(str(s), quote=False).replace('"', "&quot;")


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return "%s %s %s %d" % (WEEKDAYS[d.weekday()], "1er" if d.day == 1 else d.day, MONTHS[d.month - 1], d.year)


def day_month(iso):
    d = datetime.date.fromisoformat(iso)
    return "%s %s" % ("1er" if d.day == 1 else d.day, MONTHS[d.month - 1])


def short_date(iso):
    d = datetime.date.fromisoformat(iso)
    return "%s %d %s" % (WEEKDAYS_SHORT[d.weekday()], d.day, MONTHS_SHORT[d.month - 1])


def prerender(page, index):
    """Écrit dans le HTML le contenu du jour que la page remplit sinon par JavaScript (titre, date, images, historique).
    Un robot qui n'exécute pas le script, et le navigateur avant le script, voient déjà le vrai contenu.
    Les textes sont les mêmes que ceux du script de la page : celui-ci les réécrit à l'identique au chargement."""
    days = index.get("days") or []
    if not days:
        return page
    d = days[0]
    f = d.get("files") or {}
    pc, mob = f.get("pcSigned"), f.get("mobileSigned")
    if not (pc and mob and d.get("date") and d.get("theme")):
        return page
    theme = d["theme"]
    n = len(days)
    items = []
    for x in days:
        xf = x.get("files") or {}
        items.append(
            '<li><button type="button" class="card" data-date="%s" aria-label="%s"><div class="thumbs">'
            '<img class="t-pc" loading="lazy" alt="%s" src="%s"><img class="t-mob" loading="lazy" alt="" src="%s"></div>'
            '<span class="d">%s</span><span class="n">%s</span></button></li>'
            % (esc(x["date"]), esc("%s, %s" % (day_month(x["date"]), x["theme"])),
               esc("%s : aperçu du fond d’écran du %s" % (x["theme"], day_month(x["date"]))),
               esc(xf.get("pcThumb", "")), esc(xf.get("mobileThumb", "")), esc(short_date(x["date"])), esc(x["theme"])))
    note = ("Le premier jour est en ligne. Un nouveau wallpaper s’ajoute chaque matin et l’historique se remplit ici."
            if n == 1 else "%d wallpapers disponibles. Clique sur un jour pour le voir en grand." % n)
    reps = [
        ('<p class="eyebrow" id="dateLabel">&nbsp;</p>', '<p class="eyebrow" id="dateLabel">%s</p>' % esc(long_date(d["date"]))),
        ('<h1 id="themeName">Chargement</h1>', '<h1 id="themeName">%s</h1>' % esc(theme)),
        ('<img id="pcImg" alt="Wallpaper pour ordinateur" width="1920" height="1080">',
         '<img id="pcImg" src="%s" alt="%s" width="1920" height="1080" fetchpriority="high">'
         % (esc(pc), esc("Fond d’écran PC « %s », signé Zlormack, 1920 × 1080" % theme))),
        ('<img id="mobImg" alt="Wallpaper pour téléphone" width="1080" height="1920">',
         '<img id="mobImg" src="%s" alt="%s" width="1080" height="1920">'
         % (esc(mob), esc("Fond d’écran téléphone « %s », signé Zlormack, 1080 × 1920" % theme))),
        ('<a id="pcLink" href="#"', '<a id="pcLink" href="%s"' % esc(pc)),
        ('<a id="mobLink" href="#"', '<a id="mobLink" href="%s"' % esc(mob)),
        ('<p id="hNote"></p>', '<p id="hNote">%s</p>' % esc(note)),
        ('<ol id="grid"></ol>', '<ol id="grid">%s</ol>' % "".join(items)),
    ]
    for old, new in reps:
        if page.count(old) != 1:
            print("avertissement : repère de prérendu introuvable ou en double : %s" % old[:50], file=sys.stderr)
            continue
        page = page.replace(old, new, 1)
    return page


def json_ld(kind, index):
    org = {"@type": "Organization", "@id": BASE_URL + "#org", "name": "Zlormack Gaming", "url": BASE_URL,
           "logo": {"@type": "ImageObject", "url": BASE_URL + "logo.png"}, "sameAs": [YOUTUBE_URL]}
    site = {"@type": "WebSite", "@id": BASE_URL + "#site", "url": BASE_URL, "name": "Zlormack Gaming",
            "inLanguage": "fr-FR", "publisher": {"@id": BASE_URL + "#org"}}
    graph = [site, org]
    if kind == "cartes":
        graph.append({
            "@type": "CollectionPage", "@id": CARTES_URL + "#page", "url": CARTES_URL, "name": CARTES_TITLE,
            "description": CARTES_DESC, "inLanguage": "fr-FR", "isPartOf": {"@id": BASE_URL + "#site"},
            "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Wallpapers", "item": BASE_URL},
                {"@type": "ListItem", "position": 2, "name": "Cartes à collectionner", "item": CARTES_URL}]}})
    else:
        site["description"] = DESC
        days = index.get("days") or []
        if days:
            d = days[0]
            f = d.get("files") or {}
            for key, label, w, h in (("pcSigned", "PC", 1920, 1080), ("mobileSigned", "téléphone", 1080, 1920)):
                if f.get(key):
                    graph.append({
                        "@type": "ImageObject", "contentUrl": BASE_URL + f[key], "width": w, "height": h,
                        "name": "Fond d’écran %s « %s »" % (label, d["theme"]),
                        "description": "Fond d’écran gaming gratuit « %s » pour %s, %d × %d, du %s."
                                       % (d["theme"], "ordinateur" if label == "PC" else "téléphone", w, h, long_date(d["date"])),
                        "datePublished": d["date"], "creator": {"@id": BASE_URL + "#org"}, "inLanguage": "fr-FR"})
    text = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    return '<script type="application/ld+json">%s</script>' % text.replace("</", "<\\/")


def full_document(page, kind="home", index=None):
    """Transforme le fragment publié (title, link, style, puis contenu) en document HTML complet.
    kind = « home » (page d'accueil) ou « cartes » (même page, ouverte sur l'onglet Cartes, avec ses propres titre,
    description et adresse : c'est elle que les moteurs de recherche indexent pour les cartes)."""
    end = page.find("</style>")
    if end < 0:
        sys.exit("page.html.txt : balise </style> introuvable")
    end += len("</style>")
    head, body = page[:end], page[end:]
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
    head = re.sub(r'<meta name="claude:[^>]*>\s*', "", head)
    cartes = kind == "cartes"
    title, desc, url = (CARTES_TITLE, CARTES_DESC, CARTES_URL) if cartes else (TITLE, DESC, BASE_URL)
    body = body.replace("document.title = 'Zlormack Gaming';", "document.title = %s;" % json.dumps(title, ensure_ascii=False))
    index = index or {}
    try:
        body = prerender(body, index)
    except Exception as e:                    # le prérendu est un plus : sans lui, la page marche comme avant
        print("avertissement : prérendu ignoré : %s" % e, file=sys.stderr)
    try:
        ld = json_ld(kind, index)
    except Exception as e:
        print("avertissement : données structurées ignorées : %s" % e, file=sys.stderr)
        ld = ""
    seo = [
        '<title>%s</title>' % esc(title),
        '<meta name="description" content="%s">' % esc(desc),
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="theme-color" content="#060a07">',
        '<link rel="canonical" href="%s">' % url,
        '<link rel="icon" type="image/png" href="favicon.png">',
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Zlormack Gaming">',
        '<meta property="og:locale" content="fr_FR">',
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % url,
        '<meta property="og:image" content="%sog.jpg">' % BASE_URL,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="%s">' % esc(OG_ALT),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(desc),
        '<meta name="twitter:image" content="%sog.jpg">' % BASE_URL,
        ld,
        ] + ['<meta name="%s" content="%s">' % (k, esc(v)) for k, v in SITE_VERIFICATION.items() if v] + [
        # sans JavaScript, les deux onglets s'affichent l'un sous l'autre (le sélecteur d'onglets est masqué)
        '<noscript><style>#panelWall[hidden],#panelCartes[hidden]{display:block!important}.tabs{display:none!important}</style></noscript>',
    ]
    if cartes:
        seo.insert(0, '<base href="../">')                  # la page /cartes/ lit index.json, logo.png, img/... à la racine du site
        seo.append('<script>window.ZLO_START="cartes";</script>')
    return ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + "\n".join(s for s in seo if s) + "\n" + RESET + "\n" + head.strip() + "\n</head>\n<body>" + body.rstrip() + "\n</html>\n")


def sitemap(index):
    days = index.get("days") or []
    lastmod = index.get("updated") or (days[0].get("date") if days else "")
    imgs = []
    for d in days:                            # images signées de chaque jour : le plan du site aide Google Images
        for key in ("pcSigned", "mobileSigned"):
            p = (d.get("files") or {}).get(key)
            if p:
                imgs.append("    <image:image><image:loc>%s</image:loc></image:image>" % esc(BASE_URL + p))
    lm = "    <lastmod>%s</lastmod>\n" % lastmod if lastmod else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
            '  <url>\n    <loc>%s</loc>\n%s%s\n  </url>\n'
            '  <url>\n    <loc>%s</loc>\n  </url>\n</urlset>\n' % (BASE_URL, lm, "\n".join(imgs), CARTES_URL))


def make_extras(repo, latest_pc):
    from PIL import Image
    logo = os.path.join(repo, "logo.png")
    fav = os.path.join(repo, "favicon.png")
    if not os.path.exists(fav) and os.path.exists(logo):
        im = Image.open(logo).convert("RGBA")
        im.thumbnail((128, 128), Image.LANCZOS)
        im.save(fav, optimize=True)
    touch = os.path.join(repo, "apple-touch-icon.png")
    if not os.path.exists(touch) and os.path.exists(logo):      # icône d'écran d'accueil iPhone : logo centré sur fond sombre
        try:
            lg = Image.open(logo).convert("RGBA")
            lg.thumbnail((150, 150), Image.LANCZOS)
            tile = Image.new("RGBA", (180, 180), (6, 10, 7, 255))
            tile.alpha_composite(lg, ((180 - lg.width) // 2, (180 - lg.height) // 2))
            tile.convert("RGB").save(touch, optimize=True)
        except Exception as e:
            print("avertissement : apple-touch-icon non créée : %s" % e, file=sys.stderr)
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
    check_embargo(page, wanted)
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
    for d in CARD_DIRS:                      # images de cartes qui ne sont plus citées : retirées du dépôt
        folder = os.path.join(a.repo, d)
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                rel = d + "/" + name
                if rel not in wanted and os.path.isfile(os.path.join(folder, name)):
                    os.remove(os.path.join(folder, name))
                    removed.append(rel)
    days = index.get("days", [])
    latest = None
    if days:
        latest_files = (days[0].get("files") or {})
        latest = os.path.join(a.repo, latest_files.get("pcSigned", ""))
    make_extras(a.repo, latest)
    with open(os.path.join(a.repo, "index.html"), "w", encoding="utf-8") as f:
        f.write(full_document(page, "home", index))
    try:                                      # page /cartes/ : même contenu, onglet Cartes ouvert, titre et adresse à elle
        doc = full_document(page, "cartes", index)
        os.makedirs(os.path.join(a.repo, "cartes"), exist_ok=True)
        with open(os.path.join(a.repo, "cartes", "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)
    except Exception as e:
        print("avertissement : page /cartes/ non fabriquée : %s" % e, file=sys.stderr)
    try:
        with open(os.path.join(a.repo, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(sitemap(index))
    except Exception as e:
        print("avertissement : sitemap.xml non fabriqué : %s" % e, file=sys.stderr)
    with open(os.path.join(a.repo, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % BASE_URL)
    nj = os.path.join(a.repo, ".nojekyll")
    if not os.path.exists(nj):
        with open(nj, "w", encoding="utf-8") as f:
            f.write("")
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
