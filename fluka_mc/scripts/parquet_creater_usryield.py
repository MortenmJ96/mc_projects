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
    os.path.join(search_root, "**", "compiled_*_tab.lis"),
    recursive=True,
)
print(f"[INFO] matched {len(files)} files")

# compiled_<secondary>_<EEEE>_<N>_tab.(lis|out|txt)
# secondary may contain hyphens (e.g., 4-helium)
#fname_rx = re.compile(
#    r"^compiled_(?P<secondary>.+?)_(?P<E>\d{4})_(?P<N>\d+)_tab.lis$"
#)
fname_rx = re.compile(
    r"^compiled_(?P<secondary>.+?)_(?P<E>\d{10})_(?P<N>\d+)_tab\.lis$"
)

ANGLE_RX = re.compile(
    r"^(?P<species>.{3})(?P<center>\d+(?:\.\d+)?)(?P<score>[A-Za-z]{3})$"
)
det_header_rx = re.compile(r"^\s*#\s*Detector\s+n:\s*(?P<n>\d+)\s+(?P<name>\S+)")
nint_rx       = re.compile(r"^\s*#\s*N\.\s*of\s*x1\s*intervals\s*(?P<nint>\d+)")

# optional: remap secondary names
REMAP = {
    "4-helium": "alpha",
    # "d": "deuteron",
    # "t": "triton",
    # add others if needed
}

def angle_center_from_det_name(det_name: str) -> float | None:
    s = det_name.strip()

    # 1) Old style: exactly 3 chars + number + 3 letter score, e.g. "4-H50Yld"
    m = ANGLE_RX.match(s)
    if m:
        return float(m.group("center"))

    # 2) New style: letters followed by a number, e.g. "NEUTR60", "PROT172"
    m = re.match(r"^[A-Za-z]+(?P<center>\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group("center"))

    # 3) Generic fallback: take the LAST number appearing anywhere in the name
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if nums:
        return float(nums[-1])

    return None


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

# --- parse angle center from detector name like "4-H5Yld", "4-H50Yld", "4-H150Yld"
ANGLE_RX = re.compile(r"^(?P<species>.{3})(?P<center>\d+(?:\.\d+)?)(?P<score>[A-Za-z]{3})$")

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

    # keep only forts 100..109 , USRYIELD forts
    if not (100 <= fort <= 120):
        continue

    try:
        with open_text_any(pathlib.Path(f)) as fh:
            current_hdr = None  # holds {'det_n','det_name','angle_lower_deg','angle_upper_deg'}

            for line in fh:
                md = det_header_rx.match(line)
                if md:
                    det_n = int(md["n"])
                    det_name = md["name"].strip()

                    center = angle_center_from_det_name(det_name)
                    if center is None:
                        bad.append((name, f"could not parse angle center from '{det_name}'"))
                        current_hdr = None
                        continue

                    # center ±5° edges (change if your bin half-width ≠ 5°)
                    angle_lower = max(0.0, center - 5.0)
                    angle_upper = min(180.0, center + 5.0)

                    current_hdr = {
                        "det_n": det_n,
                        "det_name": det_name,
                        "angle_lower_deg": angle_lower,
                        "angle_upper_deg": angle_upper,
                    }
                    continue

                # skip non-interest lines (your existing regex)
                if nint_rx.match(line):
                    continue
                # data lines (need a current header)
                if current_hdr and line.strip() and not line.lstrip().startswith("#"):
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            if 0:
                                rows.append({
                                    "secondary": secondary,
                                    "primary_energy": primary_energy,
                                    "fort": fort,
                                    "det_n": current_hdr["det_n"],
                                    "det_name": current_hdr["det_name"],
                                    "angle_lower_deg": current_hdr["angle_lower_deg"],
                                    "angle_upper_deg": current_hdr["angle_upper_deg"],
                                    "E_low": float(parts[0]),
                                    "E_high": float(parts[1]),
                                    "Yld": float(parts[2]) * 1000.0,  # keep your original scaling
                                    "rel_err": float(parts[3]),
                                    "source_file": name,
                                })
                            rows.append({
                                "secondary": secondary,
                                "primary_energy": primary_energy,
                                "angle_lower_deg": current_hdr["angle_lower_deg"],
                                "angle_upper_deg": current_hdr["angle_upper_deg"],
                                "E_low": float(parts[0])*1000,
                                "E_high": float(parts[1])*1000,
                                "yld": 0.0 if (int(round(float(parts[3]))) == 99 or (secondary.lower() in ("aproton","aprotons") and float(parts[1])*1000 >= primary_energy*0.95)) else float(parts[2]) * 1e-3,
                                "rel_err": float(parts[3])
                            })
                        except ValueError:
                            bad.append((name, f"malformed numeric row under det_n={current_hdr['det_n']}"))
                            continue

    except Exception as e:
        bad.append((name, repr(e)))


if bad:
    print("[WARN] Issues encountered:")
    for nm, msg in bad[:15]:
        print("   ", nm, "->", msg)
    if len(bad) > 15:
        print(f"   ... and {len(bad)-15} more")

if not rows:
    raise SystemExit("[FATAL] No rows parsed — check paths & patterns.")

df = pd.DataFrame.from_records(rows)

# Ensure expected index columns exist
for col in ["secondary","primary_energy","angle_lower_deg","angle_upper_deg","E_low","E_high"]:
    if col not in df.columns:
        df[col] = pd.NA

index_cols = ["secondary","primary_energy","angle_lower_deg","angle_upper_deg","E_low","E_high"]
df = df.set_index(index_cols).sort_index()

# Save for reuse everywhere
df.to_parquet(f"{base_dir}/{out_name}_usryld.parquet")

all_sp = df.index.get_level_values("secondary").unique()
print(f"All secondaries recorded: {all_sp}")
all_primE = df.index.get_level_values("primary_energy").unique()
print(f"All primary energies recorded: {all_primE}")
print(f"[OK] wrote {out_name} with {len(df)} rows")
