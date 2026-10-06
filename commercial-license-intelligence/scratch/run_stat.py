import csv
import io
import re

with open('scratch/sanitize_mvp_dataset.py', 'r', encoding='utf-8') as f:
    raw_content = f.read()

idx = raw_content.find('Tier,Application,Vendor')
end_idx = raw_content.find('"""', idx)
csv_text = raw_content[idx:end_idx].strip()

reader = list(csv.DictReader(io.StringIO(csv_text)))
total = len(reader)

noise_rows = 0
duplicates = 0
seen = set()
false_positives = 0
vendor_errors = 0
empty_url_verified = 0
purely_correct = 0

for r in reader:
    app = r.get('Application', '').strip()
    vend = r.get('Vendor', '').strip()
    cls = r.get('Classification', '').strip()
    req = r.get('License Required', '').strip()
    ver = r.get('Version', '').strip()
    ev_stat = r.get('Evidence Status', '').strip()
    ev_url = r.get('Evidence URL', '').strip()

    is_row_flawed = False

    # 1. Duplicates
    key = (vend, app)
    if key in seen:
        duplicates += 1
        is_row_flawed = True
    else:
        seen.add(key)

    # 2. Noise & OS Internals
    if app.startswith(('cr.sb.', '1_https___')) or 'sharepoint.com' in app.lower() or app.endswith(('_cw5n1h2txyewy', '_8wekyb3d8bbwe')):
        noise_rows += 1
        is_row_flawed = True
    elif re.match(r'^[0-9a-fA-F\-]{30,}', app) or app in ('App', 'windows_ie_ac_001') or app.startswith(('MicrosoftWindows.', 'Windows System Component (')):
        noise_rows += 1
        is_row_flawed = True
    elif app.lower().startswith(('lib', 'gir1.2-', 'python3-', 'fonts-', 'linux-headers-', 'linux-image-')):
        noise_rows += 1
        is_row_flawed = True

    # 3. False Positives
    if app in ('Google Docs', 'Google Sheets', 'Google Slides', 'Gmail') and req == 'YES':
        false_positives += 1
        is_row_flawed = True
    elif app == 'Oracle VirtualBox' and req == 'YES':
        false_positives += 1
        is_row_flawed = True

    # 4. Vendor Errors
    if app == 'Gkbd Capplet' and vend == 'Apple Inc.':
        vendor_errors += 1
        is_row_flawed = True
    elif app == 'Photos' and vend == 'Apple Inc.' and '2026.' in ver:
        vendor_errors += 1
        is_row_flawed = True
    elif app == 'ParentalControls' and 'Microsoft' in vend:
        vendor_errors += 1
        is_row_flawed = True

    # 5. Audit gaps
    if ev_stat == 'VERIFIED' and not ev_url:
        empty_url_verified += 1
        is_row_flawed = True

    if not is_row_flawed:
        purely_correct += 1

print(f"Total Rows: {total}")
print(f"Purely Correct Rows: {purely_correct} ({purely_correct/total*100:.2f}%)")
print(f"Noise / Junk Rows: {noise_rows} ({noise_rows/total*100:.2f}%)")
print(f"Duplicate Rows: {duplicates} ({duplicates/total*100:.2f}%)")
print(f"Unsubstantiated VERIFIED (No URL): {empty_url_verified} ({empty_url_verified/total*100:.2f}%)")
print(f"False Positives: {false_positives} ({false_positives/total*100:.2f}%)")
print(f"Vendor Errors: {vendor_errors} ({vendor_errors/total*100:.2f}%)")
