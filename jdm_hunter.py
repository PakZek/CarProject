import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import time
import re

YEN_TO_EUR = 1 / 180
BUDGET_UE_MAX = 25000
BUDGET_IMPORT_MAX = 20000

MODELES = {
    "eclipse_gsx":  {"priorite": 1, "prix_moyen": 22000},
    "gtr_r32":      {"priorite": 2, "prix_moyen": 40000},
    "evo_vii":      {"priorite": 3, "prix_moyen": 25000},
    "gtr_r34":      {"priorite": 4, "prix_moyen": 120000},
    "gtr_r33":      {"priorite": 5, "prix_moyen": 60000},
    "supra_mkiv":   {"priorite": 6, "prix_moyen": 45000},
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PARKING_URLS = {
    "eclipse_gsx": "https://www.theparking.eu/used-cars/mitsubishi-eclipse-manual.html",
    "gtr_r32":     "https://www.theparking.eu/used-cars/nissan-skyline-manual.html",
    "evo_vii":     "https://www.theparking.eu/used-cars/mitsubishi-lancer-evolution-manual.html",
    "gtr_r34":     "https://www.theparking.eu/used-cars/nissan-skyline-manual.html",
    "gtr_r33":     "https://www.theparking.eu/used-cars/nissan-skyline-manual.html",
    "supra_mkiv":  "https://www.theparking.eu/used-cars/toyota-supra-manual.html",
}

KEYWORDS = {
    "eclipse_gsx":  ["eclipse", "gsx", "dsm"],
    "gtr_r32":      ["r32", "bnr32", "gt-r", "gtr"],
    "evo_vii":      ["evo", "lancer", "evo 7", "evo vii", "ct9a"],
    "gtr_r34":      ["r34", "bnr34", "gt-r", "gtr"],
    "gtr_r33":      ["r33", "bcnr33", "gt-r", "gtr"],
    "supra_mkiv":   ["mk4", "mkiv", "2jz", "1jz", "a80", "jza80", "1993", "1994", "1995", "1996", "1997", "1998"],
}

GOO_URLS = {
    "eclipse_gsx": "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/ECLIPSE/?transmission=2",
    "gtr_r32":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2",
    "evo_vii":     "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/LANCER_EVOLUTION/?transmission=2",
    "gtr_r34":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2",
    "gtr_r33":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2",
    "supra_mkiv":  "https://www.goo-net-exchange.com/usedcars/TOYOTA/SUPRA/?transmission=2",
}


def calcul_ptrf(prix_yen):
    achat_eur = prix_yen * YEN_TO_EUR
    fret_port = 3000
    douane = achat_eur * 0.10
    tva = (achat_eur + douane) * 0.20
    rti = 4650
    return round(achat_eur + fret_port + douane + tva + rti)


def compute_score(prix_net, km, annee, prix_moyen, risque_rti):
    qualite = max(0.01, (1 - km / 150000) * max(0.01, 1 - (2026 - annee) / 30))
    prix_rel = min(prix_net / prix_moyen, 1.5)
    risque = 0.8 if "moyen" in risque_rti else 1.0
    return round((qualite / prix_rel) * risque, 2)


def parse_prix(text):
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def parse_km(text):
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else 0


def keyword_match(text, modele):
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS[modele])


def scrape_parking(modele):
    url = PARKING_URLS[modele]
    annonces = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(string=re.compile(r"Detail")):
            parent = tag.find_parent()
            if not parent:
                continue
            block_text = parent.get_text(" ", strip=True)
            prix_match = re.search(r"([0-9][0-9,\.]+)\s*€", block_text)
            if not prix_match:
                continue
            prix = parse_prix(prix_match.group(1))
            if prix <= 0 or prix > BUDGET_UE_MAX:
                continue
            km_match = re.search(r"([0-9][0-9,\.]+)\s*[Kk]m", block_text)
            km = parse_km(km_match.group(1)) if km_match else 0
            if km > 150000:
                continue
            annee_match = re.search(r"\b(19[89][0-9]|200[0-5])\b", block_text)
            annee = int(annee_match.group(1)) if annee_match else 1995
            if "manual" not in block_text.lower():
                continue
            if not keyword_match(block_text, modele):
                continue
            if "UNITED KINGDOM" in block_text.upper() or " UK" in block_text.upper():
                continue
            pays = "UE"
            for p in ["FRANCE", "GERMANY", "NETHERLANDS", "BELGIUM", "SPAIN", "ITALY", "PORTUGAL"]:
                if p in block_text.upper():
                    pays = p.capitalize()
                    break
            lien_tag = parent.find("a", href=True)
            lien = lien_tag["href"] if lien_tag else url
            if lien and not lien.startswith("http"):
                lien = "https://www.theparking.eu" + lien
            annonces.append({
                "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                "pays": pays, "type": "UE", "risque_rti": "faible",
                "lien": lien, "titre": block_text[:80],
            })
    except Exception as e:
        print(f"  [parking] {modele} erreur: {e}")
    return annonces[:5]


