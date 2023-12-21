import requests
import json
import time
from datetime import datetime, timedelta
from threading import Thread

MAX_OFFRES = 3149

def get_secrets():
    with open('./secrets.json') as secrets:
        secrets = json.load(secrets)
    return secrets

def authenticate(app):

    global app_1
    global app_2

    url = 'https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}    

    params = {
        'grant_type': 'client_credentials',
        'scope': 'api_offresdemploiv2 o2dsoffre'
    }

    secrets = get_secrets()

    if app == 'app_1':
        params['client_id'] = secrets.get("client_id_job_market_1")
        params['client_secret'] = secrets.get("client_secret_job_market_1")

    elif app == 'app_2':
        params['client_id'] = secrets.get("client_id_job_market_2")
        params['client_secret'] = secrets.get("client_secret_job_market_2")

    response = requests.post(url=url,data=params,headers=headers)
    response = json.loads(response.text)

    if app == 'app_1':

        app_1 = {
            'access_token': response['access_token'],
            'expire_at': datetime.now() + timedelta(seconds=int(response['expires_in']))
        }

    elif app == 'app_2':

        app_2 = {
            'access_token': response['access_token'],
            'expire_at': datetime.now() + timedelta(seconds=int(response['expires_in']))
        }

def get_referentiel(url, app):

    token = None
    
    if app == 'app_1':
        if datetime.now() >= app_1['expire_at']:
            authenticate(app=app)
        token = app_1['access_token']
    else:
        if datetime.now() >= app_2['expire_at']:
            authenticate(app=app)
        token = app_2['access_token']

    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url=url, headers=headers)
    response.raise_for_status
    response.encoding = 'utf-8'
    return response.text

def index_offres_elasticsearch(response):

    if response.status_code in (200, 206):

        resultats = json.loads(response.text)['resultats']

        if resultats is not None:

            ndjson = []

            for offre in resultats:

                ndjson.append(json.dumps({"index": {"_id": offre['id']}}))
                ndjson.append(json.dumps(offre))

            data = '\n'.join(d for d in ndjson)
            data += '\n'

            headers = {'Content-Type': 'application/x-ndjson'}
            requests.put(url='http://localhost:9200/offres/_bulk', data=data, headers=headers)

def get_nb_total_offres(app):

    token = None
    
    if app == 'app_1':
        if datetime.now() >= app_1['expire_at']:
            authenticate()
        token = app_1['access_token']
    else:
        if datetime.now() >= app_2['expire_at']:
            authenticate()
        token = app_2['access_token']

    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url='https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range=0-5', headers=headers)
    content_range = response.headers['Content-Range']
    total = int(content_range.split(sep=' ')[1].split(sep='/')[1])
    return total

def search(url, app):

    token = None
    
    if app == 'app_1':
        if datetime.now() >= app_1['expire_at']:
            authenticate(app=app)
        token = app_1['access_token']
    else:
        if datetime.now() >= app_2['expire_at']:
            authenticate(app=app)
        token = app_2['access_token']

    headers = {'Authorization': f'Bearer {token}'}

    response = None

    try:

        start, end, total = (0, 0, 0)

        # execution requête
        response = requests.get(url=url,headers=headers)

        while response.status_code == 429: #429 Too Many Requests            
            
            retry_after = response.headers['Retry-After']
            time.sleep(int(retry_after))
            response = requests.get(url=url,headers=headers)     

        if 'Content-Range' in response.headers:

            content_range = response.headers['Content-Range']

            # NB: si aucun résultat content_range == "offres */0 communes"
            if int(content_range.split('/')[1]) == 0:
                start = 0
                end = 0
                total = 0            
            else:
                start = int(content_range.split(sep=' ')[1].split(sep='/')[0].split(sep='-')[0])
                end = int(content_range.split(sep=' ')[1].split(sep='/')[0].split(sep='-')[1])
                total = int(content_range.split(sep=' ')[1].split(sep='/')[1])

        else:
            
            start = 0
            end = 0
            total = 0

            erreur_data = {
                "query": url, 
                "message": "HTTP Header Content-Range absent", 
                "status_code": f"{response.status_code}", 
                "response": f"{response.text}"
            }

            requests.post(url='http://localhost:9200/erreurs/_doc/', data=json.dumps(erreur_data), headers={'Content-Type': 'application/json'})

    except Exception as e:
        
        erreur_data = {
                "query": url, 
                "message": e, 
                "status_code": f"{response.status_code}", 
                "response": f"{response.text}"
        }

        requests.post(url='http://localhost:9200/erreurs/_doc/', data=json.dumps(erreur_data), headers={'Content-Type': 'application/json'})

    finally:

        if response is not None:
            return start, end, total, response
        else:
            return start, end, total, None


