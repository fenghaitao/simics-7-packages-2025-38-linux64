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


import cmputil
import cli
import simics

from simics import (
    pr,
)

from cli import (
    addr_t,
    arg,
    bool_t,
    filename_t,
    flag_t,
    float_t,
    int16_t,
    int64_t,
    int_t,
    integer_t,
    list_t,
    nil_t,
    obj_t,
    poly_t,
    range_t,
    sint32_t,
    sint64_t,
    str_t,
    string_set_t,
    uint16_t,
    uint64_t,
    uint_t,
    new_command,
    new_unsupported_command,
    new_operator,
    new_info_command,
    new_status_command,
    CliError,
    Markup,
)

from sim_commands import (
    print_table,
)

#
# -------------------- branch recorder commands --------------------
#

def attach_branch_rec(cpu, brec):
    if cpu.iface.branch_recorder_handler.attach_branch_recorder(brec) == 0:
        print("Error! Failed to connect branch recorder to %s." % cpu.name)
def detach_branch_rec(cpu, brec):
    if cpu.iface.branch_recorder_handler.detach_branch_recorder(brec) == 0:
        print("Error! Failed to disconnect branch recorder from %s." % cpu.name)

def new_branch_recorder_cmd(name, address_type):
    try:
        simics.SIM_get_object(name)
        simics.pr("An object called '%s' already exists.\n" % name)
        return
    except simics.SimExc_General:
        try:
            brec = simics.SIM_create_object(
                "branch_recorder", name,
                [["address_type", simics.Addr_Type_Virtual
                  if address_type == "virtual" else simics.Addr_Type_Physical]])
        except:
            simics.pr("Error creating branch recorder '%s'\n" % name)

    def interactive_msg():
        return ("Created '%s'" % brec.name)

    return cli.command_return(message = interactive_msg, value = brec)

cli.new_command("new-branch-recorder", new_branch_recorder_cmd,
            args = [cli.arg(cli.str_t, "name"),
                    cli.arg(cli.string_set_t(["physical", "virtual"]), "address_type")],
            type  = ["Profiling"],
            see_also = ['<branch_recorder_handler>.attach-branch-recorder'],
            short = "create a new branch recorder",
            doc = """
Create a new branch recorder object called <arg>name</arg>, to record
branches using addresses of type <arg>address_type</arg> (either
<tt>physical</tt> or <tt>virtual</tt>). The branch recorder is
initially not bound to any processor.""")

def clean_branch_recorder_cmd(brec):
    brec.clean = None

cli.new_command("clean", clean_branch_recorder_cmd,
            args = [],
            cls = "branch_recorder",
            type  = ["Profiling"],
            short = "delete all branch arcs in the branch recorder",
            doc = """
Delete all branch arcs stored in the branch recorder.""")

def attach_branch_recorder_to_processor_cmd(cpu, brec):
    attach_branch_rec(cpu, brec)

def detach_branch_recorder_from_processor_cmd(cpu, brec):
    detach_branch_rec(cpu, brec)

cli.new_command("attach-branch-recorder", attach_branch_recorder_to_processor_cmd,
            [cli.arg(cli.obj_t("branch_recorder", "branch_recorder"), "branch_recorder")],
            iface = "branch_recorder_handler",
            type  = ["Profiling"],
            short = "attach a branch recorder to a processor",
            see_also = ['<branch_recorder_handler>.detach-branch-recorder'],
            doc = """
Attach the <arg>branch_recorder</arg> to the processor, so
that it will record its branches. Note that once you have attached a
branch recorder to a processor, it adapts to that processor type and
you cannot attach it to other processors of different types.""")

cli.new_command("detach-branch-recorder", detach_branch_recorder_from_processor_cmd,
            [cli.arg(cli.obj_t("branch_recorder", "branch_recorder"), "branch_recorder")],
            iface = "branch_recorder_handler",
            type  = ["Profiling"],
            short = "detach a branch recorder from a processor",
            see_also = ['<branch_recorder_handler>.attach-branch-recorder'],
            doc = """
Detach the <arg>branch_recorder</arg> from the processor.
""")

