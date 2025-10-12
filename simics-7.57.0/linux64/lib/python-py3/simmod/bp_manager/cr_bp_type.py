# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import sys
import cli
import conf
import simics

common_doc = """
The <arg>name</arg> or <arg>number</arg> parameter specifies which
control register is considered. The available control registers depend
on the simulated target. If the <tt>-all</tt> flag is specified, all
registers are considered.

If <tt>-r</tt> is specified, only register read accesses are
considered. If <tt>-w</tt> is specified, only register write accesses
are considered. The default is to consider both reads and writes.

If <tt>-only-changes</tt> is specified, only write accesses that
change the register value are considered. In this case, if
<arg>mask</arg> is specified, only changes affecting this mask of the
register are considered.

If <arg>value</arg> is specified, only write accesses that results in
the register having this value are considered, or read accesses when
the register has this value. If <arg>mask</arg> is specified, only
this mask of the register and given value are considered.

If no processor object is specified, the currently selected processor is used.
"""

break_doc = """
Enables breaking simulation on control register updates.
""" + common_doc

run_until_doc = """
Run the simulation until the specified control register update occurs.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until the specified
control register update occurs.
""" + common_doc

trace_doc = """
Enables tracing of control register updates.  When this
is enabled, every time the specified control register is updated
during simulation a message is printed. The message will name the
register being updated, and the new value. The new value will be
printed even if it is identical to the previous value.
""" + common_doc

class Breakpoint:
    __slots__ = ('cpu', 'haps', 'regno', 'regname',
                 'track_all', 'access', 'value', 'mask',
                 'only_changes', 'once')
    def __init__(self, cpu, haps, regno, regname, track_all, access,
                 value, mask, only_changes, once):
        self.cpu = cpu
        self.haps = haps
        self.regno = regno
        self.regname = regname
        self.track_all = track_all
        self.access = access
        self.value = value
        self.mask = mask
        self.only_changes = only_changes
        self.once = once

