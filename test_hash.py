import json
import httpx
import time

def fetch_and_clean():
    resp = httpx.get("http://127.0.0.1:8014/api/plazas_status")
    data = resp.json()["plazas"]
    for p in data:
        for a in p.get("agents", []):
            a.pop("last_active", None)
            a.pop("login_history", None)
    return data

if __name__ == "__main__":
    d1 = fetch_and_clean()
    time.sleep(3)
    d2 = fetch_and_clean()
    if json.dumps(d1) != json.dumps(d2):
        print("Differences found!")
        print(d1 == d2) # Deep equality check
    else:
        print("No differences.")
