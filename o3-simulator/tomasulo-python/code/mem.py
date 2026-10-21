# Qing
# 26th May 2017
# Extended for COSC 6385 Assignment 1: store forwarding rules of the handout.

'''
MEM stage for loads (stores write memory in the commit stage)
1. forwarding-from-a-store is checked first: the nearest older Sd whose address is
   known and equal; forwarding takes 1 cycle once that Sd has its data
2. otherwise (no match, even with unresolved older Sd addresses) the Ld accesses the
   single-ported, non-pipelined memory for "Cycles in Mem" cycles
3. once a Ld has its value, its ld_sd_queue entry is cleared
'''
from init import MEM_BYTES


# function: forward check from sd (nearest older Sd with a known, equal address)
def forward_check_from_sd(ld_sd_queue, index, cycle):
    load = ld_sd_queue[index]
    for i in reversed(range(index)):
        entry = ld_sd_queue[i]
        if entry.op == 'Sd' and entry.addr_cycle is not None and entry.addr_cycle < cycle \
                and entry.address == load.address:
            return entry
    return None


# function: read a word for a load (invalid addresses fault only if the load commits)
def read_memory(m, address, rob):
    if address % 4 or not 0 <= address < MEM_BYTES:
        rob.fault = 'load address %d is not a word address below %d' % (address, MEM_BYTES)
        return 0.0
    return float(m.memory[address])


# function: mem
def mem(m, cycle):
    time_ld_sd_mem = m.cfg['ld_sd']['mem']
    for entry in list(m.ld_sd_queue):
        rob = entry.dest_tag
        if entry.op != 'Ld' or rob.mem or entry.addr_cycle is None or entry.addr_cycle >= cycle:
            continue
        store = forward_check_from_sd(m.ld_sd_queue, m.ld_sd_queue.index(entry), cycle)
        if store is not None:
            if store.data_valid and store.data_ready < cycle:
                rob.mem = [cycle, cycle]
                rob.value = float(store.data)
                rob.src = store.dest_tag
                rob.result_cycle = cycle
                entry.leave_cycle = cycle
            continue                       # wait for the store data
        if m.mem_busy_until < cycle:       # memory port free
            end = cycle + time_ld_sd_mem - 1
            rob.mem = [cycle, end]
            rob.value = read_memory(m, entry.address, rob)
            rob.src = 'mem'
            rob.result_cycle = end
            entry.leave_cycle = end
            m.mem_busy_until = end
            m.mem_owner = rob
    # loads that get their value in this cycle leave the queue
    m.ld_sd_queue = [e for e in m.ld_sd_queue if e.leave_cycle != cycle]
