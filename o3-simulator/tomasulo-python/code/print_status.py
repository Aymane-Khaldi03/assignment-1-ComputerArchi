# Qing
# 21st May 2017
# Rewritten for COSC 6385 Assignment 1: output format of the handout.

'''
Print the final instruction status table, the register values and the
non-zero memory values.
'''


def fmt_value(value, fp):
    if not fp:
        return str(value)
    text = '%.6g' % value
    return text if ('.' in text or 'e' in text or 'n' in text) else text + '.0'


def print_ROB(rob):
    item = rob.ins.text.ljust(24)
    for stage in (rob.issue, rob.exe, rob.mem, rob.cdb, rob.commit):
        item += str(stage).ljust(12)
    print(item.rstrip())


def print_registers(name, values, fp):
    for first in range(0, len(values), 8):
        names = ''.join(('%s%d' % (name, i)).ljust(10) for i in range(first, first + 8))
        row = ''.join(fmt_value(v, fp).ljust(10) for v in values[first:first + 8])
        print('       ' + names.rstrip())
        print('value: ' + row.rstrip())


def print_results(m, cycles):
    print(''.ljust(24) + ''.join(s.ljust(12) for s in ('ISSUE', 'EX', 'MEM', 'WB', 'COMMIT')).rstrip())
    for rob in m.committed:
        print_ROB(rob)
    instructions = len(m.committed)
    print()
    print('Issue width %d: %d cycles, %d instructions committed, IPC %.3f'
          % (m.issue_width, cycles, instructions, instructions / cycles if cycles else 0))
    print('Branch mispredictions %d, memory-order violations %d, squashed instructions %d'
          % (m.stats['mispredictions'], m.stats['violations'], m.stats['squashed']))
    print()
    print('REGISTER VALUES')
    print_registers('R', m.reg_int, False)
    print_registers('F', m.reg_fp, True)
    print()
    print('NON-ZERO MEMORY VALUES')
    print('Addresses'.ljust(11) + 'Values')
    for address, value in enumerate(m.memory):
        if value != 0:
            print(str(address).ljust(11) + fmt_value(value, True))
