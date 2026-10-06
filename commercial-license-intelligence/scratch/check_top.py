import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for idx in range(3):
        line = f.readline()
        obj = json.loads(line)
        print(f"Line {idx}: keys={list(obj.keys())}")
        for k in obj:
            if k not in ['step_index', 'source', 'type', 'status', 'created_at']:
                print(f"  {k}: type={type(obj[k])}, len={len(str(obj[k]))}")
                # check if 360 in obj[k]
                if '360' in str(obj[k]):
                    print(f"    -> 360 found in {k}!")
