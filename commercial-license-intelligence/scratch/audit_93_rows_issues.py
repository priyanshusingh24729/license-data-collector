import sqlite3
import pandas as pd

conn = sqlite3.connect('data/license_intelligence.db')
cursor = conn.cursor()
cursor.execute("SELECT upload_id FROM inventory_uploads WHERE file_name LIKE '%PF490A36%' ORDER BY created_at DESC LIMIT 1")
upload_id = cursor.fetchone()[0]

query = f"""
    SELECT row_index, raw_application, raw_vendor, raw_version, canonical_product, canonical_vendor,
           classification, license_required, license_model, metric, conflict_status, consensus_status, override_reason
    FROM upload_license_results
    WHERE upload_id = '{upload_id}'
    ORDER BY row_index ASC
"""
df = pd.read_sql_query(query, conn)

print(f"Loaded {len(df)} rows for {upload_id}")

issues = []
for idx, r in df.iterrows():
    row_no = r['row_index']
    app = str(r['raw_application'])
    cls_ = str(r['classification'])
    req = str(r['license_required'])
    model = str(r['license_model'])
    metric = str(r['metric'])
    canon = str(r['canonical_product'])

    issue_reasons = []

    # Issue type 1: Contradiction - Non-commercial software requiring license
    if cls_ in ('FREEWARE', 'OPEN_SOURCE', 'OS_BUNDLED', 'OEM_OR_BUNDLED', 'COMMERCIAL_COMPONENT') and req == 'YES':
        issue_reasons.append(f"Non-commercial ({cls_}) marked as License Required = YES")

    # Issue type 2: Contradiction - Commercial software marked as License Required = NO
    if cls_ == 'COMMERCIAL' and req == 'NO':
        issue_reasons.append(f"Commercial software marked as License Required = NO")

    # Issue type 3: FREE_AND_PAID marked as License Required = NO in enterprise audit
    if cls_ == 'FREE_AND_PAID' and req == 'NO':
        issue_reasons.append(f"Dual-use / Freemium (FREE_AND_PAID) marked as License Required = NO (under-licensing compliance risk for client)")

    # Issue type 4: Bad canonical product
    if canon in ('Microsoft', 'Unknown', 'None', '') or canon == app and 'Setup' in app:
        if app == 'Power BI Desktop' and canon == 'Microsoft':
            issue_reasons.append(f"Canonical product is '{canon}' instead of 'Power BI Desktop'")

    # Issue type 5: Metric mismatch
    if req == 'NO' and metric not in ('No license required', 'No License Required', '', 'None'):
        issue_reasons.append(f"License Required = NO but Metric is '{metric}' instead of 'No license required'")
    if req == 'YES' and metric in ('No license required', 'No License Required'):
        issue_reasons.append(f"License Required = YES but Metric is '{metric}'")

    # Issue type 6: Incorrect license model
    if app == 'Power BI Desktop' and 'Per Core' in model:
        issue_reasons.append(f"Power BI Desktop incorrectly licensed as 'Commercial — Per Core'")

    if issue_reasons:
        issues.append({
            "row": row_no,
            "app": app,
            "classification": cls_,
            "license_required": req,
            "metric": metric,
            "model": model,
            "issues": " | ".join(issue_reasons)
        })

print(f"\nTotal problematic rows identified: {len(issues)} out of {len(df)}\n")
for iss in issues:
    print(f"Row {iss['row']:2d}: {iss['app'][:32]:32s} [{iss['classification']}] Req={iss['license_required']} | {iss['issues']}")
