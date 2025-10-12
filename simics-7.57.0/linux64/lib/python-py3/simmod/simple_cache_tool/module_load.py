# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import sim_commands
import instrumentation
import table
import re

from cli import (
    CliError,
    arg,
    command_return,
    flag_t,
    int_t,
    new_command,
    new_info_command,
    new_status_command,
    str_t,
    )
from simics import *

CL_Invalid   = 0
CL_Shared    = 1
CL_Exclusive = 2
CL_Modified  = 3

state_map = {
    CL_Invalid   : "I",
    CL_Shared    : "S",
    CL_Exclusive : "E",
    CL_Modified  : "M"
}

# create extra namespace for cache hierarchies
def create_cache_place(cpu):
    cpu_comp = cpu.name.split(".")
    cpu_path = cpu_comp[:-1]
    cpu_base = cpu_comp[-1]

    mo = re.match(r'.*\[(\d+)\]\[\d+\]', cpu_base)
    if mo:
        namespace = "cache[%s]" % mo.group(1)
    else:
        namespace = "cache"

    cpu_root = ".".join(cpu_path)
    cpu_root_obj = SIM_get_object(cpu_root)

    if not hasattr(cpu_root_obj, namespace):
        cache = SIM_create_object("namespace", cpu_root + "." + namespace)
    else:
        cache = SIM_get_object(cpu_root + "." + namespace)

    return cpu_root_obj, cache

# create or get a new cache
def get_cache(con, name, level, attrs):
    cpu = con.cpu
    root, cache_place = create_cache_place(cpu)
    full_name = cache_place.name + "." + name
    if hasattr(cache_place, name):
        return (SIM_get_object(full_name), cache_place, None)

    dirname = "directory_l" + str(level)
    if not hasattr(root, dirname):
        dir = SIM_create_object("simple_directory", root.name+"."+dirname)
    else:
        dir = SIM_get_object(root.name + "." + dirname)

    c = SIM_create_object("simple_cache", full_name,
                          [["directory", dir],
                           ["cpu", cpu],
                           ["level", level]] + attrs)
    c.cache_conn = con
    return c, cache_place, c


common_cache_args = [arg(int_t, "line-size", "?", 64),
                     arg(int_t, "sets"),
                     arg(int_t, "ways", "?", 1),
                     arg(int_t, "read-penalty", "?", 0),
                     arg(int_t, "read-miss-penalty", "?", 0),
                     arg(int_t, "write-penalty", "?", 0),
                     arg(int_t, "write-miss-penalty", "?", 0),
                     arg(int_t, "prefetch-additional", "?", 0),
                     arg(flag_t, "-write-through"),
                     arg(flag_t, "-no-write-allocate"),
                     arg(flag_t, "-prefetch-adjacent"),
                     arg(flag_t, "-ip-read-prefetcher"),
                     arg(flag_t, "-ip-write-prefetcher")]

def get_cache_attrs(block_size, index_number, ways,
                    read_hit_penalty, read_miss_penalty,
                    write_hit_penalty, write_miss_penalty,
                    prefetch_additional,
                    write_through, no_write_allocate,
                    prefetch_adjacent,
                    ip_read_prefetcher, ip_write_prefetcher):
    return [["cache_block_size", block_size],
            ["cache_set_number", index_number],
            ["cache_ways", ways],
            ["read_penalty", read_hit_penalty],
            ["read_miss_penalty", read_miss_penalty],
            ["write_penalty", write_hit_penalty],
            ["write_miss_penalty", write_miss_penalty],
            ["prefetch_additional", prefetch_additional],
            ["write_back", not write_through],
            ["write_allocate", not no_write_allocate],
            ["prefetch_adjacent", prefetch_adjacent],
            ["ip_read_prefetcher", ip_read_prefetcher],
            ["ip_write_prefetcher", ip_write_prefetcher]]

def return_objs(caches):
    msg = ""
    for c in caches:
        msg += "Created cache %s\n" % c.name

    return command_return(message = (msg[:-1] if msg else ""), value = caches)

def add_l1d_cache_cmd(obj, name, *cache_args):
    attrs = get_cache_attrs(*cache_args)
    caches = []
    for con in obj.connections:
        dl1, _, new = get_cache(con, name, 1, attrs)
        if new:
            caches.append(new)
        con.dcache = dl1
    return return_objs(caches)

def add_l1i_cache_cmd(obj, name, no_issue, *cache_args):
    attrs = get_cache_attrs(*cache_args)
    caches = []
    for con in obj.connections:
        il1, _, new = get_cache(con, name, 1, attrs)
        if new:
            caches.append(new)

        con.icache = il1
        con.issue_instructions = not no_issue
    return return_objs(caches)

