import xml.etree.ElementTree as ET
import requests, time, json

env = {}
with open("../../../poc/kcisa_api_poc/.env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

key = env["KCISA_SERVICE_KEY"]

all_items = []
for page in range(1, 13):  # up to ~1200 items
    resp = requests.get(
        "https://api.kcisa.kr/openapi/service/rest/meta13/getCTE01701",
        params={"serviceKey": key, "numOfRows": "100", "pageNo": str(page), "keyword": ""},
        timeout=30,
    )
    root = ET.fromstring(resp.content)
    items = root.findall(".//item")
    if not items:
        break
    for it in items:
        title = (it.findtext("title") or "").strip()
        sub = (it.findtext("subDescription") or "").strip()
        ref = (it.findtext("referenceIdentifier") or "").strip()
        if sub.lower().endswith(".mp4"):
            all_items.append({"title": title, "mp4": sub, "thumb": ref})
    time.sleep(0.2)

with open("all_items.json", "w", encoding="utf-8") as f:
    json.dump(all_items, f, ensure_ascii=False, indent=1)
print("fetched", len(all_items), "items with mp4")
