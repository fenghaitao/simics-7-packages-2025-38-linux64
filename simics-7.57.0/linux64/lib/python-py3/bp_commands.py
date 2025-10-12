# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import collections
import re

import cli
import simics
import conf

from sim_commands import (
    expand_notifiers,
    object_expander,
    format_log_line,
)

from simics import (
    SIM_VERSION_6,
    SIM_VERSION_7,

    Sim_Access_Execute,
    Sim_Access_Read,
    Sim_Access_Write,

    SIM_hap_add_callback,
    SIM_hap_add_callback_obj,
    SIM_hap_add_callback_obj_index,
    SIM_hap_delete_callback_id,
    SIM_hap_delete_callback_obj_id,

    SIM_get_object,
    SIM_object_iterator,
)

from cli import (
    addr_t,
    arg,
    flag_t,
    float_t,
    int_t,
    obj_t,
    poly_t,
    str_t,
    string_set_t,
    uint64_t,
    uint_t,
    new_command,
    CliError,
    command_return,
    number_str,
    current_cpu_obj,
    current_cycle_obj,
    current_frontend_object,
    print_columns,

    # script-branch related imports:
    check_script_branch_command,
    sb_signal_waiting,
    sb_wait,
)

from script_branch import (
    sb_wait_for_hap_internal,
    sb_wait_for_notifier_internal,
)

from log_commands import (
    logger,
    get_cycle_object_for_timestamps,
)

def get_objs_in_group(cpu, namespace, same_class = False):
    """Returns a list of objects in the same cell as cpu, and that implement
       the interface given in namespace. Optionally only the processors of the
       same class as cpu is included in the list."""
    cpu_cell = cpu.queue.cell
    cpu_class = simics.SIM_object_class(cpu)

    def match_cell_and_class(obj):
        if ((not hasattr(obj.iface, namespace)) or (not obj.queue) or
            (not obj.queue.cell)):
            return False
        cell = obj.queue.cell
        if same_class and cpu_class != simics.SIM_object_class(obj):
            return False
        return cell == cpu_cell

    return list(filter(match_cell_and_class, simics.SIM_object_iterator(None)))

#
# -------------------- tracker class --------------------
#

# This class provides a command factory for break-* and trace-* functions. It
# shouldn't be used directly, but instead be subclassed with the specifics.
#
# The stop parameter to __init__ decides if it breaks or traces.
#
# The callback method is usually used as a hap callback.  It can be
# given to SIM_hap_add_callback().
#
# if namespace is != None, then namespace commands will be created
# if global_commands is True, then global commands will be created
#

class Tracker:
    def __init__(self, stop, cmd, target_name, expander,
                 short, doc,
                 iface = None,
                 global_commands = True,
                 group = "breakpoint",
                 see_also = [],
                 expander_cpu = None,
                 cls = None,
                 global_commands_with_obj = False,
                 deprecated = None,
                 deprecated_version = None):
        self.cmd = cmd
        self.stop = stop
        uncmd = "un" + cmd
        if isinstance(target_name, str):
            target_types = (str_t,)
            target_names = (target_name,)
            expander = (expander,)
            expander_cpu = (expander_cpu,)
        elif isinstance(target_name, tuple):
            target_types, target_names = target_name
            if not isinstance(target_types, tuple):
                target_types = (target_types,)
                target_names = (target_names,)
        else:
            raise TypeError

        args = [arg(target_types + (flag_t, flag_t),
                    target_names + ("-all", "-list"),
                    expander = expander + (0, 0))]

        self.iface = iface
        if self.iface:
            new_command(cmd, self.do_namespace_cmd, args, type=group,
                        short=short,
                        iface = iface,
                        see_also = see_also,
                        doc=doc,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)

            new_command(uncmd, self.do_namespace_uncmd, args, type=group,
                        iface = iface,
                        short=short,
                        doc_with='<' + iface + '>.' + cmd,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)

            # if it's a processor, register commands on current processor
            if global_commands:
                # use new args with expander_cpu instead
                cpu_args = [arg(target_types + (flag_t, flag_t),
                                target_names + ("-all", "-list"),
                                expander = expander_cpu + (0, 0))]

                new_command(cmd, self.do_cpu_cmd, cpu_args, type=group,
                            short=short,
                            doc_with='<' + iface + '>.' + cmd,
                            deprecated = deprecated,
                            deprecated_version = deprecated_version)

                new_command(uncmd, self.do_cpu_uncmd, cpu_args, type=group,
                            short=short,
                            doc_with='<' + iface + '>.' + cmd,
                            deprecated = deprecated,
                            deprecated_version = deprecated_version)

        elif global_commands_with_obj:
            args = [arg(obj_t("object"), "object", "?", None)] + args
            new_command(cmd, self.do_namespace_cmd, args, type=group,
                        short=short,
                        see_also = see_also,
                        doc=doc,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)

            new_command(uncmd, self.do_namespace_uncmd, args, type=group,
                        short=short,
                        doc_with=cmd,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)
        elif global_commands:
            new_command(cmd, self.do_cmd, args, type=group,
                        short=short,
                        see_also = see_also,
                        doc=doc,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)

            new_command(uncmd, self.do_uncmd, args, type=group,
                        short=short,
                        doc_with=cmd,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)
        if cls:
            new_command(cmd, self.do_cls_cmd, args, type=group,
                        short=short, see_also = see_also, doc=doc,
                        cls=cls,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)
            new_command(uncmd, self.do_cls_uncmd, args, type=group,
                        short=short, see_also = see_also,
                        doc_with='<' + cls + '>.' + cmd, cls=cls,
                        deprecated = deprecated,
                        deprecated_version = deprecated_version)

    def filter(self, *args):
        # Override this in your subclass if you want to ignore some
        # callbacks.
        #if self.iface:
        #    obj = args[0]
        return 1

    def resolve_target(self, *args):
        # This function translates the string given by the command to
        # something internally more useful, such as a configuration
        # object or something like that. Throw CliError on incorrect
        # values. Override in a subclass.
        if self.iface:
            obj, target = args
        else:
            target = args[0]
        return target

    def show(self, *args):
        # This function is called to print that something happened.
        # It should be overridden in a subclass.
        assert False

    def list(self, *args):
        # This function is called to list the tracked things, in
        # response to the -list parameter.
        assert False

    def is_tracked(self, *args):
        # This function is called to check if something is already
        # tracked.  Override it with something more useful.
        assert False

    def track_all(self, *args):
        # This function is called to set tracking on all possible choices.
        # Override it with something more useful.
        assert False

    def track_none(self, *args):
        # This function is called to remove tracking on all possible choices.
        # Override it with something more useful.
        assert False

    def track_on(self, *args):
        # This function is called to set tracking on a target.
        # Override it with something more useful.
        assert False

    def track_off(self, *args):
        # This function is called to remove tracking on a target.
        # Override it with something more useful.
        assert False

    def callback(self, *args):
        # Do not override this without a very good reason.
        if not self.filter(*args):
            return

        self.show(*args)
        if self.stop:
            simics.SIM_break_simulation(self.cmd)

    def do_namespace_cmd(self, obj, target_desc):
        type, target_name, param = target_desc
        if type == flag_t and param == "-all":
            if obj:
                self.track_all(obj)
            else:
                self.track_all()
        elif type == flag_t and param == "-list":
            if obj:
                self.list(obj)
            else:
                self.list()
        else:
            if obj:
                target = self.resolve_target(obj, target_name)
                if not self.is_tracked(obj, target):
                    self.track_on(obj, target)
            else:
                target = self.resolve_target(target_name)
                if not self.is_tracked(target):
                    self.track_on(target)

    def do_cmd(self, target_desc):
        self.do_namespace_cmd(None, target_desc)

    def do_cpu_cmd(self, target_desc):
        curr_cpu = current_frontend_object()
        if not hasattr(curr_cpu.iface, self.iface):
            raise CliError("The selected cpu does not implement the %s interface." % self.iface)
        for cpu in get_objs_in_group(curr_cpu, self.iface, same_class = True):
            self.do_namespace_cmd(cpu, target_desc)

    def do_namespace_uncmd(self, obj, target_desc):
        type, target_name, param = target_desc
        if type == flag_t and param == "-all":
            if obj:
                self.track_none(obj)
            else:
                self.track_none()
        elif type == flag_t and param == "-list":
            if obj:
                self.list(obj)
            else:
                self.list()
        else:
            if obj:
                target = self.resolve_target(obj, target_name)
                if self.is_tracked(obj, target):
                    self.track_off(obj, target)
            else:
                target = self.resolve_target(target_name)
                if self.is_tracked(target):
                    self.track_off(target)

    def do_uncmd(self, target_desc):
        self.do_namespace_uncmd(None, target_desc)

    def do_cpu_uncmd(self, target_desc):
        curr_cpu = current_frontend_object()
        if not hasattr(curr_cpu.iface, self.iface):
            raise CliError("The selected cpu does not implement the %s interface." % self.iface)
        for cpu in get_objs_in_group(curr_cpu, self.iface, same_class = True):
            self.do_namespace_uncmd(cpu, target_desc)

    def do_cls_cmd(self, obj, target_desc):
        self.do_namespace_cmd(obj, target_desc)

    def do_cls_uncmd(self, obj, target_desc):
        self.do_namespace_uncmd(obj, target_desc)