def add_l2_cache_cmd(obj, name, *cache_args):
    attrs = get_cache_attrs(*cache_args)
    caches = []
    for con in obj.connections:
        l2, cache, new = get_cache(con, name, 2, attrs)
        if new:
            caches.append(new)

        prev_level = []
        for c in SIM_object_iterator(cache):
            if c.classname == "simple_cache" and c.level == 1:
                prev_level.append(c)
                c.next_level = l2
        l2.prev_level = prev_level
    return return_objs(caches)

def add_l3_slice_cache_cmd(obj, name, *cache_args):
    attrs = get_cache_attrs(*cache_args)
    caches = []
    for con in obj.connections:
        l3, cache, new = get_cache(con, name, 3, attrs)
        if new:
            caches.append(new)

        l2 = None
        for c in SIM_object_iterator(cache):
            if c.classname == "simple_cache" and c.level == 2:
                if l2:
                    raise CliError("More than one l2 cache found")
                l2 = c
                c.next_level = l3
    return return_objs(caches)

def add_l3_cache_cmd(obj, name, *cache_args):
    attrs = get_cache_attrs(*cache_args)
    caches = []
    for con in obj.connections:
        cpu = con.cpu
        cpu_comp = cpu.name.split(".")
        cpu_path = cpu_comp[:-1]
        cpu_root = ".".join(cpu_path)
        cpu_root_obj = SIM_get_object(cpu_root)
        if hasattr(cpu_root_obj, name):
            continue

        dir = SIM_create_object(
            "simple_directory", cpu_root + ".directory_l3", [])
        l3 = SIM_create_object("simple_cache", cpu_root + "." + name,
                               [["directory", dir]] + attrs)
        caches.append(l3)
        l3.cache_conn = con

        prev_level = []
        for c in SIM_object_iterator(cpu_root_obj):
            if c.classname == "simple_cache" and c.level == 2:
                prev_level.append(c)
                c.next_level = l3

        l3.prev_level = prev_level
    return return_objs(caches)

def get_cache_connections(cache):
    t = cache.cache_conn.tool
    conns = []
    for c in t.connections:
        if c.icache == cache:
            conns.append(c)
        if c.dcache == cache:
            conns.append(c)
    return conns

def get_sum_of_attr(conns, attr):
    sum = 0
    for conn in conns:
        sum += getattr(conn, attr)
    return sum

