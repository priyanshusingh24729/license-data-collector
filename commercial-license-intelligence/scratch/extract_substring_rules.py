with open('backend/inventory/detection/detection_normalizer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
end_idx = None
for i, l in enumerate(lines):
    if '# Check third-party publisher strings' in l:
        start_idx = i
    if start_idx and 'return norm' in l and i > start_idx:
        end_idx = i
        break

print(f"Lines {start_idx+1} to {end_idx+1}:")
sub_rules = []
for i in range(start_idx, end_idx):
    l = lines[i].strip()
    if l.startswith('if ') and 'in lower_key' in l:
        # get next non-empty line
        ret_l = lines[i+1].strip()
        print(f"{l}  =>  {ret_l}")