#
# -------------------- trace-cr --------------------
#

# NB: the class is also used by x86 CPU module, see x86_commands.py
class BaseCRTracker(Tracker):
    def __init__(self, stop, cmd, short, doc, type, iface, see_also = [],
                 global_commands = True, cls = None, deprecated_version = None,
                 deprecated = None):
        Tracker.__init__(self, stop, cmd, "register", self.expander,
                         short, doc,
                         iface = iface,
                         global_commands = global_commands,
                         see_also = see_also,
                         group = type,
                         expander_cpu = self.expander_cpu,
                         cls = cls,
                         deprecated_version = deprecated_version,
                         deprecated = deprecated)
        self.hap = "Core_Control_Register_Write"
        self.map = {}
        self.catchall = {}

    def expander(self, comp, cpu):
        try:
            iface = cpu.iface.int_register
            regs = [ cpu.iface.int_register.get_name(r)
                     for r in cpu.iface.int_register.all_registers()
                     if iface.register_info(r, simics.Sim_RegInfo_Catchable) ]
        except simics.SimExc_Lookup:
            regs = []
        return cli.get_completions(comp, regs)

    def expander_cpu(self, comp):
        return self.expander(comp, current_cpu_obj())

    # These four are here so that they can be overridden
    def get_all_registers(self, obj):
        iface = obj.iface.int_register
        return iface.all_registers()
    def get_register_number(self, obj, regname):
        id = obj.iface.int_register.get_number(regname)
        if id < 0:
            raise simics.SimExc_Lookup("No such register")
        return id
    def get_register_name(self, obj, reg):
        return obj.iface.int_register.get_name(reg)
    def register_number_catchable(self, obj, regno):
        return obj.iface.int_register.register_info(
            regno, simics.Sim_RegInfo_Catchable)

    def filter(self, *args):
        return simics.SIM_simics_is_running()

    def list(self, obj):
        if obj in self.catchall:
            print("[%s] %s enabled for all control registers" % (
                obj.name, "Breaking" if self.stop else "Tracing"))
        else:
            print("[%s] %s enabled for these control registers:" % (
                obj.name, "Breaking" if self.stop else "Tracing"))
            if obj in self.map:
                for reg in sorted(self.map[obj]):
                    print("  %s" % self.get_register_name(obj, reg))

    def resolve_target(self, obj, regname):
        try:
            return (regname, self.get_register_number(obj, regname))
        except:
            raise cli.CliError("No '%s' register in %s (%s)" % (regname, obj.name,
                                                            obj.classname))

    def is_tracked(self, obj, target):
        regname, regno = target
        return (obj in self.catchall
                or (obj in self.map and regno in self.map[obj]))

    def track_all(self, obj):
        if obj in self.catchall:
            return
        if not (obj in self.map):
            self.map[obj] = {}
        for regno,hdl in list(self.map[obj].items()):
            SIM_hap_delete_callback_obj_id(self.hap,
                                           obj, hdl)
            del self.map[obj][regno]
        self.catchall[obj] = SIM_hap_add_callback_obj(
            self.hap,                      # hap
            obj,                           # trigger object
            0,                             # flags
            self.callback,                 # callback
            None)                          # user value

    def track_none(self, obj):
        if obj in self.catchall:
            SIM_hap_delete_callback_obj_id(self.hap,
                                           obj,
                                           self.catchall[obj])
            del self.catchall[obj]
        else:
            if not (obj in self.map):
                self.map[obj] = {}
            for regno,hdl in list(self.map[obj].items()):
                SIM_hap_delete_callback_obj_id(self.hap, obj, hdl)
                del self.map[obj][regno]

    def track_on(self, obj, target):
        regname, regno = target
        if obj in self.catchall:
            print(("[%s] Already %s all control registers"
                   % (obj.name, "breaking on" if self.stop else "tracing")))
            return
        if self.is_tracked(obj, target):
            print(("[%s] Already %s %s"
                   % (obj.name, "breaking on" if self.stop else "tracing",
                      regname)))
            return
        if not self.register_number_catchable(obj, regno):
            print(("[%s] Cannot %s on %s"
                   % (obj.name, "break" if self.stop else "trace", regname)))
            return

        if not obj in self.map:
            self.map[obj] = {}
        self.map[obj][regno] = SIM_hap_add_callback_obj_index(
            self.hap,                      # hap
            obj,                           # trigger object
            0,                             # flags
            self.callback,                 # callback
            regname,                       # user value
            regno)                         # index

    def track_off(self, obj, target):
        regname, regno = target
        if obj in self.catchall:
            # All tracked, remove all
            self.track_none(obj)
            # Reinstall all catchable registers, except the one removed
            for r in self.get_all_registers(obj):
                if r != regno:
                    if self.register_number_catchable(obj, r):
                        regname = self.get_register_name(obj, r)
                        self.track_on(obj, (regname, r))
            return
        if not self.is_tracked(obj, target):
            print("[%s] Not %s %s" % (
                obj.name,
                "breaking on" if self.stop else "tracing",
                regname))
            return
        SIM_hap_delete_callback_obj_id(self.hap, obj, self.map[obj][regno])
        del self.map[obj][regno]