def get_statistics_table(obj):
    cols = [[[Column_Key_Name, "Counter"],
             [Column_Key_Description, "Various cache counters"]],
            [[Column_Key_Name, "Value"],
             [Column_Key_Int_Radix, 10],
             [Column_Key_Description, "The value of the counter"]],
            [[Column_Key_Name, "%"],
             [Column_Key_Description, "Percentage"]]
            ]
    properties = [ [Table_Key_Name, "Cache statistics"],
                   [Table_Key_Description, ("Various statistics")],
                   [Table_Key_Columns, cols]]

    cache_connections = get_cache_connections(obj)

    data = []
    if obj.stat_data_read != 0:
        data.append(["read accesses", obj.stat_data_read, ""])
        data.append(["read misses", obj.stat_data_read_miss,
                     (obj.stat_data_read_miss*100.0)/obj.stat_data_read])

    if obj.stat_data_write != 0:
        data.append(["write accesses", obj.stat_data_write, ""])

        data.append(["write misses", obj.stat_data_write_miss,
                     (obj.stat_data_write_miss*100.0)/obj.stat_data_write])

    if obj.stat_data_write_back != 0:
        data.append(["write backs (from previous)", obj.stat_data_write_back,
                     ""])

    if obj.stat_data_write_back_miss:
        data.append(["write back misses (from previous)",
            obj.stat_data_write_back_miss,
            (obj.stat_data_write_back_miss*100.0)/obj.stat_data_write_back])

    if obj.stat_data_read_for_ownership != 0:
        data.append(["read for ownership accesses",
                     obj.stat_data_read_for_ownership, ""])
        data.append(["read for ownership misses",
                     obj.stat_data_read_for_ownership_miss,
                     (obj.stat_data_read_for_ownership_miss*100.0)
                     /obj.stat_data_read_for_ownership])

    if obj.stat_data_prefetch != 0:
        data.append(["prefetch accesses", obj.stat_data_prefetch, ""])

        data.append(["prefetch misses", obj.stat_data_prefetch_miss,
                     (obj.stat_data_prefetch_miss*100.0)
                     /obj.stat_data_prefetch])

    if obj.stat_data_prefetch_read_for_ownership != 0:
        data.append(["read for ownership prefetch accesses",
                     obj.stat_data_prefetch_read_for_ownership, ""])
        data.append(["read for ownership prefetch misses",
                     obj.stat_data_prefetch_read_for_ownership_miss,
                     (obj.stat_data_prefetch_read_for_ownership_miss*100.0)
                     /obj.stat_data_prefetch_read_for_ownership])

    prefetches = (obj.stat_data_prefetch
                  + obj.stat_data_prefetch_read_for_ownership)
    if prefetches and obj.stat_prefetches_used:
        data.append(["prefetched lines used",
                     obj.stat_prefetches_used,
                     (obj.stat_prefetches_used*100.0)/prefetches])

    prefetch_instructions = get_sum_of_attr(
        cache_connections, "prefetch_instructions")

    if prefetch_instructions:
        data.append(["prefetch instructions",
                     prefetch_instructions, ""])

    if obj.stat_instr_fetch != 0:
        data.append(["instruction fetch", obj.stat_instr_fetch, ""])
        data.append(["instruction misses", obj.stat_instr_fetch_miss,
                     (obj.stat_instr_fetch_miss*100.0)/obj.stat_instr_fetch])

    if obj.evicted_total:
        data.append(["evicted lines (total)", obj.evicted_total, ""])

    if obj.evicted_modified:
        data.append(["evicted modified lines", obj.evicted_modified,
                     (obj.evicted_modified*100.0) / obj.evicted_total])

    cache_all_flush_instructions = get_sum_of_attr(
        cache_connections, "cache_all_flush_instructions")

    if cache_all_flush_instructions:
        data.append(["entire cache flushes (invd, wbinvd)",
                     cache_all_flush_instructions, ""])

    cache_line_flush_instructions = get_sum_of_attr(
        cache_connections, "cache_line_flush_instructions")

    if cache_line_flush_instructions:
        data.append(["cache line flushes (clflush)",
                     cache_line_flush_instructions, ""])

    uncachable_reads = get_sum_of_attr(cache_connections, "uncachable_reads")
    if uncachable_reads != 0:
        data.append(["uncachable read accesses",
                     uncachable_reads, ""])

    uncachable_writes = get_sum_of_attr(cache_connections, "uncachable_writes")
    if uncachable_writes != 0:
        data.append(["uncachable write accesses",
                     uncachable_writes, ""])

    return properties, data

def print_statistics_cmd(obj, *table_args):
    properties, data = get_statistics_table(obj)
    table.show(properties, data, *table_args)

table.new_table_command("print-statistics", print_statistics_cmd,
                        args = [],
                        cls = "simple_cache",
                        short = "print statistics",
                        sortable_columns = ["Counter"],
                        doc = ("""Print statistics about the cache.
                        """))

def get_see_also(me):
    s = set(["<simple_cache_tool>.add-l1i-cache",
         "<simple_cache_tool>.add-l2-cache",
         "<simple_cache_tool>.add-l3-cache",
         "<simple_cache_tool>.add-l3-cache-slice",
         "<simple_cache_tool>.list-caches",
             ])
    return sorted(list(s - set([me])))

common_cache_doc = """<arg>name</arg> can be given to set a name for
the cache object in the hierarchy. <arg>line-size</arg> is cache line
size (default 64 bytes), <arg>sets</arg> number of sets/indices, and
<arg>ways</arg> number of ways (default 1).

You can configure the cache to be a write through cache by giving the
<tt>-write-through</tt> flag, default is a write back cache.

To prevent the cache from allocating lines on writes use the
<tt>-no-write-allocate</tt> flag.

The <arg>read-penalty</arg>, <arg>read-miss-penalty</arg>,
<arg>write-penalty</arg>, <arg>write-miss-penalty</arg> sets the
penalties in cycles for cache accesses and misses, respectively. The
read/write penalty is added to the total penalty when accessing the
cache (i.e., the cost of reaching the cache), a miss penalty is added
when a miss occurs and there is no next level cache.

If <arg>prefetch-additional</arg> is given, the cache will prefetch
additional consecutive cache lines on a
miss.

<tt>-prefetch-adjacent</tt> means that the cache will, on a miss, prefetch
the adjacent cache line as well, so the total fetch region is cache line
size * 2, naturally aligned.

<tt>-ip-read-prefetcher</tt> and <tt>-ip-write-prefetcher</tt> adds a
hardware instruction pointer based stride prefetcher for reads and
writes respectively. Write prefetching will issue read for ownership
prefetch accesses to the cache, meaning that other caches having those lines
will be forced to flush them.
"""

