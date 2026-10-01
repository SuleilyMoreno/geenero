import requests

def print_cols(dataset_id):
    url = f"https://www.datos.gov.co/resource/{dataset_id}.json?$limit=1"
    res = requests.get(url).json()
    if res and isinstance(res, list) and len(res) > 0:
        print(f"Dataset {dataset_id}:")
        print(", ".join(res[0].keys()))
    else:
        print(f"Dataset {dataset_id} empty or not found: {res}")

print_cols("qfm2-wcdf")
print_cols("udzs-3e7r")
print_cols("w9zh-vetq")
