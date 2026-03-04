import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import time
import re
import json

YEN_TO_EUR = 1 / 180
BUDGET_UE_MAX = 40000
BUDGET_IMPORT_MAX = 35000

MODELES = {
    "eclipse_gsx":  {"priorite": 1, "prix_moyen": 22000},
    "gtr_r32":      {"priorite": 2, "prix_moyen": 40000},
    "evo_vii":      {"priorite": 3, "prix_moyen": 25000},
    "gtr_r34":      {"priorite": 4, "prix_moyen": 120000},
    "gtr_r33":      {"priorite": 5, "prix_moyen": 60000},
    "supra_mkiv":   {"priorite": 6, "prix_moyen": 45000},
}

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9",
        "Connection": "keep-alive",
    },
]

KEYWORDS = {
    "eclipse_gsx":  ["eclipse", "gsx", "dsm", "4g63"],
    "gtr_r32":      ["r32", "bnr32", "skyline", "gt-r"],
    "evo_vii":      ["evo vii", "evo 7", "lancer evo", "ct9a", "evolution vii", "evolution 7"],
    "gtr_r34":      ["r34", "bnr34", "skyline", "gt-r"],
    "gtr_r33":      ["r33", "bcnr33", "skyline", "gt-r"],
    "supra_mkiv":   ["supra", "mk4", "mkiv", "2jz", "1jz", "a80", "jza80"],
}

BEFORWARD_URLS = {
    "eclipse_gsx": "https://www.beforward.jp/stocklist/make/MITSUBISHI/model/ECLIPSE/transmission/MT/mileage_to/150000/",
    "gtr_r32":     "https://www.beforward.jp/stocklist/make/NISSAN/model/SKYLINE/transmission/MT/mileage_to/150000/",
    "evo_vii":     "https://www.beforward.jp/stocklist/make/MITSUBISHI/model/LANCER/transmission/MT/mileage_to/150000/",
    "gtr_r34":     "https://www.beforward.jp/stocklist/make/NISSAN/model/SKYLINE/transmission/MT/mileage_to/150000/",
    "gtr_r33":     "https://www.beforward.jp/stocklist/make/NISSAN/model/SKYLINE/transmission/MT/mileage_to/150000/",
    "supra_mkiv":  "https://www.beforward.jp/stocklist/make/TOYOTA/model/SUPRA/transmission/MT/mileage_to/150000/",
}

CFJ_URLS = {
    "eclipse_gsx": "https://www.carfromjapan.com/cheap-used-mitsubishi-eclipse-for-sale/?transmission=manual&mileage_to=150000",
    "gtr_r32":     "https://www.carfromjapan.com/cheap-used-nissan-skyline-for-sale/?transmission=manual&mileage_to=150000",
    "evo_vii":     "https://www.carfromjapan.com/cheap-used-mitsubishi-lancer-evolution-for-sale/?transmission=manual&mileage_to=150000",
    "gtr_r34":     "https://www.carfromjapan.com/cheap-used-nissan-skyline-for-sale/?transmission=manual&mileage_to=150000",
    "gtr_r33":     "https://www.carfromjapan.com/cheap-used-nissan-skyline-for-sale/?transmission=manual&mileage_to=150000",
    "supra_mkiv":  "https://www.carfromjapan.com/cheap-used-toyota-supra-for-sale/?transmission=manual&mileage_to=150000",
}

GOO_URLS = {
    "eclipse_gsx": "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/ECLIPSE/?transmission=2&mileage_to=150000",
    "gtr_r32":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "evo_vii":     "https://www.goo-net-exchange.com/usedcars/MITSUBISHI/LANCER_EVOLUTION/?transmission=2&mileage_to=150000",
    "gtr_r34":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "gtr_r33":     "https://www.goo-net-exchange.com/usedcars/NISSAN/SKYLINE_GT_R/?transmission=2&mileage_to=150000",
    "supra_mkiv":  "https://www.goo-net-exchange.com/usedcars/TOYOTA/SUPRA/?transmission=2&mileage_to=150000",
}

JCD_URLS = {
    "eclipse_gsx": "https://www.japancardirect.com/search/?make=mitsubishi&model=eclipse&transmission=manual",
    "gtr_r32":     "https://www.japancardirect.com/search/?make=nissan&model=skyline&transmission=manual",
    "evo_vii":     "https://www.japancardirect.com/search/?make=mitsubishi&model=lancer+evolution&transmission=manual",
    "gtr_r34":     "https://www.japancardirect.com/search/?make=nissan&model=skyline&transmission=manual",
    "gtr_r33":     "https://www.japancardirect.com/search/?make=nissan&model=skyline&transmission=manual",
    "supra_mkiv":  "https://www.japancardirect.com/search/?make=toyota&model=supra&transmission=manual",
}

