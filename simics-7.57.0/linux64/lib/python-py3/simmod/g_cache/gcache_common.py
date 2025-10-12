# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
import cli
import math

#
# default cache status
#
def gc_cli_status_cmd(gc):
    return []

def gc_default_status_cmd(gc, cycle):
    assoc = gc.config_assoc
    line_number = gc.config_line_number
    line_size = gc.config_line_size
    set_nb = line_number/assoc

    print()
    print("Cache status:", gc.name)
    print("-------------")
    print("(M/E/S/I) for Modified/Exclusive/Shared/Invalid.")
    print("The value for each cache line is the base address, not the tag.")
    if cycle:
        if (gc.config_replacement_policy == "lru"):
            print("The value below each cache lines is the last access cycle.")
        else:
            print("*** LRU is not active, cycle information is not available.")
    if (gc.config_replacement_policy == "cyclic"):
        print("A '<' marks the next line that will be replaced.")
    print()

    for i in range(set_nb):
        for j in range(assoc):
            cl = gc.lines[i * assoc + j]
            if (cl[0] == 3):
                simics.pr("M ")
            elif (cl[0] == 2):
                simics.pr("E ")
            elif (cl[0] == 1):
                simics.pr("S ")
            else:
                simics.pr("I ")
            simics.pr("0x%016x" % (cl[1] * line_size))
            if (gc.config_replacement_policy == "cyclic"):
                if ((i * assoc + j) == gc.next_line_in_set[i]):
                    simics.pr("< ")
                else:
                    simics.pr("  ")
            else:
                simics.pr("  ")
        print()
        if cycle and (gc.config_replacement_policy == "lru"):
            for j in range(assoc):
                lu = gc.lines_last_used[i * assoc + j]
                simics.pr("    %016d  " % lu)
            print()
    print()


