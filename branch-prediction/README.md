# Assignment 1, Part 1: Pentium M Branch Predictor

The `pm_predictor` class in `cbp2-infrastructure-v2/src/my_predictor.h`
implements the Pentium M branch direction predictor described in the
assignment: a bimodal table plus a tagged, set-associative global predictor.
As the assignment allows, the loop predictor, the PIR and its hash, and branch
target prediction are not implemented. No external cache code was used.
The report is Part 1 of `../report.pdf`.

The default uses 4096 bimodal counters and a 512-set, four-way global table.
A global hit overrides the bimodal prediction; new global entries are allocated
on a global miss when bimodal is wrong. A two-way variant is supported with
`-DPM_WAYS=2`. Both allocation policies and the two-way variants are evaluated
in the report.

## Build and run (Linux or WSL)

The provided `run` script needs `csh` and `dc`. From this README's directory:

```sh
sudo apt install build-essential csh dc bzip2
cd cbp2-infrastructure-v2
make -C src            # builds src/predict
chmod +x run           # needed if executable permission was lost during copying
./run traces           # default predictor on all 20 traces
make -C tests test     # replays the handout's 22-step hybrid example
bash experiments.sh    # every configuration in the report -> results/results.csv
```

A single trace: `./src/predict traces/256.bzip2/bzip2.trace.bz2` prints
`0.062 MPKI`. 

## Results (average MPKI over the 20 traces)

| Predictor                                       | Storage  | MPKI      |
|-------------------------------------------------|----------|-----------|
| Bimodal only (4K entries)                       | 1 KiB    | 10.267    |
| gshare (32K entries, provided)                  | 8 KiB    | 6.306     |
| PM 4-way, allocate on every miss                | 3.75 KiB | 7.758     |
| **PM 4-way, allocate on mispredict (default)**  | 3.75 KiB | **5.849** |

Per-trace numbers are in `cbp2-infrastructure-v2/results/` and in the report.