def scrape_goo(modele):
    url = GOO_URLS[modele]
    annonces = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for h3 in soup.find_all("h3"):
            try:
                titre = h3.get_text(strip=True)
                parent = h3.find_parent()
                if not parent:
                    continue
                block = parent.get_text(" ", strip=True)
                if "MT" not in block:
                    continue
                if not keyword_match(titre + " " + block, modele):
                    continue
                yen_match = re.search(r"¥([0-9,]+)", block)
                if not yen_match:
                    continue
                prix_yen = parse_prix(yen_match.group(1))
                if prix_yen <= 0:
                    continue
                ptrf = calcul_ptrf(prix_yen)
                if ptrf > BUDGET_IMPORT_MAX:
                    continue
                km_match = re.search(r"([0-9,]+)\s*km", block, re.IGNORECASE)
                km = parse_km(km_match.group(1)) if km_match else 0
                if km > 150000:
                    continue
                annee_match = re.search(r"(19[89][0-9]|200[0-5])\.", block)
                annee = int(annee_match.group(1)) if annee_match else 1997
                lien_tag = h3.find("a", href=True) or parent.find("a", href=True)
                lien = lien_tag["href"] if lien_tag else url
                if lien and not lien.startswith("http"):
                    lien = "https://www.goo-net-exchange.com" + lien
                annonces.append({
                    "modele": modele, "prix_net": ptrf, "km": km, "annee": annee,
                    "pays": "Japon", "type": "Import", "risque_rti": "moyen (RHD)",
                    "lien": lien, "titre": titre[:80], "prix_yen": prix_yen,
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  [goo] {modele} erreur: {e}")
    return annonces[:3]


def generer_rss():
    fg = FeedGenerator()
    fg.title("JDM Deals Hunter RSS")
    fg.link(href="https://PakZek.github.io/CarProject/", rel="alternate")
    fg.description("Meilleurs deals JDM: Eclipse GSX > R32 > Evo VII | score >= 0.70")
    fg.language("fr")

    toutes = []
    for modele, infos in MODELES.items():
        print(f"Scraping {modele}...")
        time.sleep(2)
        ue = scrape_parking(modele)
        jp = scrape_goo(modele)
        print(f"  -> UE: {len(ue)} | JP: {len(jp)}")
        for ann in ue + jp:
            score = compute_score(
                ann["prix_net"], ann["km"], ann["annee"],
                infos["prix_moyen"], ann["risque_rti"]
            )
            if score >= 0.70:
                toutes.append((score, ann, infos["priorite"]))

    top = sorted(toutes, key=lambda x: (-x[0], x[2]))[:15]
    print(f"\n==> {len(top)} deals qualifies (seuil 0.70)")

    for score, ann, _ in top:
        fe = fg.add_entry()
        flag = "JP" if ann["type"] == "Import" else "EU"
        budget_info = f"{ann['prix_net']}EUR (incl. import)" if ann["type"] == "Import" else f"{ann['prix_net']}EUR"
        titre = (
            f"[{flag}][{ann['modele'].upper()}] {ann['annee']} MT "
            f"{ann['km']}km | {budget_info} | score {score}"
        )
        fe.title(titre)
        fe.id(ann["lien"])
        fe.link(href=ann["lien"])
        yen_info = f" | Prix Japon: {ann['prix_yen']:,}JPY" if "prix_yen" in ann else ""
        fe.description(
            f"Prix: {ann['prix_net']}EUR{yen_info} | Km: {ann['km']} | "
            f"Annee: {ann['annee']} | Pays: {ann['pays']} | "
            f"Risque RTI: {ann['risque_rti']} | {ann.get('titre', '')}"
        )
        fe.pubDate(datetime.now(timezone.utc))

    fg.rss_file("jdm-deals-hunter.xml")
    print("RSS genere: jdm-deals-hunter.xml")


if __name__ == "__main__":
    generer_rss()
