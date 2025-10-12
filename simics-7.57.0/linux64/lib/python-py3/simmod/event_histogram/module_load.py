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


from simics import *
from table import *
from cli import new_command

class entry:
    def __init__(self, type, clock, obj, evclass, desc, first_seen, flags):
        self.type = type
        self.clock = clock
        self.obj = obj
        self.evclass = evclass
        self.desc = desc
        self.count = 1
        self.first_seen = first_seen
        self.flags = flags

ev_flags = {
    Sim_EC_Notsaved : "NotSaved",
    Sim_EC_Slot_Early : "SlotEarly",
    Sim_EC_Slot_Late : "SlotLate",
    Sim_EC_Machine_Sync : "MachineSync",
    Sim_EC_No_Serialize : "NoSerialize"
}

def update_dict(type, tool_obj, key, cpu, ev_obj, evclass, desc, time):
    hist = SIM_object_data(tool_obj).hist

    if key in hist:
        val = hist[key]
        val.count += 1
    else:
        ec = SIM_get_event_class(ev_obj.classname, evclass)
        if ec == None:
            # Some internal events does not have a class
            flags_str = ["Internal"]
        else:
            flags = SIM_event_class_flags(ec)
            flags_str = [v for (k,v) in ev_flags.items() if flags & k]
        hist[key] = entry(type, cpu, ev_obj, evclass, desc, time, ", ".join(flags_str))

def listify(seq):
    if not isinstance(seq, list) and not isinstance(seq, tuple):
        return seq
    ret = []
    for s in seq:
        ret.append(listify(s))
    return ret

class event_histogram_connection:
    cls = confclass("event_histogram_connection",
                    short_doc = "event histogram sub class",
                    pseudo = True)
    cls.doc = "Connection object for the event_histogram class"

    cls.attr.clock("o", default = None, doc = "clock")
    cls.attr.tool("o", default = None, doc = "tool")

    @cls.finalize
    def finalize_instance(self):
        self.sid = None
        self.cid = None
        self.event_count = 0
        self.obj.iface.instrumentation_connection.enable()

    @staticmethod
    def step_cb(conn, cpu, ev_obj, steps, evclass, desc, val, user_data):
        key = f"step {cpu.name} {ev_obj.name} {evclass} {desc}"
        update_dict("step", conn.tool, key, cpu, ev_obj, evclass, desc, steps)
        SIM_object_data(conn).event_count += 1

    @staticmethod
    def cycle_cb(conn, cpu, ev_obj, cycles, evclass, desc, val, user_data):
        key = f"cycle {cpu.name} {ev_obj.name} {evclass} {desc}"
        update_dict("cycle", conn.tool, key, cpu, ev_obj, evclass, desc, cycles)
        SIM_object_data(conn).event_count += 1

    @cls.iface.instrumentation_connection
    def enable(self):
        c = self.clock
        if hasattr(c.iface, "step_event_instrumentation"):
            self.sid = c.iface.step_event_instrumentation.register_step_event_cb(
                self.obj, self.step_cb, None)
        if hasattr(c.iface, "cycle_event_instrumentation"):
            self.cid = c.iface.cycle_event_instrumentation.register_cycle_event_cb(
                self.obj, self.cycle_cb, None)

    @cls.iface.instrumentation_connection
    def disable(self):
        c = self.clock
        if self.sid != None:
            c.iface.step_event_instrumentation.remove_step_event_cb(self.sid)
        if self.cid != None:
            c.iface.cycle_event_instrumentation.remove_cycle_event_cb(self.cid)

