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


# This file should only contain internal commands which should not be
# seen by the end-user.

import cli
import simics
import dmg
import os.path
import conf
import table

#
# VTmem debug commands
#

cli.add_unsupported("malloc-debug")

class Struct:
    def __init__(self, **entries): self.__dict__.update(entries)

class Columns:
    def __init__(self, info):
        self.info = info
        self.selected = None
        self.index = None
        self.ascending = None

    def select(self, column):
        if column and column not in self.names():
            raise cli.CliError(f"Argument 'sort-on-column' must be one of"
                               f" {self.names()}.")
        self.selected = column if column else self.info[0][0]
        self.index = self.names().index(self.selected)
        self.ascending = self.info[self.index][1]

    def names(self):
        return [x[0] for x in self.info]

    def complete(self, s):
        return cli.get_completions(s, self.names())

def mm_get_sites():
    m = simics.DBG_mm_get_sites()
    if not m:
        print ("To enable memory tracking, start Simics with the environment"
               " variable\nSIMICS_MEMORY_TRACKING set.")
        raise cli.CliError
    return m

def mm_props(names, aligns):
    return [(table.Table_Key_Columns,
             [[(table.Column_Key_Name, n), (table.Column_Key_Alignment, a)]
              for (n, a) in zip(names, aligns)])]

def mm_list_types_columns():
    return Columns((("bytes", False), ("allocs", False), ("type", True)))

def mm_list_msg_bytes_format(sites):
    return [f"{cli.number_str(sum(s.bytes for s in sites))} bytes,",
            f"{cli.number_str(sum(s.nallocs for s in sites))} allocations"]

def mm_list_msg_bytes(shown, filtered, total):
    return [["Total shown"] + mm_list_msg_bytes_format(shown),
            ["Total filtered"] + mm_list_msg_bytes_format(filtered),
            ["Total"] + mm_list_msg_bytes_format(total)]

def mm_list_types_cmd(maxtypes, human, type_substring, sort_on_column):
    sites = [Struct(bytes=b, nallocs=na, totallocs=ta, type=t, file=f, line=l)
             for (b, na, ta, t, f, l) in mm_get_sites()
             if na != 0 or b != 0]
    def sites_of_type(sites, t):
        ts = [s for s in sites if s.type == t]
        return Struct(type=t,
                      bytes=sum(s.bytes for s in ts),
                      nallocs=sum(s.nallocs for s in ts))
    tsites = [sites_of_type(sites, t) for t in set(s.type for s in sites)]
    filtered = [s for s in tsites if type_substring in s.type]
    max = maxtypes if maxtypes else None
    shown = sorted(filtered, key=lambda x: x.bytes, reverse=True)[:max]

    columns = mm_list_types_columns()
    columns.select(sort_on_column)
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, n)] for n in columns.names()])]
    if human:
        props[0][1][0].append((table.Column_Key_Binary_Prefix, "B"))
    data = [[s.bytes, s.nallocs, s.type] for s in shown]
    data.sort(key=lambda x:x[columns.index], reverse=not columns.ascending)
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    tot_tbl = table.Table(mm_props(("", "", ""), ("left", "right", "right")),
                          mm_list_msg_bytes(shown, filtered, sites))
    msg += f"""\n{tot_tbl.to_string(
        rows_printed=0, no_row_column=True, border_style = 'borderless')}"""
    return cli.command_verbose_return(msg, data)

cli.new_unsupported_command("mm-list-types", "malloc-debug", mm_list_types_cmd,
                        [cli.arg(cli.int_t, "max", "?", 64),
                         cli.arg(cli.flag_t, "-human-readable"),
                         cli.arg(cli.str_t, "type-substr", "?", ""),
                         cli.arg(cli.str_t, "sort-on-column", "?", None,
                                 expander=mm_list_types_columns().complete)],
                        short = "list all object types currently active",
                        doc = """
            List memory allocation types aggregated by size.

            Limit the output using the <arg>max</arg> argument, default is
            <tt>64</tt>, or use <tt>0</tt> to list all types.
            The <tt>-human-readable</tt> flag will show rounded, human readable
            values.
            Filtering can be achieved by specifying <arg>type-substr</arg>.
            By default the result is sorted on allocated size, but
            a different sorting order can be selected by specifying
            <arg>sort-on-column</arg>.""")