def get_offres_region(region, departements, metiers, app):

    start = 0
    end = 149
    total = 0

    code = region["code"]
    libelle = region["libelle"]
   
    url = f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&region={code}"
    start, end, total, response = search(url, app)

    print(f'Début itération région {code} {libelle} - app = {app} total_offres = {total}')

    if total > MAX_OFFRES:

        departements_region = [ d for d in departements if d['region']['code'] == code ]

        for departement in departements_region:
            get_offres_departement(departement, metiers, app)

    else:

        if total > 0:

            index_offres_elasticsearch(response)

            while end < total - 1:

                start += 150
                end += 150

                url = f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&region={code}"
                start, end, total, response = search(url, app)

                index_offres_elasticsearch(response)


def get_offres_departement(departement, metiers, app):

    start = 0
    end = 149
    total = 0

    url=f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&departement={departement['code']}"
    start, end, total, response = search(url, app)

    if total > MAX_OFFRES:

        for metier in metiers:
            get_offres_departement_metier(departement, metier['code'], app)

    else:

        if total > 0:

            index_offres_elasticsearch(response)

            while end < total - 1:

                start += 150
                end += 150

                url=f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&departement={departement['code']}"
                start, end, total, response = search(url, app)

                index_offres_elasticsearch(response)


def get_offres_departement_metier(departement, code_rome, app):

    start = 0
    end = 149
    total = 0
    
    url = f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&departement={departement['code']}&codeROME={code_rome}"
    start, end, total, response = search(url, app)


    if total > MAX_OFFRES:

        print(f"{url.split('?')[1]}: total > MAX_OFFRES !")

    else:

        if total != 0:

            index_offres_elasticsearch(response)

            while end < total - 1:

                start += 150
                end += 150

                url = f"https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search?range={start}-{end}&departement={departement['code']}&codeROME={code_rome}"
                start, end, total, response = search(url, app)

                index_offres_elasticsearch(response)


if __name__ == '__main__':

    authenticate(app='app_1')
    authenticate(app='app_2')

    total_offres_api = get_nb_total_offres(app='app_1')
    debut_total = time.time()
    date_debut = datetime.now()

    print(f"\n\n{date_debut.strftime('%d/%m/%Y %H:%M:%S')}: démarrage collecte de {total_offres_api} offres d'emploi depuis API pole-emploi.io\n\n")

    # Création des index ElasticSearch    

    requests.delete(url=f'http://localhost:9200/offres')
    requests.put(url=f'http://localhost:9200/offres')
    requests.delete(url=f'http://localhost:9200/erreurs')
    requests.put(url=f'http://localhost:9200/erreurs')
    requests.delete(url=f'http://localhost:9200/ingestion')
    requests.put(url=f'http://localhost:9200/ingestion')

    # référentiels (pour itération des offres)

    url_referentiel = 'https://api.pole-emploi.io/partenaire/offresdemploi/v2/referentiel'
    regions = json.loads(get_referentiel(url=f'{url_referentiel}/regions', app='app_1')) #régions
    departements = json.loads(get_referentiel(url=f'{url_referentiel}/departements', app='app_1')) #départements
    communes = json.loads(get_referentiel(url=f'{url_referentiel}/communes', app='app_1')) #communes
    metiers = json.loads(get_referentiel(url=f'{url_referentiel}/metiers', app='app_1')) #métiers (ROME)

    threads = []

    app_switch = 'app_2'
    app = 'app_1'

    for region in regions:
        threads.append(Thread(target=get_offres_region, args=(region, departements, metiers, app)))
        app_switch, app = app, app_switch

    [t.start() for t in threads]
    [t.join() for t in threads]   

    fin_total = time.time()

    hours = int((fin_total - debut_total) // 3600)
    minutes = int((fin_total - debut_total) // 60)

    duree_totale = ('0' + str(hours) if hours < 10 else str(hours)) + ':' + ('0' + str(minutes) if minutes < 10 else str(minutes))

    response_count = requests.get(url='http://localhost:9200/offres/_count')
    response_count_json = json.loads(response_count.text)

    nb_offres = response_count_json['count']

    ingestion_data = {
        "message": "Fin ingestion des offres d'emploi depuis API pole-emploi.io",
        "date_debut": date_debut.strftime('%d/%m/%Y %H:%M:%S'),
        "date_fin": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        "total_offres": total_offres_api,
        "total_offres_collecte": nb_offres,
        "duree_totale": duree_totale
    }

    headers = {'Content-Type': 'application/json'}
    requests.post(url='http://localhost:9200/ingestion/_doc/', data=json.dumps(ingestion_data), headers=headers)

    print(f"\n\n{ingestion_data}\n\n")