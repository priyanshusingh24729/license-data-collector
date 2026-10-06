import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    line0 = f.readline()
    data = json.loads(line0)
    print("line 0 type:", type(data), "keys:", data.keys())
    print("content length:", len(data.get('content', '')))