#
# -------------------- break-io, trace-io --------------------
#

# Returns a tuple of (value, big_endian)
def get_memop_value(memop):
    obj = memop.ini_ptr
    if not obj or simics.SIM_get_mem_op_size(memop) > 8:
        return (0, None)
    if hasattr(obj, "iface") and hasattr(obj.iface, "processor_info"):
        if obj.iface.processor_info.get_endian() == simics.Sim_Endian_Big:
            return (simics.SIM_get_mem_op_value_be(memop), True)
        else:
            return (simics.SIM_get_mem_op_value_le(memop), False)
    if conf.prefs.default_log_endianness == "big":
        return (simics.SIM_get_mem_op_value_be(memop), True)
    else:
        return (simics.SIM_get_mem_op_value_le(memop), False)

# This function is only kept to keep sb_wait_for_exception working.
def wait_for_exception_command(obj, wait_for_all, name, nbr):
    if not check_script_branch_command("wait-for-exception"):
        return
    if wait_for_all:
        if name or nbr >= 0:
            raise cli.CliError("Cannot use both -all and a specific exception")
        index = -1
    elif name and nbr >= 0:
        raise cli.CliError("Cannot use both name and number")
    elif name:
        index = obj.iface.exception.get_number(name)
        if index < 0:
            raise cli.CliError("%s does not implement the '%s' exception"
                           % (obj.name, name))
    elif nbr >= 0:
        name = obj.iface.exception.get_name(nbr)
        if not name:
            raise cli.CliError(f"{obj.name} does not implement the {nbr} exception")
        index = nbr
    else:
        raise cli.CliError("No exception specified")
    (_, ex) = sb_wait_for_hap_internal(
        'wait-for-hap', 'Core_Exception', obj, index,
        wait_data = name if name else "<all>")
    return obj.iface.exception.get_name(ex)

class IOTrackerItem(collections.namedtuple(
        'IOTrackerItem',
        ['id', 'obj', 'portname', 'idx', 'func', 'offset', 'length', 'mode'],
        defaults = [None]*8)):
    __slots__ = ()

    def is_match(self, obj, portname, idx, func, offset, length, mode):

        if self.obj is None:  # tracer which matches all objects
            return True

        def is_mode_match():
            return mode in self.mode

        def is_address_match():
            if self.offset is None:  # tracer doesn't check address range
                return True
            stop1 = self.offset + self.length - 1
            stop2 = offset + length - 1
            return self.offset <= stop2 and stop1 >= offset

        def is_port_match():
            if self.portname is None:
                return True   # we don't care about port
            # Values -1 and 0 of idx are special and we try to allow for that.
            return (self.portname == portname
                    and ((self.idx is None and idx in [0, -1])
                         or self.idx == idx))

        def is_func_match():
            return (self.func is None  # we don't care about func
                    or self.func == func)

        def is_device_match():
            return self.obj == obj and is_port_match() and is_func_match()

        return is_device_match() and is_mode_match() and is_address_match()

