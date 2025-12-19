# E_specs are 14 chars wide per column


def main():
    p = argparse.ArgumentParser(
        description="Convert FLUKA parquet (from data_collector.py) to PHITS-like .fgy"
    )
    p.add_argument("--parquet", help="Input parquet file",required=True)
    p.add_argument(
        "-o",
        "--out",
        default=None,
        help="Output .fgy file (default: basename_<E>MeV.fgy)",
    )
    p.add_argument("--E", help="Primary energy",type=float,required=True)
    args = p.parse_args()

    parquet_path = Path(args.parquet)
    if args.out is None:
        base = parquet_path.stem
        args.out = f"{base}_{int(round(args.primary_energy))}MeV.fgy"
    out_path = Path(args.out)

    # --- Load parquet ---
    df = pd.read_parquet(parquet_path)
    primary_energy = args.E

    # select rows for that primary energy
    df_sel = df[df["primary_energy"] == primary_energy]

    with out_path.open("w") as fh:

        fh.write(f"/DataSource Fluka cern 4-5.0")
        fh.write(f"/IncidentParticle {beam_type}")
        fh.write(f"/TargetMedium {targ_type}")
        fh.write(f"/TargetThickness {thickness}")
        fh.write(f"/BeamEnergy {primary_energy}")
        fh.write(f"/NumberOfPrimaries {n_prim}")

        for secondary, sub in df_sel.groupby("secondary"):
            fh.write(f"/EmissionSpectrum {secondary}")
            sigmas_prod = 0
            # group by E_low so we collect all angles at that energy
            for E_low, block in sub.groupby("E_low"):
                # sort by angle, if needed
                block = block.sort_values("angle_lower_deg")
                # collect the yields
                yields = block["yld"].tolist()
                fh.write(f"{E_low:12.7f} " + " ".join(f"{y: .7E}" for y in yields) + "\n")
                
                dE = E_high - E_low  # MeV (or whatever units your energies are in)

                theta_low = np.deg2rad(block["angle_lower_deg"].to_numpy())
                theta_up  = np.deg2rad(block["angle_upper_deg"].to_numpy())

                dOmega = 2.0 * np.pi * (np.cos(theta_low) - np.cos(theta_up))

                # add contribution from all angle bins at this energy
                sigma_prod += np.sum(yields * dE * dOmega)
            
            fh.write(f"/ProductionCrossSection {sigmas_prod}    {secondary} mb")