def brec_get_info(obj):
    return [(None,
             [("Address type",
               "virtual" if obj.address_type == simics.Addr_Type_Virtual
               else "physical"),
              ("CPU type", obj.cpu_type)])]

def brec_get_status(obj):
    plist = []
    for cpu in obj.processors:
        plist.append(cpu.name)
    return [(None,
             [("Number of arcs", obj.num_arcs),
              ("Attached processors", ", ".join(plist))])]

cli.new_info_command("branch_recorder", brec_get_info)
cli.new_status_command("branch_recorder", brec_get_status)

def start_instruction_profiling_cmd(cpu, virtual):
    try:
        bname = cmputil.derived_object_name(cpu, '_branch_recorder')
    except cmputil.CmpUtilException as e:
        raise cli.CliError(str(e))
    try:
        brec = simics.SIM_create_object(
            "branch_recorder", bname,
            [["address_type", (simics.Addr_Type_Virtual if virtual
                               else simics.Addr_Type_Physical)]])
        attach_branch_rec(cpu, brec)
    except simics.SimExc_General:
        raise cli.CliError('Could not create a branch recorder for %s' % cpu.name)

    def interactive_msg():
        return ("Created '%s' attached to '%s'" % (brec.name, cpu.name))

    return cli.command_return(message = interactive_msg, value = brec)

cli.new_command("start-instruction-profiling", start_instruction_profiling_cmd,
            args = [cli.arg(cli.flag_t, "-virtual")],
            iface = "branch_recorder_handler",
            type  = ["Profiling"],
            short = "get started with instruction profiling",
            see_also = ['new-branch-recorder',
                        '<branch_recorder_handler>.attach-branch-recorder',
                        '<address_profiler>.address-profile-data'],
            doc = """
This command gets you started with instruction profiling quickly by
creating a branch recorder for you and attaching it to the processor.
If you want more control, use other profiling commands instead.

It creates a branch recorder and attaches it to the processor, just as
if you had typed

<tt>new-branch-recorder</tt> <i>branch_recorder</i> <tt>physical</tt>

<i>cpu</i><tt>.attach-branch-recorder</tt> <i>branch_recorder</i>

The branch recorder will (as the name implies) record branches taken
by the processor (by physical addresses); various useful numbers can
be computed from them. You can for example display execution count
statistics by typing

<i>branch_recorder</i><tt>.address-profile-data</tt>

(but you will not see anything interesting until you have let the
processor run a few instructions).

With the <tt>-virtual</tt> flag, record virtual addresses; otherwise,
record physical addresses.""")

pbad_directions = {"to": simics.BR_Direction_To, "from": simics.BR_Direction_From}
def print_branch_arcs_direction_expander(string):
    return cli.get_completions(string, list(pbad_directions.keys()))

def print_branch_arcs_cmd(brec, dir, start, stop):
    if stop < start:
        print("Start address must not be greater than stop address.")
        return
    try:
        dir = pbad_directions[dir]
    except KeyError:
        print("Direction must be either 'from' or 'to'.")
        return
    ifc = brec.iface.branch_arc
    addr_width = int((brec.iface.address_profiler.address_bits(0) + 3)/4)
    for (from_a, to_a, count, type) in ifc.iter(start, stop, dir):
        if type == simics.Branch_Arc_Exception:
            ptype = "exception"
        elif type == simics.Branch_Arc_Exception_Return:
            ptype = "exception_return"
        else:
            ptype = ""
        print("0x%0*x -> 0x%0*x %12i %s" % (addr_width, from_a,
                                            addr_width, to_a,
                                            count, ptype))

cli.new_command("print-branch-arcs", print_branch_arcs_cmd,
            args = [cli.arg(cli.str_t, "direction", spec = "?", default = "from",
                        expander = print_branch_arcs_direction_expander),
                    cli.arg(cli.int_t, "start", spec = "?", default = 0),
                    cli.arg(cli.int_t, "stop", spec = "?", default = (1 << 64) - 1)],
            cls = "branch_recorder",
            type  = ["Profiling"],
            short = "print branch arcs",
            doc = """
Print a subset of the branch arcs in a branch recorder. With no
arguments, print all arcs. Given <arg>start</arg> and <arg>stop</arg>
addresses, print only arcs with 'to' or 'from' address in that
interval, depending on whether <arg>direction</arg> is 'to' or 'from' (its
default value is 'from'). The printed arcs are sorted by their 'to' or
'from' address, as specified by <arg>direction</arg>.""")

