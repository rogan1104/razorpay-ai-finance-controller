import json
from pathlib import Path

# Extract dataset from conversation transcript
transcript = Path(r'C:\Users\ADMIN\.gemini\antigravity\brain\202f6ffc-bac2-4a49-aaa7-6366559d54cf\.system_generated\logs\transcript_full.jsonl')
raw_text = ""
with open(transcript, 'r', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('step_index') == 100 or 'transaction_description,category' in obj.get('content', ''):
            c = obj.get('content', '')
            if 'transaction_description,category' in c:
                raw_text = c[c.find('transaction_description,category'):]
                break

if not raw_text:
    # Read from transcript.jsonl if not in full
    transcript2 = Path(r'C:\Users\ADMIN\.gemini\antigravity\brain\202f6ffc-bac2-4a49-aaa7-6366559d54cf\.system_generated\logs\transcript.jsonl')
    with open(transcript2, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            c = obj.get('content', '')
            if 'transaction_description,category' in c:
                raw_text = c[c.find('transaction_description,category'):]
                break

out_path = Path('data/raw/transactions_v2.csv')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(raw_text.strip(), encoding='utf-8')
print(f"Saved transactions_v2.csv with {len(raw_text.strip().splitlines())} lines.")