new_command("add-l1d-cache", add_l1d_cache_cmd,
            [arg(str_t, "name", "?", "dl1")] + common_cache_args,
            cls = "simple_cache_tool",
            short = "add level 1 data cache",
            see_also = get_see_also("<simple_cache_tool>.add-l1d-cache"),
            doc = ("""
            Add a level 1 data cache to all connected processor. Each
            hardware thread in the same core will be connected to the
            same level 1 cache. The command also created an extra
            namespace, cache[N] for each core where the cache
            hierarchy will be created. """ + common_cache_doc))

new_command("add-l1i-cache", add_l1i_cache_cmd,
            [arg(str_t, "name", "?", "il1"),
             arg(flag_t, "-no-issue")] + common_cache_args,
            cls = "simple_cache_tool",
            short = "add level 1 instruction cache",
            see_also = get_see_also("<simple_cache_tool>.add-l1i-cache"),
            doc = ("""
            Add a level 1 instruction cache to all connected
            processor. Each hardware thread in the same core will be
            connected to the same level 1 cache. The command also
            created an extra namespace, cache[N] for each core where
            the cache hierarchy will be created. The
            <tt>-no-issue</tt> flag means that the connection will not
            issue any instruction accesses to the cache. This can be
            useful if the instruction cache should be called from
            another tool instead, for instance a branch
            predictor. Also, if the cache block for an instruction is
            the same as last access, no instruction cache issue will
            be done, thus modeling that several instructions can be
            read from the same cache block. """ + common_cache_doc))

new_command("add-l2-cache", add_l2_cache_cmd,
            [arg(str_t, "name", "?", "l2")] + common_cache_args,
            cls = "simple_cache_tool",
            short = "add level 2 cache",
            see_also = get_see_also("<simple_cache_tool>.add-l2-cache"),
            doc = ("""Add level 2 caches to all connected processors.
            The level 1 data and instruction caches will be connected to
            this one. """ + common_cache_doc))

new_command("add-l3-cache-slice", add_l3_slice_cache_cmd,
            [arg(str_t, "name", "?", "l3_slice")] + common_cache_args,
            cls = "simple_cache_tool",
            short = "add level 3 slice",
            see_also = get_see_also("<simple_cache_tool>.add-l3-cache-slice"),
            doc = ("""
            Add a slice of a level 3 cache to all connected
            processors.  This means that it will not be shared with
            lower level 2 caches in other cores. """ + common_cache_doc))

new_command("add-l3-cache", add_l3_cache_cmd,
            [arg(str_t, "name", "?", "l3_shared")] + common_cache_args,
            cls = "simple_cache_tool",
            short = "add l3",
            see_also = get_see_also("<simple_cache_tool>.add-l3-cache"),
            doc = ("""

            Add a level 3 cache for all CPU sockets. The cache will be connected
            to all level 2 caches in the same CPU and therefore shared by all
            cores in the CPU. """ + common_cache_doc))

def get_cache_size(c):
    return c.cache_block_size * c.cache_set_number * c.cache_ways

def add_cache_and_sub_caches(cache, cset):
    cset.add(cache)
    if cache.next_level != None:
        add_cache_and_sub_caches(cache.next_level, cset)

def list_caches_cmd(obj, *table_args):
    caches = set()
    for conn in obj.connections:
        if conn.dcache != None:
            add_cache_and_sub_caches(conn.dcache, caches)
        if conn.icache != None:
            add_cache_and_sub_caches(conn.icache, caches)

    data = []
    for c in caches:
        data.append([c, c.cache_set_number, c.cache_ways, c.cache_block_size,
                     get_cache_size(c)])

    cols = [[(Column_Key_Name, "Cache Object")],
            [(Column_Key_Name, "Sets")],
            [(Column_Key_Name, "Ways")],
            [(Column_Key_Name, "Line Size")],
            [(Column_Key_Name, "Total Size"), (Column_Key_Binary_Prefix, "B")]]
    prop = [(Table_Key_Columns, cols),
            (Table_Key_Default_Sort_Column, "Cache Object")]

    table.show(prop, data, *table_args)

table.new_table_command("list-caches", list_caches_cmd,
                        [],
                        cls = "simple_cache_tool",
                        short = "list connected caches",
                        sortable_columns = ["Cache Object", "Sets", "Ways", "Line Size",
                                            "Total Size"],
                        see_also = get_see_also("<simple_cache_tool>.list-caches"),
                        doc = ("""
                        List all caches connected to the cache tool"""))