def mm_list_sites_columns():
    return Columns((("bytes", False), ("allocs", False), ("type", True),
                    ("file:line", True)))

def mm_list_sites_cmd(maxsites, human, type_substring, file_line_substring,
                      sort_on_column):
    sites = [Struct(bytes=b, nallocs=na,
                    totallocs=ta, type=t, file_line=f"{f}:{l}")
             for (b, na, ta, t, f, l) in mm_get_sites()
             if na != 0 or b != 0]
    filtered = [s for s in sites
                if type_substring in s.type
                and file_line_substring in s.file_line]
    max = maxsites if maxsites else None
    shown = sorted(filtered, key=lambda x: x.bytes, reverse=True)[:max]

    columns = mm_list_sites_columns()
    columns.select(sort_on_column)
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, n)] for n in columns.names()])]
    if human:
        props[0][1][0].append((table.Column_Key_Binary_Prefix, "B"))
    data = [[s.bytes, s.nallocs, s.type, s.file_line] for s in shown]
    data.sort(key=lambda x:x[columns.index], reverse=not columns.ascending)
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    tot_tbl = table.Table(mm_props(("", "", ""), ("left", "right", "right")),
                          mm_list_msg_bytes(shown, filtered, sites))
    msg += f"""\n{tot_tbl.to_string(
        rows_printed=0, no_row_column=True, border_style = 'borderless')}"""
    return cli.command_verbose_return(msg, data)

cli.new_unsupported_command("mm-list-sites", "malloc-debug", mm_list_sites_cmd,
                        [cli.arg(cli.int_t, "max", "?", 32),
                         cli.arg(cli.flag_t, "-human-readable"),
                         cli.arg(cli.str_t, "type-substr", "?", ""),
                         cli.arg(cli.str_t, "file-line-substr", "?", ""),
                         cli.arg(cli.str_t, "sort-on-column", "?", None,
                                 expander=mm_list_sites_columns().complete)],
                        short = "list busiest allocation sites",
                        doc = """
            List amount of allocated memory per allocation site.

            Limit the output using the <arg>max</arg> argument, default
            is <tt>32</tt>, or use <tt>0</tt> to list all sites.
            The <tt>-human-readable</tt> flag will show rounded, human readable
            values.
            Filtering can be achieved by specifying
            <arg>type-substr</arg> to filter type name and
            <arg>file-line-substr</arg> to filter file:line.
            By default the result is sorted on allocated size, but
            a different sorting order can be selected by specifying
            <arg>sort-on-column</arg>.""")


def mm_list_allocs_columns():
    return Columns((("bytes", False), ("calls", False), ("type", True),
                    ("file:line", True)))

def mm_list_allocs_cmd(maxsites, human, type_substring, file_line_substring,
                       sort_on_column):
    sites = [Struct(bytes=b, nallocs=na, totallocs=ta, type=t, file=f, line=l)
             for (b, na, ta, t, f, l) in mm_get_sites()]
    max = maxsites if maxsites else None
    shown = sorted(sites, key=lambda x: x.totallocs, reverse=True)[:max]
    columns = mm_list_allocs_columns()
    columns.select(sort_on_column)
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, n)] for n in columns.names()])]
    if human:
        props[0][1][0].append((table.Column_Key_Binary_Prefix, "B"))
    data = [[s.bytes, s.totallocs, s.type, f"{s.file}:{s.line}"] for s in shown]
    data = [x for x in data if type_substring in x[2]]
    data = [x for x in data if file_line_substring in x[3]]
    data.sort(key=lambda x:x[columns.index], reverse=not columns.ascending)
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    tot_data = [
        ["Total shown", f"{cli.number_str(sum(s.bytes for s in shown))} bytes,",
         f"{cli.number_str(sum(s.totallocs for s in shown))} calls"],
        ["Total", f"{cli.number_str(sum(s.bytes for s in sites))} bytes,",
         f"{cli.number_str(sum(s.totallocs for s in sites))} calls"]]
    tot_tbl = table.Table(mm_props(("", "", ""), ("left", "right", "right")),
                          tot_data)
    msg += f"""\n{tot_tbl.to_string(
        rows_printed=0, no_row_column=True, border_style = 'borderless')}"""
    return cli.command_verbose_return(msg, data)

