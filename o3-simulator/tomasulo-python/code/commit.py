# Qing
# 29th may 2017
# Extended for COSC 6385 Assignment 1: commit up to issue_width per cycle.

'''
COMMIT stage, in program order, up to issue_width instructions per cycle
-- ALU / Ld: after the CDB broadcast, write the architectural register
-- branch: after it was resolved in EX
-- Sd: writes memory here, using the single memory port for "Cycles in Mem"
   cycles; it leaves the ld_sd_queue when it commits
'''
from init import MEM_BYTES, SimulationError


# function: modify architectural reg
def modify_arch_reg(rob, m):
    register = rob.dest_tag
    if register is None or register == 'R0':   # R0 stays 0
        return
    num = int(register[1:])
    if register[0] == 'R':
        m.reg_int[num] = rob.value
        if m.rat_int[num] is rob:
            m.rat_int[num] = None
    else:
        m.reg_fp[num] = rob.value
        if m.rat_fp[num] is rob:
            m.rat_fp[num] = None


# function: can the ROB head commit in this cycle?
def committable(rob, m, cycle):
    op = rob.ins.op
    if op in ('Beq', 'Bne'):
        return rob.resolved and rob.exe[1] < cycle
    if op == 'Sd':
        entry = rob.lsq
        return (entry.addr_cycle is not None and entry.addr_cycle < cycle and entry.data_valid
                and entry.data_ready < cycle and m.mem_busy_until < cycle)
    return bool(rob.cdb) and rob.cdb[0] < cycle


# function: commit
def commit(m, cycle):
    for _ in range(m.issue_width):
        if not m.ROB or not committable(m.ROB[0], m, cycle):
            return
        rob = m.ROB[0]
        if rob.ins.op == 'Sd' and (rob.address % 4 or not 0 <= rob.address < MEM_BYTES):
            rob.fault = 'store address %d is not a word address below %d' % (rob.address, MEM_BYTES)
        if rob.fault:
            raise SimulationError('cycle %d: %s: %s' % (cycle, rob.ins.text, rob.fault))
        if rob.ins.op == 'Sd':
            end = cycle + m.cfg['ld_sd']['mem'] - 1
            rob.mem = [cycle, end]
            m.mem_busy_until, m.mem_owner = end, None
            m.memory[rob.address] = float(rob.lsq.data)
            m.ld_sd_queue.remove(rob.lsq)
        else:
            modify_arch_reg(rob, m)
        rob.commit = [cycle]
        m.committed.append(m.ROB.pop(0))
