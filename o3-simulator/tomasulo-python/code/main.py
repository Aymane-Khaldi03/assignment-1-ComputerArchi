# Qing
# 21st May 2017
# Extended for COSC 6385 Assignment 1: input file, issue width 1-4, branch prediction.

'''
Usage: python main.py [input file] [--issue-width N]
The input file holds the hardware configuration, the initial register and memory
values and the program (see test_case.txt). "Issue width = N" in the file sets
the issue width (default 1); --issue-width overrides it.
'''
import argparse
import os
import sys
from init import read_input, Machine, InputError, SimulationError, MAX_ISSUE_WIDTH
from issue import issue
from exe import exe
from mem import mem
from wb import wb
from commit import commit
from print_status import print_results


def simulate(m, max_cycles=100000):
    '''Run until every instruction has committed; return the last commit cycle.'''
    cycle = 1
    while m.ROB or m.PC < len(m.instructions):
        if cycle > max_cycles:
            raise SimulationError('no result after %d cycles (infinite loop?)' % max_cycles)
        # A structure freed in a cycle is reused from the next cycle on, and a
        # value produced in a cycle is consumed from the next cycle on.
        issue(m, cycle)
        commit(m, cycle)
        wb(m, cycle)
        mem(m, cycle)
        exe(m, cycle)
        cycle += 1
    return m.committed[-1].commit[0] if m.committed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Tomasulo simulator with in-order multi-issue')
    parser.add_argument('input', nargs='?',
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_case.txt'))
    parser.add_argument('--issue-width', type=int, choices=range(1, MAX_ISSUE_WIDTH + 1))
    parser.add_argument('--max-cycles', type=int, default=100000)
    args = parser.parse_args(argv)
    try:
        setup = read_input(args.input)
        if args.issue_width:
            setup['issue_width'] = args.issue_width
        m = Machine(setup)
        cycles = simulate(m, args.max_cycles)
    except (InputError, SimulationError, OSError) as error:
        print('error: %s' % error, file=sys.stderr)
        return 1
    print_results(m, cycles)
    return 0


if __name__ == '__main__':
    sys.exit(main())