cli.new_unsupported_command(
    "mm-list-allocations", "malloc-debug",
    mm_list_allocs_cmd, [
        cli.arg(cli.int_t, "max", "?", 32),
        cli.arg(cli.flag_t, "-human-readable"),
        cli.arg(cli.str_t, "type-substr", "?", ""),
        cli.arg(cli.str_t, "file-line-substr", "?", ""),
        cli.arg(cli.str_t, "sort-on-column", "?", None,
                expander=mm_list_allocs_columns().complete)],
    short = "list busiest allocation sites",
    doc = """
    List the amount of calls to allocation sites.

    Limit the output using the <arg>max</arg> argument, default is
    <tt>32</tt>, or use <tt>0</tt> to list all sites. The
    <tt>-human-readable</tt> flag
    will show rounded, human readable values. Filtering can be achieved by
    specifying <arg>type-substr</arg> to filter type name and
    <arg>file-line-substr</arg> to filter file:line.

    Use the <arg>sort-on-column</arg> argument to sort on a given column.
    By default output is sorted on allocated size, the net number of bytes
    allocated but not yet freed.""")

#
# ------------------- uncatch-signal -------------------
#
def uncatch_signal_cmd(signo):
    if (simics.DBG_uncatch_signal(signo) == -1):
        raise cli.CliError("Failed to remove signal handler for %d" % signo)
    else:
        print("Signal %d not caught by Simics anymore" % signo)


cli.new_unsupported_command("uncatch-signal", "internals", uncatch_signal_cmd,
                        args = [cli.arg(cli.int_t, "signo")],
                        short = "disable a Simics signal handler",
                        doc = """
            Disable a Simics installed signal handler for the specified
            <arg>signo</arg> in favor of the default behavior.

            This can be useful if you have an error which only happens
            occasionally and you want to generate a core file to analyze the
            problem when and why it has happened.""")



#
# ------------------- dump-sr-stat -------------------
#
def dump_sr_stat_cmd(filename):
    cpu = cli.current_cpu_obj()
    try:
        if not cpu.iface.processor.dump_sr_stat(filename):
            print("Failed to dump statistics")
    except:
        print("Simics does not have SR statistics.")

cli.new_unsupported_command("dump-sr-stat", "internals", dump_sr_stat_cmd,
                        [cli.arg(cli.filename_t(), "file_name")],
                        short = "dump service routine statistics",
                        doc = """
Dump statistics about service routines and more to <arg>file_name</arg>.

On a Simics compiled with the <b>-gs</b> Simgen flag, this command generates a
file with statistics on which service routines and parameter combinations that
has been executed during this session. This file can be used as an input file
to Simgen (<b>-as</b> and <b>-s</b> flags) to sort and specialize service
routines, making a faster sim.
""")

#
# -------------------- dump-dstc --------------------
#

def dump_dstc():
    try:
        cli.current_cpu_obj().iface.stc.dump_dstc()
    except:
        print("dump dstc failed")

cli.new_unsupported_command("dstc-dump", "internals", dump_dstc, [],
                        short = "print contents of D-STC",
                        doc = """
Print contents of data STCs for debugging Simics internals. The STC tables are
used to speed up memory access operations, and cache translations between
virtual, physical, and real addresses. Note: if there are multiple sets, this
command will only dump the currently active STC set.""")

#
# -------------------- cpu-pages-dump --------------------
#

def dump_pages(cpu):
    def pretty_access(acc):
        if acc & simics.Sim_Access_Read:
            ret = "r"
        else:
            ret = " "
        if acc & simics.Sim_Access_Write:
            ret = ret + "w"
        else:
            ret = ret + " "
        if acc & simics.Sim_Access_Execute:
            ret = ret + "x"
        else:
            ret = ret + " "
        return ret

    print_list = []
    for (paddr, page_offset, size, permission, inhibit,
         owns_icode, breakpoints) in cpu.cached_cpu_pages:
        print_list.append(["0x%x" % paddr, page_offset, size,
                           pretty_access(permission),
                           pretty_access(inhibit),
                           owns_icode,
                           pretty_access(breakpoints)])
    cli.print_columns([cli.Just_Left, cli.Just_Left, cli.Just_Left,
                       cli.Just_Left, cli.Just_Left, cli.Just_Left,
                       cli.Just_Left],
                  [[ "Paddr", "Offset", "Size", "Perm", "Inhibit",
                     "Owns", "BPs" ]] + print_list)

