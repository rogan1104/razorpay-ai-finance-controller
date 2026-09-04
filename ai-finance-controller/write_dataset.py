import base64
import zlib
from pathlib import Path

# We will write the CSV in chunks.
p = Path("data/raw/transactions_v2.csv")
p.parent.mkdir(parents=True, exist_ok=True)
