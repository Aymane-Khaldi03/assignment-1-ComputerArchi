# Assignment 1, Part 2: Tomasulo Algorithm with Multi-Issue

`tomasulo-python/` is the provided Python Tomasulo simulator, extended to issue
1 to 4 instructions per cycle in order (default 1). The issue width is set with
`Issue width = N` in the input file. The simulator now follows the processor of
the assignment: configuration read from the input file, one-bit branch prediction
with an 8-entry BTB and squash on a misprediction, `Beq`/`Bne`, stores that write
memory at commit, and the required output (instruction status table, registers,
non-zero memory).

## Run (Python 3, no packages needed)

```sh
cd tomasulo-python/code
python3 main.py                                  # provided test_case.txt, width 1
python3 main.py ../tests/t3_loop.txt --issue-width 2
cd ../tests && python3 run_tests.py              # check every test at widths 1-4
```

`tomasulo-python/results/` holds the output of `main.py` for every test at
widths 1 to 4 (for example `t3_loop_w2.txt` is the second command above).
`run_tests.py` compares every run with an in-order execution of the program,
checks the timing rules and the 8-entry BTB, and rewrites `results/`.

## Results (cycles until the last commit)

| Test | What it checks | W=1 | W=2 | W=3 | W=4 |
|---|---|---|---|---|---|
| `test_case` (provided) | loop, FP dependence chain, store at commit | 41 | 35 | 33 | 32 |
| `t1_independent` | independent instructions | 19 | 15 | 14 | 14 |
| `t2_dependencies` | RAW/WAR/WAW in one issue group, R0 | 31 | 28 | 28 | 28 |
| `t3_loop` | branch prediction, wrong-path stores | 38 | 32 | 30 | 30 |
| `t4_branches` | Beq/Bne, BTB entry shared by two branches | 44 | 38 | 37 | 36 |
| `t5_memory` | forwarding, memory-order violation | 25 | 21 | 21 | 21 |
| `t6_structural` | full ROB / RS / queue, late WAW | 21 | 20 | 20 | 20 |

In all 28 runs the final registers and memory equal an in-order execution of
the program (see Part 2 of the report).

## Files

- `tomasulo-python/code/`: simulator (`main.py`, one module per stage) and the provided `test_case.txt`.
- `tomasulo-python/tests/`: test inputs and `run_tests.py`.
- `tomasulo-python/results/`: simulator output for every test and width, and `summary.txt`.
- `tomasulo-python/data_structure.txt`: fields of the data structures.
