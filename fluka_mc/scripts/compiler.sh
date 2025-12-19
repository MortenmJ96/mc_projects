#!/usr/bin/env bash

##=== Bash script for compiling fluka forts (PARALLEL job pool, robust fort detection) ===##

set -euo pipefail
shopt -s nullglob

# Respect existing QUIET; default to quiet if not set
#QUIET=${QUIET:-0}

#read -r -a Es <<< "$2" # List of proton beam energies
E="$2"
echo "Primary E recieved by compiler: $E"
read -r -a sp <<< "$1" # List of secondary species
sp_naming_tags=( "${sp[@]}" )


# Collect unique fort numbers robustly, even if filenames have extra suffixes (e.g., *_fort.102.dat)
echo "#=== Running compiler ===#"

mapfile -t FORT_NUMS < <(
  find ./ -maxdepth 1 -type f -name '*_fort.*' ! -name '*_fort.19' -printf '%f\n' 2>/dev/null \
  | sed -n 's/.*_fort\.\([0-9]\+\).*/\1/p' \
  | sort -n -u
)


((${#FORT_NUMS[@]})) || { echo "No *_fort.# files found"; exit 1; }
echo " Forts found: ${#FORT_NUMS[@]}"

COMP=usysuw
COMP2=usbrea

for ((i=0; i<${#FORT_NUMS[@]}; i++)); do
  N=${FORT_NUMS[i]}
  if (( N >= 100 && N < 120 )); then COMP="usysuw" #USRYIELD
  elif (( N >= 80 && N < 100 )); then COMP="ustsuw" #USRBDX
  elif (( N >= 60 && N < 80 )); then COMP="usbsuw" #USRBIN
  else                                COMP="usysuw"
  fi
  #E_tag=${E//./}        # remove decimal point
  E_tag=$(
    awk -v E="$E" 'BEGIN {
      ev = E * 1e9;                # GeV -> eV
      if (ev < 0) ev = -ev;        # optional: remove if you want signed
      printf "%010.0f", ev         # integer, zero-padded to 10 chars
    }'
  )

  j=$(( i % ${#sp_naming_tags[@]} ))
  sp_name_tag="${sp_naming_tags[j],,}"

  in_files=( deck_*_fort."${N}" )
  out_file=compiled_"${sp_name_tag}"_"${E_tag}"_"${N}".out
  out_file2=compiled_"${sp_name_tag}"_"${E_tag}"_"${N}"
  if [[ "$COMP" == "usbsuw" ]]; then out_file="${out_file2}.bnn"
  fi
  echo "${COMP}: fort.${N}: (${#in_files[@]} files) -> ${out_file}"
  {
      printf '%s\n' "${in_files[@]}"
      printf '\n'
      printf '%s\n' "${out_file2}"
      printf '\n'
  } | "${COMP}"
  if [[ "$COMP" == "usbsuw" ]]; then
    echo "${COMP2}: ${out_file} -> ${out_file2}. ascii"
    {
      printf '%s\n' "${out_file2}.bnn"
      printf '%s\n' "${out_file2}.ascii"
    } | "${COMP2}"
  fi
done

echo "Compilation done"
