# data_collector.py
import pandas as pd, re, glob, pathlib, gzip
from decimal import Decimal  # optional, but nice for exact decimals
import os
import argparse

ap = argparse.ArgumentParser(description="Write Pandas parquet from compiled fluka output.")
ap.add_argument("--dir", default="output", help="Path to FLUKA compiled data")
args = ap.parse_args()

root = args.dir  # Data directory
out_name = args.dir # Parquet naming
base_dir = os.path.expanduser("~/repos/grendel/projects/fluka_mc")
files = []
print(f"Looking up data dir: {base_dir}/{root}")
search_root = os.path.join(base_dir, root)
files = []
files += glob.glob(
    os.path.join(search_root, "**", "compiled_*.ascii"),
    recursive=True,
)
print(f"[INFO] matched {len(files)} files")

# compiled_<secondary>_<EEEE>_<N>_tab.(lis|out|txt)
# secondary may contain hyphens (e.g., 4-helium)

fname_rx = re.compile(
    r"^compiled_(?P<secondary>.+?)_(?P<E>\d{10})_(?P<N>\d+)\.ascii$"
)

#det_header_rx = re.compile(r"^\s*#\s*Detector\s+n:\s*(?P<n>\d+)\s+(?P<name>\S+)")
#nint_rx       = re.compile(r"^\s*#\s*N\.\s*of\s*x1\s*intervals\s*(?P<nint>\d+)")

track_len_rx = re.compile(r"^\s*this\s*is\s*a\s*track-length\s*binning\n*\s(?P<track_len>f+)")

# optional: remap secondary names
REMAP = {
    "4-helium": "alpha",
    # "d": "deuteron",
    # "t": "triton",
    # add others if needed
}


def open_text_any(path: pathlib.Path):
    with open(path, "rb") as probe:
        if probe.read(2) == b"\x1f\x8b":
            return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return open(path, "r", encoding=enc)
        except UnicodeDecodeError:
            continue
    return open(path, "r", encoding="utf-8", errors="replace")

rows, bad,headers = [], [],[]

import re, pathlib

rows, bad = [], []

for f in files:
    name = pathlib.Path(f).name
    m = fname_rx.match(name)
    
    if not m:
        bad.append((name, "filename pattern mismatch"))
        continue

    secondary_raw = m["secondary"].lower()
    secondary = REMAP.get(secondary_raw, secondary_raw)
    primary_energy_tag = m["E"]
    primary_energy_eV = int(primary_energy_tag)
    primary_energy = float(Decimal(primary_energy_eV)/Decimal("1e6"))
    fort = int(m["N"])
    
    if not (60 <= fort < 80):
        continue
    with open_text_any(pathlib.Path(f)) as fh:
        current_hdr = None  # holds {'det_n','det_name'}
        rl,rel_err=0,0
        for i,line in enumerate(fh):
            #print(i,line)
            if i==10:
                dose = float(line)
            if i==14: 
                rel_err = float(line)
        try:
            rows.append({
                "secondary": secondary,
                "primary_energy": primary_energy,
                "dose": dose,
                "rel_error": rel_err,
            })
        except ValueError:
            bad.append((name, f"malformed numeric row under det_n={current_hdr['det_n']}"))
            continue

    #except Exception as e:
    #    bad.append((name, repr(e)))


if bad:
    print("[WARN] Issues encountered:")
    #for nm, msg in bad[:15]:
    for nm, msg in bad:
        print("   ", nm, "->", msg)
    #if len(bad) > 15:
    #    print(f"   ... and {len(bad)-15} more")

if not rows:
    raise SystemExit("[FATAL] No rows parsed — check paths & patterns.")

df = pd.DataFrame.from_records(rows)

# Ensure expected index columns exist
for col in ["secondary","primary_energy"]:
    if col not in df.columns:
        df[col] = pd.NA

index_cols = ["secondary","primary_energy"]
df = df.set_index(index_cols).sort_index()

# Save for reuse everywhere
df.to_parquet(f"{base_dir}/{out_name}_usrbin.parquet")

all_sp = df.index.get_level_values("secondary").unique()
print(f"All secondaries recorded: {all_sp}")
all_primE = df.index.get_level_values("primary_energy").unique()
print(f"All primary energies recorded: {all_primE}")
print(f"[OK] wrote {out_name} with {len(df)} rows")
