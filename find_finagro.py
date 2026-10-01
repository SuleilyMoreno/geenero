import requests

url = "http://api.us.socrata.com/api/catalog/v1"
params = {
    "domains": "www.datos.gov.co",
    "search_context": "www.datos.gov.co",
    "q": "finagro",
    "only": "datasets"
}

res = requests.get(url, params=params).json()
for item in res.get('results', [])[:10]:
    resource = item.get('resource', {})
    print(resource.get('id'), resource.get('name'))
