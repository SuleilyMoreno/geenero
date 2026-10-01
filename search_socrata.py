import requests

url = "http://api.us.socrata.com/api/catalog/v1"
params = {
    "domains": "www.datos.gov.co",
    "search_context": "www.datos.gov.co",
    "q": "finagro"
}

res = requests.get(url, params=params).json()
for item in res.get('results', [])[:5]:
    resource = item.get('resource', {})
    print(resource.get('id'), resource.get('name'))

print("--- superfinanciera ---")
params["q"] = "superfinanciera creditos"
res = requests.get(url, params=params).json()
for item in res.get('results', [])[:5]:
    resource = item.get('resource', {})
    print(resource.get('id'), resource.get('name'))