#
# ---------------------- data profiler commands ---------------------
#

def data_profiler_clear_cmd(obj):
    try:
        dpi = obj.iface.data_profiler
    except:
        simics.pr("%s is not a data profiler!\n" % obj)
        return
    dpi.clear()

new_command("clear", data_profiler_clear_cmd,
            args = [],
            iface = "data_profiler",
            type = ["Profiling"],
            short = "clear data profiler",
            doc = """
Reset all counters of the data profiler to zero.""")

#
# -------------------- address profiler commands --------------------
#

def address_profile_info_cmd(obj, sum, max):
    try:
        simics.SIM_get_interface(obj, "address_profiler")
        api = obj.iface.address_profiler
    except:
        simics.pr("%s is not an address profiler!\n" % obj)
        return
    num = api.num_views()
    if num == 0:
        simics.pr("%s has no views defined!\n" % obj)
        return
    simics.pr("%s has %d address profiler view%s:\n" % (obj.name, num,
                                                 ["s", ""][num == 1]))
    for i in range(num):
        addr_bits = api.address_bits(i)
        maxaddr = (1 << addr_bits) - 1
        simics.pr("View %d: %s\n" % (i, api.description(i)))
        gran_log2 = api.granularity_log2(i)
        simics.pr("   %d-bit %s addresses, granularity %d byte%s\n" %
           (addr_bits,
            ["virtual", "physical"][api.physical_addresses(i)],
            1 << gran_log2, ["s", ""][gran_log2 == 0]))
        if sum:
            simics.pr("   Total counts: %d\n" % api.sum(i, 0, maxaddr))
        if max:
            simics.pr("   Maximal count: %d\n" % api.max(i, 0, maxaddr))

new_command("address-profile-info", address_profile_info_cmd,
            args = [arg(flag_t, "-sum"), arg(flag_t, "-max")],
            iface = "address_profiler",
            type = ["Profiling"],
            short = "general info about an address profiler",
            doc = """
Print general info about an object implementing the address_profiler
interface, such as a list of the available views. If the <tt>-sum</tt>
or <tt>-max</tt> flags are given, will also print the sum or max of
each view over the entire address space.""")

aprof_views = {}

