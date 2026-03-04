import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import schedule, time
from datetime import datetime
YEN_TO_EUR = 1/180  # Ton taux fixe

# Prix marché moyens (de tes convos + sources)
MODELES = {
    'eclipse_gsx': {'priorite':1, 'prix_moyen_ue':22000, 'chassis':'1G2MB35B*'},
    'gtr_r32': {'priorite':2, 'prix_moyen_ue':40000, 'chassis':'BNR32'},
    'evo_vii': {'priorite':3, 'prix_moyen_ue':25000, 'chassis':'CT9A'},
    'gtr_r34': {'priorite':4, 'prix_moyen_ue':120000, 'chassis':'BNR34'},
    'gtr_r33': {'priorite':5, 'prix_moyen_ue':60000, 'chassis':'BCNR33'},
    'supra_mkiv': {'priorite':6, 'prix_moyen_ue':45000, 'chassis':'JZA80'}
}

def scrape_source(url_base, modele):
    # Ex scrape theparking.eu
    params = {'make':'Toyota', 'model':'Supra', 'gear':'manual', 'km_max':150000}  # Par modèle
    resp = requests.get(url_base.format(modele), params=params)
    soup = BeautifulSoup(resp.text, 'html.parser')
    annonces = []
    for item in soup.find_all('div', class_='annonce'):
        prix = float(item.find('span', class_='price').text.replace('€',''))
        km = int(item.find('span', 'km').text.replace('km',''))
        if prix > 25000 or km > 150000: continue  # Budget UE
        # Parse état, CT mention, etc.
        annonces.append({'prix_net':prix, 'km':km, 'lien':item.a['href'], 'pays':'FR', 'type':'UE'})
    return annonces

def calcul_ptrf(annonce_japon):
    prix_y = annonce_japon['prix_yen']
    achat_eur = prix_y * YEN_TO_EUR
    fret_port = 3000
    douane = achat_eur * 0.10
    tva = (achat_eur + douane) * 0.20
    rti = 4500 + 150
    return achat_eur + fret_port + douane + tva + rti

def compute_score(annonce, modele):
    qualite = (1 - annonce['km']/150000) * (1 - (2026 - annonce['annee'])/30)
    prix_relatif = min(annonce['prix_net'] / MODLES[modele]['prix_moyen_ue'], 1)
    risque = 1.0  # Ajuste -0.2 si mods risquées, +0.1 proximité Sud FR
    return (qualite / prix_relatif) * risque

def generer_rss():
    fg = FeedGenerator(title='JDM Deals Hunter', link='ton-site.com/rss')
    toutes_annonces = []
    # Scrape toutes sources
    for modele in MODLES:
        ue_ann = scrape_source('https://theparking.eu/used-cars/{}.html'.format(modele), modele)
        jp_ann = scrape_source('https://goo-net-exchange.com/{}/'.format(modele), modele)
        for ann in ue_ann + jp_ann:
            if 'japon' in ann['type']: ann['prix_net'] = calcul_ptrf(ann)
            if ann['prix_net'] > (20000 if 'japon' in ann['type'] else 25000): continue
            score = compute_score(ann, modele)
            if score >= 0.70:
                toutes_annonces.append((score, ann, modele))
    # Trier par score desc, priorite
    top_ann = sorted(toutes_annonces, key=lambda x: (x[0], -MODLES[x[2]]['priorite']))[:20]
    for score, ann, mod in top_ann:
        fe = fg.add_entry()
        fe.title(f"[{mod.upper()}] {ann['annee']} MT {ann['km']}km - {ann['prix_net']:.0f}€ (score {score:.2f})")
        fe.link(href=ann['lien'])
        fe.description(f"...")  # Détails + risques
    fg.rss_file('jdm-deals-hunter.xml')

# Scheduler
schedule.every().day.at("08:00").do(generer_rss)  # Quotidien
schedule.every(1).hours.do(lambda: generer_rss() if check_top_deal() else None)  # Horaire si >=0.95

while True:
    schedule.run_pending()
    time.sleep(1)