class IOTracker:
    def __init__(self, stop, cmd, short, doc, type, see_also = [],
                 deprecated = None, deprecated_version = None,
                 legacy = None, legacy_version = None):

        # The self.tracers list contains information about tracers. The set
        # entries are IOTrackerItem items. Please note that there can be
        # multiple entries with the same id.
        self.tracers = []

        # The self.monitored_objects dict holds information about installed
        # hap callbacks. It maps an object (an object equal to None means
        # that the callback is installed for all objects) to a hap handler.
        self.monitored_objects = {}

        self.next_id = 0
        self.cmd = cmd
        self.stop = stop
        if stop:
            self.break_io_hap = simics.SIM_hap_get_number("Internal_Break_IO")
        uncmd = 'un' + cmd
        self.register_commands(cmd, uncmd, short, doc, type, see_also,
                               deprecated, deprecated_version,
                               legacy, legacy_version)

    def register_commands(self, cmd, uncmd, short, doc, type, see_also,
                          deprecated, deprecated_version, legacy,
                          legacy_version):
        args = [arg(str_t, 'device', '?', expander = self.expander),
                arg(poly_t("port", str_t, int_t), "port", '?'),
                arg(int_t, 'offset', '?'),
                arg(int_t, 'length', '?'),
                arg(flag_t, '-r'),
                arg(flag_t, '-w'),
                arg(flag_t, '-all'),
                arg(flag_t, '-list')]

        new_command(cmd, self.do_cmd, args, type=type,
                    short=short,
                    see_also = see_also,
                    doc=doc[0],
                    deprecated=deprecated,
                    deprecated_version=deprecated_version,
                    legacy=legacy,
                    legacy_version=legacy_version)

        args_uncmd = [arg((flag_t, flag_t, str_t, int_t),
                          ('-list', '-all', 'device', 'id'),
                          expander = (0, 0,
                                      self.expander_uncmd, self.id_expander))]

        new_command(uncmd, self.do_uncmd, args_uncmd, type=type,
                    short=short,
                    doc=doc[1])

        if self.stop:
            new_command('wait-for-io-break', self.wait_for_io,
                        [arg(int_t, 'id', expander = self.id_expander)],
                        short='wait for IO activity',
                        see_also = ["bp.bank.break"],
                        legacy = "bp.bank.wait-for",
                        legacy_version = SIM_VERSION_7,
                        doc = """
Suspends execution of a script branch until the IO breakpoint <arg>id</arg> is
triggered. The script branch is then resumed and the simulation is not
interrupted. The IO breakpoint must be created using <cmd>break-io</cmd>.""")

    def is_io_device(self, obj):
        """Return True if this device, any of its ports or any of its
        port-objects implement the io_memory interface"""
        if hasattr(obj.iface, 'io_memory'):
            return True
        for c in set(simics.VT_get_port_classes(obj.classname).values()):
            if simics.SIM_c_get_class_interface(c, 'io_memory'):
                return True
        for (_, _, iface) in simics.VT_get_port_interfaces(obj.classname):
            if iface == 'io_memory':
                return True

    def expander(self, prefix):
        return cli.get_completions(prefix, (obj.name for obj
                                        in SIM_object_iterator(None)
                                        if self.is_io_device(obj)))

    def id_expander(self, prefix):
        return cli.get_completions(prefix, [str(id) for id in self.get_ids()])

    def wait_for_io(self, id):
        if not id in self.get_ids():
            raise cli.CliError("No IO breakpoint with ID %d" % id)
        sb_wait_for_hap_internal('wait-for-io-break', "Internal_Break_IO",
                                 None, id, wait_data = "%d" % id)

    def get_ids(self):
        return set(tracer.id for tracer in self.tracers)

    def get_devices(self):
        return [tracer.obj for tracer in self.tracers if tracer.obj]

    def expander_uncmd(self, prefix):
        return cli.get_completions(prefix, [obj.name for obj
                                        in self.get_devices()])

    def extract_devices(self, obj, port):
        """Returns a list of tuples (obj, portname, index, func) to track:
        obj is the object on which the hap callback will be registered
        portname is the name of the iface-port (if any) without index (if any)
        index is the index of the iface-port (if any)
        func is the function number (if any)

        If both portname and func are None all ports and interfaces
        should be tracked."""
        if not self.is_io_device(obj):
            raise cli.CliError("Invalid device '%s'" % obj.name)

        def split_port(port):
            portname, index = re.match(r"(\w+)(?:\[(\d+)])?", port).groups()
            if index is None:
                return (portname, None)
            return (portname, int(index))

        devices = []
        if port is None:
            devices.append((obj, None, None, None))
            parent = simics.SIM_port_object_parent(obj)
            if (parent):
                # trace on parent to catch [obj, port] mappings
                port = obj.name.rsplit('.')[-1]
                if simics.SIM_c_get_port_interface(parent, 'io_memory', port):
                    portname, index = split_port(port)
                    devices.append((parent, portname, index, None))
            else:
                # trace on port-objects to catch obj.port mappings
                port_objects = (o for o in SIM_object_iterator(obj)
                                if hasattr(o.iface, 'io_memory')
                                and simics.SIM_port_object_parent(o) == obj)
                for o in port_objects:
                    devices.append((o, None, None, None))
        elif isinstance(port, str):
            if simics.SIM_c_get_port_interface(obj, 'io_memory', port):
                portname, index = split_port(port)
                devices.append((obj, portname, index, None))

                # DMLC creates port-objects for banks and ports and
                # wraps these in port-interfaces (which is traced
                # above), we must also trace on the port-object to catch
                # obj.port mappings
                for port_obj_name in simics.VT_get_port_classes(obj.classname):
                    if port_obj_name in ("bank.%s" % port, "port.%s" % port):
                        o = SIM_get_object("%s.%s" % (obj.name, port_obj_name))
                        devices.append((o, None, None, None))
            else:
                raise cli.CliError("Invalid port '%s'" % port)
        elif isinstance(port, int):
            devices.append((obj, None, None, port))
        else:
            raise cli.CliError(
                "Invalid type %s for port '%s'" % (type(port), port))

        return devices

    def ids_triggered_tracers(
            self, obj, portname, idx, func, offset, length, mode):

        return set(
            tracer.id for tracer in self.tracers
            if tracer.is_match(obj, portname, idx, func, offset, length, mode))

    def show(self, id, obj, memop, portname, idx, func, offset):
        (value, be) = get_memop_value(memop)
        if portname:
            port = portname if not idx else portname + '[' + str(idx) + ']'
            kind = "port"
        else:
            # access on device io_memory interface
            port = str(func)
            kind = "func"

        simics.SIM_log_message(
            obj, 0, 0, simics.Sim_Log_Trace, format_log_line(
                memop.ini_ptr, memop.physical_address,
                simics.SIM_mem_op_is_read(memop), value,
                simics.SIM_get_mem_op_size(memop), be) + " %s %s offset 0x%x" % (
                    kind, port, offset) + " (%s: %d)" % (
                        'breakpoint' if self.stop else 'tracing', id))

    def callback(self, _, obj, memop, portname, idx, func, offset):
        size = simics.SIM_get_mem_op_size(memop)
        mode = 'r' if simics.SIM_mem_op_is_read(memop) else 'w'
        tracer_ids = self.ids_triggered_tracers(
            obj, portname, idx, func, offset, size, mode)
        if self.stop:
            # If there are only script branches waiting on wait-for-io-break
            # (has_callbacks is True) then we don't stop. Otherwise, we stop.
            stop_tracer_ids = set()
            for tracer_id in tracer_ids:
                has_callbacks = (
                    simics.SIM_hap_occurred_always(
                        self.break_io_hap, None, tracer_id, [tracer_id])
                    != 0)
                if not has_callbacks:
                    stop_tracer_ids.add(tracer_id)
            if stop_tracer_ids:
                # Unlike execution breakpoints, io breakpoints are triggered
                # only once even if multiple breakpoints are installed.
                for tracer_id in stop_tracer_ids:
                    self.show(tracer_id, obj, memop, portname, idx, func, offset)
                simics.SIM_break_simulation(self.cmd)
        else:
            for tracer_id in tracer_ids:
                self.show(tracer_id, obj, memop, portname, idx, func, offset)

    # Function ensures that self.callback will be called (and only once)
    # whenever obj (or all objects if obj == None) is accessed.
    def monitor_object(self, obj):
        if obj in self.monitored_objects or None in self.monitored_objects:
            return  # the obj is already monitored
        if obj is None:
            # All objects are to be monitored. To achieve this we remove all hap
            # callbacks for all objects and install a new one which will track
            # all objects:
            # fisketur[chained-cond]
            assert None not in self.monitored_objects
            self.unmonitor_objects()
            self.monitored_objects[None] = SIM_hap_add_callback(
                'Internal_Device_Reg_Access', self.callback, None)
            assert len(self.monitored_objects) == 1
        else:
            # fisketur[chained-cond]
            assert None not in self.monitored_objects
            self.monitored_objects[obj] = SIM_hap_add_callback_obj(
                'Internal_Device_Reg_Access', obj, 0, self.callback, None)

    def unmonitor_objects(self):
        for hap_handler in self.monitored_objects.values():
            SIM_hap_delete_callback_id('Internal_Device_Reg_Access', hap_handler)
        self.monitored_objects.clear()

    def filter_out_deleted_objects(self):
        # Returns False if object has been deleted, otherwise True.
        def object_exists(obj):
            return hasattr(obj, 'name')

        self.tracers = list(
            tracer for tracer in self.tracers
            if tracer.obj is None or object_exists(tracer.obj))

    def get_port(self, portname, idx, func):
        if portname:
            return portname if idx is None else portname + '[' + str(idx) + ']'
        return func if func is not None else ''

    def do_listing(self):
        self.filter_out_deleted_objects()
        if not self.tracers:
            return

        just = ['r', 'l', 'l', 'r', 'r', 'l']
        head = ['Id', 'Device', 'Port', 'Offset', 'Length', 'Mode']
        data = [head]
        for tracer in sorted(self.tracers, key = lambda t: t.id):
            dev_name = tracer.obj.name if tracer.obj else '<all>'
            port = self.get_port(tracer.portname, tracer.idx, tracer.func)
            data.append((tracer.id, dev_name, port,
                         tracer.offset or '',
                         tracer.length or '',
                         tracer.mode or ''))
        print_columns(just, data)

    def get_new_tracer_id(self):
        tracer_id = self.next_id
        self.next_id += 1
        return tracer_id

    def track_all(self):
        tracer_id = self.get_new_tracer_id()
        self.monitor_object(None)
        self.tracers.append(
            IOTrackerItem(id = tracer_id, obj = None))
        return tracer_id

    def resolve_target(self, target):
        try:
            return SIM_get_object(target)
        except simics.SimExc_General:
            raise cli.CliError("No object '%s'" % target)

    def track_dev(self, dev, mode):
        return self.track_port(dev, None, mode)

    def track_port(self, dev, port, mode):
        return self.track_range(dev, port, None, None, mode)

    def track_range(self, dev, port, offset, length, mode):
        tracer_id = self.get_new_tracer_id()
        devices = self.extract_devices(dev, port)
        for (dev, portname, idx, func) in devices:
            self.monitor_object(dev)
            self.tracers.append(
                IOTrackerItem(
                    tracer_id, dev, portname, idx, func, offset, length, mode))
        return tracer_id

    def do_cmd(self, *args):
        (dev, port, offset, length, r, w, all_flag, listing) = args
        if listing:
            if any(args[:-1]):
                raise cli.CliError(
                    "'-list' cannot be used together with other arguments")
            self.do_listing()
        elif all_flag:
            if any(args[:-2]):
                raise cli.CliError(
                    "'-all' cannot be used together with other arguments")
            return self.track_all()
        elif dev:
            dev = self.resolve_target(dev)
            mode = ''
            if r: mode = mode + 'r'
            if w: mode = mode + 'w'
            if not r and not w: mode = 'rw'

            if offset is None and length:
                raise cli.CliError(
                    "'length' argument can only be given together with 'offset'")

            if not length:
                length = 1

            if port is None:
                if offset is not None:
                    raise cli.CliError(
                        "'offset' argument can only be given together with 'port'")
                else:
                    return self.track_dev(dev, mode)
            else:
                if offset is None:
                    return self.track_port(dev, port, mode)
                else:
                    return self.track_range(dev, port, offset, length, mode)
        else:
            raise cli.CliError("one of 'device', '-list', '-all' should be given")

    def remove_ids(self, tracer_ids):
        tracers_new = []
        objs_to_monitor = set()
        for tracer in self.tracers:
            if tracer.id not in tracer_ids:
                tracers_new.append(tracer)
                objs_to_monitor.add(tracer.obj)
        self.tracers = tracers_new

        # For simplicity we first stop monitoring all objects and then start
        # to monitor objects based on the updated self.tracers value.
        self.unmonitor_objects()
        if None in objs_to_monitor:
            self.monitor_object(None)
        else:
            for obj in objs_to_monitor:
                self.monitor_object(obj)

    def remove_all(self):
        self.unmonitor_objects()
        self.tracers = []

    def remove_obj(self, obj):
        tracer_ids = set()
        for tracer in self.tracers:
            if tracer.obj == obj:
                tracer_ids.add(tracer.id)

        self.remove_ids(tracer_ids)

    def do_uncmd(self, arg):
        (type, val, param) = arg
        if type == flag_t and param == '-list':
            self.do_listing()
        if type == flag_t and param == '-all':
            self.remove_all()
        if type == str_t:
            obj = self.resolve_target(val)
            if not self.is_io_device(obj):
                raise cli.CliError("Invalid device '%s'" % obj.name)
            self.remove_obj(obj)
        if type == int_t:
            self.remove_ids([val])

