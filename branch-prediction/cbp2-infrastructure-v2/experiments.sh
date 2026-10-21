#!/bin/bash
# Rebuild seven configurations; publish the CSV only after every run succeeds.
# Usage: JOBS=4 bash experiments.sh
set -euo pipefail
export LC_ALL=C
cd "$(dirname "$0")"

if [[ ${1:-} == --worker ]]; then
    name=$2
    trace=$3
    output=$("./build/$name" "$trace")
    [[ $output =~ ^([0-9]+\.[0-9]+)\ MPKI$ ]] || {
        echo "Invalid simulator output: $name $trace: $output" >&2; exit 1;
    }
    label=${trace##*/}
    printf '%s,%s,%s\n' "$name" "${label%%.trace.*}" "${BASH_REMATCH[1]}"
    exit 0
fi

jobs=${JOBS:-4}
[[ $jobs =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS must be positive.' >&2; exit 1; }
mkdir -p build results
all='-DPM_ALLOC_ON_MISPREDICT=0 -DPM_ALLOC_RESET_COUNTER=0'
miss='-DPM_ALLOC_ON_MISPREDICT=1 -DPM_ALLOC_RESET_COUNTER=0'
best='-DPM_ALLOC_ON_MISPREDICT=1 -DPM_ALLOC_RESET_COUNTER=1'
configs=(
    'bimodal|-DPM_GLOBAL=0'
    "pm_4way_all|$all"
    "pm_4way_miss|$miss"
    "pm_4way|$best"
    "pm_2way_512sets|-DPM_WAYS=2 $best"
    "pm_2way_1024sets|-DPM_WAYS=2 -DPM_SET_BITS=10 $best"
)
for config in "${configs[@]}"; do
    name=${config%%|*}
    read -r -a flags <<< "${config#*|}"
    "${CXX:-g++}" -O3 -Wall "${flags[@]}" -o "build/$name" src/predict.cc src/trace.cc -Isrc
done
sed 's/new pm_predictor/new gshare_predictor/' src/predict.cc > build/predict_gshare.cc
"${CXX:-g++}" -O3 -Wall -o build/gshare build/predict_gshare.cc src/trace.cc -Isrc

trace_list=$(mktemp)
output_file=$(mktemp results/results.csv.XXXXXX)
trap 'rm -f -- "$trace_list" "$output_file"' EXIT
find traces -type f -name '*.trace.*' -print0 | sort -z > "$trace_list"
mapfile -d '' -t traces < "$trace_list"
(( ${#traces[@]} > 0 )) || { echo 'No traces found.' >&2; exit 1; }
names=(bimodal gshare pm_4way_all pm_4way_miss pm_4way pm_2way_512sets pm_2way_1024sets)
for name in "${names[@]}"; do
    for trace in "${traces[@]}"; do
        printf '%s\0%s\0' "$name" "$trace"
    done
done | xargs -0 -P "$jobs" -n 2 bash ./experiments.sh --worker | sort > "$output_file"
expected=$(( ${#names[@]} * ${#traces[@]} ))
[[ $(wc -l < "$output_file") -eq $expected ]] || { echo 'Incomplete results.' >&2; exit 1; }
mv -- "$output_file" results/results.csv
echo "wrote results/results.csv ($expected rows)"