def register_aprof_views(aprof_class):

    def aprof_views_cmd(cpu, add, remove, view, clear):

        def indexof(aprof, view):
            index = 0
            for ap, v in cpu.aprof_views:
                if aprof == ap and view == v:
                    return index
                index += 1
            return -1

        if clear:
            if add or remove:
                print("Error! Too many options.")
                return
            cpu.aprof_views = []
        elif add:
            if remove:
                print("Error! Cannot specify both add and remove.")
                return
            index = indexof(add, view)
            if index >= 0:
                print("View %d of %s is already selected." % (view, add.name))
                return
            numviews = add.iface.address_profiler.num_views()
            if view < 0 or view >= numviews:
                print("Error! View %d is out of range for %s." % (view, add.name))
                return
            temp = cpu.aprof_views
            temp.append([add, view])
            cpu.aprof_views = temp
        elif remove:
            index = indexof(remove, view)
            if index < 0:
                print("View %d of %s is not selected." % (view, remove.name))
                return
            temp = cpu.aprof_views
            del temp[index]
            cpu.aprof_views = temp
        else:
            if len(cpu.aprof_views) < 1:
                print("No address profiler views selected for %s." % cpu.name)
                return
            print(("The following address profiler views are selected for %s:"
                   % cpu.name))
            i = 1
            for ap, view in cpu.aprof_views:
                api = ap.iface.address_profiler
                print(("  %d. (%s) View %d of %s (%s)"
                       % (i, ["virtual", "physical"]
                          [api.physical_addresses(view)],
                          view, ap.name, api.description(view))))
                i += 1

    aprof_obj_t = obj_t("address_profiler", "address_profiler")
    new_command("aprof-views", aprof_views_cmd,
                args = [arg(aprof_obj_t, "add", spec = "?", default = None),
                        arg(aprof_obj_t, "remove", spec = "?", default = None),
                        arg(int_t, "view", spec = "?", default = 0),
                        arg(flag_t, "-clear")],
                cls = simics.SIM_get_class_name(aprof_class),
                type = ["Profiling"],
                short = "manipulate list of selected address profiling views",
                doc = """
Determines which address profiler views are displayed alongside
disassembled code.

The <arg>add</arg> and <arg>view</arg> arguments select an address profiler
view to add to the list. Alternatively, the <arg>remove</arg> and
<arg>view</arg> arguments specify an address profiler view to remove from
the list. <arg>view</arg> defaults to 0 if not specified.

If called with the <tt>-clear</tt> flag, remove all address profiler
views from the list.

If called without arguments, print a detailed list of the currently
selected address profiler views for the processor. """)

    def get_aprof_views(conf_obj):
        global aprof_views
        if not conf_obj in aprof_views:
            return []
        return aprof_views[conf_obj]

    def set_aprof_views(conf_obj, val):
        global aprof_views
        for (prof, view) in val:
            if not hasattr(prof.iface, 'address_profiler'):
                return simics.Sim_Set_Illegal_Value
            if view < 0 or view >= prof.iface.address_profiler.num_views():
                return simics.Sim_Set_Illegal_Value
        aprof_views[conf_obj] = val
        return simics.Sim_Set_Ok

    simics.SIM_register_attribute(
            aprof_class,
            "aprof_views",
            get_aprof_views,
            set_aprof_views,
            simics.Sim_Attr_Pseudo,
            "[[o,i]*]",
            "((<i>address profiler</i>, <i>view</i>)*) Address profiler"
            " views selected for this processor. Affects only the display"
            " of profiling information, and has nothing to do with"
            " collecting it."
            "\n\n"
            "This attribute should contain a list of lists: one list for"
            " each address profiler view you want to select (in the order"
            " they are to appear), each containing first the address"
            " profiler object, then the index of the desired view.")

#
# ------- address profiler toplist --------
#
def address_profile_toplist_cmd(ap, samples, start, stop,
                                view, cnt_ival):
    try:
        simics.SIM_get_interface(ap, "address_profiler")
        api = ap.iface.address_profiler
    except:
        pr("%s is not an address profiler!\n" % ap)
        return

    num_views = api.num_views()
    if not num_views > view:
        pr("%s does not have view %d!\n" % (ap, view))
    gran = 2**(api.granularity_log2(view))

    #
    # sample_list = [[count, address], ...]
    #
    sample_list = [[0, 0]] * samples
    for (count, addr) in api.iter(view, start, stop):
        if count > sample_list[-1][0]:
            sample_list[-1] = [count, addr]
            sample_list.sort(key=lambda x: x[0])
    sample_list.sort(key=lambda x: x[1])

    #
    # top_list = [[count, address, length], ...]
    #
    top_list = []
    addr_width = 8
    for (s_cnt, s_addr) in sample_list:
        match = False
        if s_addr >= 2 ** 32:
            addr_width = 16
        for entr in top_list:
            if (entr[1] + entr[2] == s_addr
                and entr[0] - cnt_ival <= s_cnt
                and entr[0] + cnt_ival >= s_cnt):
                match = True
                entr[2] += gran
        if not match:
            top_list.append([s_cnt, s_addr, gran])
    top_list.sort()
    top_list.reverse()

    if top_list[0][0] == 0:
        return

    head = ["count", "address range", "len"]
    just = ["right", "left", "right"]

    data = []
    for (count, addr, length) in top_list:
        if count == 0:
            break
        entry = [str(count), "0x%0*x..0x%0*x" % (
            addr_width, addr, addr_width, addr + length - 1),
                 str(length)]
        data.append(entry)
    print_table(head, data, just)

