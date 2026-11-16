"""Download the public NHANES files used by train_menopause.py into data/raw/ (not committed)."""
from pathlib import Path
from urllib.request import Request, urlopen

RAW = Path(__file__).parent / "data" / "raw"
CYCLES = {"2013": "H", "2015": "I", "2017": "J"}
FILES = ["RHQ", "DEMO", "BMX", "SMQ"]

RAW.mkdir(parents=True, exist_ok=True)
for year, c in CYCLES.items():
    for f in FILES:
        dest = RAW / f"{f}_{c}.XPT"
        if dest.exists():
            continue
        url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{f}_{c}.XPT"
        print("Downloading", url)
        dest.write_bytes(urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read())
print("Done:", sorted(p.name for p in RAW.glob("*.XPT")))
