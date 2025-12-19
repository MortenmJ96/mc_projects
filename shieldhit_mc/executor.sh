#!/bin/bash

PARTITION=q48
ANG_BINS=45
NPRIM=1000000
#NPRIM=5000
CYCLES=100
FILE_TYPE=bdo
#FILE_TYPE=ascii
rm -rf output
mkdir -p output
E_LIST=(5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 23 27 30 35 40 50 60 70 80 90 100 110 120 130 140 150 160 170 180 190 200 210 220 230 240 250)
#E_LIST=(100)

for E in "${E_LIST[@]}"; do
    echo "Submitting E = ${E} MeV"

    # generate PBS file with substitutions
    sed -e "s/__ENERGY__/${E}/g" \
        -e "s/__N_PRIMARIES__/${NPRIM}/g" \
        -e "s/__ANG_BINS__/${ANG_BINS}/g" \
        -e "s/__FILE_TYPE__/${FILE_TYPE}/g" \
        -e "s/__CYCLES__/${CYCLES}/g" \
        run_scripts/shieldhit_template.pbs > shieldhit_E${E}.pbs

    sbatch -p "$PARTITION" shieldhit_E${E}.pbs
done
rm shieldhit_*