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


import cli
import conf
import itertools
import sim_commands
import simics
import table


class ThreadingMode:
    _modes = ["multicore", "subsystem", "serialized"]
    _alias = {}

    # Sets with cells used to handle combined
    # usage of enable/disable-mca and enable/disable-ct.
    mc_enabled = set()
    sub_enabled = set()

    def __init__(self):
        cli.new_command(
            'set-threading-mode',
            self.set_threading_mode_cmd,
            args = [
                cli.arg(cli.string_set_t(self._modes + list(self._alias)),
                        "mode", "?", None),
                cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None),
            ],
            type = ["Execution", "Performance"],
            short = "set threading mode",
            see_also = ["set-max-time-span",
                        "set-time-quantum",
                        "set-min-latency",
                        "set-thread-limit",
                        "list-thread-domains"],
            doc = """
        Set the threading mode to be used by Simics. The following values
        for <arg>mode</arg> are supported:

        <tt>multicore</tt> - run in multicore-threaded mode. This
        is a nondeterministic mode where individual CPU cores
        are simulated in parallel, for models supporting it.

        <tt>subsystem</tt> - run in subsystem-threaded mode. In this mode,
        groups of tightly coupled CPU cores can be simulated in parallel,
        but tightly coupled cores are simulated in sequence.
        This is also a nondeterministic mode.

        <tt>serialized</tt> - run in serialized mode, which usually is
        deterministic. All CPUs belonging to a particular cell are
        simulated in sequence.

        Regardless of the selected threading modes, models belonging to
        different cells can always be simulated in parallel unless
        all multithreading has been disabled with the
        <cmd>disable-multithreading</cmd> command.

        If a <arg>cell</arg> argument is specified, then the threading mode is
        only applied to that particular cell.

        If the command is given without a <arg>mode</arg> argument, then
        the current threading configuration is displayed together
        with various latency settings affecting the simulation. Settings
        which do not apply to the current mode or configuration are printed
        in parentheses. The number of concurrent threads that can be used
        to simulate the workload of a particular cell is listed in
        the <tt>#td</tt> column (the number of distinct thread domains in
        the cell containing CPUs). Please note that if, for example, the CPUs
        in the cell support the <tt>subsystem</tt> mode but don't support
        the <tt>multithreading</tt> mode then commands
        <cmd>set-threading-mode multicore</cmd> and
        <cmd>set-threading-mode subsystem</cmd> are equivalent (i.e. both
        commands switch CPUs to
        the <tt>Sim_Concurrency_Mode_Serialized_Memory</tt> mode). For such case
        the cell's current threading configuration
        that is reported by the <cmd>set-threading-mode</cmd> command
        is reported as being in a <tt>multicore/subsystem</tt> mode.
        """)

        cli.new_command(
            'enable-cell-threading',
            self.enable_subsystem_threading_cmd,
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None)],
            short = "deprecated",
            deprecated_version = simics.SIM_VERSION_7,
            deprecated = ('enable-subsystem-threading',))

        cli.new_command(
            'disable-cell-threading',
            self.disable_subsystem_threading_cmd,
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None)],
            short = "deprecated",
            deprecated_version = simics.SIM_VERSION_7,
            deprecated = ('disable-subsystem-threading',))

        cli.new_command(
            'enable-subsystem-threading',
            self.enable_subsystem_threading_cmd,
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None)],
            type = ["Execution", "Performance"],
            short = "enable cell threading",
            see_also = ["set-threading-mode",
                        "set-time-quantum",
                        "set-min-latency"],
            doc = """
        The <cmd>enable-subsystem-threading</cmd> command enables
        subsystem threading for the cell <arg>cell</arg>, or for all
        cells if the <arg>cell</arg> argument is omitted.

        A cell running in the <tt>subsystem</tt> simulation mode
        allows groups of tightly coupled CPUs to be simulated in parallel.

        The <cmd>enable-subsystem-threading</cmd> command is similar
        to the "<cmd>set-threading-mode subsystem</cmd>" command,
        except that cells already configured to run in a more
        parallel threading mode (i.e. use 'multicore' threading),
        will continue to do so.
        """)

        cli.new_command(
            'disable-subsystem-threading',
            self.disable_subsystem_threading_cmd,
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None)],
            see_also = ["set-threading-mode"],
            short = "deprecated",
            doc = """
        Disable the use of 'subsystem' threading mode
        in the cell <arg>cell</arg>,

        If the cell <arg>cell</arg> is currently using the 'subsystem'
        threading mode, then the threading mode is changed to 'serialized'.

        If the cell parameter is omitted, then all cells running in
        'subsystem' mode are switched to the 'serialized' threading mode.

        Note: cells using the 'multicore' threading mode are
        not affected by this command.
        """)

        cli.new_command(
            'enable-multicore-accelerator', self.enable_mca_cmd,
            alias = "enable-mca",
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None),
                    cli.arg(cli.string_set_t(["msi", "ww", "wwp"]),
                            "protocol", "?", "wwp"),
                    cli.arg(cli.float_t, "max-time-span", "?", None)],
            type = ["Execution", "Performance"],
            short = "enable multicore-accelerator",
            see_also = ["set-threading-mode"],
            doc = """
        Activate the "multicore" threading mode. In this mode, multiple
        threads are used to simulate processors and clocks concurrently
        within a cell, provided that the models support this execution mode.

        The command is a shorthand for <cmd>set-threading-mode multicore</cmd>.

        If <arg>cell</arg> is given, then "multicore" threading mode is
        set for that particular cell, otherwise it will be used for all
        cells in the configuration.

        The <arg>protocol</arg> argument chooses between different memory
        protection schemes and can be one of: <tt>msi</tt>, <tt>ww</tt>, or
        <tt>wwp</tt>. The msi protocol means that there can be multiple
        simultaneous readers for each memory region (currently the MMU page
        size of the target architecture) but only one writer. The ww protocol
        allows multiple simultaneous writers to the same memory region. This
        requires that the host has an equal or stricter memory consistency
        model then the simulated target architecture. In particular, target
        write operations must be as atomic on the host as on the target. Both
        these protocol requests exclusive read/write permissions for
        atomic operations. The wwp protocol uses host atomic operations to
        implement target atomic operations if possible. Currently this is not
        100% accurate but will only fail for very obscure cases not normally
        found in parallel workloads.

        The <arg>max-time-span</arg> argument specifies the maximum virtual
        time span (in seconds) that is allowed between clocks in an multicore
        accelerator enabled cell. This corresponds to the min latency that can
        be set between cells in sync domains.

        NOTE: The multicore accelerator mode is not deterministic. This means
        that running the same workload multiple times will most likely behave
        differently due to different interleaving of memory accesses.
        """)

        cli.new_command(
            'disable-multicore-accelerator', self.disable_mca_cmd,
            alias = 'disable-mca',
            args = [cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None)],
            short = "disable mca",
            type = ["Execution", "Performance"],
            doc = """
        Disable the multicore on multicore accelerator feature.

        If <arg>cell</arg> is given multicore acceleration will be deactivated
        for that particular cell, otherwise it will be deactivated for all
        cells in the configuration.""")

        cli.new_command(
            'multicore-accelerator-status', self.mca_status_cmd,
            alias = 'mca-status',
            args = [],
            type = ["Execution", "Performance"],
            short = "print multicore accelerator status",
            see_also = ["set-threading-mode"],
            doc = """Print the status of Multicore Accelerator.""")

        cli.new_command(
            'set-max-time-span',
            self.set_max_time_span_cmd,
            args = [
                cli.arg(cli.float_t, "max-time-span", "?", None),
                cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None),
            ],
            type = ["Execution", "Performance"],
            short = "set threading mode",
            see_also = ["set-threading-mode",
                        "set-time-quantum",
                        "set-min-latency"],
            doc = """
        Set the <arg>max-time-span</arg> parameter for the cell
        <arg>cell</arg>, or for all cells if the <arg>cell</arg> argument
        is omitted.

        Simics ensures that CPUs simulated in parallel within a
        particular cell never has virtual time differences that
        exceed this setting. The setting is only applicable if Simics
        is running in the <tt>subsystem</tt> or the <tt>multicore</tt>
        threading mode.

        Setting a too large interval may introduce too much latency
        in the simulation. On the other hand, setting a too small value
        may increase the synchronization overhead and limit the
        parallelism, leading to degraded simulation performance.

        The special value 0 means that the <tt>time-quantum</tt>
        value should be used as the <arg>max-time-span</arg> parameter.

        <b>NOTE</b>: The parameter resembles the <tt>time-quantum</tt>
        parameter, which is used by Simics when CPUs are simulated in sequences
        from a single thread.

        <b>NOTE</b>: CPUs belonging to different cells will also be
        kept synchronized, but in this case the maximal virtual time
        difference is controlled by the <cmd>set-min-latency</cmd> command.
        """)

        cli.new_command(
            'multimachine-accelerator-status',
            self.mma_status_cmd,
            short = "deprecated",
            deprecated = ('set-threading-mode',),
            deprecated_version = simics.SIM_VERSION_7)

        cli.new_command(
            'enable-multithreading',
            self.enable_multithreading_cmd,
            args = [cli.arg(cli.flag_t, "-force")],
            type = ["Execution", "Performance"],
            see_also = ["set-threading-mode",
                        "disable-multithreading"],
            short = "enable multithreaded simulation",
            doc = """
        Enable the use of multiple concurrent threads for processor
        model simulation. Running with multithreading enabled requires that all
        loaded modules are thread safe, and that the objects are correctly
        partitioned into cells.

        Note: the <cmd>set-threading-mode</cmd> command is used
        to control the actual threading mode of the simulation. This command
        is just a master switch which enables multithreading.

        The use of multithreading can be forced on, even when
        unsafe modules are loaded or when the cell partitioning rules are
        violated, by using the <tt>-force</tt> flag. The <tt>-force</tt>
        flag should only be used during model development.
        """)

        cli.new_command(
            'disable-multithreading',
            self.disable_multithreading_cmd,
            args = [],
            short = "disable multithreading",
            type = ["Execution", "Performance"],
            see_also = ["set-threading-mode"],
            doc = """
        Disable the use of multiple concurrent threads
        for processor model simulation.

        Note: turning off multithreading only prevents multiple threads
        from being used for instruction simulation. It does not disable
        usage of additional threads for things like JIT compilation.

        Disabling multithreading does not affect the threading
        mode of the simulation (see <cmd>set-threading-mode</cmd>).
        In particular, the thread domain partitioning and the virtual
        time synchronization mechanism is not affected.

        The ability to turn off multithreading is primarily intended as
        way to help debug concurrency issues in models.
        """)

        cli.new_command(
            'list-thread-domains',
            self.list_thread_domains_cmd,
            alias = "list-cells",  # easier-to-find name for inspecting cells
            args = [
                cli.arg(cli.flag_t, "-a", "?", None),
                cli.arg(cli.obj_t("cell", "cell"), "cell", "?", None),
            ],
            short = "list cells and thread domains in them",
            type = ["Execution", "Performance", "Inspection"],
            see_also = ["set-threading-mode"],
            doc = """
        The command lists cells and thread domains inside them. By default, with
        the <arg>cell</arg> argument omitted, all cells and thread domains in
        them are shown. When the <arg>cell</arg> argument is provided then only
        thread domains in the given cell are shown. Please note that devices
        belonging to cell thread domains, i.e. thread domains to which a cell
        object is assigned, are not reported because they are usually too many.

        The <tt>-a</tt> flag is currently ignored.

        Thread domains are entities that can be simulated in parallel
        with other thread domains. The thread-domain partitioning is
        managed by device models but depends on the active threading
        mode used by the simulation, which can be changed with the
        <cmd>set-threading-mode</cmd> command.
        """)

        cli.new_tech_preview_command(
            'enable-freerunning-mode', 'freerunning',
            self.enable_freerunning,
            args = [
                cli.arg(cli.obj_t("namespace"), "namespace", "?", None),
            ],
            see_also = ["disable-freerunning-mode",
                        "set-freerunning-speed",
                        "set-threading-mode",
                        ],
            short = "enable freerunning execution mode",
            doc = """
            Enable freerunning execution mode. In freerunning mode,
            the relationship between the virtual time and the time spent
            simulating a particular CPU is fixed. The ratio, called speed,
            defaults to 1, but can be changed with the
            <cmd>set-freerunning-speed</cmd> command.

            Freerunning mode typically allows more instructions to be
            executed in parallel if Simics is running in e.g. multicore
            threading mode. The main reason for this is that a CPU which is
            difficult to simulate no longer holds back a faster model from
            being simulated at full speed. On the other hand, a slower
            model will execute fewer instructions per virtual time compared
            to a faster model.

            The fixed ratio between virtual time and time spent simulating
            a model is subject to restrictions configured with the
            <cmd>set-freerunning-speed</cmd> command. In particular,
            limits can be set to ensure that the instructions per cycle
            ratio stays in a certain interval. The limits takes precedence
            over the selected execution speed ratio.

            Hypersimulation occurring e.g. when a CPU is idle, is allowed in
            freerunnig mode and is excluded from the execution speed ratio
            calculation.

            Since freerunning mode depends on how fast instructions are
            simulated, it is not deterministic.

            If the <arg>namespace</arg> argument is supplied, then
            freerunning mode is enabled only for the CPUs below this
            namespace.

            Note: all CPU models do not necessarily support freerunning mode.
            The <cmd>set-freerunning-speed</cmd> can be used to list all CPUs
            with support for freerunning mode.
        """)
        cli.new_tech_preview_command(
            'disable-freerunning-mode', 'freerunning',
            self.disable_freerunning,
            args = [
                cli.arg(cli.obj_t("namespace"), "namespace", "?", None),
            ],
            see_also = ["disable-freerunning-mode",
                        "set-freerunning-speed",
                        "set-threading-mode",
                        ],
            short = "disable freerunning execution mode",
            doc = """
            Disable freerunning execution mode. If the
            <arg>namespace</arg> argument is supplied, then freerunning mode
            is disabled only for CPUs below this namespace.
        """)
        cli.new_tech_preview_command(
            'set-freerunning-speed', 'freerunning',
            self.set_freerunning_speed,
            args = [
                cli.arg(cli.obj_t("namespace"), "namespace", "?", None),
                cli.arg(cli.float_t, "speed", "?", None),
                cli.arg(cli.float_t, "min_ips", "?", None),
                cli.arg(cli.float_t, "max_ips", "?", None),
            ],
            see_also = ["enable-freerunning-mode",
                        "disable-freerunning-mode",
                        ],
            short = "set freerunning speed",
            doc = """
            Set freerunning speed ratio to <arg>speed</arg>, expressed
            as a percentage. The speed ratio is the relation between the
            virtual time and the time spent simulating a particular mode.
            A value of 100 means that virtual time for a CPU advances with
            the amount of time spent simulating the model.

            The freerunning speed is subject to restrictions;
            the <arg>min_ips</arg> setting is expressed
            as a percentage of the CPU frequency and imposes a lower
            limit on the number of instructions executed per virtual second.
            Similarly, <arg>max_ips</arg> imposes an upper limit for the
            number of instructions that may be executed per virtual second.

            The configured restrictions take precedence over the speed
            setting.

            If no arguments are specified, then the current settings for
            all CPUs with in the simulation with freerunning support are listed.

            If a <arg>namespace</arg> argument is specified, then settings
            are modified only for CPUs below this namespace.
        """)

    def _freerun_objs(self, ns):
        def is_child(par, child):
            while child:
                if child == par or not par:
                    return True
                child = simics.SIM_object_parent(child)
        return [x for x in simics.SIM_object_iterator_for_interface(["freerun"])
                if is_child(ns, x)]

    def set_freerunning_speed(self, ns, speed, ips_min, ips_max):
        objs = self._freerun_objs(ns)
        if not all(x is None for x in [ips_min, ips_max, speed]):
            for x in objs:
                if ips_min is not None:
                    x.freerun_min_ips = ips_min / 100.0
                    if ns:
                        print(f"Setting freerunning IPS min for {x.name}"
                              f" to {ips_min:.1f}%")
                if ips_max is not None:
                    x.freerun_max_ips = ips_max / 100.0
                    if ns:
                        print(f"Setting freerunning IPS max for {x.name}"
                              f" to {ips_max:.1f}%")
                if speed:
                    x.freerun_speed = speed / 100.0
                    if ns:
                        print(f"Setting freerunning speed for {x.name}"
                              f" to {speed:.1f}%")
            if not ns:
                if speed is not None:
                    print(f"Setting freerunning speed to {speed}%")
                if ips_min is not None:
                    print(f"Setting freerunning IPS min"
                          f" to {ips_min:.1f}%")
                if ips_max is not None:
                    print(f"Setting freerunning IPS max"
                          f" to {ips_max:.1f}%")

        else:
            props = [(table.Table_Key_Columns,
                      [[(table.Column_Key_Name, "Processor")],
                       [(table.Column_Key_Name, "Speed"),
                        (table.Column_Key_Alignment, "center")],
                       [(table.Column_Key_Name, "Min IPS (%)"),
                        (table.Column_Key_Alignment, "right")],
                       [(table.Column_Key_Name, "Max IPS (%)"),
                        (table.Column_Key_Alignment, "right")],
                       [(table.Column_Key_Name, "Enabled"),
                        (table.Column_Key_Alignment, "center")],
                       ])]
            rows = [[x.name,
                     f"{x.freerun_speed * 100:.1f}",
                     f"{x.freerun_min_ips * 100:.1f}",
                     f"{x.freerun_max_ips * 100:.1f}",
                     str(x.iface.freerun.enabled()),
                     ]
                    for x in objs]
            t = table.Table(props, rows)
            tstr = t.to_string(rows_printed=0, no_row_column=True)
            return cli.command_verbose_return(tstr, rows)

    def enable_freerunning(self, ns):
        for x in self._freerun_objs(ns):
            x.freerun_enabled = True

    def disable_freerunning(self, ns):
        for x in self._freerun_objs(ns):
            x.freerun_enabled = False

    def list_thread_domains_cmd(self, unused_all_flag, cell):

        def is_clock(obj):
            return hasattr(obj.iface, "step") or hasattr(obj.iface, "cycle")

        def get_td_to_objects():
            '''Returns a dictionary mapping thread domains to the list of
               objects belonging to them. The list of objects is sorted
               by objects' name.'''
            rv = dict()
            objs_td_ordered = sorted(simics.SIM_object_iterator(None),
                                     key=simics.VT_get_thread_domain)
            for (td, group) in itertools.groupby(
                    objs_td_ordered, key=simics.VT_get_thread_domain):
                # NB: items from 'group' are sorted by name; dict below emulates
                # an ordered set:
                rv[td] = dict.fromkeys(group)
            return rv

        def get_cells_to_td_groups(self, cell):
            '''Returns a dictionary mapping cells to a list of lists where
               each inner list contains objects from the cell belonging
               to the same thread domain. Please note that not all objects
               from the cell are included in the list: to make output shorter
               some objects are filtered out.'''
            rv = dict()
            td_to_objects = get_td_to_objects()

            for cell in self._cells(cell):
                cell_td = simics.VT_get_thread_domain(cell)
                tds_to_report = set(simics.VT_get_thread_domain(clock)
                                    for clock in cell.clocks)
                tds_to_report.add(cell_td)

                groups = []  # all groups except for the one containing cell
                for td in tds_to_report:
                    group = td_to_objects.pop(td)
                    if td == cell_td:  # it is Cell Thread domain
                        # To keep output shorter, we report only clocks and
                        # cells. Cell is reported first for users' convenience.
                        group_with_cell = [cell]
                        group_with_cell.extend(o for o in group if is_clock(o))
                    else:
                        def is_reported(obj, group):
                            p = simics.SIM_port_object_parent(obj)
                            return (
                                # report all not port objects:
                                (p is None)

                                # plus report "strange" port objects which
                                # are in other TD than their parent (except for
                                # a special case with cell.ps which is a port
                                # object but may be not in cell thread domain:
                                or (p not in group and p != cell)
                            )
                        group = [o for o in group if is_reported(o, group)]

                        # Hopefully, there are not too many objects in group
                        # here. And if there can be such cases, one can consider
                        # reporting devices only when 'all_flag' is set.
                        groups.append(group)

                # NB: group with cell (i.e. cell thread domain) comes first. It
                # then gets #0 domain number in the output which is intended.
                rv[cell] = [group_with_cell] + sorted(groups)

            # Possible TODO: at this point td_to_objects contains thread domains
            # which were not included into 'rv'. If input argument 'cell' is
            # None than we would report all thread domains except for the
            # special thread domain that is assigned to, e.g., the 'sim'
            # object. Usually, only "special" objects like 'sim' are assigned to
            # this special thread domain. However, other object - for example,
            # the one not assigned to any cell - may also be assigned to this
            # special thread domain. It may be good to inform a user if there
            # are "usual" objects that were assigned to the special thread
            # domain.
            return rv

        ret = []
        out = ""

        cells_to_td_groups = get_cells_to_td_groups(self, cell)

        for (c, groups) in cells_to_td_groups.items():
            ret.extend(groups)
            props = [
                (table.Table_Key_Columns,
                      [[(table.Column_Key_Name, "Cell")],
                       [(table.Column_Key_Name, "Domain"),
                        (table.Column_Key_Alignment, "right")],
                       [(table.Column_Key_Name, "Objects")],
                      ])]
            if groups:
                rows = []
                for (i, g) in enumerate(groups):
                    is_cell_td = i == 0
                    rows.append(
                        [c.name if is_cell_td else "",
                         f"#{i}{'*' if is_cell_td else ''}",
                         "\n".join(x.name for x in g)])
            else:
                rows = [[c.name, "", ""]]
            t = table.Table(props, rows)
            tstr = t.to_string(rows_printed=0, no_row_column=True)
            out = (out and out + "\n") + tstr

        out += ("\n* thread domains marked with '*' are cell thread domains."
                " To keep output shorter, only the cell, CPU, and clock"
                " objects are reported for them.")

        return cli.command_verbose_return(out, ret)


    def _get_concurrency_objs(self, cell):
        return [o
                for o in simics.SIM_object_iterator_for_interface(
                        ["concurrency_mode"])
                if o.iface.concurrency_mode.supported_modes
                if o.iface.concurrency_mode.switch_mode
                if simics.VT_object_cell(o) is cell]

    def _get_concurrency_mode(self, cell):
        if not cell.clocks:
            return "n/a"
        cur = {o: o.iface.concurrency_mode.current_mode()
               for o in self._get_concurrency_objs(cell)}
        possible_modes = []
        for mode in ("multicore", "subsystem", "serialized"):
            if self._make_concurrency_mode(cell, mode) == cur:
                possible_modes.append(mode)
        if not possible_modes:
            # This can happen if, for example, some manual manipulation with
            # modes was done, or if new CPU objects were created after
            # threading mode was set for existing CPUs.
            return "<mixed>"
        if len(possible_modes) == 1:
            return possible_modes[0]
        else:
            # We cannot guess exactly what command was used to reach current
            # state. And ThreadingMode class has no such information as the
            # configuration could be loaded from a checkpoint. Let's return
            # every possible mode.
            return "/".join(possible_modes)

    # return {obj: concurrency_setting} dict for mode 'mode'
    def _make_concurrency_mode(self, cell, mode):
        s = {
            "multicore": 0,
            "subsystem": 1,
            "serialized": 2,
        }[mode]

        # The concurrency modes we want to run in, in priority order
        mode_list = [
            simics.Sim_Concurrency_Mode_Full,
            simics.Sim_Concurrency_Mode_Serialized_Memory,
            simics.Sim_Concurrency_Mode_Serialized,
            simics.Sim_Concurrency_Mode_Serialized_Memory,
            simics.Sim_Concurrency_Mode_Full,
        ][s:]

        return {o: next(x for x in mode_list
                        if x & o.iface.concurrency_mode.supported_modes())
                for o in self._get_concurrency_objs(cell)}

    # Used by 'cell.status' command
    def get_threading_mode(self, cell):
        return self._get_concurrency_mode(cell)

    # Used, among other places, by 'cell.status' command
    def get_num_thread_domains(self, cell):
        return len(set(simics.VT_get_thread_domain(clock)
                       for clock in cell.clocks))

    def _threading_status(self, cell=None):
        if cell is None:
            cells = list(simics.SIM_object_iterator_for_class("cell"))
        else:
            cells = [cell]

        rows = []
        retmode = set()
        if self._get_concurrency_objs(None):
            mode = self._get_concurrency_mode(None)
            rows.append(["<no cell>", mode, "n/a", "n/a", "n/a"])
            retmode.add(mode)
        for c in cells:
            mode = self._get_concurrency_mode(c)
            tq = cli.format_seconds(c.time_quantum_ps/1E12)
            n_td = self.get_num_thread_domains(c)
            if c.max_time_span_ps != 0:
                ts = cli.format_seconds(c.max_time_span_ps/1E12)
            else:
                ts = tq
            min_lat = cli.format_seconds(c.sync_domain.min_latency)
            if len(cells) == 1:
                min_lat = f"({min_lat})"
            if not mode in ("multicore", "subsystem"):
                ts = f"({ts})"
            if self.get_num_thread_domains(c) == len(c.clocks):
                tq = f"({tq})"
            rows.append([c.name, mode, n_td, tq, ts, min_lat])
            retmode.add(mode)

        props = [(table.Table_Key_Columns,
                  [[(table.Column_Key_Name, "cell")],
                   [(table.Column_Key_Name, "mode"),
                    (table.Column_Key_Alignment, "center")],
                   [(table.Column_Key_Name, "#td")],
                   [(table.Column_Key_Name, "time-quantum"),
                    (table.Column_Key_Alignment, "right")],
                   [(table.Column_Key_Name, "max-time-span"),
                    (table.Column_Key_Alignment, "right")],
                   [(table.Column_Key_Name, "min-latency"),
                    (table.Column_Key_Alignment, "right")],
                   ])]
        t = table.Table(props, rows)

        out = t.to_string(rows_printed=0, no_row_column=True)
        if not conf.sim.multithreading:
            out += "\nNote: multithreading is currently disabled"

        retmode.discard("n/a")
        if len(retmode) == 1:
            return (out, retmode.pop())
        else:
            return (out, None)

    def _enable_multithreading(self, force = False):
        if conf.sim.multithreading:
            return
        unsafe_modules = 0
        for mod in simics.SIM_get_all_modules():
            name = mod[0]
            report_loaded = mod[2]
            thread_safe = mod[8]
            if report_loaded and not thread_safe:
                print(("WARNING: Module '%s' is not certified as"
                       " thread safe." % name))
                unsafe_modules += 1
        if not force:
            if unsafe_modules:
                raise cli.CliError("Multimachine Accelerator not enabled due to"
                                   " unsafe loaded modules.")
            if not sim_commands.check_cell_partitioning_global():
                raise cli.CliError("Multimachine Accelerator not enabled due to"
                                   " unsafe cell partitioning.")
        conf.sim.multithreading = True

    def mma_status_cmd(self):
        s = "enabled" if conf.sim.multithreading else "disabled"
        return cli.command_verbose_return(
            message=f"Multithreading {s}", value=conf.sim.multithreading)

    def enable_multithreading_cmd(self, force):
        if cli.interactive_command():
            if conf.sim.multithreading:
                print("Multithreading already enabled")
            else:
                print("Multithreading enabled")
        self._enable_multithreading(force)

    def disable_multithreading_cmd(self):
        if cli.interactive_command():
            if conf.sim.multithreading:
                print("Multithreading disabled")
            else:
                print("Multithreading already disabled")
        conf.sim.multithreading = False

    # change threading mode, if 'from_mode' is the current mode
    def _change_threading_modes(self, cell, modefunc):
        m = {c: modefunc(c) for c in self._cells(cell)}
        modes = set(m.values())
        if len(modes) == 1:
            self._set_threading_mode(modes.pop(), cell=cell)
        else:
            for (c, mode) in sorted(m.items()):
                self._set_threading_mode(mode, cell=c)

    def enable_subsystem_threading_cmd(self, cell):
        def mode(c):
            return "multicore" if c in self.mc_enabled else "subsystem"
        self.sub_enabled.update(self._cells(cell))
        self._change_threading_modes(cell, mode)

    def disable_subsystem_threading_cmd(self, cell):
        def mode(c):
            return "multicore" if c in self.mc_enabled else "serialized"
        self._change_threading_modes(cell, mode)

    def enable_mca_cmd(self, cell, proto, time_span):
        if time_span is not None:
            self.set_max_time_span_cmd(time_span, cell)
        ret = self._set_threading_mode("multicore", cell=cell, mca_prot=proto)
        return ret

    def disable_mca_cmd(self, cell):
        def mode(c):
            return "subsystem" if c in self.sub_enabled else "serialized"
        self._change_threading_modes(cell, mode)

    def mca_status_cmd(self):
        (out, value) = self._threading_status()
        mca_enabled = value == "multicore"
        return cli.command_verbose_return(message=out, value=mca_enabled)

    def set_threading_mode_cmd(self, mode, cell, mca_prot=None, force=False):
        mode = self._alias.get(mode, mode)
        if not mode:
            (out, value) = self._threading_status(cell)
            return cli.command_verbose_return(message=out, value=value)
        self._set_threading_mode(mode, cell, mca_prot, force)

    def _cells(self, cell):
        if cell is None:
            return list(simics.SIM_object_iterator_for_class("cell"))
        else:
            return [cell]

    def _set_threading_mode(self, mode, cell=None, mca_prot=None, force=False):
        if mode == "single-threaded" and cell:
            raise cli.CliError("'cell' parameter cannot be specified"
                               " when switching to 'single-threaded' mode")

        # Fibers that are suspended in calls to SIM_transaction_wait may have
        # references to thread domains. Changing threading mode may create or
        # delete thread domains - see VT_update_thread_domain_assignments. As a
        # result, the references to thread domains from the fibers become
        # dangling. To avoid any crashes we prohibit updates to threading mode
        # while there are ongoing calls to SIM_transaction_wait:
        if any(i.is_wait for i in simics.CORE_get_deferred_transactions_info()):
            raise cli.CliError(
                "Cannot change threading mode because some model(s)"
                " used in simulation invoked SIM_transaction_wait function"
                " and it has not completed yet. Unfortunately, the simulator"
                " cannot change threading mode in such cases. One can try"
                " the following command to run the simulation until all calls"
                " to the SIM_transaction_wait function are completed:"
                ' "bp.notifier.run-until name = transaction-wait-all-completed".'
                ' See "help transaction-wait-all-completed" for more'
                ' information. The "list-transactions -chains" command'
                " can be used to see information about the transactions"
                " that are used in the call(s) to SIM_transaction_wait function"
                " and have not completed yet.")

        cells = self._cells(cell)

        if mode == "multicore":
            self.mc_enabled.update(cells)
        elif mode == "subsystem":
            self.sub_enabled.update(cells)
            self.mc_enabled.difference_update(cells)
        else:
            self.sub_enabled.difference_update(cells)
            self.mc_enabled.difference_update(cells)

        simics.SIM_flush_all_caches()

        # Give appropriate interactive response
        if cli.interactive_command():
            old_modes = {c: self._get_concurrency_mode(c) for c in cells}
            new_modes = {c: mode for c in cells}
            cellstr = f" for {cell.name}" if cell else ""
            if old_modes == new_modes:
                print(f"Using threading mode '{mode}'{cellstr}")
            else:
                print(f"Switching threading mode to '{mode}'{cellstr}")

        # Update thread domains and thread settings
        if mode == "single-threaded":
            conf.sim.multithreading = False

        extra = [] if cell else [None]
        for c in cells + extra:
            for (o, v) in self._make_concurrency_mode(c, mode).items():
                o.iface.concurrency_mode.switch_mode(v)

        simics.VT_update_thread_domain_assignments()

        if mca_prot is None:
            mca_prot = "base" if mode != "multicore" else "wwp"
        enable_ct = mode in ("multicore", "subsystem")

        for c in cells:
            self._set_mca_prot(c, mca_prot)
            self._set_cell_threading(c, enable_ct)

    # Set MCA protocol
    def _set_cell_threading(self, cell, enable):
        # The simulation setup is reconfigured when the
        # enable_cell_threading attribute is changed. Set it 'False'
        # to make sure a transaction between MCA and cell_threading
        # actually takes effect.
        cell.enable_cell_threading = False
        cell.enable_cell_threading = enable
        cell.multicore_accelerator_enabled = enable

    # Set MCA protocol
    def _set_mca_prot(self, cell, ma_prot):
        for cpu in cell.clocks:
            if hasattr(cpu, "ma_prot"):
                cpu.ma_prot = ma_prot

    # Change max_time_span
    def set_max_time_span_cmd(self, time_span, cell):
        cells = self._cells(cell)

        if time_span is None:
            (out, _) = self._threading_status(cell)
            val = None
            if cells:
                vals = set(c.max_time_span_ps for c in cells)
                if len(vals) == 1:
                    val = vals.pop()
            return cli.command_verbose_return(message=out, value=val)

        for c in cells:
            self._set_time_span(c, time_span)

    def _set_time_span(self, cell, time_span):
        if not 0 <= time_span < 2**64 // 1e12:
            raise cli.CliError("'max-time-span' negative or too large")

        if time_span is None:
            time_span_ps = cell.time_quantum_ps * 2
        else:
            time_span_ps = int(time_span * 1000000000000)
        cell.max_time_span_ps = max(min(time_span_ps, 2**63 - 1), 0)