IOTracker(False, 'trace-io',
          short = 'trace device accesses',
          type = [],
          see_also = ['bp.bank.break', '<memory-space>.map',
                      'log-setup' ],
          legacy = "bp.bank.trace",
          legacy_version = SIM_VERSION_7,
          doc = ["""
The command enables tracing of accesses to a <arg>device</arg>.
With the <tt>-all</tt> flag, accesses to all devices are traced.

Accesses made to one or all device objects through their
<iface>io_memory</iface> interface are traced. The following information
is included in a trace: the initiator object, physical address of the access,
size of the access, value (read or written), port
name and port-relative address. The port name is <tt>None</tt> when
the non-port <iface>io_memory</iface> interface of the given
<arg>device</arg> is accessed.

The <arg>port</arg> argument, if given, restricts the monitoring in
different ways. If it is a string, only accesses to the
<iface>io_memory</iface> port interface by that name are considered.
If an integer, only accesses to the non-port <iface>io_memory</iface>
interface using that function number are considered.

When <arg>offset</arg> and <arg>length</arg> are given, tracing is
restricted to that address interval within the bank. The default
interval length is 1 if <arg>offset</arg> is given.

By default, both reads and writes are traced. With <tt>-r</tt> only
reads are traced, and with <tt>-w</tt> only writes are traced.

Devices providing multiple banks of registers usually expose them
as <iface>io_memory</iface> port interfaces using the bank names.
Some devices use the non-port <iface>io_memory</iface> interface
with a function number instead.

List all tracers and their ID numbers with the <tt>-list</tt> flag.""",

"""
Disables tracing of device accesses.

List all tracers and their ID numbers with the <tt>-list</tt> flag.
Specify the tracer to remove with the <arg>id</arg> argument.
Remove the given <arg>device</arg> from all tracers.
Or remove all devices from all tracers with the <tt>-all</tt> flag."""])

