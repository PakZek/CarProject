import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import time
import re
import json

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

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HEADERS_JSON = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.leboncoin.fr",
    "Referer": "https://www.leboncoin.fr/",
}

KEYWORDS = {
    "eclipse_gsx":  ["eclipse", "gsx", "dsm", "4g63"],
    "gtr_r32":      ["r32", "bnr32", "skyline"],
    "evo_vii":      ["evo vii", "evo 7", "lancer evo", "ct9a", "evolution vii", "evolution 7"],
    "gtr_r34":      ["r34", "bnr34", "skyline"],
    "gtr_r33":      ["r33", "bcnr33", "skyline"],
    "supra_mkiv":   ["supra", "mk4", "mkiv", "2jz", "1jz", "a80", "jza80"],
}

LBC_QUERIES = {
    "eclipse_gsx":  "mitsubishi eclipse gsx",
    "gtr_r32":      "nissan skyline r32",
    "evo_vii":      "mitsubishi lancer evo 7",
    "gtr_r34":      "nissan skyline r34",
    "gtr_r33":      "nissan skyline r33",
    "supra_mkiv":   "toyota supra mk4",
}

MOBILE_URLS = {
    "eclipse_gsx":  "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=17200&makeModelVariant1.modelId=9&transmission=MANUAL&maxMileage=150000&maxPrice=25000",
    "gtr_r32":      "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=18700&makeModelVariant1.modelId=77&transmission=MANUAL&maxMileage=150000&maxPrice=40000",
    "evo_vii":      "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=17200&makeModelVariant1.modelId=3&transmission=MANUAL&maxMileage=150000&maxPrice=25000",
    "gtr_r34":      "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=18700&makeModelVariant1.modelId=77&transmission=MANUAL&maxMileage=150000&maxPrice=120000",
    "gtr_r33":      "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=18700&makeModelVariant1.modelId=77&transmission=MANUAL&maxMileage=150000&maxPrice=60000",
    "supra_mkiv":   "https://suchen.mobile.de/fahrzeuge/search.html?makeModelVariant1.makeId=23600&makeModelVariant1.modelId=21&transmission=MANUAL&maxMileage=150000&maxPrice=45000",
}