cli.add_tech_preview("freerunning")
_tm = ThreadingMode()


cli.new_info_command('cell',
                 lambda obj: [
    (None,
     [("Execute objects", obj.clocks),
      ("Sync. Domain", obj.sync_domain)])])

def cell_info(obj):
    if obj.max_time_span_ps == 0:
        ts = f"{cli.format_seconds(obj.time_quantum)}" \
            "   (same as time-quantum)"
    else:
        ts = cli.format_seconds(obj.max_time_span_ps / 1E12)
    return [
        (None,
         [("Threading Mode", _tm.get_threading_mode(obj)),
          ("Thread Domains", _tm.get_num_thread_domains(obj)),
          ("Time Quantum", cli.format_seconds(obj.time_quantum)),
          ("Max Time Span", ts),
          ("Min Latency", cli.format_seconds(obj.sync_domain.min_latency)),
          ])]

cli.new_status_command('cell', cell_info)

def set_thread_limit_cmd(limit):
    if limit == None:
        lim = conf.sim.max_threads
        if lim:
            print("The number of simulation threads is limited to %d." % lim)
        else:
            print("The number of simulation threads is unlimited.")
    else:
        conf.sim.max_threads = limit

cli.new_command('set-thread-limit', set_thread_limit_cmd,
            args = [cli.arg(cli.uint_t, "limit", "?", None)],
            type = ["Execution", "Performance"],
            short = "limit the number of simulation threads",
            doc = """
Limits the number of threads Simics may use for multithreaded simulation.
If <arg>limit</arg> is zero, the thread limit is removed.

If no argument is given, the current setting is displayed.
""")
