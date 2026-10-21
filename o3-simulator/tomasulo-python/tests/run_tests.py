'''
Run every test input at issue widths 1-4 and check the results.
1. the committed instructions, final registers and memory must equal an in-order
   reference execution of the same program
2. the timing must follow the processor rules (see check_timing)
3. an 8-entry BTB indexed by PC[2:0] gives the expected mispredictions (see btb_check)
Simulator outputs and a summary are written to ../results/.
Usage (from this directory): python run_tests.py
'''
import contextlib
import io
import os
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'code'))
from init import read_input, Machine, UNIT, MEM_BYTES     # noqa: E402
from main import simulate                                  # noqa: E402
from print_status import print_results                     # noqa: E402

RESULTS = os.path.join(HERE, '..', 'results')
TESTS = [os.path.join(HERE, '..', 'code', 'test_case.txt')] + sorted(
    os.path.join(HERE, f) for f in os.listdir(HERE) if f.endswith('.txt'))


def reference(setup):
    '''In-order execution: final registers, memory and the executed PCs.'''
    regs = {'R': list(setup['reg_int']), 'F': list(setup['reg_fp'])}
    memory = list(setup['memory'])
    program, pc, trace = setup['instructions'], 0, []

    def read(register):
        return regs[register[0]][int(register[1:])]

    def write(register, value):
        if register != 'R0':
            regs[register[0]][int(register[1:])] = value

    while pc < len(program):
        ins, nxt = program[pc], pc + 1
        trace.append(pc)
        assert len(trace) < 100000, 'reference execution does not terminate'
        if ins.op in ('Ld', 'Sd'):
            address = read(ins.base) + ins.imm
            assert address % 4 == 0 and 0 <= address < MEM_BYTES
            if ins.op == 'Ld':
                write(ins.rd, float(memory[address]))
            else:
                memory[address] = float(read(ins.data))
        elif ins.op in ('Beq', 'Bne'):
            equal = read(ins.srcs[0]) == read(ins.srcs[1])
            if equal == (ins.op == 'Beq'):
                nxt = pc + 1 + ins.imm
        else:
            a = read(ins.srcs[0])
            b = read(ins.srcs[1]) if len(ins.srcs) == 2 else ins.imm
            write(ins.rd, a + b if ins.op in ('Add', 'Addi', 'Add.d')
                  else a - b if ins.op in ('Sub', 'Sub.d') else a * b)
        pc = nxt
    return regs['R'], regs['F'], memory, trace


def check_timing(m, width):
    '''Return a list of violated timing rules.'''
    errors, cfg, rows = [], m.cfg, m.committed
    mem_cycles = cfg['ld_sd']['mem']
    for name, cycles in (('issue', [r.issue[0] for r in rows]), ('commit', [r.commit[0] for r in rows])):
        if cycles != sorted(cycles):
            errors.append('%s is not in program order' % name)
        if max(Counter(cycles).values()) > width:
            errors.append('more than %d instructions %sd in one cycle' % (width, name))
    wb_cycles = [r.cdb[0] for r in rows if r.cdb]
    if len(wb_cycles) != len(set(wb_cycles)):
        errors.append('two broadcasts on the single CDB in one cycle')
    ports = []
    for r in rows:
        op, (start, end) = r.ins.op, r.exe
        latency = cfg[UNIT[op]]['ex']
        where = '%s (issued %d)' % (r.ins.text, r.issue[0])
        if end - start + 1 != latency or start <= r.issue[0]:
            errors.append('%s: EX %s does not follow ISSUE with %d cycles' % (where, r.exe, latency))
        if op == 'Ld':
            if r.mem[0] <= end or r.mem[1] - r.mem[0] + 1 != (mem_cycles if r.src == 'mem' else 1):
                errors.append('%s: bad MEM %s' % (where, r.mem))
            if r.src == 'mem':
                ports.append(r.mem)
            last = r.mem[1]
        elif op == 'Sd':
            if r.mem != [r.commit[0], r.commit[0] + mem_cycles - 1] or r.commit[0] <= end:
                errors.append('%s: store must write memory at commit' % where)
            ports.append(r.mem)
            continue
        else:
            last = end
        if op in ('Beq', 'Bne'):
            if r.cdb or r.commit[0] <= end:
                errors.append('%s: branch commit before resolution' % where)
        elif not (r.cdb and last < r.cdb[0] < r.commit[0]):
            errors.append('%s: WB %s / COMMIT %s out of order' % (where, r.cdb, r.commit))
    ports.sort()
    for a, b in zip(ports, ports[1:]):
        if b[0] <= a[1]:
            errors.append('memory port used by two accesses: %s and %s' % (a, b))
    for r, nxt in zip(rows, rows[1:]):
        if r.mispredicted and nxt.issue[0] < r.exe[1] + 2:
            errors.append('%s: correct path fetched before cycle n+2' % r.ins.text)
    return errors


