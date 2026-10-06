import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for line_idx, line in enumerate(f):
        if '360 Extreme Browser' in line:
            print(f"Found on line {line_idx}, line length: {len(line)}")
            obj = json.loads(line)
            # Find which key contains it
            for k, v in obj.items():
                if '360 Extreme Browser' in str(v):
                    print(f"  Key: {k}, type: {type(v)}, len: {len(str(v))}")
                    if k == 'content' or (k == 'tool_calls'):
                        pass
