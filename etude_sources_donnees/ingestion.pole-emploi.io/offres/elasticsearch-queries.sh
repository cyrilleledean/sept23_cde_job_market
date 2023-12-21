#!/bin/bash

#
# romeCode = M1805 (Études et développement informatique)
#
curl --location --request GET 'http://localhost:9200/offres/_search' \
--header 'Content-Type: application/json' \
--data '{
  "query": {
    "match": {
      "romeCode": "M1805"
    }
  }
}'

#
# romeCode = M1805 (Études et développement informatique): nombre de résultats
#
curl --location --request GET 'http://localhost:9200/offres/_count' \
--header 'Content-Type: application/json' \
--data '{
  "query": {
    "match": {
      "romeCode": "M1805"
    }
  }
}'

# {
#     "count": 8645,
#     "_shards": {
#         "total": 1,
#         "successful": 1,
#         "skipped": 0,
#         "failed": 0
#     }
# }