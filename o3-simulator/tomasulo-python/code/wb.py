# Qing
# 29th May 2017
# Extended for COSC 6385 Assignment 1.

'''
WB stage: one CDB, one broadcast per cycle
1. pick the result that has waited longest (ties: oldest instruction)
2. broadcast it to the reservation stations, the ld_sd_queue and the ROB
The RAT keeps pointing to the ROB entry until commit, so a late broadcast of an
older instruction cannot overwrite the mapping of a younger writer.
'''


# function: broadcast
def broadcast(m, rob, cycle):
    rob.cdb = [cycle]
    for station in m.rs.values():
        for entry in station:
            if entry.busy and entry.valid_1st == 0 and entry.tag_1st is rob:
                entry.value_1st, entry.valid_1st, entry.ready_1st = rob.value, 1, cycle
            if entry.busy and entry.valid_2nd == 0 and entry.tag_2nd is rob:
                entry.value_2nd, entry.valid_2nd, entry.ready_2nd = rob.value, 1, cycle
    for entry in m.ld_sd_queue:
        if entry.valid == 0 and entry.reg_tag is rob:
            entry.reg_value, entry.valid, entry.base_ready = rob.value, 1, cycle
        if entry.op == 'Sd' and entry.data_valid == 0 and entry.data_tag is rob:
            entry.data, entry.data_valid, entry.data_ready = rob.value, 1, cycle


# function: wb
def wb(m, cycle):
    waiting = [rob for rob in m.ROB
               if rob.result_cycle is not None and rob.result_cycle < cycle and not rob.cdb]
    if waiting:
        broadcast(m, min(waiting, key=lambda rob: (rob.result_cycle, rob.seq)), cycle)