GOO_URLS = {
    "eclipse_gsx": "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/ECLIPSE/?transmission=2&mileage_to=150000",
    "gtr_r32":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "evo_vii":     "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/LANCER_EVOLUTION/?transmission=2&mileage_to=150000",
    "gtr_r34":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "gtr_r33":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "supra_mkiv":  "https://www.goo-net-exchange.com/usedcars/TOYOTA/SUPRA/?transmission=2&mileage_to=150000",
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


def nettoyer_nombre(text):
    digits = re.sub(r"[^0-9]", "", str(text))
    return int(digits) if digits else 0


def keyword_match(text, modele):
    return any(kw in text.lower() for kw in KEYWORDS[modele])


def scrape_leboncoin(modele):
    annonces = []
    try:
        payload = {
            "filters": {
                "category": {"id": "2"},
                "keywords": {"text": LBC_QUERIES[modele]},
                "enums": {"transmission": ["manual"]},
                "ranges": {
                    "mileage": {"max": 150000},
                    "price": {"max": BUDGET_UE_MAX}
                }
            },
            "limit": 10,
            "sort_by": "price",
            "sort_order": "asc"
        }
        resp = requests.post(
            "https://api.leboncoin.fr/finder/search",
            headers=HEADERS_JSON,
            json=payload,
            timeout=15
        )
        if resp.status_code != 200:
            print(f"  [lbc] {modele} HTTP {resp.status_code}")
            return []
        data = resp.json()
        for ad in data.get("ads", []):
            titre = ad.get("subject", "")
            if not keyword_match(titre, modele):
                continue
            prix = nettoyer_nombre(ad.get("price", [0])[0] if ad.get("price") else 0)
            if prix <= 0 or prix > BUDGET_UE_MAX:
                continue
            attrs = {a.get("key"): a.get("value_label", a.get("value")) for a in ad.get("attributes", [])}
            km = nettoyer_nombre(attrs.get("mileage", 0))
            if km > 150000:
                continue
            annee = int(str(attrs.get("regdate", "1995"))[:4]) if attrs.get("regdate") else 1995
            lien = f"https://www.leboncoin.fr/voitures/{ad.get('list_id')}.htm"
            annonces.append({
                "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                "pays": "France", "type": "UE", "risque_rti": "faible",
                "lien": lien, "titre": titre[:80],
            })
    except Exception as e:
        print(f"  [lbc] {modele} erreur: {e}")
    return annonces[:5]


def scrape_mobile(modele):
    url = MOBILE_URLS[modele]
    annonces = []
    try:
        resp = requests.get(url, headers=HEADERS_WEB, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            data = json.loads(script.string)
            listings = (data.get("props", {})
                           .get("pageProps", {})
                           .get("searchResult", {})
                           .get("items", []))
            for item in listings[:8]:
                titre = item.get("title", "")
                if not keyword_match(titre, modele):
                    continue
                prix = nettoyer_nombre(item.get("price", {}).get("amountInEuro", 0))
                if prix <= 0 or prix > BUDGET_UE_MAX:
                    continue
                km = nettoyer_nombre(item.get("mileageInKm", 0))
                if km > 150000:
                    continue
                annee = item.get("firstRegistration", {}).get("year", 1995) or 1995
                lien = "https://suchen.mobile.de" + item.get("relativeUrl", "")
                pays = item.get("seller", {}).get("countryCode", "DE")
                if pays == "GB":
                    continue
                annonces.append({
                    "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                    "pays": pays, "type": "UE", "risque_rti": "faible",
                    "lien": lien, "titre": titre[:80],
                })
        else:
            for article in soup.find_all("article")[:8]:
                texte = article.get_text(" ", strip=True)
                if not keyword_match(texte, modele):
                    continue
                prix_m = re.search(r"([0-9][0-9.]+)\s*EUR", texte)
                km_m = re.search(r"([0-9][0-9.]+)\s*km", texte, re.I)
                annee_m = re.search(r"\b(19[89][0-9]|200[0-5])\b", texte)
                if not prix_m:
                    continue
                prix = nettoyer_nombre(prix_m.group(1))
                km = nettoyer_nombre(km_m.group(1)) if km_m else 0
                annee = int(annee_m.group(1)) if annee_m else 1995
                if prix <= 0 or prix > BUDGET_UE_MAX or km > 150000:
                    continue
                lien_tag = article.find("a", href=True)
                lien = lien_tag["href"] if lien_tag else url
                if not lien.startswith("http"):
                    lien = "https://suchen.mobile.de" + lien
                annonces.append({
                    "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                    "pays": "EU", "type": "UE", "risque_rti": "faible",
                    "lien": lien, "titre": texte[:80],
                })
    except Exception as e:
        print(f"  [mobile] {modele} erreur: {e}")
    return annonces[:5]


def scrape_goo(modele):
    url = GOO_URLS[modele]
    annonces = []
    try:
        resp = requests.get(url, headers=HEADERS_WEB, timeout=15)
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
                if "¥" not in block:
                    continue
                yen_text = block.split("¥")[1][:15]
                prix_yen = nettoyer_nombre(yen_text)
                if not prix_yen:
                    continue
                ptrf = calcul_ptrf(prix_yen)
                if ptrf > BUDGET_IMPORT_MAX:
                    continue
                km_m = re.search(r"([0-9,]+)\s*km", block, re.I)
                km = nettoyer_nombre(km_m.group(1)) if km_m else 0
                if km > 150000:
                    continue
                annee_m = re.search(r"(19[89][0-9]|200[0-5])", block)
                annee = int(annee_m.group(1)) if annee_m else 1997
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
        lbc = scrape_leboncoin(modele)
        time.sleep(1)
        mob = scrape_mobile(modele)
        time.sleep(1)
        jp = scrape_goo(modele)
        time.sleep(1)
        print(f"  -> LBC: {len(lbc)} | Mobile.de: {len(mob)} | JP: {len(jp)}")
        for ann in lbc + mob + jp:
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
        titre_rss = (
            f"[{flag}][{ann['modele'].upper()}] {ann['annee']} MT "
            f"{ann['km']}km | {budget_info} | score {score}"
        )
        fe.title(titre_rss)
        fe.id(ann["lien"])
        fe.link(href=ann["lien"])
        yen_info = f" | Japon: {ann['prix_yen']:,}JPY" if "prix_yen" in ann else ""
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