#
# info
#
def gc_default_info_cmd(gc):
    return [(None, [('Number of cache lines',  gc.config_line_number),
                    ('Cache line size of bytes', gc.config_line_size),
                    ('Total cache size of kbytes', (gc.config_line_number * gc.config_line_size) // 1024),
                    ('Associativity', gc.config_assoc),
                    ('Index', "virtual" if gc.config_virtual_index else "physical"),
                    ('Tag', "virtual" if gc.config_virtual_tag else "physical"),
                    ('Write allocate', "yes" if gc.config_write_allocate else "no"),
                    ('Write policy', "write-back" if gc.config_write_back else "write-through"),
                    ('Replacement policy', gc.config_replacement_policy),
                    ('Connected to CPUs', gc.cpus if gc.cpus else "None"),
                    ('Next level cache', gc.timing_model if gc.timing_model else "None")])]

# statistics
#
def gc_default_stats_cmd(gc, ratio):
    def prstat(s, val):
        print("%32s:%14s" % (s, cli.number_str(val, 10)))
    def prstat_ratio(s, miss, total):
        print("%32s:%14.2f%%" % (s, 100.0 - (100.0 * miss) / total))

    print()
    print("Cache statistics:", gc.name)
    print("-----------------")

    prstat("Total number of transactions", gc.stat_transaction)
    print()
    prstat("Cacheable device data reads", gc.stat_c_dev_data_read)
    prstat("Cacheable device data writes", gc.stat_c_dev_data_write)
    prstat("Uncacheable device data reads (DMA)", gc.stat_dev_data_read)
    prstat("Uncacheable device data writes (DMA)", gc.stat_dev_data_write)
    print()
    prstat("Uncacheable data reads", gc.stat_uc_data_read)
    prstat("Uncacheable data writes", gc.stat_uc_data_write)
    prstat("Uncacheable instruction fetches", gc.stat_uc_inst_fetch)
    print()
    prstat("Data read transactions", gc.stat_data_read)
    prstat("Data read misses", gc.stat_data_read_miss)
    if (gc.stat_data_read > 0 and ratio):
        prstat_ratio("Data read hit ratio",
                     gc.stat_data_read_miss, gc.stat_data_read)
    print()
    prstat("Instruction fetch transactions", gc.stat_inst_fetch)
    prstat("Instruction fetch misses", gc.stat_inst_fetch_miss)
    if (gc.stat_inst_fetch > 0 and ratio):
        prstat_ratio("Instruction fetch hit ratio",
                     gc.stat_inst_fetch_miss, gc.stat_inst_fetch)
    print()
    prstat("Data write transactions", gc.stat_data_write)
    prstat("Data write misses", gc.stat_data_write_miss)
    if (gc.stat_data_write > 0 and ratio):
        prstat_ratio("Data write hit ratio",
                     gc.stat_data_write_miss, gc.stat_data_write)
    print()
    prstat("Copy back transactions", gc.stat_copy_back)
    print()

    try:
        if gc.stat_lost_stall_cycles:
            prstat("Lost Stall Cycles", gc.stat_lost_stall_cycles)
    except:
        pass

    try:
        if gc.snoopers:
            prstat("[MESI] Exclusive to Shared",
                   gc.stat_mesi_exclusive_to_shared)
            prstat("[MESI] Modified to Shared",
                   gc.stat_mesi_modified_to_shared)
            prstat("[MESI] Invalidates", gc.stat_mesi_invalidate)
    except:
        pass

#
# reset statistics
#
def gc_default_reset_stats_cmd(gc):
    # flush the STC counters before resetting stats
    for c in gc.cpus:
        simics.SIM_STC_flush_cache(c)

    gc.stat_transaction = 0

    gc.stat_dev_data_read = 0
    gc.stat_dev_data_write = 0

    gc.stat_uc_data_read = 0
    gc.stat_uc_data_write = 0
    gc.stat_uc_inst_fetch = 0

    gc.stat_data_read = 0
    gc.stat_data_read_miss = 0
    gc.stat_inst_fetch = 0
    gc.stat_inst_fetch_miss = 0
    gc.stat_data_write = 0
    gc.stat_data_write_miss = 0

    gc.stat_copy_back = 0

    try:
        gc.stat_mesi_exclusive_to_shared = 0
        gc.stat_mesi_modified_to_shared = 0
        gc.stat_mesi_invalidate = 0
    except:
        pass

#
# reset the cache lines
#
def gc_default_reset_cache_lines_cmd(gc):
    # flush the STC before emptying the cache
    for c in gc.cpus:
        simics.SIM_STC_flush_cache(c)
    for i in range(gc.config_line_number):
        # reset the line's values
        gc.lines[i] = [0,0,0,0]

#
# add a profiler to the cache
#
def type_expander(string):
    return cli.get_completions(string,
                           ["data-read-miss-per-instruction",
                            "data-read-miss-per-virtual-address",
                            "data-read-miss-per-physical-address",
                            "data-write-miss-per-instruction",
                            "data-write-miss-per-virtual-address",
                            "data-write-miss-per-physical-address",
                            "instruction-fetch-miss-per-virtual-address",
                            "instruction-fetch-miss-per-physical-address"])

type_to_itype = {
    "data-read-miss-per-instruction"              : (0, 1, 0),
    "data-read-miss-per-virtual-address"          : (1, 0, 0),
    "data-read-miss-per-physical-address"         : (2, 0, 1),
    "data-write-miss-per-instruction"             : (3, 1, 0),
    "data-write-miss-per-virtual-address"         : (4, 0, 0),
    "data-write-miss-per-physical-address"        : (5, 0, 1),
    "instruction-fetch-miss-per-virtual-address"  : (6, 1, 0),
    "instruction-fetch-miss-per-physical-address" : (7, 1, 1)}

# calculates floor(log2(x))
def log2(x):
    return math.frexp(x)[1] - 1

def gc_add_profiler(gc, type, obj):
    try:
        itype, instr_gran, phys_addr = type_to_itype[type]
    except:
        print("'type' is not a valid profiler type.")
        return

    # set an existing profiler
    if obj:
        try:
            real_obj = simics.SIM_get_object(obj)
            simics.SIM_get_interface(real_obj, "data_profiler")
        except:
            print("'obj' is not a valid data profiler.")
            return
        gc.profilers[itype] = simics.SIM_get_object(obj)
    # create an adapted profiler
    else:
        if gc.profilers[itype]:
            print("There's already an active profiler connected to the cache.")
        else:
            try:
                if instr_gran:
                    granularity = 4
                else:
                    granularity = gc.config_line_size
                name = gc.name + "_prof_" + type
                # Don't use hyphens in object name
                name = name.replace('-', '_')
                desc = gc.name + " prof: " + type
                prof = simics.SIM_create_object(
                    'data-profiler', name,
                    [['granularity', log2(granularity)],
                     ['physical_addresses', phys_addr],
                     ['description', desc]])

                # flush the STC counters before adding the profiler
                for c in gc.cpus:
                    simics.SIM_STC_flush_cache(c)

                gc.profilers[itype] = prof
                print(("[%s] New profiler added for %s: %s"
                       % (gc.name, type, name)))
            except:
                print("Failed to create profiler")

def gc_rem_profiler(gc, type):
    try:
        itype = type_to_itype[type]
    except:
        print("'type' is not a valid profiler type.")
        return

    # flush the STC counters before removing the profiler
    for c in gc.cpus:
        simics.SIM_STC_flush_cache(c)
    gc.profilers[itype[0]] = None

def gc_define_cache_commands(device_name,
                             gc_status_cmd,
                             gc_info_cmd,
                             gc_stats_cmd,
                             gc_reset_cache_lines_cmd,
                             gc_reset_stats_cmd = None):
    # status
    if not gc_status_cmd:
        gc_status_cmd = gc_default_status_cmd
    cli.new_command("line-status", gc_status_cmd,
                [cli.arg(cli.flag_t, "-cycle")],
                cls = device_name,
                short ="print the cache lines status",
                doc = """
Print the cache lines status. With the <tt>-cycle</tt> flag, this command
prints the last cycle each cache line was accessed (if LRU replacement policy
is active). A '&lt;' marks the next line to be replaced (if cyclic replacement
policy is active).
""")
    cli.new_status_command(device_name, gc_cli_status_cmd)
    # info
    if not gc_info_cmd:
        gc_info_cmd = gc_default_info_cmd
    cli.new_info_command(device_name, gc_info_cmd)
    # statistics
    if not gc_stats_cmd:
        gc_stats_cmd = gc_default_stats_cmd
    cli.new_command("statistics", gc_stats_cmd,
                [],
                cls = device_name,
                short="print the cache statistics",
                doc  = """
                Print the current value of the cache statistics (this will flush the STC counters to report correct values).
                """)
    # reset-statistics
    if not gc_reset_stats_cmd:
        gc_reset_stats_cmd = gc_default_reset_stats_cmd
    cli.new_command("reset-statistics", gc_reset_stats_cmd,
                [],
                cls = device_name,
                short="reset the cache statistics",
                doc  = """
                Reset the cache statistics.
                """)
    # reset-cache-lines
    if not gc_reset_cache_lines_cmd:
        gc_reset_cache_lines_cmd = gc_default_reset_cache_lines_cmd
    cli.new_command("reset-cache-lines", gc_reset_cache_lines_cmd,
                [],
                cls = device_name,
                short="reset all the cache lines",
                doc  = """
                Reset all the cache lines to their default values.
                """)
    # add-profiler
    cli.new_command("add-profiler", gc_add_profiler,
            [cli.arg(cli.str_t, "type", "?", "", expander = type_expander),
             cli.arg(cli.str_t, "profiler", "?", "")],
            cls = device_name,
            short="add a profiler to the cache",
            doc  = """
Add a profiler of the given <arg>type</arg> to the cache. If a
<arg>profiler</arg> is passed as argument, it will be used instead of a newly
created object.
""")

    # remove-profiler
    cli.new_command("remove-profiler", gc_rem_profiler,
                [cli.arg(cli.str_t, "type", "?", "", expander = type_expander)],
                cls = device_name,
                short="remove a profiler from the cache",
                doc  = """
Remove the profiler of a given <arg>type</arg> from the cache.
""")
