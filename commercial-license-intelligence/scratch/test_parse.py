import csv
import json
import re

# Read the raw text from the prompt stored in transcript
p_full = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'

# Let's find the exact prompt in transcript_full or transcript
raw_lines = []
with open(p_full, 'r', encoding='utf-8') as f:
    for line in f:
        if '360 Extreme Browser' in line:
            # Let's extract
            d = json.loads(line)
            # search in all string fields
            def find_csv(obj):
                if isinstance(obj, str) and 'Tier,Application,Vendor' in obj:
                    return obj[obj.find('Tier,Application,Vendor'):]
                if isinstance(obj, dict):
                    for v in obj.values():
                        res = find_csv(v)
                        if res: return res
                if isinstance(obj, list):
                    for item in obj:
                        res = find_csv(item)
                        if res: return res
                return None
            res = find_csv(d)
            if res:
                raw_lines = res.splitlines()
                print(f"Extracted {len(raw_lines)} CSV lines from transcript!")
                break

print(f"Total raw lines: {len(raw_lines)}")
