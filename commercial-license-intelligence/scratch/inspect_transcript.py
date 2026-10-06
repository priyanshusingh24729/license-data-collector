import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        data = json.loads(line)
        print(f"Index: {i}, keys: {list(data.keys())}, type: {data.get('type')}, source: {data.get('source')}")
        if 'content' in data:
            print(f"  content preview: {str(data['content'])[:100]}...")
