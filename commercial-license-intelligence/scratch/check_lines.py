import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for idx, l in enumerate(f):
        if idx in [28, 32, 35]:
            obj = json.loads(l)
            print(f"Line {idx}:")
            print(json.dumps(obj, indent=2)[:500])