IOTracker(True, 'break-io',
          short = 'break on device accesses',
          type = ["Breakpoints"],
          see_also = ['bp.bank.trace', '<memory-space>.map'],
          legacy = "bp.bank.break",
          legacy_version = SIM_VERSION_7,
          doc = ["""
Enable breaking simulation on accesses to devices.
The simulation will be stopped when an access is made to one or all devices
objects through their <iface>io_memory</iface> interface.

The breakpoint is set either on a given <arg>device</arg>, or on all devices
with the <tt>-all</tt> flag.

Devices providing multiple banks of registers usually expose them
as <iface>io_memory</iface> port interfaces using the bank names.
Some devices use the non-port <iface>io_memory</iface> interface
with a function number instead.

If <arg>port</arg> is given, argument restricts the monitoring in different
ways. If it is a string, only accesses to the <iface>io_memory</iface> port
interface by that name are considered. If an integer, only accesses to the
non-port <iface>io_memory</iface> interface using that function number are
considered.

If <arg>offset</arg> and <arg>length</arg> are given, the breakpoint
is restricted to that address interval within the bank. The default
interval length is 1 if <arg>offset</arg> is given.

By default, both reads and writes trigger the breakpoint. With
<tt>-r</tt> only reads are considered, and with <tt>-w</tt> only
writes are considered.

If several breakpoints are set on the same address, Simics will only
break once.

List all breakpoints and their ID numbers with the <tt>-list</tt> flag.
""",

"""
Disable breaking simulation on device accesses.

List all breakpoints and their ID numbers with the <tt>-list</tt> flag.

Specify the breakpoint to remove with the <arg>id</arg> argument.
Remove the given <arg>device</arg> from all breakpoints.
Or remove all devices from all breakpoints with the <tt>-all</tt> flag.
"""])


def br_all_registers_expander(string, obj):
    regs= [obj.iface.int_register.get_name(reg)
          for reg in obj.iface.int_register.all_registers()]
    return cli.get_completions(string, regs)

def unbreak_register_cmd(cpu, action):
    (_, brk_id, option) = action
    if option == "-all":
        # Remove all breakpoints
        cpu.iface.register_breakpoint.remove_breakpoint(-1)
    else:
        brks = cpu.iface.register_breakpoint.get_breakpoints()
        for (id, reg, v, mask) in brks:
            if id == brk_id:
                ret = cpu.iface.register_breakpoint.remove_breakpoint(brk_id)
                assert ret
                return
        raise cli.CliError('No such breakpoint: %d' % (brk_id,))

def break_register_list_cmd(cpu):
    brks = cpu.iface.register_breakpoint.get_breakpoints()
    if len(brks) == 0:
        print("No register breakpoints defined")
        return

    print("Breakpoints:\nID" + "\tregister".rjust(8)
          + "\tvalue".rjust(8) + "\tmask".rjust(8))
    for i in range(len(brks)):
        (id, reg, v, mask) = brks[i]
        if v is None:
            print("%d" % id + "\t%s" % reg.rjust(8)
                  + ("\t%s" % "Upon Change").rjust(8) + ("\t0x%x" % mask).rjust(8))
        else:
            print("%d" % id + "\t%s" % reg.rjust(8)
                  + ("\t0x%x" % v).rjust(8) + ("\t0x%x" % mask).rjust(8))

def break_register_cmd(cpu, register, brk_value, mask):
    bid = cpu.iface.register_breakpoint.add_breakpoint(
        register, 0 if brk_value is None else brk_value,
        mask, brk_value is None)
    val = " with value %d" % brk_value if brk_value else ""
    msk = " with mask %d" % mask if mask != 0xffffffffffffffff else ""
    text_repr = "Breakpoint %d set on write to register %s%s%s." % (
        bid, register, val, msk)
    return command_return(message = text_repr, value = bid)

new_command("break-register-list", break_register_list_cmd,
            iface = "register_breakpoint",
            type = ["Breakpoints"],
            short = "list current breakpoints",
            see_also = ["<register_breakpoint>.break-register",
                        "<register_breakpoint>.unbreak-register"],
            doc = """List the active register breakpoints.""")

new_command("break-register", break_register_cmd,
            args = [arg(str_t, "register",
                        expander=br_all_registers_expander),
                    arg(uint64_t, "value", "?", None),
                    arg(uint64_t, "mask", "?", 0xffffffffffffffff)],
            iface = "register_breakpoint",
            type = ["Breakpoints", "Registers"],
            short = "add a register breakpoint",
            see_also = ["<register_breakpoint>.break-register-list",
                        "<register_breakpoint>.unbreak-register",
                        "<processor_internal>.bp-break-control-register"],
            doc = """Set a breakpoint on the <arg>register</arg>. If <arg>value</arg>
                     is given, simulation will stop everytime when the
                     register content becomes this <arg>value</arg>,
                     otherwise simulation will stop when the register
                     value changes. When the <arg>mask</arg> is given,
                     it is applied to the register value. This can be
                     used when only certain bits are of interest.
                     Note that, using register breakpoints will have a
                     large performance impact. This command breaks
                     execution on most processor register changes,
                     both explicit changes by the software, or
                     implicit changes by the model itself. For
                     explicit control-register changes, the
                     bp.control_register.break command can used instead, which
                     has lower performance overhead.""")

new_command("unbreak-register", unbreak_register_cmd,
            args = [arg((int_t, flag_t), ("id", "-all"))],
            iface = "register_breakpoint",
            type = ["Breakpoints", "Registers"],
            short = "remove a register breakpoint",
            see_also = ["<register_breakpoint>.break-register",
                        "<register_breakpoint>.break-register-list",
                        "bp.delete"],
            doc = """Remove either a breakpoint with the given <arg>id</arg>, or all
                     breakpoints with <tt>-all</tt>.""")

#
# -------------------- break-on-log-message --------------------
#

log_types = {
    'info':      simics.Sim_Log_Info,
    'error':     simics.Sim_Log_Error,
    'critical':  simics.Sim_Log_Critical,
    'spec-viol': simics.Sim_Log_Spec_Violation,
    'unimpl':    simics.Sim_Log_Unimplemented,
}
#
# ------------ wait-for-log ------------
#

