#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)

def catalogue():
    with (ROOT / "index.json").open(encoding="utf-8") as f:
        return json.load(f)

def verifier():
    data = catalogue()
    jours = data.get("days", [])
    erreurs = []

    dates = [d.get("date") for d in jours]

    if len(dates) != len(set(dates)):
        erreurs.append("Dates en double")

    if len(jours) > data.get("keepDays", 30):
        erreurs.append("Historique trop long")

    for jour in jours:
        try:
            date.fromisoformat(jour["date"])
        except (KeyError, ValueError):
            erreurs.append("Date incorrecte")
            continue

        for cle, chemin in jour.get("files", {}).items():
            p = Path(chemin)
            if (
                p.is_absolute()
                or ".." in p.parts
                or not chemin.startswith("wallpapers/")
                or not (ROOT / p).is_file()
            ):
                erreurs.append(
                    f"{jour['date']} : {cle} manquant ou invalide"
                )

    if erreurs:
        for erreur in erreurs:
            print("ERREUR :", erreur)
        return False

    print("Catalogue valide.")
    print("Jours :", len(jours))
    return True

def etat():
    data = catalogue()
    print("ZLORMACK GAMING")
    print("Dernière mise à jour :", data.get("updated"))
    print("Wallpapers :", len(data.get("days", [])))
    print("Dépôt :", ROOT)
    print()
    run("git", "status", "--short")

def rss():
    if not verifier():
        sys.exit("RSS annulé : catalogue invalide")

    run(sys.executable, "outils/generer_rss.py")
    ET.parse(ROOT / "feed.xml")
    print("RSS XML valide.")

def publier():
    rss()

    run(
        "git", "add",
        "--", "index.json", "feed.xml", "wallpapers"
    )

    changements = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT
    )

    if changements.returncode == 0:
        print("Aucun changement à publier.")
        return

    if changements.returncode != 1:
        sys.exit("Impossible de vérifier les changements Git.")

    run("git", "diff", "--cached", "--stat")

    confirmation = input(
        "Publier ces changements sur GitHub ? (oui/non) : "
    )

    if confirmation.strip().lower() != "oui":
        print("Publication annulée.")
        return

    run("git", "commit", "-m", "Publication Zlormack Gaming")
    run("git", "push")
    print("Publication GitHub envoyée.")

def main():
    parser = argparse.ArgumentParser(
        description="Pilote central Zlormack Gaming"
    )
    parser.add_argument(
        "commande",
        choices=["etat", "verifier", "rss", "publier"]
    )
    args = parser.parse_args()

    {
        "etat": etat,
        "verifier": verifier,
        "rss": rss,
        "publier": publier
    }[args.commande]()

if __name__ == "__main__":
    main()