class CRBreakpoints:
    TYPE_DESC = "control register access breakpoints"
    cls = simics.confclass("bp-manager.cr", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.last_access = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "control-register", self.obj,
            [[["str_t", "int_t", "flag_t"], ["name", "number", "-all"],
              '1', None, None, "", [True, None, None]],
             ["uint_t", "value", '?', -1, None, "", None],
             ["uint_t", "mask", '?', -1, None, "", None],
             ["flag_t", "-r", '1', None, None, "", None],
             ["flag_t", "-w", '1', None, None, "", None],
             ["flag_t", "-only-changes", '1', None, None, "", None]],
            None, 'processor_internal', [
                "set break on control register access", break_doc,
                "run until specified control register access", run_until_doc,
                "wait for specified control register access", wait_for_doc,
                "enable tracing of control register accesses", trace_doc],
            False, False, False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _extra_desc(self, bp):
        extra = " (changing writes only)" if bp.only_changes else ""
        mask = f" mask=0x{bp.mask:x}" if bp.mask != -1 else ""
        value = f" value=0x{bp.value:x}" if bp.value != -1 else ""
        return f"{value}{mask}{extra}"

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        regs = "any register" if bp.track_all else bp.regname
        return (f"{bp.cpu.name} break on {bp.access} of {regs}"
                + self._extra_desc(bp))

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.cpu.name,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, cpu, arg, value, mask,
                   is_read, is_write, only_changes, once):
        bp_id = self.next_id
        self.next_id += 1

        if cpu is None:
            cpu = cli.current_cpu_obj_null()
        if cpu is None:
            return 0

        # Default is both read and write
        if not is_read and not is_write:
            is_read = is_write = True

        track_all = False
        assert arg[0] in {"int_t", "str_t", "flag_t"}
        if arg[0] == "int_t":
            regno = arg[1]
            regname = cpu.iface.int_register.get_name(arg[1])
        elif arg[0] == "str_t":
            regname = arg[1]
            regno = cpu.iface.int_register.get_number(arg[1])
        else:
            track_all = True
            regno = -1
            regname = ""

        if not track_all and regno < 0:
            return 0

        assert is_read or is_write

        if not is_write:
            if only_changes or (mask != -1 and value == -1):
                print("Mask without value and -only-changes are only applicable"
                      " for breakpoints on write access", file=sys.stderr)
                return 0

        haps = {}
        if is_read:
            hap = "Core_Control_Register_Read"
            cb = self._bp_read_cb
            if track_all:
                haps[hap] = simics.SIM_hap_add_callback_obj(
                    hap, cpu, 0, cb, bp_id)
            else:
                haps[hap] = simics.SIM_hap_add_callback_obj_index(
                    hap, cpu, 0, cb, bp_id, regno)
        if is_write:
            hap = "Core_Control_Register_Write"
            cb = self._bp_write_cb
            if track_all:
                haps[hap] = simics.SIM_hap_add_callback_obj(
                    hap, cpu, 0, cb, bp_id)
            else:
                haps[hap] = simics.SIM_hap_add_callback_obj_index(
                    hap, cpu, 0, cb, bp_id, regno)
        if is_read and is_write:
            access = "R/W"
        elif is_read:
            access = "read"
        else:
            access = "write"

        # Store list for mutability
        self.bp_data[bp_id] = Breakpoint(cpu, haps, regno, regname, track_all,
                                         access, value, mask,
                                         only_changes, once)
        return bp_id

    def _bp_cb(self, bp_id):
        bp = self.bp_data[bp_id]
        cli.set_current_frontend_object(bp.cpu, True)
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, bp.cpu,
                                              self.trace_msg(bp_id))
        return 1

    def _bp_read_cb(self, bp_id, cpu, regno):
        regname = cpu.iface.int_register.get_name(regno)
        self.last_access[bp_id] = ("read", regno, regname, None)
        bp = self.bp_data[bp_id]
        if bp.value != -1:
            # Only break if value matches
            cmp_val = bp.value
            cur_val = cpu.iface.int_register.read(regno)
            if bp.mask != -1:
                cmp_val &= bp.mask
                cur_val &= bp.mask

            if cur_val == cmp_val:
                self._bp_cb(bp_id)
        else:
            self._bp_cb(bp_id)

    def _bp_write_cb(self, bp_id, cpu, regno, value):
        regname = cpu.iface.int_register.get_name(regno)

        last_access = self.last_access.get(bp_id)
        self.last_access[bp_id] = ("write", regno, regname, value)
        bp = self.bp_data[bp_id]

        if bp.value != -1:
            # Only break if new value matches
            cmp_val = bp.value
            new_val = value
            if bp.mask != -1:
                cmp_val &= bp.mask
                new_val &= bp.mask

            if new_val == cmp_val:
                self._bp_cb(bp_id)
        elif bp.only_changes:
            # Only break if changes affect specified mask
            if last_access:
                (_, _, _, cmp_val) = last_access
            else:
                cmp_val = cpu.iface.int_register.read(regno)
            new_val = value

            if bp.mask != -1:
                cmp_val &= bp.mask
                new_val &= bp.mask

            if new_val != cmp_val:
                self._bp_cb(bp_id)
        else:
            self._bp_cb(bp_id)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (cpu, arg, value, mask, is_read, is_write, only_changes, once) = args
        return self._create_bp(cpu, arg, value, mask,
                               is_read, is_write, only_changes, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        for (hap, hap_id) in bp.haps.items():
            simics.SIM_hap_delete_callback_obj_id(hap, bp.cpu, hap_id)
        del self.bp_data[bp_id]
        if bp_id in self.last_access:
            del self.last_access[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        def unsigned_value(v):
            return v & 0xffffffffffffffff

        # This can be called before any access, e.g. from test-trigger
        if bp_id in self.last_access:
            (access, _, regname, value) = self.last_access[bp_id]
            if access == "write":
                return f"{regname} <- 0x{unsigned_value(value):x}"
            else:
                return f"{access} of {regname}"
        else:
            return ""

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        regs = "any register" if bp.track_all else bp.regname
        return (f"{bp.cpu.name} will break on {bp.access} of {regs}"
                + self._extra_desc(bp))

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        regs = "any register" if bp.track_all else bp.regname
        return (f"{bp.cpu.name} waiting on {bp.access} of {regs}"
                + self._extra_desc(bp))

    @cls.iface.breakpoint_type_provider.values
    def values(self, arg, prev_args):
        cpu = prev_args[1]
        try:
            if not cpu:
                cpu = cli.current_cpu_obj_null()
            if (cpu and isinstance(cpu, simics.conf_object_t)
                and hasattr(cpu.iface, 'int_register')):
                iface = cpu.iface.int_register
                regs = [iface.get_name(r) for r in iface.all_registers()
                        if iface.register_info(
                                r, simics.Sim_RegInfo_Catchable)]
            else:
                regs = []
        except simics.SimExc_Lookup:
            regs = []
        return regs

def register_cr_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "control_register",
                             CRBreakpoints.cls.classname,
                             CRBreakpoints.TYPE_DESC)
