import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    first_line = f.readline()
    data = json.loads(first_line)
    content = data.get('content', '')
    print(f"Content length: {len(content)}")
    idx = content.find('Tier,Application,Vendor')
    if idx != -1:
        csv_data = content[idx:].strip()
        with open('raw_data.csv', 'w', encoding='utf-8') as out:
            out.write(csv_data)
        print(f"Saved raw_data.csv successfully! Lines: {len(csv_data.splitlines())}")
    else:
        print("Tier,Application,Vendor not found in first line")
