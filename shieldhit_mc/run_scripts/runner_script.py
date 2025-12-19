#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import random as rand
import subprocess
import math

def main():
    if len(sys.argv) != 6:
        raise SystemExit("Usage: runner_script.py <ENERGY_MEV> <N_PRIMARIES>")

    ENERGY = float(sys.argv[1])  # MeV
    N_PRIMARIES = int(sys.argv[2]) # number of primaries
    ANG_BINS = sys.argv[3]
    FILE_TYPE = sys.argv[4]
    CYCLES = int(sys.argv[5])

    # --- binning: width ~ 3.5 MeV ---
    # example: 7 MeV -> 2 bins
    E_BINS = max(1, math.ceil(ENERGY / 3.5))

    # simple deterministic seed from ENERGY
    # (adjust formula if you like)
    #SEED = 89736501 + int(round(ENERGY * 10.0))

    

    cwd = Path(".").resolve()

    # --- load templates ---
    beam_tpl   = (cwd / "beam.dat.template").read_text()
    detect_tpl = (cwd / "detect.dat.template").read_text()

    for c in np.arange(1,CYCLES+1):
        SEED = rand.randint(1,100000) + int(round(ENERGY * 10.0))
        print(f"ENERGY = {ENERGY} MeV, E_BINS = {E_BINS}, Cycle = {c}, SEED = {SEED}")
        # --- write beam.dat ---
        beam_text = beam_tpl.format(
            N_PRIMARIES=N_PRIMARIES,
            SEED=SEED,
            BEAM_MEV=ENERGY,
        )
        (cwd / "beam.dat").write_text(beam_text)

        # --- write detect.dat ---
        detect_text = detect_tpl.format(
            out_type=FILE_TYPE,
            BEAM_MEV=ENERGY,
            E_BINS=E_BINS,
            ANG_BINS=ANG_BINS,
            CYCLES=c,
        )
        (cwd / "detect.dat").write_text(detect_text)

        # geo.dat and mat.dat are already present in the directory

        # --- run shieldhit ---
        subprocess.run(["shieldhit", "."], check=True)

if __name__ == "__main__":
    main()