new_command("address-profile-toplist", address_profile_toplist_cmd,
            args = [arg(int_t, "samples", spec = "?", default = 100),
                    arg(uint64_t, "start", spec = "?", default = 0x0),
                    arg(uint64_t, "stop", spec = "?", default = 0xfffffffc),
                    arg(int_t, "view", spec = "?", default = 0),
                    arg(int_t, "count_interval", spec = "?", default = 1)],
            iface = "address_profiler",
            type  = ["Profiling"],
            see_also = ["<address_profiler>.address-profile-info"],
            short = "print toplist of address profiling data",
            doc = """
Print address profiling regions sorted by count.

The <arg>samples</arg> argument specifies the number of sampling points
used to create the list containing the highest count. The sampling
range is determined by <arg>start</arg> and <arg>stop</arg>. The default
values are 100 samples in the interval 0x0&ndash;0xfffffffc. The
granularity is defined by the data profiler object.

The <arg>view</arg> argument selects the address profiler view.

The <arg>count_interval</arg> attribute defines the range in which sampled
data regions will match even thought the data profiler count is not
equal. For example, assume that the samples in the region
0x20c&ndash;0x20c has a count of 4711 and 4713 in 0x20d&ndash;0x20f.
These regions will be considered to be one region if
<arg>count_interval</arg> is 4, but not if it is 1.
""")

def rshift_round_up(x, s):
    return (x + (1 << s) - 1) >> s

def pow2_bytes_to_str(n):
    orig_n = n
    if n < 10:
        return "%d byte%s" % (1 << n, ["s", ""][n == 0])
    for prefix in ["kilo", "Mega", "Giga", "Tera", "Peta", "Exa"]:
        n -= 10
        if n < 10:
            return "%d %sbyte%s" % (1 << n, prefix, ["s", ""][n == 0])
    return "2^%d bytes" % orig_n

# Return a string representation of num (positive) of at most maxlen
# characters. Use prefixes (and round up) if necessary. The string
# representations of zero and overflow are configurable. If
# minprefixnum is given, num will be forced to use the prefix that
# minprefixnum would have gotten (or bigger), even in the face of
# precision loss.
def num_to_str(num, maxlen, zero = "0", almostzero = None,
               overflow = "inf", minprefixnum = 0):
    if num == 0:
        return zero
    pnum = max(num, minprefixnum)
    pstr = "%d" % pnum
    if len(pstr) <= maxlen:
        return "%d" % num
    for suffix in ["k", "M", "G", "T", "P", "E"]:
        num = num/1000
        pnum = pnum/1000
        pstr = "%d%s" % (pnum, suffix)
        if len(pstr) <= maxlen:
            if num == 0:
                return almostzero
            return "%d%s" % (num, suffix)
    return overflow

def long_and_short_num(num):
    numstr = num_to_str(num, 6)
    numstr2 = "%d" % num
    if numstr != numstr2:
        numstr = "%s (%s)" % (numstr2, numstr)
    return numstr

