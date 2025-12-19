#!/bin/bash

PROJ_NAME=apo16_low_E_
PARTITION=q48

BEAM_TYPE=APROTON
NPRIM=1.0E7
CYCLES=1
TIME=10:00:00

#ENVIROMENT=/home/dcpt/bashrc.dcpt
#ENVIROMENT=/home/mortenmj/opt/fluka_infn/env_fluka_infn.sh
ENVIROMENT=/home/mortenmj/opt/fluka_cern/env_fluka_cern.sh
#ENVIROMENT=/home/mortenmj/opt/shieldhit/env_shieldhit.sh

#TARG_THICKNESS=1E-3
TARG_THICKNESS=1E-2
TARG_WIDTH=0.5E-3
TARG_TYPE=OXYGEN

# === BINNING OPTIONS ===
ANG_BINS=45
E_BIN_WIDTH=1
E_BIN_MIN=30
MAX_E_SCORE=1.2 # fractional increase from beam energy to max scored energy

# === LISTS FOR SPECIES SCORING AND LOGIC OUTPUT ===

# = PBAR SET-UP = #
SPECIES=(1.0 8.0 -3.0 7.0 -6.0 -4.0 23.0 13.0 14.0 2.0 10.0 11.0)
SPECIES_N=(PROTON NEUTRON DEUTERON PHOTON 4-HELIUM TRITON PIZERO PION+ PION- APROTON MUON+ MUON-)

# = PROTON SET-UP = #
#SPECIES=(1.0 8.0 -3.0 7.0 -6.0 -4.0)
#SPECIES_N=(PROTON NEUTRON DEUTERON PHOTON 4-HELIUM TRITON)



mkdir -p output

# = PARTICLE THERAPY SET-UP = #
#E_LIST=(0.005 0.006 0.007 0.008 0.009 0.010 0.011 0.012 0.013 0.014 0.015 0.016 0.017 0.018 0.019 0.020 0.023 0.027 0.030 0.035 0.040 0.050 0.060 0.070 0.080 0.090 0.100 0.110 0.120 0.130 0.140 0.150 0.160 0.170 0.180 0.190 0.200 0.210 0.220 0.230 0.240 0.250)

# = LOW E SET-UP = #
#E_LIST=(0.000000001 0.00000001 0.0000001 0.000001 0.00001 0.0001 0.001) #1eV -> 1MeV
E_LIST=(0.00001)

for E in "${E_LIST[@]}"; do
    echo "Submitting E = ${E} GeV"

    # generate PBS file with substitutions
    sed -e "s/__ENERGY__/${E}/g" \
        -e "s/__N_PRIMARIES__/${NPRIM}/g" \
        -e "s/__ANG_BINS__/${ANG_BINS}/g" \
        -e "s/__E_BIN_WIDTH__/${E_BIN_WIDTH}/g" \
        -e "s/__SPECIES_N__/${SPECIES_N[*]}/g" \
        -e "s/__PROJ_NAME__/${PROJ_NAME}/g" \
        -e "s/__BEAM_TYPE__/${BEAM_TYPE}/g" \
        -e "s/__TARG_TYPE__/${TARG_TYPE}/g" \
        -e "s/__CYCLES__/${CYCLES}/g" \
        -e "s#__ENVIROMENT__#${ENVIROMENT}#g" \
        -e "s#__TARG_THICKNESS__#${TARG_THICKNESS}#g" \
        -e "s#__TARG_WIDTH__#${TARG_WIDTH}#g" \
        -e "s/__TIME__/${TIME}/g" \
        -e "s/__E_BIN_MIN__/${E_BIN_MIN}/g" \
        -e "s/__E_LIST__/${E_LIST}/g" \
        -e "s/__MAX_E_SCORE__/${MAX_E_SCORE}/g" \
        templates/cluster_run_template.pbs > cluster_run_E${E}.pbs

    sbatch -p "$PARTITION" cluster_run_E${E}.pbs
done
rm cluster_run_E*