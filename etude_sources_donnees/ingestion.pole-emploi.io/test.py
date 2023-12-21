import json
import requests

if __name__ == '__main__':

    response = requests.get(url='http://localhost:9200/offres/_count')
    response_json = json.loads(response.text)

    print(response_json['count'])