def address_profile_data_cmd(ap, view, address, cell_bits, row_bits,
                             table_bits, start, stop, maxlines, maxcolumns,
                             sameprefix):

    cell_width = 6
    cells_per_line = 0
    while (1 << (cells_per_line + 1)) <= maxcolumns:
        cells_per_line += 1

    def zero_out_low_bits(x, b):
        return (x >> b) << b

    def print_header():
        cellgran = gran - cells_per_line
        sh = cellgran % 4
        cellgran -= sh
        columns = 1 << cells_per_line
        columnheaderdigits = (cells_per_line + sh + 3)/4
        pr("column offsets:\n")
        pr("%*s*" % (int(2 + addr_size), "0x%x" % (1 << cellgran)))
        for i in range(columns):
            pr(" %*s" % (int(cell_width),
                         "0x%0*x" % (int(columnheaderdigits), i << sh)))
        pr("\n")
        pr("-" * (2 + addr_size + 1 + columns*(1 + cell_width)) + "\n")

    def print_lines(start, numlines, gran):
        cellgran = 1 << (gran - cells_per_line)
        tsum = 0
        left = []
        lines = []
        m = 0
        for i in range(numlines):
            left.append("0x%0*x:" % (int(addr_size), start))
            line = []
            for j in range(1 << cells_per_line):
                c = api.sum(view, start, start + cellgran - 1)
                m = max(m, c)
                line.append(c)
                start += cellgran
                tsum += c
            lines.append(line)

        if sameprefix:
            mp = m
        else:
            mp = 0

        for i in range(len(left)):
            pr(left[i])
            for c in lines[i]:
                pr(" %*s" % (int(cell_width), num_to_str(
                    c, cell_width, zero = ".", almostzero = "o",
                    minprefixnum = mp)))
            pr("\n")
        return tsum

    def find_firstlast_counter(a, b, first):
        if a >= b:
            if a == b:
                return a
            return -1

        # Basecase: linear search.
        if b - a < 100:
            if first:
                start = b + 1
                fun = min
            else:
                start = a - 1
                fun = max
            best = start
            for count, addr in api.iter(view, a, b):
                best = fun(best, addr)
            if best == start:
                return -1
            return best

        # Recursion: split interval in half.
        guess = (b + a) // 2
        if first:
            ca = next(api.iter(view, a, guess), None)
            if ca is not None:
                (_, addr) = ca
                return find_firstlast_counter(a, addr, first)
            return find_firstlast_counter(guess + 1, b, first)
        else:
            ca = next(api.iter(view, guess, b), None)
            if ca is not None:
                (_, addr) = ca
                return find_firstlast_counter(addr, b, first)
            return find_firstlast_counter(a, guess - 1, first)

    try:
        simics.SIM_get_interface(ap, "address_profiler")
        api = ap.iface.address_profiler
    except:
        pr("%s is not an address profiler!\n" % ap)
        return

    if api.num_views() == 0:
        pr("%s has no views defined!\n" % ap)
        return

    if view >= api.num_views() or view < 0:
        pr("Invalid view (%d) specified, valid range [0,%d]!\n" %
           (view, api.num_views() - 1))
        return

    addr_bits = api.address_bits(view)
    lastaddr = (1 << addr_bits) - 1
    addr_size = rshift_round_up(addr_bits, 2) # address size in hex digits
    prof_gran_bits = api.granularity_log2(view)
    gran = mingran = cells_per_line + prof_gran_bits

    bit_args = 0
    if cell_bits != None:
        bit_args += 1
        if cell_bits < prof_gran_bits:
            print("Cells must contain at least %d bits." % prof_gran_bits)
            return
    if row_bits != None:
        bit_args += 1
        if row_bits < mingran:
            print("Rows must contain at least %d bits." % mingran)
            return
    if table_bits != None:
        bit_args += 1
        if table_bits < mingran:
            print("Table must contain at least %d bits." % mingran)
            return
    if bit_args > 1:
        print(("You may specify at most one of cell-bits, row-bits"
               + " and table-bits."))
        return

    # If no range is specified, find the minimal range that contains
    # all counts.
    if start == None and stop == None and address == None and bit_args == 0:
        start = find_firstlast_counter(0, lastaddr, first = 1)
        if start == -1:
            start = 0
            stop = lastaddr
        else:
            stop = find_firstlast_counter(0, lastaddr, first = 0)

        # If user specified address argument, make sure we include it.
        if address != None:
            start = min(start, address)
            stop = max(stop, address)

    # Determine what interval to display.
    if start != None or stop != None:
        if start == None or stop == None:
            print("You must specify both start and stop (or neither of them).")
            return
        if address != None or bit_args != 0:
            print("You cannot specify both start+stop and address+bits.")
            return
        for x in [start, stop]:
            if x < 0 or x >= (1 << addr_bits):
                print("0x%x is not a %d-bit address." % (x, addr_bits))
                return
        stop += 1 # let stop point to first address after interval
        while True:
            if start > stop:
                (start, stop) = (stop, start)
            start = zero_out_low_bits(start, gran)
            stop = zero_out_low_bits(stop + (1 << gran) - 1, gran)
            length = stop - start
            numlines = rshift_round_up(length, gran)
            if numlines <= maxlines:
                break
            gran += 1
        stop -= 1 # stop points to last address again
    else:
        if address == None:
            address = 0
        elif bit_args == 0:
            print(("You must specify cell-bits, row-bits or table-bits"
                   + " when address is specified."))
            return
        if address < 0 or address >= (1 << addr_bits):
            print("0x%x is not a %d-bit address!" % (address, addr_bits))
            return
        if table_bits != None:
            if table_bits > addr_bits:
                print("Address space is only %d bits!" % addr_bits)
                return
            length = 1 << table_bits
            while True:
                numlines = rshift_round_up(length, gran)
                if numlines <= maxlines:
                    break
                gran += 1
            start = zero_out_low_bits(max(0, address - length/2), gran)
        elif cell_bits != None:
            if row_bits == None:
                row_bits = cell_bits + cells_per_line
            if row_bits > addr_bits:
                print("Address space is only %d bits!" % addr_bits)
                return
            gran = row_bits
            numlines = min(maxlines, 1 << (addr_bits - gran))
            start = max(0, (zero_out_low_bits(address, gran)
                            - numlines*(1 << (gran - 1))))

    gran_log2 = api.granularity_log2(view)
    cellgran = gran - cells_per_line
    totalsum = api.sum(view, 0, lastaddr)

    # Print table.
    print("View %d of %s: %s" % (view, ap.name, api.description(view)))
    print(("%d-bit %s addresses, profiler granularity %d byte%s" %
           (api.address_bits(view),
            ["virtual", "physical"][api.physical_addresses(view)],
            1 << gran_log2, ["s", ""][gran_log2 == 0])))
    if totalsum > 0:
        print(("Each cell covers %d address bits (%s)."
               % (cellgran, pow2_bytes_to_str(cellgran))))
        print() # empty line
        print_header()
        sum = print_lines(start, numlines, gran)
        print() # empty line
        print(("%s counts shown. %s not shown."
               % (long_and_short_num(sum), long_and_short_num(totalsum - sum))))
        print() # empty line
    else:
        print() # empty line
        print("    Profiler is empty.")
        print() # empty line

