Tomasulo Algorithm Simulation
* includes instructions Ld, Sd, Beq, Bne, Add, Addi, Sub, Add.d, Sub.d, Mult.d;
* implements ROB, RAT, reservation stations, load-store queue and one CDB;
* issues 1-4 instructions per cycle in order (default 1), executes out of order;
* one-bit branch predictor with an 8-entry BTB, squash and RAT recovery on a misprediction;
* store-to-load forwarding and memory disambiguation.

How to run:
cd code
python main.py [input file] [--issue-width N]    (default input: test_case.txt)

Tests: the inputs in tests/, e.g. python main.py ../tests/t1_independent.txt --issue-width 4
(results/ holds the output of every test at issue widths 1-4)
Check all tests at widths 1-4: cd tests; python run_tests.py