# Branches at PC 1 and PC 5 use BTB entries 1 and 5 with PC[2:0], but would share
# an entry with a smaller BTB. Expected with 8 entries and a one-bit predictor:
# Beq misses once (empty BTB); Bne misses once (empty BTB) and at the loop exit.
BTB_PROGRAM = '''Addi R1, R0, 4
Beq R0, R0, 1
Addi R7, R0, 99
Addi R1, R1, -1
Addi R2, R2, 1
Bne R1, R0, -5
'''
BTB_EXPECTED_MISPREDICTIONS = 3


def btb_check(width):
    '''Return errors if the BTB does not behave as an 8-entry BTB indexed by PC[2:0].'''
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'btb_check.txt')
        with open(path, 'w') as f:
            f.write(BTB_PROGRAM)
        m, cycles, errors, output = run_one(path, width)
    if m.stats['mispredictions'] != BTB_EXPECTED_MISPREDICTIONS:
        errors.append('BTB check: %d mispredictions, expected %d for an 8-entry BTB'
                      % (m.stats['mispredictions'], BTB_EXPECTED_MISPREDICTIONS))
    return errors


def run_one(path, width):
    setup = read_input(path)
    setup['issue_width'] = width
    m = Machine(setup)
    cycles = simulate(m)
    reg_int, reg_fp, memory, trace = reference(read_input(path))
    errors = check_timing(m, width)
    if [r.PC for r in m.committed] != trace:
        errors.append('committed instructions differ from the in-order execution')
    if (m.reg_int, m.reg_fp, m.memory) != (reg_int, reg_fp, memory):
        errors.append('final registers or memory differ from the in-order execution')
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        print_results(m, cycles)
    return m, cycles, errors, output.getvalue()


def main():
    os.makedirs(RESULTS, exist_ok=True)
    lines = ['%-18s %5s %7s %6s %6s %11s %10s %8s' % ('test', 'width', 'cycles', 'instr', 'IPC',
                                                   'mispredict', 'violation', 'squashed')]
    failures = 0
    for path in TESTS:
        name = os.path.splitext(os.path.basename(path))[0]
        for width in range(1, 5):
            m, cycles, errors, output = run_one(path, width)
            with open(os.path.join(RESULTS, '%s_w%d.txt' % (name, width)), 'w', newline='\n') as f:
                f.write(output)
            n = len(m.committed)
            lines.append('%-18s %5d %7d %6d %6.3f %11d %10d %8d' % (
                name, width, cycles, n, n / cycles, m.stats['mispredictions'],
                m.stats['violations'], m.stats['squashed']))
            print('%-4s %s, issue width %d' % ('FAIL' if errors else 'PASS', name, width))
            for error in errors:
                print('     ' + error)
            failures += bool(errors)
    with open(os.path.join(RESULTS, 'summary.txt'), 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    btb_failures = 0
    for width in range(1, 5):
        errors = btb_check(width)
        print('%-4s BTB check, issue width %d' % ('FAIL' if errors else 'PASS', width))
        for error in errors:
            print('     ' + error)
        btb_failures += bool(errors)
    failures += btb_failures
    print('%d check(s) failed' % failures if failures else
          'all %d runs and 4 BTB checks passed' % (4 * len(TESTS)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
