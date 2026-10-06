import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        data = json.loads(line)
        c = data.get('content', '')
        if isinstance(c, str):
            print(f"Line {idx}: len={len(c)}, preview={c[:80]!r}")
