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


import cli
import pyobj
import table
import re
import simics
import conf
from probes import *

class TrackerNotEnabled(Exception):
    pass

class CPUInfo:
    __slots__ = ("cpu", "scheduled", "steps", "quantum_start_steps", "moved_to")
    def __init__(self, cpu):
        self.cpu = cpu
        self.scheduled = 0
        self.steps = 0
        self.quantum_start_steps = 0
        self.moved_to = False

class ProcessInfo:
    __slots__ = ("name", "cpus", "created")
    def __init__(self, name):
        self.name = name
        self.created = 0
        self.cpus = {} # dict of CPUInfo:s

class TrackProcesses:
    def __init__(self, tool, software_comp):
        # Get the osa_admin object from the component, this will be used to
        # access the node tree interfaces.
        if not software_comp.current_tracker:
            raise TrackerNotEnabled("No available software tracker")

        self.tool = tool
        self.osa_admin = software_comp.iface.osa_component.get_admin()
        self.notifiers = set()          # Global notifiers
        self.node_notifiers = {} # Process notifiers, dict indexed by node_id

        self.processes = {} # Process dict with ProcessInfo:s

        osa_ctrl_iface = self.osa_admin.iface.osa_control_v2
        (status, id) = osa_ctrl_iface.request("process-histogram")
        if not status:
            print("Failed to enable process-tracker")
            raise TrackerNotEnabled

        self.osa_id = id

        # Most OSA interface functions require a node ID. Retrieve the root_id
        # from the component. Using the root ID in combination with the
        # recursive flag makes it possible to get notifications for the entire
        # node tree.
        root_node = software_comp.iface.osa_component.get_root_node()
        if not root_node.valid:
            print("No root node present, tracker not properly configured?")
            raise TrackerNotEnabled

        self.root_id = root_node.id

        # Interface used to register callback functions for node tree updates.
        self.notification_ifc = self.osa_admin.iface.osa_node_tree_notification

        # Interface used to query the current state in the node tree.
        self.query_ifc = self.osa_admin.iface.osa_node_tree_query

        # Install callbacks for when any process is created or changed name
        create_id = self.notification_ifc.notify_create(
            self.root_id, True, self.create_cb, None)
        change_id = self.notification_ifc.notify_property_change(
            self.root_id, "name", True, self.name_cb, None)

        self.notifiers.add(create_id)
        self.notifiers.add(change_id)

        self.find_running_processes() # If OS is already running

    def find_running_processes(self):
        self.active_processes_detected = []
        self.scheduled_processes_detected = []
        self.search_for_processes(self.root_id)

        if self.active_processes_detected:
            processes_found = ",".join(self.active_processes_detected)
            self.output(1, f"Active processes: {processes_found}")
        if self.scheduled_processes_detected:
            for (process, cpu) in self.scheduled_processes_detected:
                self.output(1, f"Process '{process}' scheduled on {cpu.name}")
        else:
            self.output(1, "No processes are currently being scheduled")


    # If the process-histogram is started on an already running OS
    # get hold of the processes being run right now so we can start
    # counting execution for these too. Recursively traverse the
    # node-tree to find user-processes
    def search_for_processes(self, node_id):
        if self.is_process(node_id):
            process_name = self.get_process_name(node_id)
            self.output(2, f"Process '{process_name}' detected")
            self.active_processes_detected.append(process_name)
            self.new_process(node_id, process_name)
            self.check_if_process_is_being_scheduled(node_id, process_name)

        children = self.query_ifc.get_children(node_id)
        for cid in children:
            self.search_for_processes(cid)

    # Check if a process is scheduled on a processor.
    # If so, start to count its instructions
    def check_if_process_is_being_scheduled(self, node_id, process_name):
        cpus = self.query_ifc.get_all_processors()
        for cpu in cpus:
            nodes = self.query_ifc.get_current_nodes(self.root_id, cpu)
            for n in nodes:
                if n == node_id:
                    self.output(2, f"Process '{process_name}' scheduled on {cpu.name}")
                    self.scheduled_processes_detected.append((process_name, cpu))
                    self.assign_process_to_cpu(process_name, cpu)
                    return

    def new_process(self, node_id, process_name):
        self.register_process_notifiers(node_id)
        pinfo = self.get_process_info(process_name)
        pinfo.created += 1

    def assign_process_to_cpu(self, process_name, cpu):
        pinfo = self.get_process_info(process_name)
        cinfo = self.get_cpu_info(pinfo, cpu)
        cinfo.scheduled += 1
        cinfo.moved_to = True
        assert cinfo.quantum_start_steps == 0
        cinfo.quantum_start_steps = simics.SIM_step_count(cpu)


    # Called from the outside to get rid of all notifiers (object dead)
    def disable(self):
        # Remove global callbacks
        while self.notifiers:
            self.notification_ifc.cancel_notify(self.notifiers.pop())

        # Process specific callbacks
        for p in self.node_notifiers:
            for n in self.node_notifiers[p]:
                self.notification_ifc.cancel_notify(n)
        self.node_notifiers = {}

        # Release OSA connection
        osa_ctrl_iface = self.osa_admin.iface.osa_control_v2
        osa_ctrl_iface.release(self.osa_id)
        self.osa_id = None

    # Add more notifier for a newly detected process that we should follow.
    def register_process_notifiers(self, id):
        destroy_id = self.notification_ifc.notify_destroy(
            id, True, self.destroy_cb, None)

        to_id = self.notification_ifc.notify_cpu_move_to(
            id, self.move_to_cb, None)

        from_id = self.notification_ifc.notify_cpu_move_from(
            id, self.move_from_cb, None)

        self.node_notifiers[id] = (destroy_id, to_id, from_id)

    def output(self, level, string):
        simics.SIM_log_info(level, self.tool, 0, string)

    # Check if a node is a process. This will only work for the Linux
    # tracker. It uses the fact that a process node contains the
    # process id, but not the thread id.
    def is_process(self, node_id):
        props = self.query_ifc.get_node(node_id)
        return 'pid' in props and not 'tid' in props

    # Return the process name for a node.
    def get_process_name(self, node_id):
        return self.query_ifc.get_node(node_id)['name']

    def get_cpu_info(self, pinfo, cpu):
        # Create cpu info if not already present
        cinfo = pinfo.cpus.get(cpu, CPUInfo(cpu))
        pinfo.cpus[cpu] = cinfo # make sure it is in the table
        return cinfo

    def get_process_info(self, process_name):
        # Create process info if not already present
        if not process_name in self.processes:
            self.processes[process_name] = ProcessInfo(process_name)
        return self.processes[process_name]

    # Called when any process is created
    def create_cb(self, cb_data, osa_admin, cpu, node_id):
        if not self.is_process(node_id):
            return
        process_name = self.get_process_name(node_id)
        self.output(2, f"Process created: '{process_name}' on {cpu.name}")
        self.new_process(node_id, process_name)

    # Called when a tracked process dies
    def destroy_cb(self, data, osa_admin, cpu, node_id):
        if not self.is_process(node_id):
            return
        process_name = self.get_process_name(node_id)
        self.output(2, "Process finished: '%s' on %s" % (
            process_name, cpu.name))

        # Remove associated notifiers
        for n in self.node_notifiers[node_id]:
            self.notification_ifc.cancel_notify(n)
        del self.node_notifiers[node_id]

    # Called when any process changes its name
    def name_cb(self, cb_data, osa_admin, cpu, node_id,
                key, old_name, new_name):

        # There can be other nodes than the process node with a
        # matching name, for example thread nodes.
        if not self.is_process(node_id):
            return

        # Create process info if not already present
        if not new_name in self.processes:
            self.processes[new_name] = ProcessInfo(new_name)

        self.output(2, "Process name change: '%s' -> '%s' on %s" % (
            old_name, new_name, cpu.name))

        pinfo = self.get_process_info(new_name)
        pinfo.created += 1

    # Called when the tracked process starts to run on a CPU
    def move_to_cb(self, cb_data, osa_admin, cpu, node_path):
        for id in node_path:
            if not self.is_process(id):
                continue

            process_name = self.get_process_name(id)
            self.output(3, "Process move: '%s' to '%s'" % (
                process_name, cpu.name))

            self.assign_process_to_cpu(process_name, cpu)

    # Called when the tracked process stops executing on a CPU
    def move_from_cb(self, cb_data, osa_admin, cpu, node_path):
        for id in node_path:
            if not self.is_process(id):
                continue
            process_name = self.get_process_name(id)
            self.output(3, "Process move: '%s' from %s" % (
                process_name, cpu.name))

            pinfo = self.get_process_info(process_name)
            cinfo = self.get_cpu_info(pinfo, cpu)
            if not cinfo.moved_to: # if we have not moved to this, skipp it
                continue
            cinfo.steps += simics.SIM_step_count(cpu) - cinfo.quantum_start_steps
            cinfo.quantum_start_steps = 0
            cinfo.moved_to = False

