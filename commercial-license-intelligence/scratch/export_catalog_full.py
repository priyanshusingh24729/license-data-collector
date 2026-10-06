import csv
import re
from collections import defaultdict

with open('data/mvp_4169_full_license_intelligence.csv', 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Group by (Vendor, Application)
grouped = defaultdict(lambda: {
    "Tier": "",
    "Application": "",
    "Vendor": "",
    "Versions": set(),
    "Install Count": 0,
    "Classification": "",
    "License Required": "",
    "License Model": "",
    "Confidence": "",
    "Evidence Status": "",
    "Evidence URL": "",
    "Hostnames": set()
})

for r in rows:
    app = r["Application"].strip()
    vend = r["Vendor"].strip()
    key = (vend, app)
    g = grouped[key]
    g["Tier"] = r["Tier"]
    g["Application"] = app
    g["Vendor"] = vend
    g["Classification"] = r["Classification"]
    g["License Required"] = r["License Required"]
    g["License Model"] = r["License Model"]
    g["Confidence"] = r["Confidence"]
    g["Evidence Status"] = r["Evidence Status"]
    if r["Evidence URL"] and not g["Evidence URL"]:
        g["Evidence URL"] = r["Evidence URL"]
    if r["Version"] and r["Version"] != "N/A":
        g["Versions"].add(r["Version"])
    g["Install Count"] += 1
    if r["Hostname"] and r["Hostname"] != "N/A":
        g["Hostnames"].add(r["Hostname"])

catalog_rows = []
for (vend, app), data in sorted(grouped.items(), key=lambda x: (x[1]["Tier"], x[0][1])):
    sorted_v = sorted(list(data["Versions"]))
    if not sorted_v:
        ver_str = "N/A"
    elif len(sorted_v) <= 3:
        ver_str = "; ".join(sorted_v)
    else:
        ver_str = f"{sorted_v[0]}; {sorted_v[1]} (+{len(sorted_v)-2} more)"

    catalog_rows.append({
        "Tier": data["Tier"],
        "Canonical Product": app,
        "Vendor / Publisher": vend,
        "Installed Version(s)": ver_str,
        "Install Count": data["Install Count"],
        "Classification": data["Classification"],
        "License Required": data["License Required"],
        "Licensing Model": data["License Model"],
        "Confidence": data["Confidence"],
        "Evidence Status": data["Evidence Status"],
        "Evidence URL": data["Evidence URL"],
        "Machine Count": len(data["Hostnames"]) or 1
    })

out_path = 'data/mvp_canonical_catalog_full.csv'
with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(catalog_rows[0].keys()))
    writer.writeheader()
    writer.writerows(catalog_rows)

print(f"Saved {out_path} with {len(catalog_rows)} canonical applications.")
