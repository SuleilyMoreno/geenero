import requests

url = "http://api.us.socrata.com/api/catalog/v1"
params = {
    "domains": "www.datos.gov.co",
    "search_context": "www.datos.gov.co",
    "q": "superfinanciera",
    "only": "datasets"
}

res = requests.get(url, params=params).json()
for item in res.get('results', [])[:10]:
    resource = item.get('resource', {})
    ds_id = resource.get('id')
    print(ds_id, resource.get('name'))
    
    # get columns
    url_cols = f"https://www.datos.gov.co/resource/{ds_id}.json?$limit=1"
    try:
        cols_res = requests.get(url_cols).json()
        if cols_res and isinstance(cols_res, list) and len(cols_res) > 0:
            print("   Cols:", ", ".join(cols_res[0].keys()))
    except:
        pass
