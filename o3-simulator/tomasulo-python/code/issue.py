# Qing
# 21st May 2017
# Extended for COSC 6385 Assignment 1: in-order multi-issue and branch prediction.

"""
ISSUE stage (includes fetch and decode). Up to issue_width instructions per cycle,
in program order:
1. put the instruction in the ROB
2. put it in a reservation station or the ld_sd_queue
3. update the RAT
Issue stops at the first instruction that finds no ROB / RS / queue entry, and
after a branch predicted taken (the next group is fetched from its target).
"""
from init import ld_sd_entry, ROB_entry, UNIT, BTB_ENTRIES


# function: find a tag for ld_sd_entry
def find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue):
    used = {entry.ld_sd_tag for entry in ld_sd_queue}
    for i in range(size_ld_sd_queue):
        if 'ldsd' + str(i) not in used:
            return 'ldsd' + str(i)


# function: put ins into ROB
def put_ins_into_ROB(m, ins, cycle):
    entry = ROB_entry(m.next_seq, m.size_ROB, m.PC, ins, cycle)
    m.next_seq += 1
    m.ROB.append(entry)
    return entry


# function: read a source register -> (tag, value, valid, ready cycle)
def read_operand(m, register):
    kind, num = register[0], int(register[1:])
    if kind == 'R' and num == 0:          # R0 is hardwired to 0
        return None, 0, 1, 0
    producer = (m.rat_int if kind == 'R' else m.rat_fp)[num]
    if producer is None:                  # value is in the register file
        return None, (m.reg_int if kind == 'R' else m.reg_fp)[num], 1, 0
    if producer.cdb:                      # already broadcast, value is in the ROB
        return None, producer.value, 1, producer.cdb[0]
    return producer, None, 0, 0           # wait for the producer on the CDB


# function: put ins into reservation station
def put_ins_into_rs(entry, ins, rob, m):
    entry.busy = 1
    entry.op = ins.op
    entry.dest_tag = rob
    entry.tag_1st, entry.value_1st, entry.valid_1st, entry.ready_1st = read_operand(m, ins.srcs[0])
    if len(ins.srcs) == 2:
        entry.tag_2nd, entry.value_2nd, entry.valid_2nd, entry.ready_2nd = read_operand(m, ins.srcs[1])
    else:                                 # Addi: immediate operand
        entry.tag_2nd, entry.value_2nd, entry.valid_2nd, entry.ready_2nd = None, ins.imm, 1, 0


# function: put ins into ld_sd_queue
def put_ins_into_ldsd(ldsd_tag, ins, rob, m):
    entry = ld_sd_entry(ldsd_tag, ins.op, rob)
    entry.immediate = ins.imm
    entry.reg_tag, entry.reg_value, entry.valid, entry.base_ready = read_operand(m, ins.base)
    if ins.op == 'Sd':
        entry.data_tag, entry.data, entry.data_valid, entry.data_ready = read_operand(m, ins.data)
    rob.lsq = entry
    m.ld_sd_queue.append(entry)


# function: check space of reservation station
def check_rs_space(station):
    for i in range(len(station)):
        if station[i].busy == 0:
            return i
    return -1


# update RAT (after the sources were read)
def update_rat(rob, m):
    register = rob.dest_tag
    if register is None or register == 'R0':
        return
    (m.rat_int if register[0] == 'R' else m.rat_fp)[int(register[1:])] = rob


# predict the next PC: one-bit predictor in an 8-entry BTB indexed by PC[2:0]
def predict(rob, m):
    slot = m.btb[rob.PC % BTB_ENTRIES]
    if slot.valid and slot.tag == rob.PC and slot.taken:
        rob.predicted_next = slot.target
    else:
        rob.predicted_next = rob.PC + 1
    return rob.predicted_next


""""""
def issue(m, cycle):
    if cycle < m.fetch_resume:            # recovering from a squash
        return
    for _ in range(m.issue_width):
        if m.PC >= len(m.instructions):
            return
        ins = m.instructions[m.PC]
        unit = UNIT[ins.op]
        # check space
        if len(m.ROB) >= m.size_ROB:
            return
        if unit == 'ld_sd':
            if len(m.ld_sd_queue) >= m.size_ld_sd_queue:
                return
        else:
            index = check_rs_space(m.rs[unit])
            if index < 0:
                return
        rob = put_ins_into_ROB(m, ins, cycle)
        if unit == 'ld_sd':
            put_ins_into_ldsd(find_tag_new_ldsd_entry(m.ld_sd_queue, m.size_ld_sd_queue), ins, rob, m)
        else:
            put_ins_into_rs(m.rs[unit][index], ins, rob, m)
        update_rat(rob, m)
        if ins.op in ('Beq', 'Bne'):
            m.PC = predict(rob, m)
            if m.PC != rob.PC + 1:        # predicted taken: fetch the target next cycle
                return
        else:
            m.PC += 1
