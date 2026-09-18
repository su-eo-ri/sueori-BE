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

FIELDS = [
    "title", "alternativeTitle", "subjectCategory", "subjectKeyword",
    "description", "signDescription", "url", "subDescription", "referenceIdentifier",
]

all_items = []
total_count = None
for page in range(1, 40):  # 40 * 100 = 4000, covers 3754
    resp = requests.get(
        "https://api.kcisa.kr/openapi/service/rest/meta13/getCTE01701",
        params={"serviceKey": key, "numOfRows": "100", "pageNo": str(page), "keyword": ""},
        timeout=30,
    )
    root = ET.fromstring(resp.content)
    if total_count is None:
        tc = root.findtext(".//totalCount")
        if tc:
            total_count = int(tc)
            print("totalCount:", total_count)
    items = root.findall(".//item")
    if not items:
        break
    for it in items:
        row = {f: (it.findtext(f) or "").strip() for f in FIELDS}
        all_items.append(row)
    time.sleep(0.15)
    if total_count and len(all_items) >= total_count:
        break

with open("all_items_full.json", "w", encoding="utf-8") as f:
    json.dump(all_items, f, ensure_ascii=False, indent=1)
print("fetched", len(all_items), "items total")