JDMHEAVEN_URLS = {
    "eclipse_gsx": "https://www.jdmheaven.club/vehicles/?make=mitsubishi&model=eclipse&transmission=manual",
    "gtr_r32":     "https://www.jdmheaven.club/vehicles/?make=nissan&model=skyline-r32&transmission=manual",
    "evo_vii":     "https://www.jdmheaven.club/vehicles/?make=mitsubishi&model=lancer-evolution&transmission=manual",
    "gtr_r34":     "https://www.jdmheaven.club/vehicles/?make=nissan&model=skyline-r34&transmission=manual",
    "gtr_r33":     "https://www.jdmheaven.club/vehicles/?make=nissan&model=skyline-r33&transmission=manual",
    "supra_mkiv":  "https://www.jdmheaven.club/vehicles/?make=toyota&model=supra&transmission=manual",
}

AUTOUNCLE_URLS = {
    "eclipse_gsx": "https://www.autouncle.fr/fr/voitures-occasion/mitsubishi/eclipse?transmission=manual&max_price=25000&max_mileage=150000",
    "gtr_r32":     "https://www.autouncle.fr/fr/voitures-occasion/nissan/skyline?transmission=manual&max_price=40000&max_mileage=150000",
    "evo_vii":     "https://www.autouncle.fr/fr/voitures-occasion/mitsubishi/lancer?transmission=manual&max_price=25000&max_mileage=150000",
    "gtr_r34":     "https://www.autouncle.fr/fr/voitures-occasion/nissan/skyline?transmission=manual&max_price=120000&max_mileage=150000",
    "gtr_r33":     "https://www.autouncle.fr/fr/voitures-occasion/nissan/skyline?transmission=manual&max_price=60000&max_mileage=150000",
    "supra_mkiv":  "https://www.autouncle.fr/fr/voitures-occasion/toyota/supra?transmission=manual&max_price=45000&max_mileage=150000",
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


def nettoyer(text):
    digits = re.sub(r"[^0-9]", "", str(text))
    return int(digits) if digits else 0


def kw_match(text, modele):
    return any(kw in text.lower() for kw in KEYWORDS[modele])


def get_headers(index=0):
    return HEADERS_LIST[index % len(HEADERS_LIST)]


def find_cars_in_json(data):
    cars = []
    def recurse(obj, depth=0):
        if depth > 6:
            return
        if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
            cars.extend(obj[:8])
        elif isinstance(obj, dict):
            for v in obj.values():
                recurse(v, depth + 1)
    recurse(data)
    return cars


def scrape_generic_jp(url, modele, source_nom, budget_max):
    annonces = []
    try:
        session = requests.Session()
        session.headers.update(get_headers())
        resp = session.get(url, timeout=20, allow_redirects=True)
        if resp.status_code == 403:
            print(f"  [{source_nom}] {modele} bloque (403)")
            return []
        if resp.status_code != 200:
            print(f"  [{source_nom}] {modele} HTTP {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        for script_tag in soup.find_all("script", type="application/json") + soup.find_all("script", id="__NEXT_DATA__"):
            try:
                raw = script_tag.string or ""
                if len(raw) < 50:
                    continue
                data = json.loads(raw)
                cars = find_cars_in_json(data)
                for car in cars:
                    titre = str(car.get("title", car.get("name", car.get("car_name", ""))))
                    if not kw_match(titre + " " + str(car), modele):
                        continue
                    trans = str(car.get("transmission", "")).upper()
                    if trans and "AT" in trans:
                        continue
                    prix_raw = car.get("price", car.get("total_price", car.get("fob_price", 0)))
                    prix_num = nettoyer(str(prix_raw))
                    if not prix_num:
                        continue
                    prix_yen = None
                    if prix_num > 100000:
                        ptrf = calcul_ptrf(prix_num)
                        prix_yen = prix_num
                    elif prix_num > 1000:
                        ptrf = round(prix_num * 0.93) + 3000 + round(prix_num * 0.93 * 0.30) + 4650
                    else:
                        continue
                    if ptrf > budget_max:
                        continue
                    km = nettoyer(str(car.get("mileage", car.get("mileageInKm", car.get("odometer", 0)))))
                    if km > 150000:
                        continue
                    annee_raw = str(car.get("year", car.get("manufacture_year", "1997")))
                    annee = int(annee_raw[:4]) if annee_raw[:4].isdigit() else 1997
                    lien = str(car.get("url", car.get("link", car.get("detail_url", url))))
                    if not lien.startswith("http"):
                        lien = url.split("/stocklist")[0] + lien
                    ann = {
                        "modele": modele, "prix_net": ptrf, "km": km, "annee": annee,
                        "pays": "Japon", "type": "Import", "risque_rti": "moyen (RHD)",
                        "lien": lien, "titre": titre[:80], "source": source_nom,
                    }
                    if prix_yen:
                        ann["prix_yen"] = prix_yen
                    annonces.append(ann)
                if annonces:
                    break
            except Exception:
                continue
        if not annonces:
            for bloc in soup.find_all(["div", "li", "article"], class_=re.compile(r"car|vehicle|item|listing|result", re.I))[:10]:
                texte = bloc.get_text(" ", strip=True)
                if not kw_match(texte, modele):
                    continue
                prix_yen = None
                ptrf = None
                yen_m = re.search(r"¥\s*([0-9,]+)", texte)
                usd_m = re.search(r"\$\s*([0-9,]+)", texte)
                eur_m = re.search(r"([0-9,]+)\s*€", texte)
                if yen_m:
                    prix_yen = nettoyer(yen_m.group(1))
                    ptrf = calcul_ptrf(prix_yen)
                elif usd_m:
                    usd = nettoyer(usd_m.group(1))
                    ptrf = round(usd * 0.93) + 3000 + round(usd * 0.93 * 0.30) + 4650
                elif eur_m:
                    eur = nettoyer(eur_m.group(1))
                    if eur > budget_max:
                        continue
                    ptrf = eur
                if not ptrf or ptrf > budget_max:
                    continue
                km_m = re.search(r"([0-9,]+)\s*km", texte, re.I)
                km = nettoyer(km_m.group(1)) if km_m else 0
                if km > 150000:
                    continue
                if not re.search(r"\bMT\b|manual|manuelle", texte, re.I):
                    continue
                annee_m = re.search(r"\b(19[89][0-9]|200[0-5])\b", texte)
                annee = int(annee_m.group(1)) if annee_m else 1997
                lien_tag = bloc.find("a", href=True)
                lien = lien_tag["href"] if lien_tag else url
                if lien and not lien.startswith("http"):
                    lien = url.split("/stocklist")[0].split("/search")[0] + lien
                ann = {
                    "modele": modele, "prix_net": ptrf, "km": km, "annee": annee,
                    "pays": "Japon", "type": "Import", "risque_rti": "moyen (RHD)",
                    "lien": lien, "titre": texte[:80], "source": source_nom,
                }
                if prix_yen:
                    ann["prix_yen"] = prix_yen
                annonces.append(ann)
    except Exception as e:
        print(f"  [{source_nom}] {modele} erreur: {e}")
    return annonces[:4]


def scrape_generic_eu(url, modele, source_nom, budget_max):
    annonces = []
    try:
        session = requests.Session()
        session.headers.update(get_headers(1))
        resp = session.get(url, timeout=20)
        if resp.status_code == 403:
            print(f"  [{source_nom}] {modele} bloque (403)")
            return []
        if resp.status_code != 200:
            print(f"  [{source_nom}] {modele} HTTP {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        for script_tag in soup.find_all("script", type="application/json") + soup.find_all("script", id="__NEXT_DATA__"):
            try:
                raw = script_tag.string or ""
                if len(raw) < 50:
                    continue
                data = json.loads(raw)
                cars = find_cars_in_json(data)
                for car in cars:
                    titre = str(car.get("title", car.get("name", "")))
                    if not kw_match(titre, modele):
                        continue
                    trans = str(car.get("transmission", "")).upper()
                    if trans and "AUTO" in trans:
                        continue
                    prix = nettoyer(str(car.get("price", car.get("amountInEuro", 0))))
                    if not prix or prix > budget_max:
                        continue
                    km = nettoyer(str(car.get("mileage", car.get("mileageInKm", 0))))
                    if km > 150000:
                        continue
                    annee_raw = str(car.get("year", car.get("registration_year", "1995")))
                    annee = int(annee_raw[:4]) if annee_raw[:4].isdigit() else 1995
                    pays = str(car.get("country", car.get("countryCode", "EU")))
                    if pays in ["GB", "UK"]:
                        continue
                    lien = str(car.get("url", car.get("link", url)))
                    if not lien.startswith("http"):
                        lien = "https://www.autouncle.fr" + lien
                    annonces.append({
                        "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                        "pays": pays, "type": "UE", "risque_rti": "faible",
                        "lien": lien, "titre": titre[:80], "source": source_nom,
                    })
                if annonces:
                    break
            except Exception:
                continue
        if not annonces:
            for bloc in soup.find_all(["article", "div", "li"], class_=re.compile(r"car|vehicle|listing|result|item", re.I))[:10]:
                texte = bloc.get_text(" ", strip=True)
                if not kw_match(texte, modele):
                    continue
                if not re.search(r"manual|manuelle|\bMT\b", texte, re.I):
                    continue
                prix_m = re.search(r"([0-9][0-9 .]+)\s*[€E]", texte)
                if not prix_m:
                    continue
                prix = nettoyer(prix_m.group(1))
                if not prix or prix > budget_max:
                    continue
                km_m = re.search(r"([0-9][0-9 .]+)\s*km", texte, re.I)
                km = nettoyer(km_m.group(1)) if km_m else 0
                if km > 150000:
                    continue
                annee_m = re.search(r"\b(19[89][0-9]|200[0-5])\b", texte)
                annee = int(annee_m.group(1)) if annee_m else 1995
                lien_tag = bloc.find("a", href=True)
                lien = lien_tag["href"] if lien_tag else url
                if lien and not lien.startswith("http"):
                    lien = "https://www.autouncle.fr" + lien
                annonces.append({
                    "modele": modele, "prix_net": prix, "km": km, "annee": annee,
                    "pays": "EU", "type": "UE", "risque_rti": "faible",
                    "lien": lien, "titre": texte[:80], "source": source_nom,
                })
    except Exception as e:
        print(f"  [{source_nom}] {modele} erreur: {e}")
    return annonces[:4]


def generer_rss():
    fg = FeedGenerator()
    fg.title("JDM Deals Hunter RSS")
    fg.link(href="https://PakZek.github.io/CarProject/", rel="alternate")
    fg.description("Meilleurs deals JDM: Eclipse GSX > R32 > Evo VII | score >= 0.70")
    fg.language("fr")

    toutes = []
    sources_jp = [
        (BEFORWARD_URLS, "BeForward", BUDGET_IMPORT_MAX),
        (CFJ_URLS, "CarFromJapan", BUDGET_IMPORT_MAX),
        (GOO_URLS, "GooNet", BUDGET_IMPORT_MAX),
        (JCD_URLS, "JapanCarDirect", BUDGET_IMPORT_MAX),
    ]
    sources_eu = [
        (JDMHEAVEN_URLS, "JDMHeaven", BUDGET_UE_MAX),
        (AUTOUNCLE_URLS, "AutoUncle", BUDGET_UE_MAX),
    ]

    for modele, infos in MODELES.items():
        print(f"Scraping {modele}...")
        resultats = {}
        for url_dict, nom, budget in sources_jp:
            time.sleep(2)
            res = scrape_generic_jp(url_dict[modele], modele, nom, budget)
            resultats[nom] = len(res)
            for ann in res:
                score = compute_score(ann["prix_net"], ann["km"], ann["annee"], infos["prix_moyen"], ann["risque_rti"])
                if score >= 0.70:
                    toutes.append((score, ann, infos["priorite"]))
        for url_dict, nom, budget in sources_eu:
            time.sleep(2)
            res = scrape_generic_eu(url_dict[modele], modele, nom, budget)
            resultats[nom] = len(res)
            for ann in res:
                score = compute_score(ann["prix_net"], ann["km"], ann["annee"], infos["prix_moyen"], ann["risque_rti"])
                if score >= 0.70:
                    toutes.append((score, ann, infos["priorite"]))
        print(f"  -> " + " | ".join(f"{k}: {v}" for k, v in resultats.items()))

    top = sorted(toutes, key=lambda x: (-x[0], x[2]))[:20]
    print(f"\n==> {len(top)} deals qualifies (seuil 0.70)")

    for score, ann, _ in top:
        fe = fg.add_entry()
        flag = "JP" if ann["type"] == "Import" else "EU"
        budget_info = f"{ann['prix_net']}EUR (incl. import)" if ann["type"] == "Import" else f"{ann['prix_net']}EUR"
        titre_rss = (
            f"[{flag}][{ann['modele'].upper()}] {ann['annee']} MT "
            f"{ann['km']}km | {budget_info} | score {score} | {ann.get('source','')}"
        )
        fe.title(titre_rss)
        fe.id(ann["lien"])
        fe.link(href=ann["lien"])
        yen_info = f" | Japon: {ann['prix_yen']:,}JPY" if "prix_yen" in ann else ""
        fe.description(
            f"Source: {ann.get('source','')} | Prix: {ann['prix_net']}EUR{yen_info} | "
            f"Km: {ann['km']} | Annee: {ann['annee']} | Pays: {ann['pays']} | "
            f"Risque RTI: {ann['risque_rti']} | {ann.get('titre','')}"
        )
        fe.pubDate(datetime.now(timezone.utc))

    fg.rss_file("jdm-deals-hunter.xml")
    print("RSS genere: jdm-deals-hunter.xml")


if __name__ == "__main__":
    generer_rss()