def delete_log_message_hap(hid):
    SIM_hap_delete_callback_id("Core_Log_Message_Filtered", hid)

class wait_log_data:
    def __init__(self, wait_id, is_regex, substring, log_type):
        self.wait_id = wait_id
        self.is_regex = is_regex
        self.substring = substring
        self.log_type = log_type
        self.hap_id_list = []
        # return values
        self.obj = None
        self.message = None
        self.cycle_obj = None
        self.cycle = -1
        self.time = -1
        self.log_group = None
        self.log_level = 0

def wait_log_hap_callback(wdata, obj, log_type, message, log_level, log_group):
    #(hap, id, is_regex, substring, filt_type, _) = udata
    if not wdata.hap_id_list:
        # Removal of hap callbacks is already pending (SIM_run_alone)
        return
    match = (re.search(wdata.substring, message) if wdata.is_regex
             else wdata.substring in message)
    if match and (wdata.log_type is None or wdata.log_type == log_type):
        for hap_id in wdata.hap_id_list:
            simics.SIM_run_alone(delete_log_message_hap, hap_id)
        wdata.hap_id_list = []  # Mark as pending removal
        wdata.message = message
        wdata.obj = obj
        wdata.log_group = log_group
        wdata.log_level = log_level
        wdata.log_type = log_type
        cobj = get_cycle_object_for_timestamps()
        if cobj:
            wdata.cycle_obj = cobj
            wdata.cycle = cobj.iface.cycle.get_cycle_count()
            wdata.time = cobj.iface.cycle.get_time()
        sb_signal_waiting(wdata.wait_id)

def wait_for_log(obj, is_regex, substring, log_type):
    if not check_script_branch_command("wait-for-log"):
        return
    wdata = wait_log_data(cli.sb_get_wait_id(), is_regex, substring, log_type)
    if obj:
        hap_objects = [
            SIM_get_object("%s.%s" % (obj.name, portname))
            for (portname, cls)
            in simics.VT_get_port_classes(obj.classname).items()
            if simics.SIM_c_get_class_interface(cls, 'log_object')]
        hap_objects.append(obj)
        wdata.hap_id_list = [
            SIM_hap_add_callback_obj("Core_Log_Message_Filtered", o, 0,
                                     wait_log_hap_callback, wdata)
            for o in hap_objects]
    else:
        wdata.hap_id_list = [SIM_hap_add_callback(
            "Core_Log_Message_Filtered", wait_log_hap_callback, wdata)]
    cmd_prefix = ("%s." % obj.name) if obj else ""
    sb_wait('%swait-for-log' % cmd_prefix, wdata.wait_id, wait_data = substring)
    return command_return(value=[
        wdata.cycle_obj, wdata.time, wdata.cycle,
        wdata.log_level, wdata.log_type, wdata.log_group,
        wdata.obj, wdata.message])

#
# ------------ time waiting commands ------------
#

def wait_for_time(obj, id):
    # wake up the waiting script-branch
    sb_signal_waiting(id)

wait_for_time_ev = simics.SIM_register_event(
    "wait-for-time", "sim", simics.Sim_EC_Notsaved, wait_for_time,
    None, None, None, None)

history_time_bps = []

# This function is only kept to keep sb_wait_for_cycle working.
def wait_for_cycle_command(obj, cycle, relative):
    if not check_script_branch_command("wait-for-cycle"):
        return
    now = simics.SIM_cycle_count(obj)
    if relative:
        abs_cycle = cycle + now
    else:
        abs_cycle = cycle
        cycle -= now
    if cycle == 0:
        return
    elif abs_cycle < now:
        raise cli.CliError("Cannot wait for cycle in the past")
    else:
        id = cli.sb_get_wait_id()
        try:
            simics.SIM_event_post_cycle(obj, wait_for_time_ev, obj, cycle, id)
        except (simics.SimExc_General, OverflowError) as ex:
            raise cli.CliError(str(ex))
    try:
        sb_wait('%s.wait-for-cycle' % obj.name, id, wait_data = "%d" % cycle)
    finally:
        remove_sb_time_breakpoint(id)

def wait_for_time_command(obj, seconds, relative):
    if not check_script_branch_command("wait-for-time"):
        return
    now = simics.SIM_time(obj)
    if relative:
        abs_time = seconds + now
    else:
        abs_time = seconds
        seconds -= now
    if seconds == 0:
        return
    elif abs_time < now:
        raise cli.CliError("Cannot wait for time in the past")
    else:
        id = cli.sb_get_wait_id()
        try:
            simics.SIM_event_post_time(obj, wait_for_time_ev, obj, seconds, id)
        except simics.SimExc_General as ex:
            raise cli.CliError(str(ex))
    try:
        sb_wait('%s.wait-for-time' % obj.name, id, wait_data = "%f" % seconds)
    finally:
        remove_sb_time_breakpoint(id)

def repost_time_bp(args):
    (kind, obj, abs_time, id) = args
    if kind == 'time':
        now = simics.SIM_time(obj)
    elif kind == 'step':
        now = simics.SIM_step_count(obj)
    elif kind == 'cycle':
        now = simics.SIM_cycle_count(obj)
    else:
        assert(0)
    if abs_time < now:
        return False
    if abs_time == now:
        wait_for_time(obj, id)
    else:
        if kind == 'time':
            simics.SIM_event_post_time(obj, wait_for_time_ev, obj,
                                       abs_time - now, id)
        elif kind == 'step':
            simics.SIM_event_post_step(obj, wait_for_time_ev, obj,
                                       abs_time - now, id)
        elif kind == 'cycle':
            simics.SIM_event_post_cycle(obj, wait_for_time_ev, obj,
                                        abs_time - now, id)
    return True

def remove_sb_time_breakpoint(id):
    global history_time_bps
    history_time_bps = [x for x in history_time_bps if not x[3] == id]

#
# ------------ wait-for-step ------------
#

def wait_for_step(obj, step, relative):
    if not check_script_branch_command("wait-for-step"):
        return
    now = simics.SIM_step_count(obj)
    if relative:
        abs_step = step + now
    else:
        abs_step = step
        step -= now
    if step == 0:
        return
    elif abs_step < now:
        raise cli.CliError("Cannot wait for step in the past")
    else:
        id = cli.sb_get_wait_id()
        try:
            simics.SIM_event_post_step(obj, wait_for_time_ev, obj, step, id)
        except (simics.SimExc_General, OverflowError) as ex:
            raise cli.CliError(str(ex))
    try:
        sb_wait('%s.wait-for-step' % obj.name, id, wait_data = "%d" % step)
    finally:
        remove_sb_time_breakpoint(id)

