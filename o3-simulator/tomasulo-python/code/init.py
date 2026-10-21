# Qing
# 21st May 2017
# Extended for COSC 6385 Assignment 1 (multi-issue, input file, branch prediction).

'''
Data structures (field names follow ../data_structure.txt) and input parsing.
'''
import re
from copy import deepcopy

NUM_REGS = 32
MEM_BYTES = 256          # 256 B = 64 words, byte addressed
BTB_ENTRIES = 8
MAX_ISSUE_WIDTH = 4

# canonical spelling of each opcode; the input text is case insensitive
OPCODES = {'ld': 'Ld', 'sd': 'Sd', 'beq': 'Beq', 'bne': 'Bne', 'add': 'Add',
           'addi': 'Addi', 'sub': 'Sub', 'add.d': 'Add.d', 'sub.d': 'Sub.d',
           'mult.d': 'Mult.d'}
# reservation stations / unit used by each opcode (branches use the integer ALU)
UNIT = {'Add': 'int_adder', 'Addi': 'int_adder', 'Sub': 'int_adder',
        'Beq': 'int_adder', 'Bne': 'int_adder', 'Add.d': 'fp_adder',
        'Sub.d': 'fp_adder', 'Mult.d': 'fp_multi', 'Ld': 'ld_sd', 'Sd': 'ld_sd'}
# operands: R = integer register, F = FP register, I = immediate, M = offset(Rbase)
FORMAT = {'Add': 'RRR', 'Sub': 'RRR', 'Addi': 'RRI', 'Add.d': 'FFF',
          'Sub.d': 'FFF', 'Mult.d': 'FFF', 'Ld': 'FM', 'Sd': 'FM',
          'Beq': 'RRI', 'Bne': 'RRI'}
# rows of the configuration table in the input file
UNIT_ROWS = [('integer adder', 'int_adder'), ('fp adder', 'fp_adder'),
             ('fp multiplier', 'fp_multi'), ('load/store unit', 'ld_sd')]
# defaults: the sample configuration of the assignment handout
DEFAULT_CONFIG = {'int_adder': {'rs': 2, 'ex': 1, 'fus': 1},
                  'fp_adder': {'rs': 3, 'ex': 3, 'fus': 1},
                  'fp_multi': {'rs': 2, 'ex': 20, 'fus': 1},
                  'ld_sd': {'rs': 3, 'ex': 1, 'mem': 4, 'fus': 1}}
NUMBER = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'


class InputError(Exception):
    pass


class SimulationError(Exception):
    pass


'''define data types'''
# decoded instruction
class Instruction:
    def __init__(self, op, regs, imm, text):
        self.op = op
        self.imm = imm          # Addi immediate, Ld/Sd offset, branch offset
        self.text = text
        self.rd = None          # destination register
        self.srcs = []          # source registers read through a reservation station
        self.base = None        # Ld/Sd base register
        self.data = None        # Sd data register
        if op in ('Ld', 'Sd'):
            self.base = regs[1]
            if op == 'Ld':
                self.rd = regs[0]
            else:
                self.data = regs[0]
        elif op in ('Beq', 'Bne'):
            self.srcs = regs
        else:
            self.rd = regs[0]
            self.srcs = regs[1:]


# reservation station
class rs_entry:
    def __init__(self):
        self.busy = 0
        self.op = None
        self.tag_1st = None     # producing ROB entry while the value is pending
        self.value_1st = None
        self.valid_1st = 0
        self.ready_1st = 0      # cycle in which value_1st became available
        self.tag_2nd = None
        self.value_2nd = None
        self.valid_2nd = 0
        self.ready_2nd = 0
        self.dest_tag = None    # ROB entry of this instruction


# load/store queue entry (the queue is the reservation station of the memory unit)
class ld_sd_entry:
    def __init__(self, ld_sd_tag, op, rob):
        self.ld_sd_tag = ld_sd_tag
        self.op = op
        self.dest_tag = rob     # ROB entry of this instruction
        self.address = None
        self.addr_cycle = None  # cycle in which the address calculation ends (address ready after it)
        self.immediate = 0
        self.reg_tag = None     # base register: producer, value, valid flag
        self.reg_value = None
        self.valid = 0
        self.base_ready = 0
        self.data = None        # Sd only: value to store
        self.data_tag = None
        self.data_valid = 0
        self.data_ready = 0
        self.leave_cycle = None  # Ld only: cycle in which memory returns the value