new_command("address-profile-data", address_profile_data_cmd,
            args = [arg(int_t, "view", spec = "?", default = 0),
                    arg(uint64_t, "address", spec = "?", default = None),
                    arg(int_t, "cell-bits", spec = "?", default = None),
                    arg(int_t, "row-bits", spec = "?", default = None),
                    arg(int_t, "table-bits", spec = "?", default = None),
                    arg(uint64_t, "start", spec = "?", default = None),
                    arg(uint64_t, "stop", spec = "?", default = None),
                    arg(int_t, "lines", spec = "?", default = 20),
                    arg(int_t, "columns", spec = "?", default = 8),
                    arg(flag_t, "-same-prefix")],
            iface = "address_profiler",
            type = ["Profiling"],
            short = "linear map of address profiling data",
            doc = """
Display a map of (a part of) the address space covered by the address
profiler, and the counts of one of its views associated with each
address. The view is specified by the <arg>view</arg> argument; default is
view 0. The default behavior is to display the smallest interval that
contains all counts; you can change this with either the <arg>start</arg>
and <arg>stop</arg> or the <arg>address</arg> and <arg>cell-bits</arg>,
<arg>row-bits</arg> or <arg>table-bits</arg> arguments.

Cells that have zero counts are marked with ".". Cells that have a
non-zero count, but were rounded to zero, are marked with "o".

If one of <arg>cell-bits</arg>, <arg>row-bits</arg> or <arg>table-bits</arg> is
specified, then each cell, or each table row, or the entire table is
limited to that many bits of address space. By default the display
starts at address 0, but if an address is specified with the
<arg>address</arg> argument, the displayed interval is shifted to make
that address is visible.

If <arg>start</arg> and <arg>stop</arg> are specified, the display is limited
to the smallest interval containing both addresses.

The maximum number of lines and columns in the table are limited by
the <arg>lines</arg> and <arg>columns</arg> arguments (the default is 20
lines, 8 columns). The scale of the map is adjusted to fit this limit.

Normally, the display chooses an appropriate prefix for the count of
each cell; with the <tt>-same-prefix</tt> flag, all counts will be
forced to have the same prefix. This is useful if a lot of small but
non-zero values makes it hard to spot the really big values.""")

