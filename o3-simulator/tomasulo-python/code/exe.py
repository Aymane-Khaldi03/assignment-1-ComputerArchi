# Qing
# 24th May 2017
# Extended for COSC 6385 Assignment 1: branch resolution and recovery.

'''
EX stage
1. effective-address calculation for the ld_sd_queue (dedicated adder, not the integer ALU)
2. start ready instructions from the reservation stations on free functional units
   -- the integer adder is unpipelined; the FP adder and multiplier are pipelined
   -- the reservation station entry is freed when execution starts
3. at the end of EX: resolve branches and check stores against younger loads;
   on a misprediction or memory-order violation, squash and redirect fetch
'''
from init import BTB_ENTRIES


# function: compute an ALU result
def compute(op, value1, value2):
    if op in ('Add', 'Addi', 'Add.d'):
        return value1 + value2
    if op in ('Sub', 'Sub.d'):
        return value1 - value2
    return value1 * value2                  # Mult.d


# function: first unit that can start an operation this cycle
def free_unit(units, cycle):
    for unit in units:
        if unit.can_start(cycle):
            return unit
    return None


# function: ld/sd effective-address calculation (oldest first)
def ld_sd_execution(m, cycle):
    latency = m.cfg['ld_sd']['ex']
    for entry in m.ld_sd_queue:
        rob = entry.dest_tag
        if entry.addr_cycle is not None or not entry.valid \
                or entry.base_ready >= cycle or rob.issue[0] >= cycle:
            continue
        unit = free_unit(m.addr_units, cycle)
        if unit is None:
            return
        unit.start(rob, cycle, latency)
        entry.address = entry.reg_value + entry.immediate
        entry.addr_cycle = cycle + latency - 1
        rob.address = entry.address
        rob.exe = [cycle, entry.addr_cycle]


# function: functional units execution (oldest ready instruction first)
def fu_exe(m, cycle):
    for name in ('int_adder', 'fp_adder', 'fp_multi'):
        latency = m.cfg[name]['ex']
        for unit in m.fus[name]:
            if not unit.can_start(cycle):
                continue
            ready = [e for e in m.rs[name] if e.busy and e.valid_1st and e.valid_2nd
                     and e.ready_1st < cycle and e.ready_2nd < cycle
                     and e.dest_tag.issue[0] < cycle]
            if not ready:
                break
            entry = min(ready, key=lambda e: e.dest_tag.seq)
            rob = entry.dest_tag
            unit.start(rob, cycle, latency)
            rob.exe = [cycle, cycle + latency - 1]
            if entry.op in ('Beq', 'Bne'):
                rob.operands = (entry.value_1st, entry.value_2nd)
            else:
                rob.value = compute(entry.op, entry.value_1st, entry.value_2nd)
                rob.result_cycle = cycle + latency - 1
            entry.busy = 0                  # reservation station released


# recover the RAT from the register file and the surviving ROB entries
def recover_rat(m):
    m.rat_int = [None] * len(m.rat_int)
    m.rat_fp = [None] * len(m.rat_fp)
    for rob in m.ROB:                       # oldest to youngest: youngest writer wins
        register = rob.dest_tag
        if register is not None and register != 'R0':
            (m.rat_int if register[0] == 'R' else m.rat_fp)[int(register[1:])] = rob


# function: squash ROB entries from index first to the tail and redirect fetch
def squash(m, first, cycle, new_PC):
    wrong = m.ROB[first:]
    del m.ROB[first:]
    for rob in wrong:
        rob.squashed = True
    # clear the reservation stations of the wrong instructions
    for station in m.rs.values():
        for entry in station:
            if entry.busy and entry.dest_tag.squashed:
                entry.busy = 0
    for unit in [u for units in m.fus.values() for u in units] + m.addr_units:
        if unit.owner is not None and unit.owner.squashed and unit.busy_until > cycle:
            unit.busy_until = cycle         # unpipelined unit becomes free next cycle
    m.ld_sd_queue = [e for e in m.ld_sd_queue if not e.dest_tag.squashed]
    if m.mem_owner is not None and m.mem_owner.squashed and m.mem_busy_until > cycle:
        m.mem_busy_until = cycle            # cancel a wrong-path memory read
        m.mem_owner = None
    recover_rat(m)
    if wrong:                               # nothing to squash after a final branch
        m.next_seq = wrong[0].seq
    m.stats['squashed'] += len(wrong)
    # the recovery takes one cycle: correct fetch starts in cycle + 2
    m.PC = new_PC
    m.fetch_resume = cycle + 2


# function: resolve a branch at the end of its EX stage
def resolve_branch(m, rob, cycle):
    value1, value2 = rob.operands
    taken = (value1 == value2) if rob.ins.op == 'Beq' else (value1 != value2)
    target = rob.PC + 1 + rob.ins.imm       # PC + 4 + offset << 2, in words
    valid_target = 0 <= target <= len(m.instructions)
    if taken and not valid_target:
        rob.fault = 'branch target %d is outside the program' % target
    actual_next = (target if valid_target else len(m.instructions)) if taken else rob.PC + 1
    rob.resolved = True
    if valid_target:                        # update the BTB and one-bit predictor
        slot = m.btb[rob.PC % BTB_ENTRIES]
        slot.valid, slot.tag, slot.target, slot.taken = True, rob.PC, target, taken
    if actual_next != rob.predicted_next:
        rob.mispredicted = True
        m.stats['mispredictions'] += 1
        squash(m, m.ROB.index(rob) + 1, cycle, actual_next)


# function: a store address became known; squash younger loads that read stale data
def check_younger_loads(m, store, cycle):
    for i in range(m.ROB.index(store) + 1, len(m.ROB)):
        load = m.ROB[i]
        if load.ins.op == 'Ld' and load.mem and load.address == store.address \
                and (load.src == 'mem' or load.src.seq < store.seq):
            m.stats['violations'] += 1
            squash(m, i, cycle, load.PC)
            return


# function: execution
def exe(m, cycle):
    ld_sd_execution(m, cycle)
    fu_exe(m, cycle)
    # end of EX in this cycle, oldest first (a squash removes the younger ones)
    for rob in list(m.ROB):
        if rob.squashed or not rob.exe or rob.exe[1] != cycle:
            continue
        if rob.ins.op in ('Beq', 'Bne'):
            resolve_branch(m, rob, cycle)
        elif rob.ins.op == 'Sd':
            check_younger_loads(m, rob, cycle)
