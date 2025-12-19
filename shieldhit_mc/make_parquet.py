#!/usr/bin/env python3
import pandas as pd, pathlib, os, argparse
import numpy as np
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser(description="Write Pandas parquet from convertmc .dat output.")
ap.add_argument("--dir", default="output", help="Path to directory with .dat files")
ap.add_argument("--eb", default=3.5, help="Energy bin width", type=float)
ap.add_argument("--ab", default=45, help="Number of angular bins", type=int)
ap.add_argument("--out", default="~/repos/grendel/projects/parquets/po16_shieldhit.parquet",
                help="Output parquet path")
args = ap.parse_args()

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(args.dir)
eb = float(args.eb) / 2.0
ab = int(180 / int(args.ab))

files = list(root.rglob("*.dat"))
print(f"[INFO] matched {len(files)} .dat files under {root}")
if not files:
    raise SystemExit("[FATAL] No .dat files matched – check paths & patterns.")

# filename patterns:
#   <E>_<secondary>.dat
#   <E>_<secondary>_<cycle>.dat   (cycle is integer)
fname_rx = re.compile(r"^(?P<E>[^_]+)_(?P<secondary>.+?)(?:_(?P<cycle>\d+))?\.dat$")

REMAP = {
    "he4": "alpha",
    "pro": "proton",
    "deu": "deuteron",
    "tri": "triton",
    "neu": "neutron",
    "pho": "photon",
}

rows, bad = [], []

for f in files:
    path = pathlib.Path(f)
    name = path.name

    m = fname_rx.match(name)
    if not m:
        bad.append((name, "filename pattern mismatch"))
        continue

    secondary_raw = m["secondary"].lower()
    secondary = REMAP.get(secondary_raw, secondary_raw)

    primary_energy_str = m["E"]
    try:
        primary_energy = float(primary_energy_str)
    except ValueError:
        bad.append((name, f"could not parse primary energy from '{primary_energy_str}'"))
        continue

    cycle = int(m["cycle"]) if m["cycle"] is not None else 0  # 0 means "single/unknown cycle"

    try:
        df_local = pd.read_csv(
            path,
            sep=r"\s+",
            header=None,
            names=["E_sec", "angle_deg", "yld"],
            engine="python",
        )
    except Exception as e:
        bad.append((name, f"read_csv failed: {e!r}"))
        continue

    # Apply your per-row transforms per *cycle* before aggregation
    for _, r in df_local.iterrows():
        try:
            E_sec = float(r["E_sec"])
            angle = float(r["angle_deg"])
            yld = float(r["yld"])

            yld_adj = 0.0 if (secondary.lower() in ("proton",) and E_sec >= primary_energy * 0.90 and angle <= 4) else yld * 10.0

            rows.append(
                {
                    "cycle": cycle,
                    "secondary": secondary,
                    "primary_energy": primary_energy,
                    "angle_lower_deg": angle - ab / 2,
                    "angle_upper_deg": angle + ab / 2,
                    "E_low": E_sec - eb,
                    "E_high": E_sec + eb,
                    "yld": yld_adj,
                }
            )
        except ValueError:
            bad.append((name, "malformed numeric row"))
            continue

if bad:
    print("[WARN] Issues encountered:")
    for nm, msg in bad[:15]:
        print("   ", nm, "->", msg)
    if len(bad) > 15:
        print(f"   ... and {len(bad)-15} more")

if not rows:
    raise SystemExit("[FATAL] No rows parsed — check paths & patterns.")

df = pd.DataFrame.from_records(rows)

index_cols = ["secondary", "primary_energy",
              "angle_lower_deg", "angle_upper_deg",
              "E_low", "E_high"]

# Aggregate over cycles per bin
g = df.groupby(index_cols, sort=True)

mean_yld = g["yld"].mean()
n = g["yld"].count()

# sample std over cycles (ddof=1). For n==1 -> NaN
std = g["yld"].std(ddof=1)

# standard error of the mean
sem = std / np.sqrt(n)

rel_err = sem / mean_yld.abs()
rel_err = rel_err.where(n > 1, np.nan)  # match FLUKA-style: undefined for single cycle

out = pd.DataFrame({"yld": mean_yld, "rel_err": rel_err})
out.index = out.index.set_names(index_cols)
out = out.sort_index()

out_path = os.path.expanduser(args.out)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
out.to_parquet(out_path)

# small info printout
num_bins = len(out)
num_groups = g.ngroups
print(f"[OK] wrote {out_path}")
print(f"[INFO] bins: {num_bins}, grouped bins: {num_groups}, cycle-averaged: yes")
