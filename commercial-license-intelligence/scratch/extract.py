import json
import os

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
found = False
with open(p, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        data = json.loads(line)
        content = data.get('content', '')
        if isinstance(content, str) and '360 Extreme Browser' in content:
            idx = content.find('Tier,Application,Vendor')
            if idx != -1:
                csv_data = content[idx:]
                with open('raw_data.csv', 'w', encoding='utf-8') as out:
                    out.write(csv_data)
                print(f"Extracted raw_data.csv, length={len(csv_data)}, lines={len(csv_data.splitlines())}")
                found = True
                break

if not found:
    print("Could not find '360 Extreme Browser' in transcript_full.jsonl")
