from bs4 import BeautifulSoup as bs
import requests
import csv
import time
from threading import Thread
import pandas as pd

linkedin_jobs = []

def pole_emploi():

    print('pole_emploi')


def indeed():
    print('indeed')

def scrap_job_detail(job_id: str):

    csv = "jobs-details.csv"

    job = {}

    print(f'\n\nscrap_job_detail {job_id}')

    url = f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}'
    page = requests.get(url)
    bs_page = bs(page.content, "lxml")

    try:

        titre = bs_page.find('a', attrs={'data-tracking-control-name': 'public_jobs_topcard-title'}).find('h2')
        entreprise = bs_page.find('a', attrs={'data-tracking-control-name': 'public_jobs_topcard-org-name'})

        job['titre'] = titre.text.strip() if titre is not None else None
        job['entreprise'] = entreprise.text.strip() if entreprise is not None else None

        return job

    except (Exception) as exception:
        #print(bs_page.prettify().splitlines())
        return None

def traiter_page(url):

    count = 0

    page = requests.get(url)
    bs_page = bs(page.content, "lxml")

    items = bs_page.find_all('li')
    
    for item in items:
        
        job = {}

        job_id = None
        html_titre = None
        html_location = None
        html_entreprise = None

        # principalement <div /> mais parfois <a /> ....
        element_metadata = item.select_one('.base-search-card, .job-search-card')
        
        if element_metadata is not None:

            if 'data-entity-urn' in element_metadata.attrs:

                if element_metadata.attrs['data-entity-urn'] is not None:
                    job_id = element_metadata.attrs['data-entity-urn'].split(':')[-1]

                html_location = element_metadata.select_one('.job-search-card__location')
                location = html_location.text.replace("\n","")
                location = location.replace(',','|').replace(' ','')
                

                html_titre = element_metadata.select_one('.base-search-card__title')
                titre = html_titre.text.replace("\n","")
                titre = titre.replace(","," ")
                titre = titre.strip()

                html_entreprise = element_metadata.select_one('.base-search-card__subtitle')
                entreprise = None

                if html_entreprise.find('a') is not None:
                    entreprise = html_entreprise.find('a').text
                else:
                    entreprise = html_entreprise.text

                entreprise = entreprise.replace("\n","")
                entreprise = entreprise.strip()
                entreprise = entreprise.replace(","," ")
                            
                job['job_id'] = job_id
                job['location'] = location
                job['entreprise'] = entreprise
                job['titre'] = titre

                linkedin_jobs.append(job)
                count += 1
            else:
                print('attribut data-entity-urn manquant !')         
        else:
            print('element_metadata manquant !')

    print(f"Page {url}: {count}/{len(items)}")


def traiter_pages(urls):        

    debut = time.time()

    threads = [Thread(target=traiter_page, args=(url,)) for url in urls]

    # start the threads
    [t.start() for t in threads]

    # wait for the threads to complete
    [t.join() for t in threads]

    fin = time.time()    

    return fin-debut

if __name__ == '__main__':

    LOCATION = 'France'
    NB_PAGE_SIMULTANEE = 10

    urls = []
    start = 0
    

    for i in range(1, NB_PAGE_SIMULTANEE):
        urls.append(f'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=&location={LOCATION}&start={start}')
        start += 25

    temps = traiter_pages(urls)

    df = pd.DataFrame(linkedin_jobs)
    df.to_csv(f"csv/linkedin-jobs.csv", header=True, index=0, mode='a')

    linkedin_jobs = []
    urls = []

    print(f"terminé en {temps}s")


    for i in range(1, NB_PAGE_SIMULTANEE):
        urls.append(f'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=&location={LOCATION}&start={start}')
        start += 25

    temps = traiter_pages(urls)

    df = pd.DataFrame(linkedin_jobs)
    df.to_csv(f"csv/linkedin-jobs.csv", header=True, index=0, mode='a')

    linkedin_jobs = []
    urls = []

    print(f"terminé en {temps}s")