class process_histogram(pyobj.ConfObject):
    '''The process histogram connects to the process-tracker and
gathers information about processes. For each detected process it
counts: how many times it is created, scheduled on a certain processor and
the amount of instruction it has executed on each processor.'''

    _class_desc = "gathers process information on a system"

    def _initialize(self):
        super()._initialize()
        self.connections = []

    # <process_histogram>.info cmd
    def _info(self):
        conn = self.connections[0]
        return [
            ["", [
                ("OS awareness tracker", conn.object_data.software.name)]
             ]
        ]

    # <process_histogram>.status cmd
    def _status(self):
        conn = self.connections[0]
        tr = conn.object_data.tracker
        num_processes = len(tr.processes)
        cpu_info = {} # {cpu: (processes, steps, scheduled)}

        class CpuStat:
            def __init__(self):
                self.process_names = []
                self.steps = 0

        tot_steps = 0
        for (process_name, pinfo) in tr.processes.items():
            for (cpu, cinfo) in pinfo.cpus.items():
                cpu_info.setdefault(cpu, CpuStat())
                cpu_info[cpu].process_names.append(process_name)
                cpu_info[cpu].steps += cinfo.steps
                tot_steps += cinfo.steps

        cpu_ret = []
        for (cpu, cstat) in cpu_info.items():
            cpu_ret.append(
                [f"{cpu.name}",
                 [("Num Processes", len(cstat.process_names)),
                  ("Processes", ", ".join(sorted(cstat.process_names))),
                  ("Steps", cstat.steps)],
                 ],
            )

        ret = [
            ["Overall", [
                ("User processes found", num_processes),
                ("Steps in all processes", f"{tot_steps}")
            ]],
        ]
        if cpu_ret:
            ret.extend(sorted(cpu_ret))
        return ret

    class process_histogram_connection(pyobj.ConfObject):
        """These objects holds information about a process_histogram's
        connection to the software tracker"""
        _class_desc = "software connection"

        class instrumentation_connection(pyobj.Interface):
            def enable(self):
                return

            def disable(self):
                return    # Always on

        def _pre_delete(self):
            # remove the connection from our internal list
            self.tool.object_data.connections.remove(self.obj)
            self.tracker.disable()
            super()._pre_delete()

    class instrumentation_tool(pyobj.Interface):
        def connect(self, software, args):
            try:
                tracker = TrackProcesses(self._top.obj, software)
            except TrackerNotEnabled as msg:
                print(msg)
                return None

            conn = simics.SIM_create_object(
                "process_histogram_connection",
                self._top.obj.name + ".con%d" % (len(self._top.connections)))
            if not conn:
                tracker.disable()
                return None
            conn.object_data.tracker = tracker
            conn.object_data.software = software
            conn.object_data.tool = self._top.obj
            self._top.connections.append(conn)
            return conn

        def disconnect(self, conn):
            simics.SIM_delete_object(conn)

    class table(pyobj.Interface):
        def properties(self):
            return [
                [table.Table_Key_Name, "Process histogram"],
                [table.Table_Key_Description, (
                    "Histogram of the most frequently executed processes on"
                    " the target system.")],
                [table.Table_Key_Default_Sort_Column, "Steps"],
                [table.Table_Key_Columns,  [
                    [[table.Column_Key_Name, "Process"],
                     [table.Column_Key_Description, "Name of the process."],
                    ],
                    [[table.Column_Key_Name, "Created"],
                     [table.Column_Key_Int_Radix, 10],
                     [table.Column_Key_Sort_Descending, True],
                     [table.Column_Key_Footer_Sum, True],
                     [table.Column_Key_Generate_Percent_Column, []],
                     [table.Column_Key_Generate_Acc_Percent_Column, []],
                     [table.Column_Key_Description, (
                         "Number of times the process/thread has been"
                         " created.")],
                    ],
                    [[table.Column_Key_Name, "Scheduled"],
                     [table.Column_Key_Int_Radix, 10],
                     [table.Column_Key_Sort_Descending, True],
                     [table.Column_Key_Footer_Sum, True],
                     [table.Column_Key_Generate_Percent_Column, []],
                     [table.Column_Key_Generate_Acc_Percent_Column, []],
                     [table.Column_Key_Description, (
                         "Amount of times any process-thread has been"
                         " scheduled to run on any of the processors.")],
                    ],
                    [[table.Column_Key_Name, "Steps"],
                     [table.Column_Key_Int_Radix, 10],
                     [table.Column_Key_Sort_Descending, True],
                     [table.Column_Key_Footer_Sum, True],
                     [table.Column_Key_Generate_Percent_Column, []],
                     [table.Column_Key_Generate_Acc_Percent_Column, []],
                     [table.Column_Key_Description, (
                         "Total amount of steps that the process has executed"
                         " on all processors.")],
                    ]]]
            ]

        def data(self):
            return self._top.histogram_data()

    # Return (steps, scheduled) for the processors
    @staticmethod
    def cpu_data(pinfo, only_cpu=None):
        steps = 0
        scheduled = 0
        for c in pinfo.cpus:
            if only_cpu and c != only_cpu:
                continue
            cinfo = pinfo.cpus[c]
            scheduled += cinfo.scheduled
            steps += cinfo.steps
        return (steps, scheduled)

    def histogram_data(self, cpu=None):
        if not self.connections:
            return []
        conn = self.connections[0]
        tr = conn.object_data.tracker
        rows = []
        for p in tr.processes:
            pinfo = tr.processes[p]
            (steps, scheduled) = self.cpu_data(pinfo, cpu)
            rows.append([pinfo.name, pinfo.created, scheduled, steps])
        return rows

    class probe_index(pyobj.Interface):
        def num_indices(self):
            return simics.SIM_number_processors() + 1

        def value(self, idx):
            if not self._top.connections:
                return []

            if idx == simics.SIM_number_processors():
                # All CPUs
                rows = self._top.histogram_data()
            else:
                cpu = [c for c in simics.SIM_get_all_processors()
                       if c.processor_number == idx][0]

                rows = self._top.histogram_data(cpu)
            # Only return name and steps for the probe
            return [[name, steps] for (name, _, _, steps) in rows]

        def properties(self, idx):
            obj = self._top.obj
            if idx == simics.SIM_number_processors():
                # Total of all processors
                return [[Probe_Key_Kind,
                         f"sim.tool.{obj.classname}.{obj.name}.histogram"],
                        [Probe_Key_Display_Name, "Process histogram"],
                        [Probe_Key_Description, "Most frequently run processes,"
                         "measured by the process-histogram."],
                        [Probe_Key_Width, 40],
                        [Probe_Key_Owner_Object, conf.sim],
                        [Probe_Key_Type, "histogram"],
                        [Probe_Key_Categories, ["processes", "target"]],
                        ]
            cpu = [c for c in simics.SIM_get_all_processors()
                   if c.processor_number == idx][0]

            return [[Probe_Key_Kind,
                     f"cpu.tool.{obj.classname}.{obj.name}.histogram"],
                    [Probe_Key_Display_Name, "Process histogram"],
                    [Probe_Key_Description, "Most frequently run processes,"
                         "measured by the process-histogram."],
                    [Probe_Key_Width, 40],
                    [Probe_Key_Owner_Object, cpu],
                    [Probe_Key_Type, "histogram"],
                    [Probe_Key_Categories, ["processes", "target"]],
                    ]