class event_histogrem:
    cls = confclass("event_histogram",
                    short_doc = "event histogram tool",
                    pseudo = True)
    cls.doc = """Instrumentation tool that collect and displays all events
    dispatched in connected clocks/processors in a histogram"""

    @cls.finalize
    def finalize_instance(self):
        self.connections = []
        self.num = 0
        self.hist = { } # "obj evclass_name desc" -> entry class object

    @cls.iface.instrumentation_tool
    def connect(self, clock, args):
        con = SIM_create_object("event_histogram_connection",
                                self.obj.name + f".con{self.num}",
                                args + [["clock", clock], ["tool", self.obj]])
        self.num += 1
        self.connections.append(con)
        return con

    @cls.iface.instrumentation_tool
    def disconnect(self, conn):
        self.connections.remove(conn)
        SIM_delete_object(conn)

    @cls.iface.table
    def properties(self):
        cols = [[[Column_Key_Name, "Type"],
                 [Column_Key_Description, "Whether a step or a cycle event."]],
                [[Column_Key_Name, "Clock Object"],
                 [Column_Key_Description,
                  "The clock or processor on which the event was posted."]],
                [[Column_Key_Name, "Event Object"],
                 [Column_Key_Description, "The object in the posted event."]],
                [[Column_Key_Name, "Event Class"],
                 [Column_Key_Description, "The name of the event class."]],
                [[Column_Key_Name, "Description"],
                 [Column_Key_Description, "The description of the event."]],
                [[Column_Key_Name, "Count"],
                 [Column_Key_Description,
                  "The number of times the event was triggered."],
                 [Column_Key_Int_Radix, 10],
                 [Column_Key_Sort_Descending, True],
                 [Column_Key_Footer_Sum, True],
                 [Column_Key_Generate_Percent_Column, []]],
                [[Column_Key_Name, "Average interval"],
                 [Column_Key_Description,
                  "The average interval between triggered events."]],
                [[Column_Key_Name, "First seen"],
                 [Column_Key_Description,
                  "The step or cycle where the event was first triggered."],
                 [Column_Key_Int_Radix, 10]],
                [[Column_Key_Name, "Flags"],
                 [Column_Key_Description,
                  "Event flags"]]
                ]


        prop = [[Table_Key_Name, "Event Histogram"],
                [Table_Key_Columns, cols],
                [Table_Key_Default_Sort_Column, "Count"]]
        return prop

    @cls.iface.table
    def data(self):
        rows = []
        for k in self.hist:
            e = self.hist[k]
            if e.type == "cycle":
                total = SIM_cycle_count(e.clock)
                t = "Cycle"
            else:
                total = SIM_step_count(e.clock)
                t = "Step"

            rows.append([t, e.clock, e.obj, e.evclass, e.desc, e.count,
                         int(total / e.count), e.first_seen, e.flags])
        return rows

def event_histogram_cmd(obj, *table_args):
    properties = obj.iface.table.properties()
    data = obj.iface.table.data()
    show(properties, data, *table_args)

def clear_cmd(obj):
    SIM_object_data(obj).hist = {}

new_table_command("histogram", event_histogram_cmd,
                  cls = "event_histogram",
                  args = [],
                  type = ["Instrumentation"],
                  short = "print taken exceptions with frequencies",
                  see_also = ["<event_histogram>.clear"],
                  doc ="""
Prints a histogram of the events triggered during the simulation, including
information about the clock on which they were posted, the event object, event
class name, description, number of times the event was triggered, average
interval between triggered events, and the step/cycle when the event was first
triggered. The last column shows the flags for the event, i.e.,
<tt>event_class_flag_t</tt> bits. See the documentation for the
<tt>SIM_register_event</tt> API function for an explanation.

For step events the average interval is calculated as total elapsed steps on the
processor (when the command is run) divided by the number of triggered
occurrences for that particular event. For cycle events, instead, the total
elapsed cycles for the clock is used divided by the number of triggered
occurrences.""")

new_command("clear", clear_cmd,
                [],
                cls = "event_histogram",
                type = ["Instrumentation"],
                short = "clear instruction sizes frequencies",
                see_also = ["<event_histogram>.histogram"],
                doc = ("Removes information on exceptions"
                       " that has been gathered."))