def address_profile_summary_cmd(ap, view, lines):

    try:
        simics.SIM_get_interface(ap, "address_profiler")
        api = ap.iface.address_profiler
    except:
        pr("%s is not an address profiler!\n" % ap)
        return

    if api.num_views() == 0:
        pr("%s has no views defined!\n" % ap)
        return

    addr_bits = api.address_bits(view)
    addr_size = rshift_round_up(addr_bits, 2) # address size in hex digits
    minlength = api.granularity_log2(view)
    num_width = 6
    maxlines = lines

    lcount = 0
    hcount = 1
    start  = 2
    length = 3

    def init_lines():
        lc = api.sum(view, 0, (1 << (addr_bits - 1)) - 1)
        hc = api.sum(view, (1 << (addr_bits - 1)), (1 << addr_bits) - 1)
        if hc + lc == 0:
            return None
        line = {lcount: lc, hcount: hc, start: 0, length: addr_bits}
        trim_empty_halves(line)
        return [line]

    def trim_empty_halves(line):
        if line[length] == minlength:
            return
        if line[lcount] == 0:
            line[length] -= 1
            line[start] += (1 << line[length])
            line[lcount] = api.sum(
                view, line[start],
                line[start] + (1 << (line[length] - 1)) - 1)
            line[hcount] -= line[lcount]
            trim_empty_halves(line)
            return
        if line[hcount] == 0:
            line[length] -= 1
            line[hcount] = api.sum(view,
                                   line[start] + (1 << (line[length] - 1)),
                                   line[start] + (1 << line[length]) - 1)
            line[lcount] -= line[hcount]
            trim_empty_halves(line)

    def density(line):
        return float(line[lcount] + line[hcount])/(1 << line[length])

    def add_line(lines, line):
        trim_empty_halves(line)
        d = density(line)
        i = len(lines)
        lines.append(line)
        while i > 0 and d > density(lines[i - 1]):
            lines[i], lines[i - 1] = lines[i - 1], lines[i]
            i -= 1

    def split_last(lines):
        i = len(lines) - 1
        while lines[i][length] == minlength:
            i -= 1
            if i < 0:
                return 0 # no more lines to split
        line = lines.pop(i)
        ilen = 1 << (line[length] - 2)
        c1 = api.sum(view, line[start], line[start] + ilen - 1)
        c2 = line[lcount] - c1
        c3 = api.sum(view, line[start] + 2*ilen, line[start] + 3*ilen - 1)
        c4 = line[hcount] - c3
        line1 = {lcount: c1, hcount: c2, start: line[start],
                 length: (line[length] - 1)}
        add_line(lines, line1)
        line2 = {lcount: c3, hcount: c4, start: line[start] + 2*ilen,
                 length: (line[length] - 1)}
        add_line(lines, line2)
        return 1 # success

    # Find interesting intervals.
    lines = init_lines()
    if lines == None:
        pr("Profiler is empty.\n")
        return
    while len(lines) < maxlines and split_last(lines):
        pass

    # Sort intervals by start address.
    tmplist = sorted([(line[start], line) for line in lines])
    lines = [line for (key, line) in tmplist]

    # Print intervals.
    pr("  %*s  %*s  %*s  %*s  %s\n"
       % (int(addr_size) + 2, "start",
          int(addr_size) + 2, "end",
          int(num_width), "count",
          int(num_width), "length",
          "counts/byte"))
    sum = 0
    for line in lines:
        count = line[lcount] + line[hcount]
        sum += count
        stop = line[start] + (1 << line[length]) - 1
        pr("  0x%0*x  0x%0*x  %*s  %*s  %f\n"
           % (int(addr_size), line[start],
              int(addr_size), stop,
              int(num_width), num_to_str(count, num_width),
              int(num_width), num_to_str(1 << line[length], num_width),
              density(line)))
    pr("Total sum is %s.\n" % long_and_short_num(sum))

new_unsupported_command("address-profile-summary", "internals",
                        address_profile_summary_cmd,
                        args = [arg(int_t, "view", spec = "?", default = 0),
                                arg(int_t, "lines", spec = "?", default = 10)],
                        iface = "address_profiler",
                        short = "short summary of the contents of the address profiler",
                        doc = """
Print a short summary of the address intervals that have a nonzero
count.

The view of the address profiler is selected with the <arg>view</arg>
parameter (default is view 0). <arg>lines</arg> determines the length of
the summary (the amount of information presented is increased until it
fills the specified number of lines).""")