# ROB entry
class ROB_entry:
    def __init__(self, seq, size_ROB, PC, ins, cycle):
        self.seq = seq                       # program order of live entries
        self.ROB_tag = 'ROB' + str(seq % size_ROB)
        self.PC = PC                         # word address (instruction index)
        self.ins = ins
        self.value = None
        self.dest_tag = ins.rd               # architectural destination register
        self.issue = [cycle]
        self.exe = []
        self.mem = []
        self.cdb = []
        self.commit = []
        self.result_cycle = None   # value ready for the CDB after this cycle
        self.operands = None       # branch operand values at EX
        self.predicted_next = None
        self.mispredicted = False
        self.resolved = False
        self.address = None
        self.src = None            # Ld: 'mem' or the Sd ROB entry it forwarded from
        self.fault = None          # error raised only if this instruction commits
        self.lsq = None
        self.squashed = False


# functional unit, address adder or memory port user
class functional_unit:
    def __init__(self, pipelined):
        self.pipelined = pipelined
        self.busy_until = 0    # unpipelined: last occupied cycle
        self.last_start = 0    # pipelined: last cycle an operation started
        self.owner = None

    def can_start(self, cycle):
        if self.pipelined:
            return self.last_start < cycle
        return self.busy_until < cycle

    def start(self, rob, cycle, latency):
        self.last_start = cycle
        self.busy_until = cycle + latency - 1
        self.owner = rob


# BTB entry with a one-bit predictor
class btb_entry:
    def __init__(self):
        self.valid = False
        self.tag = None      # PC (word address) of the branch
        self.target = None   # word address of the taken target
        self.taken = False   # one-bit prediction: last outcome


# function: build rs
def build_rs(num):
    return [rs_entry() for _ in range(num)]


# whole processor state
class Machine:
    def __init__(self, setup):
        cfg = setup['config']
        self.cfg = cfg
        self.instructions = setup['instructions']
        self.issue_width = setup['issue_width']
        self.size_ROB = setup['rob_entries']
        self.size_ld_sd_queue = cfg['ld_sd']['rs']
        self.reg_int = list(setup['reg_int'])
        self.reg_fp = list(setup['reg_fp'])
        self.memory = list(setup['memory'])
        self.rat_int = [None] * NUM_REGS     # None: value is in the register file
        self.rat_fp = [None] * NUM_REGS
        self.rs = {u: build_rs(cfg[u]['rs']) for u in ('int_adder', 'fp_adder', 'fp_multi')}
        # integer adder unpipelined, FP adder and multiplier pipelined
        self.fus = {u: [functional_unit(u != 'int_adder') for _ in range(cfg[u]['fus'])]
                    for u in ('int_adder', 'fp_adder', 'fp_multi')}
        self.addr_units = [functional_unit(False) for _ in range(cfg['ld_sd']['fus'])]
        self.ld_sd_queue = []    # program order
        self.ROB = []            # program order, head at index 0
        self.next_seq = 0
        self.PC = 0
        self.fetch_resume = 1    # first cycle in which fetch may continue after a squash
        self.btb = [btb_entry() for _ in range(BTB_ENTRIES)]
        self.mem_busy_until = 0  # single-ported, non-pipelined memory
        self.mem_owner = None
        self.committed = []
        self.stats = {'mispredictions': 0, 'violations': 0, 'squashed': 0}


'''input parsing'''
def parse_register(token, kind, where):
    m = re.fullmatch(r'([RF])(\d+)', token, re.IGNORECASE)
    if not m or m.group(1).upper() != kind or int(m.group(2)) >= NUM_REGS:
        name = 'integer' if kind == 'R' else 'FP'
        raise InputError('%s: expected an %s register (%s0-%s31), got %r'
                         % (where, name, kind, kind, token))
    return kind + str(int(m.group(2)))


def instruction_text(op, regs, imm):
    if op in ('Ld', 'Sd'):
        return '%s %s, %d(%s)' % (op, regs[0], imm, regs[1])
    operands = regs + ([str(imm)] if imm is not None else [])
    return '%s %s' % (op, ', '.join(operands))