def process_histogram_cmd(obj, reg_exp, cpu, *table_args):
    properties = obj.iface.table.properties()
    if cpu:
        print(f"Only showing steps for processes executed on {cpu.name}")

    phist = simics.SIM_object_data(obj)
    data = phist.histogram_data(cpu)

    if reg_exp:
        # Filter the data using the regexp
        try:
            ins_re = re.compile(reg_exp)
        except re.error:
            raise cli.CliError(
                "The regular expression '%s' is invalid" % reg_exp)

        org_num_rows = len(data)
        data = [r for r in data if ins_re.match(str(r[0]))]
        new_num_rows = len(data)
        print("Table reduced from %d to %d rows" % (
            org_num_rows, new_num_rows))

    msg = table.get(properties, data, *table_args)
    return cli.command_return(msg, data)

table.new_table_command(
    "histogram", process_histogram_cmd,
    cls = "process_histogram",
    args = [
        cli.arg(cli.str_t, "process-regexp", "?", None),
        cli.arg(cli.obj_t('cpu', 'processor_info'), "cpu", "?", None),
    ],
    type = ["Instrumentation"],
    short = "print histogram of executed processes",
    doc = """Prints histogram of the processes executed on
    the system.

    The <arg>process-regexp</arg> argument can be used
    to filter out only certain processes which matches
    the given regular expression.

    The <arg>cpu</arg> argument can be used to only show the steps
    executed on a particular processor.
    """,
    see_also = ["<process_histogram>.clear",
                "<process_histogram>.process-info"])