#
# ------------ wait-for-global-time ------------
#

def wait_for_global_time_command(seconds, relative):
    if not check_script_branch_command("wait-for-global-time"):
        return
    obj = current_cycle_obj()
    id = cli.sb_get_wait_id()
    if relative:
        seconds += simics.SIM_time(obj)
    try:
        simics.VT_domain_event_at(simics.CORE_process_top_domain(),
                                  wait_for_time_ev, obj, obj, seconds, id)
    except simics.SimExc_General as ex:
        # We want to give error messages in terms that are in scope for
        # this command, and not in terms of VT APIs. This requires fragile
        # and horrible inspection of the message in the frontend exception.
        msg = str(ex)
        if msg.endswith("can not be represented in simulation time"):
            msg = "The requested time is too large"
        elif msg == "Domain event posted too early":
            msg = "Requested time not far enough into the future"
        raise cli.CliError(msg)
    sb_wait('wait-for-global-time', id, wait_data = "%f" % seconds)

new_command("wait-for-global-time", wait_for_global_time_command,
            [arg(float_t, 'seconds'), arg(flag_t, '-relative')],
            type  = ["CLI"],
            short = "wait until reaching a specified global time",
            see_also = ["script-branch",
                        "wait-for-global-sync",
                        "<cycle>.bp-wait-for-cycle",
                        "<cycle>.bp-wait-for-time",
                        "<step>.bp-wait-for-step"],
            doc = """
Postpones execution of a script branch until all cells in the simulation
reaches the specified global time, <arg>seconds</arg>, from the start of the
simulation. If <tt>-relative</tt> is given, the branch is suspended for a
specified duration instead. The <cmd>wait-for-global-time</cmd> and
<cmd>wait-for-global-sync</cmd> commands are the only ways to synchronize
the cells in the simulation from script branches.

The requested time needs to be far enough into the future to allow
deterministic synchronization. Consider using <cmd>wait-for-global-sync</cmd>
if you want to synchronize all cells as soon as possible.
""")

#
# ------------ wait-for-global-sync ------------
#

def wait_for_sync(obj, id):
    # sync as soon as possible
    simics.VT_domain_event_soon(
        simics.CORE_process_top_domain(), wait_for_time_ev, obj, id)

wait_for_sync_ev = simics.SIM_register_event(
    "wait-for-sync", "sim", simics.Sim_EC_Notsaved, wait_for_sync,
    None, None, None, None)

def wait_for_global_sync_command():
    if not check_script_branch_command("wait-for-global-sync"):
        return
    obj = current_cycle_obj()
    id = cli.sb_get_wait_id()
    simics.SIM_event_post_cycle(obj, wait_for_sync_ev, obj, 1, id)
    sb_wait('wait-for-global-sync', id)

new_command("wait-for-global-sync", wait_for_global_sync_command,
            [],
            type  = ["CLI"],
            short = "wait until the global time in all cells is synchronized",
            see_also = ["script-branch",
                        "wait-for-global-time",
                        "<cycle>.bp-wait-for-cycle",
                        "<step>.bp-wait-for-step",
                        "<cycle>.bp-wait-for-time"],
            doc = """
Postpones execution of a script branch until the first point in time when all
cells in the system have their global time synchronized.
<cmd>wait-for-global-sync</cmd> and <cmd>wait-for-global-time</cmd> commands
are the only ways to synchronize the cells in the simulation from script
branches.
""")

# This function is only kept to keep sb_wait_for_breakpoint working.
def wait_for_breakpoint_command(id):
    if not check_script_branch_command("wait-for-breakpoint"):
        return # return value should be ignored
    breakpoint = [x for x in conf.sim.breakpoints if x[0] == id]
    if not breakpoint:
        raise cli.CliError("No breakpoint with id %d" % id)
    obj = breakpoint[0][11]
    (_, _, mop) = sb_wait_for_hap_internal(
        'wait-for-breakpoint', "Core_Breakpoint_Memop", obj, id,
        wait_data = "%d" % id)
    return mop[4] # mop is on the form [va, pa, size, type, initiator]

def get_catchable_register(obj, reg):
    id = obj.iface.int_register.get_number(reg)
    if id < 0:
        raise cli.CliError("No '%s' register in %s (%s)" % (reg, obj.name,
                                                        obj.classname))
    if not obj.iface.int_register.register_info(
            id, simics.Sim_RegInfo_Catchable):
        raise cli.CliError("The %s register is not catchable" % reg)
    return id

# This function is only kept to keep sb_wait_for_register_read working.
def wait_for_register_read_command(obj, reg):
    if not check_script_branch_command("wait-for-register-read"):
        return
    id = get_catchable_register(obj, reg)
    return sb_wait_for_hap_internal(
        '%s.wait-for-register-read' % obj.name, "Core_Control_Register_Read",
        obj, id, wait_data = reg)

# This function is only kept to keep sb_wait_for_register_write working.
def wait_for_register_write_command(obj, reg):
    if not check_script_branch_command("wait-for-register-write"):
        return
    id = get_catchable_register(obj, reg)
    return sb_wait_for_hap_internal(
        '%s.wait-for-register-write' % obj.name, "Core_Control_Register_Write",
        obj, id, wait_data = reg)

# ------------ wait-for-simulation-started ------------
#

def wait_for_simulation_started_command():
    check_script_branch_command("wait-for-simulation-started")
    if simics.SIM_simics_is_running():
        # return or error?
        return
    return sb_wait_for_hap_internal(
        'wait-for-simulation-started', "Core_Continuation", None, 0)

new_command("wait-for-simulation-started", wait_for_simulation_started_command,
            args = [],
            type  = ["CLI"],
            short = "wait for simulation to start",
            see_also = ["script-branch", "wait-for-simulation-stopped"],
            doc = """
Suspends execution of a script branch until the simulation starts running. The
command returns at once if the simulation is already running.
""")

#
# ------------ wait-for-simulation-stopped ------------
#

def wait_for_simulation_stopped_command():
    check_script_branch_command("wait-for-simulation-stopped")
    if not simics.SIM_simics_is_running():
        # return or error?
        return
    return sb_wait_for_hap_internal(
        'wait-for-simulation-stopped', "Core_Simulation_Stopped", None, 0)

new_command("wait-for-simulation-stopped", wait_for_simulation_stopped_command,
            args = [],
            type  = ["CLI"],
            short = "wait for simulation to stop",
            see_also = ["script-branch", "wait-for-simulation-started"],
            doc = """
Suspends execution of a script branch until the simulation stops running. The
command returns at once if the simulation is not running.
""")
