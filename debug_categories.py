import requests

API_URL = "https://www.olx.ua/api/v1/offers"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

def fetch(offset):
    r = requests.get(API_URL, headers=HEADERS, params={"offset": offset, "limit": 50}, timeout=15)
    return r.json().get("data", [])

seen = set()

for off in (0, 50, 100):
    offers = fetch(off)
    for o in offers:
        cat = o.get("category") or {}
        slug = cat.get("slug") or ""
        parent = cat.get("parent") or ""
        seen.add((slug, parent))

print("Found categories:")
for slug, parent in sorted(seen):
    print(f"slug: {slug!r}, parent: {parent!r}")