def info_cmd(c):
    size = get_cache_size(c)
    (v, p) = sim_commands.get_size_with_bi_prefix(size)
    return [(None,
             [("total cache size", f"{v}{p}B"),
              ("cache block size", c.cache_block_size),
              ("cache sets (indices)", c.cache_set_number),
              ("cache ways", c.cache_ways),
              ("read penalty", c.read_penalty),
              ("write penalty", c.write_penalty),
              ("read miss penalty", c.read_miss_penalty),
              ("write miss penalty", c.write_miss_penalty),
              ("snoop penalty", c.snoop_penalty),
              ("prefetch additional lines", c.prefetch_additional),
              ("prefetch adjacent", c.prefetch_adjacent),
              ("ip stride read prefetcher", c.ip_read_prefetcher),
              ("ip stride write prefetcher", c.ip_write_prefetcher),
              ("write_allocate", c.write_allocate),
              ("write_back", c.write_back),
              ("connection object",
               f"{c.cache_conn.name} issues instructions:"
               f" {c.cache_conn.issue_instructions}" if c.cache_conn
               else None)
             ])]

new_info_command("simple_cache", info_cmd)

def status_cmd(cache):
    con = [c for c in instrumentation.get_all_connections()
           if c._conn == cache.cache_conn]
    assert(len(con) == 1)

    ds = con[0].get_disabled_string()
    return [(None,
             [("Connected", "No - disabled by " + ds if ds else "Yes")])]

new_status_command("simple_cache", status_cmd)

def print_cache_content_cmd(c, no_inv_sets, *table_args):
    cols = [[[Column_Key_Name, "Index"],
             [Column_Key_Description, "The index of the set"]]]
    for w in range(c.cache_ways):
        cols.append([
            [Column_Key_Name, "Way%d" % w],
            [Column_Key_Description,
             "Content of each line: S:A:N:P, S is one of MESI," +
             " A is line address, N " +
             "represents timestamp where a high value is older, " +
             "P if line is prefetched and T if tagged in a prefetch stride"]
            ])

    properties = [ [Table_Key_Name, "Cache meta data"],
                   [Table_Key_Description, ("Meta data in cache")],
                   [Table_Key_Columns, cols]]

    sets = c.cache_set_number
    ways = c.cache_ways

    data = [[0] + [0] * ways for i in range(sets)]
    digits = 0
    idx_digits = len("%x" % (sets - 1))

    # This copy of c.meta_content is needed otherwise the usage below will be
    # awfully slow. c.meta_content[:] is also really slow. Also find max digits.
    cont = []
    for info in c.meta_content:
        tag = info[1]
        digits = max(len("%x" % tag), digits)
        cont.append(info)

    for s in range(sets):
        # sort the timestamps for the ways in the set in reverse order
        tstamp = []
        for w in range(ways):
            tstamp.append(cont[s * ways + w][2])
        tstamp.sort(reverse = True)

        # right adjust hex index
        data[s][0] = "%*s" % (len("Index"), "%0*x" % (idx_digits, s)) # index

        # add line with valid:tag:timestamp (highest number is oldest)
        for w in range(ways):
            (state, tag, ts, spf, pf) = cont[s * ways + w]
            if state != CL_Invalid:
                ps = "-"
                if pf:
                    ps = "P"
                if spf:
                    ps = "T"
                data[s][w+1] = "%s:0x%0*x:%d:%s" % (
                    state_map[state], digits, tag, tstamp.index(ts), ps)
            else:
                data[s][w+1] = state_map[state]

    if no_inv_sets:
        pdata = []
        for s in range(sets):
            all_inv = True
            for w in range(ways):
                l = data[s][w+1]
                if l != state_map[CL_Invalid]:
                    all_inv = False
                    break
            if not all_inv:
                pdata.append(data[s])
        data = pdata

    table.show(properties, data, *table_args)


table.new_table_command("print-cache-content", print_cache_content_cmd,
            args = [arg(flag_t, "-no-invalid-sets")],
            cls = "simple_cache",
            short = "meta content",
            sortable_columns = ["Index"],
            doc = ("""Print cache meta content. <tt>-no-invalid-sets</tt>
                   can be givent to skip all ways for an index if all of them
                   are invalid."""))

def initialize_class(cls):
    def prop(obj):
        (p, _) = get_statistics_table(obj)
        return p

    def data(obj):
        (_, d) = get_statistics_table(obj)
        return d

    tif = table_interface_t(properties = prop, data = data)

    SIM_register_interface(cls, "table", tif)

initialize_class("simple_cache")
