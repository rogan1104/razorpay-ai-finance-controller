import csv
from pathlib import Path

csv_path = Path("data/raw/transactions_v2.csv")
csv_path.parent.mkdir(parents=True, exist_ok=True)