def clear_cmd(obj):
    for conn in obj.object_data.connections:
        tr = conn.object_data.tracker
        tr.processes = {}

cli.new_command("clear", clear_cmd,
                args = [],
                cls = "process_histogram",
                type = ["Instrumentation"],
                short = "clear process histogram",
                doc = ("Removes information on processes"
                       " that has been gathered."))

def process_info_cmd(obj, process_name):
    for conn in obj.object_data.connections:
        tr = conn.object_data.tracker
        print("Process info for connection:", conn.name)
        if not process_name in tr.processes:
            print("No process name: '%s'" % process_name)
            return
        pinfo = tr.processes[process_name]
        print("  Process:", process_name)
        print("    Created: %s times" % pinfo.created)
        print("    Scheduling info:")
        for c in sorted(pinfo.cpus, key=lambda cpu: cpu.name):
            cinfo = pinfo.cpus[c]
            print("        %s" % c.name)
            print("            Scheduled times: %d" % cinfo.scheduled)
            print("            Steps:           %d" % cinfo.steps)

def process_expander(string, obj):
    strings = []
    for conn in obj.object_data.connections:
        tr = conn.object_data.tracker
        strings.extend(list(tr.processes.keys()))
    return cli.get_completions(string, strings)

cli.new_command("process-info", process_info_cmd,
                args = [cli.arg(cli.str_t, "process-name",
                                expander = process_expander)],
                cls = "process_histogram",
                type = ["Instrumentation"],
                short = "print detailed info on a process",
                see_also = ["<process_histogram>.histogram"],
                doc = ("""Prints detailed scheduling information about a process
                executed on the system. The name of the process is given by the
                <arg>process-name</arg> argument."""))
