#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from matplotlib.colors import LogNorm
    _HAS_LOGNORM = True
except Exception:
    _HAS_LOGNORM = False


def safe_slug(s: str) -> str:
    return "".join(c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in s).strip("_")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def heatmap_for_secondary(df_s: pd.DataFrame, sec: str, outdir: Path, title_prefix: str, use_log: bool) -> None:
    # Bin midpoints
    df_s = df_s.copy()
    df_s["angle_mid"] = 0.5 * (df_s["angle_lower_deg"] + df_s["angle_upper_deg"])
    df_s["E_mid"] = 0.5 * (df_s["E_low"] + df_s["E_high"])

    pivot = df_s.pivot_table(
        index="E_mid",
        columns="angle_mid",
        values="yld",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index(axis=0).sort_index(axis=1)

    Z = pivot.to_numpy()
    energies = pivot.index.to_numpy()
    angles = pivot.columns.to_numpy()

    # Plot (x=angle, y=energy)
    fig, ax = plt.subplots(figsize=(10, 6))
    if use_log:
        zpos = Z[Z > 0]
        vmin = float(np.nanmin(zpos)) if zpos.size else 1e-30
        norm = LogNorm(vmin=vmin, vmax=float(np.nanmax(Z)) if np.nanmax(Z) > 0 else 1.0)
        im = ax.imshow(
            Z,
            aspect="auto",
            origin="lower",
            extent=[angles.min(), angles.max(), energies.min(), energies.max()],
            norm=norm,
        )
    else:
        im = ax.imshow(
            Z,
            aspect="auto",
            origin="lower",
            extent=[angles.min(), angles.max(), energies.min(), energies.max()],
        )

    ax.set_xlabel("Angle mid (deg)")
    ax.set_ylabel(f"Secondary energy (MeV)")
    ax.set_title(f"{title_prefix} | {sec} | heatmap (yld)")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("yld")

    fname = outdir / f"heatmap_{safe_slug(sec)}.png"
    fig.tight_layout()
    fig.savefig(fname, dpi=200)
    plt.close(fig)


def angle_integrated_spectra(df_e: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    # Integrate over angle bins: sum(yld * dAngle)
    df = df_e.copy()
    df["E_mid"] = (0.5 * (df["E_low"] + df["E_high"]))*1000
    df["dA_deg"] = (df["angle_upper_deg"] - df["angle_lower_deg"]).astype(float)

    g = (
        df.groupby(["secondary", "E_mid"], as_index=False)
          .apply(lambda x: pd.Series({"y_angle_int": float(np.sum(x["yld"] * x["dA_deg"]))}))
          .reset_index(drop=True)
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    for sec, d in g.groupby("secondary"):
        d = d.sort_values("E_mid")
        ax.plot(d["E_mid"], d["y_angle_int"], label=str(sec))

    ax.set_xlabel("Secondary energy mid (KeV)")
    ax.set_ylabel("Angle-integrated yield (sum(yld * dAngle_deg))")
    ax.set_title(f"{title_prefix} | angle-integrated spectra")
    ax.set_yscale("log")
    ax.legend(ncols=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "angle_integrated_spectra.png", dpi=200)
    plt.close(fig)


def energy_integrated_angles(df_e: pd.DataFrame, outdir: Path, title_prefix: str) -> None:
    # Integrate over energy bins: sum(yld * dE)
    df = df_e.copy()
    df["angle_mid"] = 0.5 * (df["angle_lower_deg"] + df["angle_upper_deg"])
    df["dE_MeV"] = (df["E_high"] - df["E_low"]).astype(float)

    g = (
        df.groupby(["secondary", "angle_mid"], as_index=False)
          .apply(lambda x: pd.Series({"y_energy_int": float(np.sum(x["yld"] * x["dE_MeV"]))}))
          .reset_index(drop=True)
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    for sec, d in g.groupby("secondary"):
        d = d.sort_values("angle_mid")
        ax.plot(d["angle_mid"], d["y_energy_int"], label=str(sec))

    ax.set_xlabel("Angle mid (deg)")
    ax.set_ylabel("Energy-integrated yield (sum(yld * dE_MeV))")
    ax.set_title(f"{title_prefix} | energy-integrated angular distributions")
    ax.set_yscale("log")
    ax.legend(ncols=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(outdir / "energy_integrated_angles.png", dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(
        description="Make secondary yield plots from a parquet produced by your pipeline."
    )
    ap.add_argument("parquet", help="Input parquet path")
    ap.add_argument("primary_energy", type=float, help="Primary energy to select (same units as parquet column primary_energy)")
    ap.add_argument("out_title", help="Folder name to create for plots")
    ap.add_argument("--log", action="store_true", help="Use log color scale for heatmaps (LogNorm)")
    ap.add_argument("--energy-tol", type=float, default=0.0,
                    help="Optional tolerance for matching primary_energy (absolute). If 0, exact match is used.")
    args = ap.parse_args()

    parquet_path = Path(args.parquet)
    if not parquet_path.exists():
        raise FileNotFoundError(f"Not found: {parquet_path}")

    outdir = Path(f"{os.path.expanduser("~/repos/outputs_grendel")}/{args.out_title}")
    ensure_dir(outdir)

    df = pd.read_parquet(parquet_path)
    if df.index.names and any(n is not None for n in df.index.names):
        df = df.reset_index()

    required = ["secondary", "primary_energy", "angle_lower_deg", "angle_upper_deg", "E_low", "E_high", "yld"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in parquet: {missing}")

    # Filter primary energy
    pe = args.primary_energy
    if args.energy_tol > 0:
        df_sel = df[np.abs(df["primary_energy"].astype(float) - pe) <= args.energy_tol].copy()
    else:
        df_sel = df[df["primary_energy"].astype(float) == pe].copy()

    if df_sel.empty:
        raise ValueError(
            f"No rows after filtering primary_energy={pe}"
            + (f" within tol={args.energy_tol}" if args.energy_tol > 0 else " (exact match).")
        )

    title_prefix = f"{outdir.name} | primary_energy={pe*1000}KeV"

    # Heatmaps per secondary
    for sec, df_s in df_sel.groupby("secondary"):
        heatmap_for_secondary(df_s, str(sec), outdir, title_prefix, use_log=args.log)

    # Integrated plots
    angle_integrated_spectra(df_sel, outdir, title_prefix)
    energy_integrated_angles(df_sel, outdir, title_prefix)

    # Small index file for convenience
    with open(outdir / "README.txt", "w", encoding="utf-8") as f:
        f.write(f"Plots for primary_energy={pe}\n")
        f.write("Files:\n")
        f.write("  - heatmap_<secondary>.png\n")
        f.write("  - angle_integrated_spectra.png\n")
        f.write("  - energy_integrated_angles.png\n")

    print(f"Saved plots to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