def parse_instruction(line, where):
    tokens = [t for t in re.split(r'[\s,]+', line) if t]
    op = OPCODES[tokens[0].lower()]
    fmt, args = FORMAT[op], tokens[1:]
    if len(args) != len(fmt):
        raise InputError('%s: %s expects %d operands' % (where, op, len(fmt)))
    regs, imm = [], None
    for kind, token in zip(fmt, args):
        if kind in 'RF':
            regs.append(parse_register(token, kind, where))
        elif kind == 'I':
            if not re.fullmatch(r'[-+]?\d+', token):
                raise InputError('%s: bad immediate %r' % (where, token))
            imm = int(token)
        else:
            m = re.fullmatch(r'([-+]?\d+)\((\w+)\)', token)
            if not m:
                raise InputError('%s: expected offset(Rbase), got %r' % (where, token))
            imm = int(m.group(1))
            regs.append(parse_register(m.group(2), 'R', where))
    return Instruction(op, regs, imm, instruction_text(op, regs, imm))


def parse_assignments(line, pattern, where):
    pairs = []
    for piece in [p.strip() for p in line.split(',') if p.strip()]:
        m = re.fullmatch(pattern, piece, re.IGNORECASE)
        if not m:
            raise InputError('%s: cannot parse %r' % (where, piece))
        pairs.append(m.groups())
    return pairs


# function: read the input file (configuration, initial values, instructions)
def read_input(path):
    config = deepcopy(DEFAULT_CONFIG)
    setup = {'config': config, 'rob_entries': 128, 'issue_width': 1,
             'reg_int': [0] * NUM_REGS, 'reg_fp': [0.0] * NUM_REGS,
             'memory': [0] * MEM_BYTES, 'instructions': []}
    with open(path) as f:
        lines = f.read().splitlines()
    for lineno, raw in enumerate(lines, 1):
        # '#' starts a comment; this also skips the "# of rs ..." table header
        line = raw.split('#')[0].strip()
        if not line:
            continue
        low = line.lower()
        where = '%s:%d' % (path, lineno)
        row = next(((name, unit) for name, unit in UNIT_ROWS if low.startswith(name)), None)
        if row:
            nums = [int(x) for x in re.findall(r'\d+', low[len(row[0]):])]
            keys = ['rs', 'ex', 'mem', 'fus'] if row[1] == 'ld_sd' else ['rs', 'ex', 'fus']
            if len(nums) not in (len(keys) - 1, len(keys)) or min(nums) < 1:
                raise InputError('%s: expected %s for %s' % (where, ', '.join(keys), row[0]))
            config[row[1]].update(zip(keys, nums))
        elif re.fullmatch(r'rob entries\s*=\s*\d+', low):
            setup['rob_entries'] = int(low.split('=')[1])
            if setup['rob_entries'] < 1:
                raise InputError('%s: ROB entries must be at least 1' % where)
        elif re.fullmatch(r'issue width\s*=\s*\d+', low):
            setup['issue_width'] = int(low.split('=')[1])
            if not 1 <= setup['issue_width'] <= MAX_ISSUE_WIDTH:
                raise InputError('%s: issue width must be 1 to %d' % (where, MAX_ISSUE_WIDTH))
        elif low.startswith('mem['):
            for addr, value in parse_assignments(low, r'mem\[\s*(\d+)\s*\]\s*=\s*(%s)' % NUMBER, where):
                addr = int(addr)
                if addr % 4 or addr >= MEM_BYTES:
                    raise InputError('%s: Mem[%d] is not a word address below %d' % (where, addr, MEM_BYTES))
                setup['memory'][addr] = float(value)
        elif re.match(r'[rf]\d+\s*=', low):
            for kind, num, value in parse_assignments(low, r'([rf])(\d+)\s*=\s*(%s)' % NUMBER, where):
                num = int(num)
                if num >= NUM_REGS:
                    raise InputError('%s: register %s%d does not exist' % (where, kind.upper(), num))
                if kind == 'r':
                    if float(value) != int(float(value)):
                        raise InputError('%s: R%d must be an integer' % (where, num))
                    if num == 0 and float(value) != 0:
                        raise InputError('%s: R0 is hardwired to 0' % where)
                    setup['reg_int'][num] = int(float(value))
                else:
                    setup['reg_fp'][num] = float(value)
        elif low.split()[0] in OPCODES:
            setup['instructions'].append(parse_instruction(line, where))
        else:
            raise InputError('%s: unrecognized line %r' % (where, raw.strip()))
    if not setup['instructions']:
        raise InputError('%s: no instructions found' % path)
    return setup
