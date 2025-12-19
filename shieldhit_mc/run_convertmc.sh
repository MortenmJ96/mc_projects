#!/usr/bin/env bash
set -u

mkdir -p output/converts

# Debug: print all matched files (optional)
# echo output/E_*/*.bdo

# Loop over all .bdo files in directories named E_*
for bdo in output/E_*/*.bdo; do
    # Skip if glob didn't match anything
    [ -e "$bdo" ] || continue

    dir="$(dirname "$bdo")"
    folder="$(basename "$dir")"     # e.g. E_100
    energy="${folder#E_}"           # strip leading "E_"

    file="$(basename "$bdo")"       # e.g. dd_proton.bdo or proton.bdo
    name="${file%.bdo}"             # strip .bdo -> dd_proton or proton

    # secondary name: strip optional "dd_" prefix
    secondary="${name#dd_}"         # dd_proton -> proton, proton -> proton

    # Output prefix: {energy}_{secondary}
    out="${energy}_${secondary}"

    echo "Running: convertmc plotdata \"$bdo\" \"output/converts/$out\""
    convertmc plotdata "$bdo" "output/converts/$out"
    #if ! convertmc plotdata "$bdo" "output/converts/$out"; then
    #    echo "WARNING: convertmc failed for $bdo, continuing..." >&2
    #    continue
    #fi
done
