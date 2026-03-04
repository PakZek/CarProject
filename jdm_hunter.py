import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
import time  # Pour delays anti-ban

YEN_TO_EUR = 1 / 180
BUDGET_UE_MAX = 25000
BUDGET_IMPORT_MAX = 20000
MODELES = {
    'eclipse_gsx': {'priorite': 1, 'prix_moyen': 22000},
    'gtr_r32': {'priorite': 2, 'prix_moyen': 40000},
    'evo_vii': {'priorite': 3, 'prix_moyen': 25000},
    'gtr_r34': {'priorite': 4, 'prix_moyen': 120000},
    'gtr_r33': {'priorite': 5, 'prix_moyen': 60000},
    'supra_mkiv': {'priorite': 6, 'prix_moyen': 45000}
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def scrape_parking(modele):
    # Recherche theparking.eu manuelle <150k km
    search_terms = modele.replace('_', ' ')
    url = f"https://www.theparking.eu/used-cars/{search_terms}-manual.html"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        annonces = []
        for item in soup.find_all('article', class_='search-result')[:5]:  # Selectors réalistes
            prix_el = item.find('span', {'data-cy': 'price'}) or item.find(class_='price')
            if not prix_el: continue
            prix_text = prix_el.text.strip().replace('€', '').replace(',', '')
            prix = float(''.join(filter(str.isdigit, prix_text))) / 1000 if prix_text else 99999
            km_el = item.find(class_='km') or item.find(string=lambda t: 'km' in t.lower())
            km = int(''.join(filter(str.isdigit, str(km_el)))) if km_el else 999999
            if prix > BUDGET_UE_MAX or km > 150000: continue
            lien = item.find('a')['href'] if item.find('a') else url
            if not lien.startswith('http'): lien = 'https://theparking.eu' + lien
            annonces.append({
                'modele': modele, 'prix_net': prix * 1000, 'km': km, 'lien': lien,
                'annee': 1998, 'pays': 'UE Sud', 'type': 'UE', 'risque_rti': 'faible'
            })
        return annonces
    except:
        return []

def scrape_goo(modele):
    url = f"https://www.goo-net-exchange.com/catalogs/?q={modele.replace('_', ' ')}&makerCode=0&modelCode=0"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        annonces = []
        for item in soup.find_all('div', class_='car-list-item')[:3]:
            prix_y_el = item.find(class_='price')
            if not prix_y_el: continue
            prix_y_text = prix_y_el.text.strip().replace('¥', '').replace(',', '')
            prix_y = float(''.join(filter(str.isdigit, prix_y_text)))
            ptrf = calcul_ptrf({'prix_yen': prix_y})
            if ptrf > BUDGET_IMPORT_MAX: continue
            km_el = item.find(class_='mileage')
            km = int(''.join(filter(str.isdigit, str(km_el)))) if km_el else 999999
            if km > 150000: continue
            lien = 'https://goo-net-exchange.com' + item.find('a')['href'] if item.find('a') else url
            annonces.append({
                'modele': modele, 'prix_net': ptrf, 'km': km, 'lien': lien,
                'annee': 1997, 'pays': 'Japon', 'type': 'Import', 'risque_rti': 'moyen (RHD/CT)'
            })
        return annonces
    except:
        return []

def calcul_ptrf(annonce_jp):
    achat_eur = annonce_jp['prix_yen'] * YEN_TO_EUR
    fret_port = 3000
    douane = achat_eur * 0.10
    tva = (achat_eur + douane) * 0.20
    rti = 4500 + 150
    return round(achat_eur + fret_port + douane + tva + rti)

def compute_score(ann):
    qualite = max(0, (1 - ann['km'] / 150000) * (1 - (2026 - ann['annee']) / 30))
    prix_rel = min(ann['prix_net'] / MODELES[ann['modele']]['prix_moyen'], 1)
    risque = 0.8 if 'moyen' in ann['risque_rti'] else 1.0
    score = (qualite / prix_rel) * risque
    return round(score, 2)

def generer_rss():
    fg = FeedGenerator(title='JDM Deals Hunter RSS 🚗', description='Eclipse GSX > R32 > Evo VII priorisés')
    fg.link(href='https://PakZek.github.io/CarProject/', rel='alternate')
    fg.language('fr')
    
    toutes = []
    print("🔍 Scraping...")
    for modele in MODELES:
        print(f"  {modele}...")
        time.sleep(1)  # Anti-ban
        ue = scrape_parking(modele)
        jp = scrape_goo(modele)
        for ann in ue + jp:
            score = compute_score(ann)
            if score >= 0.70:
                toutes.append((score, ann))
    
    top = sorted(toutes, key=lambda x: (-x[0], MODELES[x[1]['modele']]['priorite']))[:15]
    print(f"✅ {len(top)} deals qualifiés (top score: {top[0][0] if top else 0})")
    
    for score, ann in top:
        fe = fg.add_entry()
        titre = f"[{ann['modele'].upper()}] {ann['annee']} MT {ann['km']/1000:.0f}k km | {ann['prix_net']:.0f}€ (score {score}) | {ann['pays']}"
        fe.title(titre)
        fe.id(ann['lien'])
        fe.link(href=ann['lien'])
        desc = f"**Prix** : {ann['prix_net']:.0f}€ | **Risque RTI** : {ann['risque_rti']} | **Type** : {ann['type']}\n[Ouvrir]({ann['lien']})"
        fe.description(desc)
        fe.pubDate(datetime.utcnow())
    
    fg.rss_file('jdm-deals-hunter.xml')
    print("📡 RSS généré !")

if __name__ == '__main__':
    generer_rss()
