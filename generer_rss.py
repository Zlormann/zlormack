#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://zlormann.github.io/zlormack/'
ET.register_namespace('media', 'http://search.yahoo.com/mrss/')
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')


def add_item(channel, title, path, date, category, description):
    url = BASE + quote(path, safe='/')
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'link').text = url
    ET.SubElement(item, 'guid', {'isPermaLink': 'true'}).text = url
    ET.SubElement(item, 'description').text = description
    ET.SubElement(item, 'category').text = category
    stamp = datetime.fromisoformat(date).replace(hour=12, tzinfo=timezone.utc)
    ET.SubElement(item, 'pubDate').text = format_datetime(stamp, usegmt=True)
    ET.SubElement(item, '{http://search.yahoo.com/mrss/}content', {
        'url': url, 'medium': 'image', 'type': 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
    })
    ET.SubElement(item, 'enclosure', {
        'url': url, 'type': 'image/png' if path.lower().endswith('.png') else 'image/jpeg',
        'length': '0'
    })


def main():
    data = json.loads((ROOT / 'index.json').read_text(encoding='utf-8'))
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    for tag, val in [('title', 'Zlormack Gaming — Wallpapers et cartes gratuites'),
                     ('link', BASE), ('description', 'Nouveaux wallpapers PC et mobile et cartes gratuites Zlormack Gaming.'),
                     ('language', 'fr-FR')]:
        ET.SubElement(channel, tag).text = val
    ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', {
        'href': BASE + 'feed.xml', 'rel': 'self', 'type': 'application/rss+xml'
    })
    for day in data.get('days', []):
        date, theme, files = day['date'], day['theme'], day['files']
        for key, label in [('pcSigned', 'PC'), ('mobileSigned', 'mobile')]:
            path = files.get(key)
            if path and (ROOT / path).is_file():
                add_item(channel, f'Wallpaper {label} — {theme} ({date})', path, date,
                         'Wallpapers gratuits', f'Fond d’écran {label} gratuit : {theme}. Téléchargement sur Zlormack Gaming.')
    cards = [('Lune de novembre', 'cartes-gratuites/lune-de-novembre-niveau1.png', '2026-11-09'),
             ('Lune de givre', 'cartes-gratuites/lune-de-givre-niveau1.png', '2026-11-09')]
    for name, path, date in cards:
        if (ROOT / path).is_file():
            add_item(channel, f'Carte gratuite Zlormack — {name}', path, date,
                     'Cartes gratuites', f'Carte numérique gratuite de niveau 1 : {name}.')
    tree = ET.ElementTree(rss)
    ET.indent(tree, space='  ')
    tree.write(ROOT / 'feed.xml', encoding='utf-8', xml_declaration=True)
    print('Flux RSS généré :', ROOT / 'feed.xml')

if __name__ == '__main__':
    main()
