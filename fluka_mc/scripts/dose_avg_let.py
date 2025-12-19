import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse

ap = argparse.ArgumentParser(description="Calculate dose avg LET from usrbin and usrtrack scoring.")
ap.add_argument("--track", required=True, help="Path to usrtrack parquet")
ap.add_argument("--bin", required=True, help="Path to usrbin parquet")
ap.add_argument("--V", type=float, default=(0.5E-3)**2*1E2, help="detector volume (cm^3) if you want to use it")
ap.add_argument("--pe", type=float, required=True, help="Target primary_energy value (must match parquet units)")
ap.add_argument("--pe-tol", type=float, default=0.0, help="Absolute tolerance for matching primary_energy (0 = exact)")
args = ap.parse_args()

track_path = args.track
bin_path = args.bin
PE_targ = args.pe
PE_tol = args.pe_tol

# Your current hardcoded detector setup (kept as-is)
#det_vol = (0.5E-3)**2 * 1e2   # <- your existing value
det_vol = args.V
det_rho = 1.4

track_pd = pd.read_parquet(track_path)
bin_pd = pd.read_parquet(bin_path)

def filter_primary_energy(df: pd.DataFrame, pe: float, tol: float) -> pd.DataFrame:
    # If primary_energy is an index level (your case), use IndexSlice
    if isinstance(df.index, pd.MultiIndex) and "primary_energy" in df.index.names:
        pe_vals = df.index.get_level_values("primary_energy").astype(float)
        if tol > 0:
            mask = np.abs(pe_vals - pe) <= tol
        else:
            mask = pe_vals == pe
        return df[mask]

    # Else if it's a column
    if "primary_energy" in df.columns:
        pe_vals = pd.to_numeric(df["primary_energy"], errors="coerce").astype(float)
        if tol > 0:
            return df[np.abs(pe_vals - pe) <= tol]
        return df[pe_vals == pe]

    raise ValueError("primary_energy not found as index level or column")

# Filter both inputs to the chosen primary energy
track_pd = filter_primary_energy(track_pd, PE_targ, PE_tol)
bin_pd   = filter_primary_energy(bin_pd,   PE_targ, PE_tol)

if track_pd.empty or bin_pd.empty:
    raise ValueError(f"No rows left after filtering to primary_energy={PE_targ} (tol={PE_tol}).")

# Grouping (these are index levels in your parquet)
g_bin   = dict(tuple(bin_pd.groupby(level=["secondary", "primary_energy"])))
g_track = dict(tuple(track_pd.groupby(level=["secondary", "primary_energy"])))

S_per_sec = {}

# Single track average, but now only for the selected primary energy
for k in (g_bin.keys() & g_track.keys()):
    sp, pe = k

    dose_val = float(g_bin[k]["dose"].iloc[0])  # dose is a column in bin_pd
    E_dep = dose_val * det_vol                  # (MeV * cm^-3) * cm^3 -> MeV

    track_sum = float(np.sum(g_track[k]["yld"]))  # yld is a column in track_pd
    L_p = track_sum * det_vol                      # cm

    if L_p != 0.0:
        S_p = E_dep / L_p           # MeV/cm
        LET_p = S_p / det_rho # MeV * cm^2/g
    else:
        S_p, S_LET, LET_p = 0.0, 0.0, 0.0

    print(f"{pe}MeV,{sp}: E_dep:{E_dep:<10g}MeV, L_p:{L_p:<10g}cm, LET_p:{LET_p:<10g}")
    S_per_sec[sp] = S_p