cli.new_unsupported_command("cpu-pages-dump", "internals", dump_pages,
            [cli.arg(cli.obj_t('processor', 'processor_info'), 'cpu')],
            short = "print all pages cached by the CPU",
            doc = """
Print contents of all cached pages by the given <arg>cpu</arg> for debugging
Simics internals.""")

#
# -------------------- infinite-loop --------------------
#

def infinite_loop_cmd():
    simics.DBG_infinite_loop()

cli.new_unsupported_command("infinite-loop", "internals", infinite_loop_cmd, [],
                        short = "enter infinite loop",
                        doc = """
Place Simics in an infinite loop for debugging Simics internals. Simics will
loop until an attached debugger clears a flag named
<tt>infinite_loop_condition</tt>.""")

#
# -------------------- print-last-exceptions -------------
#

def print_internal_counters(long_descriptions):
    try:
        counters = conf.sim.internal_counters
        desc = conf.sim.internal_counters_desc
    except:
        print("Internal profiling is not available")
        return
    print()
    for group, list in desc:
        print("%s" % group)
        for name, short_desc, long_desc in list:
            count = str(counters[name])
            pad = "."*(65 - len(count) - len(short_desc))
            print("   %s%s%s" % (short_desc, pad, count))
            if long_descriptions:
                print("      (%s) %s" % (name, long_desc))
                print()
        print()

cli.new_unsupported_command("print-internal-counters", "internals",
                        print_internal_counters,
                        args = [cli.arg(cli.flag_t, "-long-descriptions")],
                        short = "print values of internal counters",
                        doc = """
            Print values of internal debugging counters. Extend output with
            the <tt>-long-descriptions</tt> flag.""")

def dmg_info_cmd(dmgfile, chunks, debug):
    try:
        di = dmg.DmgImage(dmgfile, bool(debug))
    except (dmg.DmgError, IOError) as e:
        raise cli.CliError(str(e))
    di.validate()
    (version, variant, sectsize, flags, filesize, datasize) = di.get_meta_info()
    ostr = [ "Apple disk image (DMG) information",
             "DMG Image      : %s" % os.path.basename(dmgfile),
             "DMG Version    : %5s" % version,
             "DMG Variant    : %5s" % variant,
             "DMG Flags      : %5s" % hex(flags),
             "DMG Sector Size: %s" % dmg.size_fmt(sectsize),
             "DMG File Size  : %s" % dmg.size_fmt(filesize),
             "DMG Data Size  : %s" % dmg.size_fmt(datasize) ]
    if bool(chunks):
        print("DMG chunk information")
        di.print_dest()
    return cli.command_return(
        value=[version, variant, flags, sectsize, filesize, datasize],
        message="\n".join(ostr))

cli.new_unsupported_command("image-dmg-info", "internals", dmg_info_cmd,
                        args=[cli.arg(cli.filename_t(exist=True, dirs=False), "image"),
                              cli.arg(cli.flag_t, "-chunks", "?", False),
                              cli.arg(cli.flag_t, "-debug", "?", False)],
                        short = "print dmg image information",
                        doc = """
Parse the Apple disk image (DMG) <arg>image</arg> file and print some
information about the it.

The <tt>-chunks</tt> flag prints the chunk information passed to
<tt>dmglib</tt>.

The <tt>-debug</tt> flag will enable debug print-outs from the dmg parser.  """)

#
# -------------------- print-debug-info-scheduler --------------------
#

def print_debug_info_scheduler_cmd(verbosity):
    return cli.command_verbose_return(
        message=simics.DBG_dump_scheduler_state(verbosity))

cli.new_unsupported_command(
    "print-debug-info-scheduler",
    "internals",
    print_debug_info_scheduler_cmd,
    args=[cli.arg(cli.int_t, "verbosity", "?", 0)],
    type=["Debugging", "Performance"],
    short="debug information about the state of Simics scheduler",
    doc="""
The command reports internal details about the state of the simulator scheduler.
It can be useful for debugging the simulator.

The command is not supported and may change at any time with notification.

The optional <arg>verbosity</arg> parameter can sometimes be used to show
additional debug information. Output from the command contains information when
and how the parameter can be useful.""")
