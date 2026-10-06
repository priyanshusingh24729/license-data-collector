import json

p = r'C:\Users\priya\.gemini\antigravity-ide\brain\bdf05050-bcef-4048-919d-5021c17710c4\.system_generated\logs\transcript_full.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print(f"Total transcript lines: {len(lines)}")
    # check from the end backwards for USER_INPUT
    for i in range(len(lines)-1, -1, -1):
        obj = json.loads(lines[i])
        if obj.get('type') == 'USER_INPUT':
            c = str(obj.get('content', ''))
            print(f"User input at line {i}, length {len(c)}")
            if 'Tier,Application,Vendor' in c:
                print(f"  Found CSV in line {i}!")
                with open('scratch/exact_user_prompt.csv', 'w', encoding='utf-8') as out:
                    out.write(c[c.find('Tier,Application,Vendor'):])
                print("Wrote scratch/exact_user_prompt.csv!")
                break
