#!/usr/bin/env python3
from pathlib import Path
import sys
import subprocess
import math
# ---------------- helpers ---------------- #

def fluka_field(value, width=10, left=False, numeric=False, float_mode=False, decimals=3):
    """
    float_mode = False  -> scientific notation (E)
    float_mode = True   -> fixed-point (f)
    """
    if isinstance(value, str) and not numeric:
        # Treat as pure string
        return f"{value:<{width}}" if left else f"{value:>{width}}"

    # Treat as numeric
    v = float(value)
    if float_mode:
        fmt = f"{{:>{width}.{decimals}f}}"
    else:
        fmt = f"{{:>{width}.{decimals}E}}"
    return fmt.format(v)



def usryield_line1(det_id, sp_id, out_id, label,
                   region="Targ", medium="Vac", norm=1.0):
    """
    First USRYIELD card:
    USRYIELD  det_id  sp_id  out_id  region  medium  norm  label
    """
    f = []

    # printf "%-10s%10s%10s%10s%10s%10s%10s%-10s\n"
    f.append(f"{'USRYIELD':<10}")                      # %-10s
    f.append(fluka_field(det_id, 10, numeric=True, float_mode=True,decimals=1))   # %10s
    f.append(fluka_field(sp_id, 10))                  # %10s
    f.append(fluka_field(out_id, 10, numeric=True, float_mode=True,decimals=1))                 # %10s
    f.append(fluka_field(region, 10))                 # %10s
    f.append(fluka_field(medium, 10))                 # %10s
    f.append(fluka_field(norm, 10, numeric=True))     # %10s
    f.append(f"{label:<10}")                          # %-10s

    return "".join(f)


def usryield_line2(energy, n_e_bins, abmin, abmax):
    """
    Continuation USRYIELD card:
    USRYIELD  ENERGY  0.000  E_BINS  ABMAX  ABMIN  3.0  &
    """
    f = []

    # printf "%-10s%10s%10s%10s%10s%10s%10s%-10s\n"
    f.append(f"{'USRYIELD':<10}")                       # %-10s
    f.append(fluka_field(energy, 10, numeric=True))    # %10s
    f.append(fluka_field(0.0, 10, numeric=True))       # %10s
    f.append(fluka_field(n_e_bins, 10))                # %10s (integer OK as string)
    f.append(fluka_field(abmax, 10, numeric=True))     # %10s
    f.append(fluka_field(abmin, 10, numeric=True))     # %10s
    f.append(fluka_field(3.0, 10, numeric=True))       # %10s
    f.append(f"{'&':<10}")                             # %-10s

    return "".join(f)

# ---------------- core generator ---------------- #
def generate_usryield_cards(
    energy,
    n_energy_bins,
    n_angle_bins,
    sp_ids,
    det_id_start=2401.0,
    out_id_start=101,
    abmin_global=0.0,
    abmax_global=180.0,
):
    dtheta = (abmax_global - abmin_global) / n_angle_bins

    lines = []
    det_id = det_id_start
    out_id = out_id_start

    for sp in sp_ids:
        species_prefix = sp.lower()[:5]  # e.g. "proto" from "PROTON"

        for i_ang in range(n_angle_bins):
            abmin = abmin_global + i_ang * dtheta
            abmax = abmin + dtheta

            # upper angle as integer for label
            angle_int = int(round(abmax))
            label = f"{species_prefix}{angle_int}"

            # first card
            lines.append(
                usryield_line1(
                    det_id=det_id,
                    sp_id=sp,
                    out_id=-out_id,
                    label=label,
                )
            )
            # continuation card
            lines.append(
                usryield_line2(
                    energy=energy,
                    n_e_bins=n_energy_bins,
                    abmin=abmin,
                    abmax=abmax,
                )
            )

            #det_id += 1.0
        out_id += 1

    return "\n".join(lines) + "\n"

def run_fluka(cycles, inp_file, es_tag):
    log_path = Path(f"run_{es_tag}.log")

    # command equivalent to:
    # rfluka -e ./flukadpm -d -N0 -M"$CYCLES" "$in" > "run_${es_tag}.log" 2>&1 &
    cmd = [
        "rfluka",
        "-e", "./flukadpm",
        "-d",
        "-N0",
        f"-M{cycles}",
        inp_file,
    ]
    
    #with log_path.open("w") as log:
    subprocess.run(
            cmd,
            #stdout=log,
            #stderr=subprocess.STDOUT,
        )

    # proc is the background process, if you need the PID:
    #return proc

def right_replace(text: str, placeholder: str, value) -> str:
    """Replace placeholder with value right-justified to placeholder width."""
    s = str(value)
    width = len(placeholder)
    return text.replace(placeholder, s.rjust(width))

def main():
    if len(sys.argv) != 11:
        raise SystemExit(f"Wrong number of args")
    ENERGY = float(sys.argv[1])  # GeV
    N_PRIMARIES = str(sys.argv[2]) # number of primaries
    ANG_BINS = int(sys.argv[3])
    targ_type = str(sys.argv[4])
    beam_type = str(sys.argv[5])
    targ_thickness = str(sys.argv[6])
    sp_id_str = sys.argv[7]
    cycles = str(int(sys.argv[8]))
    E_BIN_WIDTH = float(sys.argv[9])
    E_BIN_MIN = int(sys.argv[10])

    sp_ids = sp_id_str.split()

    if ENERGY < E_BIN_MIN * E_BIN_WIDTH:
        # too small energy for the nominal width → shrink width to keep at least N_MIN bins
        eff_bin_width = ENERGY / E_BIN_MIN
    else:
        # normal case → use your chosen width
        eff_bin_width = E_BIN_WIDTH

    E_BINS = max(1, math.ceil(ENERGY / eff_bin_width))
    
    #E_BINS = max(1, math.ceil(ENERGY / E_BIN_WIDTH))

    print(f"All arguements:\n {sys.argv}")

    # angular range for all bins (example: 0–180 deg)
    ABMIN_GLOBAL = 0.0
    ABMAX_GLOBAL = 180.0

    cards_text = generate_usryield_cards(
        energy=ENERGY,
        n_energy_bins=E_BINS,
        n_angle_bins=ANG_BINS,
        sp_ids=sp_ids,
        det_id_start=2401.0, 
        out_id_start=101.0,      
        abmin_global=ABMIN_GLOBAL,
        abmax_global=ABMAX_GLOBAL,
    )

    # Now splice these cards into your template deck
    template_path = Path("deck.inp.template")
    output_path = Path(f"deck_E{int(ENERGY*1000)}_.inp")

    template = template_path.read_text()

    # Suppose the template has a marker like:
    #    #USRYIELD_CARDS_HERE
    # You can replace that marker with the generated block:
    deck_text = template
    deck_text = deck_text.replace("{BEAM_TYPE}",beam_type)
    deck_text = right_replace(deck_text, "{ENERGY}",          f"-{ENERGY:g}")
    deck_text = right_replace(deck_text, "{TARG_TYPE}",       targ_type)
    deck_text = right_replace(deck_text, "{SPECIES_N}",       sp_ids)
    deck_text = deck_text.replace("{TARG_THICKNESS}", targ_thickness)
    deck_text = right_replace(deck_text, "{N_PRIMARIES}",     N_PRIMARIES)
    deck_text = right_replace(deck_text, "__USRYIELD_CARD_AREA__", cards_text)
    output_path.write_text(deck_text)

    #print("#=== Running rFluka ===#")
    run_fluka(cycles, output_path, ENERGY)

if __name__ == "__main__":
    main()
