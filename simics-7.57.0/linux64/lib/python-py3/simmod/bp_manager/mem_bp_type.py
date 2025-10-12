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

break_doc = """
Adds a breakpoint (read, write, or execute) on
<arg>address</arg> for an object implementing the
<iface>breakpoint</iface> interface. For physical addresses, this is
typically a <class>memory-space</class> object, and for virtual
addresses it is a <class>context</class> object.

Accesses intersecting the given range will trigger the break. By
default the break will only trigger for instruction execution,
but any subset of read, write, and execute accesses can be set to
trigger using combinations of <tt>-r</tt>, <tt>-w</tt>, and
<tt>-x</tt>.

<arg>length</arg> is the interval length in bytes (default is 1).

When an execution breakpoint is triggered, Simics will stop the
simulation before the instructions is executed, while instructions
triggering read or write breakpoints will complete before the
simulation is stopped.

Several breakpoints can be set on the same address and Simics will break on
them in turn. If hap handlers (callback functions) are connected to the
breakpoints they will also be executed in turn. Hap handlers are called before
the access is performed, allowing the user to read a memory value that may be
overwritten by the access. See the Simics Reference Manual for a description
of hap handlers.

Each breakpoint is associated with an id (printed when the breakpoint
is set or by the <cmd iface="bp_manager">list</cmd> command)
which is used for further references to the breakpoint.

By default, the command sets a breakpoint on memory connected to the
current frontend processor (see <cmd>pselect</cmd>). Default is to
break on virtual address accesses (in the current context). To break
on physical accesses, prefix the <arg>address</arg> with <tt>p:</tt>.

Use <arg>prefix</arg> to only break on instructions with this
prefix. For example, a prefix "add" will cause
the breakpoint to only stop if the instruction begins with "add". The
text to compare the prefix with for an instruction is the one which
the instruction is disassembled to. The comparison is case
insensitive.

Use <arg>substr</arg> to only break on instructions with a certain syntax
substring. For example, specifying a substring "r31" will cause the breakpoint
to stop only if the instruction contains the substring "r31". The match is case
insensitive.

Use <arg>pattern</arg> to only break on
instructions with a certain bit-pattern. First the <arg>mask</arg> will be
applied to the instruction and then the result will be compared with
the <arg>pattern</arg>. For example, a pattern "0x0100" and mask "0x0101"
will cause the breakpoint to stop only on instructions whose first byte
has the lowest bit set and the second not.

Note that pattern and mask are supplied as strings with string byte
order (low address first).

Breakpoints can be removed using <cmd iface="bp_manager">delete</cmd>.
"""

run_until_doc = """
Run the simulation until the specified break condition is true.

The break condition is specified as (read, write, or execute) on
<arg>address</arg> for an object implementing the
<iface>breakpoint</iface> interface. For physical addresses, this is
typically a <class>memory-space</class> object, and for virtual
addresses it is a <class>context</class> object.

Accesses intersecting the given range will trigger the break. By
default the break will only trigger for instruction execution,
but any subset of read, write, and execute accesses can be set to
trigger using combinations of <tt>-r</tt>, <tt>-w</tt>, and
<tt>-x</tt>.

<arg>length</arg> is the interval length in bytes (default is 1).

By default, the break condition is set on memory connected to the
current frontend processor (see <cmd>pselect</cmd>). Default is to
break on virtual address accesses (in the current context). To break
on physical accesses, prefix the <arg>address</arg> with <tt>p:</tt>.

Use <arg>prefix</arg> to define the break condition on instructions
with this prefix. For example, a prefix "add" will run until an
instruction that begins with "add". The text to compare the prefix
with for an instruction is the one which the instruction is
disassembled to. The comparison is case insensitive.

Use <arg>substr</arg> to run until instructions with a certain syntax
substring. For example, specifying a substring "r31" will run until an
instruction containing the substring "r31". The match is case
insensitive.

Use <arg>pattern</arg> to run until an instruction with a certain
bit-pattern. First the <arg>mask</arg> will be applied to the
instruction and then the result will be compared with the
<arg>pattern</arg>. For example, a pattern "0x0100" and mask "0x0101"
will cause the simulation to stop only on an instruction whose first
byte has the lowest bit set and the second not.

Note that pattern and mask are supplied as strings with string byte
order (low address first).
"""

wait_for_doc = """
Postpones execution of a script branch the specified break condition is true.

The break condition is specified as (read, write, or execute) on
<arg>address</arg> for an object implementing the
<iface>breakpoint</iface> interface. For physical addresses, this is
typically a <class>memory-space</class> object, and for virtual
addresses it is a <class>context</class> object.

Accesses intersecting the given range will trigger the break. By
default the break will only trigger for instruction execution,
but any subset of read, write, and execute accesses can be set to
trigger using combinations of <tt>-r</tt>, <tt>-w</tt>, and
<tt>-x</tt>.

<arg>length</arg> is the interval length in bytes (default is 1).

By default, the break condition is set on memory connected to the
current frontend processor (see <cmd>pselect</cmd>). Default is to
break on virtual address accesses (in the current context). To break
on physical accesses, prefix the <arg>address</arg> with <tt>p:</tt>.

Use <arg>prefix</arg> to define the break condition on instructions
with this prefix. For example, a prefix "add" will wait for an
instruction that begins with "add". The text to compare the prefix
with for an instruction is the one which the instruction is
disassembled to. The comparison is case insensitive.

Use <arg>substr</arg> to wait for instructions with a certain syntax
substring. For example, specifying a substring "r31" will wait for an
instruction containing the substring "r31". The match is case
insensitive.

Use <arg>pattern</arg> to wait for an instruction with a certain
bit-pattern. First the <arg>mask</arg> will be applied to the
instruction and then the result will be compared with the
<arg>pattern</arg>. For example, a pattern "0x0100" and mask "0x0101"
will wait for an instruction whose first
byte has the lowest bit set and the second not.

Note that pattern and mask are supplied as strings with string byte
order (low address first).

The command returns the initiator object of the memory transaction
that resulted in the breakpoint.
"""

trace_doc = """
Enables tracing of memory accesses.

The accesses to trace are specified as (read, write, or execute) on
<arg>address</arg> for an object implementing the
<iface>breakpoint</iface> interface. For physical addresses, this is
typically a <class>memory-space</class> object, and for virtual
addresses it is a <class>context</class> object.

Accesses intersecting the given range will be traced. By default only
instruction execution is traced, but any subset of read, write, and
execute accesses can traced using combinations of <tt>-r</tt>,
<tt>-w</tt>, and <tt>-x</tt>.

<arg>length</arg> is the interval length in bytes (default is 1).

By default, tracing is done on memory connected to the
current frontend processor (see <cmd>pselect</cmd>). Default is to
trace virtual address accesses (in the current context). To trace
physical accesses, prefix the <arg>address</arg> with <tt>p:</tt>.

Use <arg>prefix</arg> to trace instructions
with this prefix. For example, a prefix "add" will trace
instructions that begins with "add". The text to compare the prefix
with for an instruction is the one which the instruction is
disassembled to. The comparison is case insensitive.

Use <arg>substr</arg> to trace instructions with a certain syntax
substring. For example, specifying a substring "r31" will trace
instructions containing the substring "r31". The match is case
insensitive.

Use <arg>pattern</arg> to trace instructions with a certain
bit-pattern. First the <arg>mask</arg> will be applied to the
instruction and then the result will be compared with the
<arg>pattern</arg>. For example, a pattern "0x0100" and mask "0x0101"
will trace instructions whose first
byte has the lowest bit set and the second not.

Note that pattern and mask are supplied as strings with string byte
order (low address first).
"""

class LastMemopInfo:
    # NB: the generic_transaction_t argument is only valid in the hap callback.
    # So the LastMemopInfo stores extracted data, not generic_transaction_t ref.
    __slots__ = ('physical_address', 'logical_address', 'is_read',
                 'value', 'is_from_cpu', 'is_instruction', 'size')
    def __init__(self, memop):
        self.physical_address = memop.physical_address
        self.logical_address = memop.logical_address
        self.is_instruction = simics.SIM_mem_op_is_instruction(memop)
        self.is_read = simics.SIM_mem_op_is_read(memop)
        self.size = memop.size
        self.is_from_cpu = simics.SIM_mem_op_is_from_cpu(memop)
        if self.size <= 8 and not (self.is_instruction or self.is_read):
            self.value = simics.SIM_get_mem_op_value_le(memop)
        else:
            self.value = None

class Breakpoint:
    __slots__ = ('obj', 'hap_id', 'change_hap_id', 'address', 'length',
                 'access', 'mode', 'break_type', 'once', 'internal',
                 'last_memop', 'last_ini')
    def __init__(self, obj, hap_id, change_hap_id, address, length,
                 access, mode, break_type, once, internal):
        self.obj = obj
        self.hap_id = hap_id
        self.change_hap_id = change_hap_id
        self.address = address
        self.length = length
        self.access = access
        self.mode = mode
        self.break_type = break_type
        self.once = once
        self.internal = internal
        self.last_memop = None
        self.last_ini = None

class MemBreakpoints:
    # Offsets in sim->breakpoints data
    FLAGS_IDX = 6
    HITS_IDX = 3
    ACTIVATE_IDX = 4
    PREFIX_IDX = 7
    SUBSTR_IDX = 8
    PATTERN_IDX = 9
    MASK_IDX = 10
    # Offsets in addr_t
    SPACE_IDX = 0
    ADDRESS_IDX = 1
    ACTIVE_IDX = 5

    TYPE_DESC = "memory access breakpoints"
    cls = simics.confclass("bp-manager.memory", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "memory",
            self.obj,
            [["addr_t", "address", '1', None, None, "", None],
             ["uint64_t", "length", "?", 1, None, "", None],
             ["flag_t", "-r", '1', None, None, "", None],
             ["flag_t", "-w", '1', None, None, "", None],
             ["flag_t", "-x", '1', None, None, "", None],
             ["str_t", "prefix", "?", "", None, "", None],
             ["str_t", "substr", "?", "", None, "", None],
             ["str_t", "pattern", "?", "", None, "", None],
             ["str_t", "mask", "?", "", None, "", None]],
            None, "breakpoint", [
                "set break on memory access", break_doc,
                "run until specified memory access", run_until_doc,
                "wait for specified memory access", wait_for_doc,
                "enable tracing of memory accesses", trace_doc], False, False,
            False)

    def _sim_breakpoint_by_id(self, bp_id):
        '''Returns breakpoint data for breakpoint 'bp_id'.
        Raises CliError if not found.'''
        for x in simics.SIM_get_attribute(conf.sim, "breakpoints"):
            if x[0] == bp_id:
                return x
        raise cli.CliError(f'No such breakpoint: {bp_id}')

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        addr = hex(bp.address[self.ADDRESS_IDX])
        disp_len = cli.number_str(bp.length)
        acc = self._access_str(bp.access)
        return (f"{bp.obj.name} break matching"
                f" (addr={addr}, len={disp_len}, access={acc})")

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        (_, type, access, hits, activate_at, active, flags, prefix, substr,
         strpattern, strmask, obj, handles) = self._sim_breakpoint_by_id(bp_id)
        ignore_count = 0
        if activate_at > 0 and activate_at > hits:
            ignore_count = activate_at - hits - 1
        props = {"enabled": bool(active),
                 "temporary": flags == simics.Sim_Breakpoint_Temporary,
                 "ignore count": ignore_count,
                 "hit count": hits,
                 "planted": True,
                 "object": obj.name,
                 "description": self._describe_bp(bp_id)}
        index = 0

        if prefix:
            props['prefix'] = prefix

        if substr:
            props['substring'] = substr

        if strpattern:
            props['pattern'] = '0x%s, Mask : 0x%s' % (
                strpattern, strmask)

        for handle in handles:
            bp_info = obj.iface.breakpoint.get_breakpoint(handle)

            if type == simics.Sim_Break_Physical:
                bp_type = "phys"
            elif type == simics.Sim_Break_Virtual:
                bp_type = "virt"
            else:
                bp_type = "lin"

            acc = self._access_str(bp_info.read_write_execute)
            props["region-%d" % index] = '%-4s-%-3s 0x%016x 0x%016x' % (
                bp_type, acc, bp_info.start, bp_info.end)
            index += 1
        return props

    def _access_str(self, access):
        acc = ""
        if access & simics.Sim_Access_Read:
            acc = acc + "r"
        if access & simics.Sim_Access_Write:
            acc = acc + "w"
        if access & simics.Sim_Access_Execute:
            acc = acc + "x"
        return acc

    def _get_object(self, obj, address):
        if obj is not None:
            break_type = simics.Sim_Break_Physical
            if obj.classname == "context":
                break_type = simics.Sim_Break_Virtual
            return (obj, break_type)

        cpu = cli.current_cpu_obj()
        if address[self.SPACE_IDX] == "p":
            obj = cpu.iface.processor_info.get_physical_memory()
            break_type = simics.Sim_Break_Physical
        else:
            obj = cpu.iface.context_handler.get_current_context()
            is_x86 = (
                cpu.iface.processor_info.architecture
                and cpu.iface.processor_info.architecture().startswith("x86"))
            if is_x86 and address[self.SPACE_IDX] == "":
                break_type = simics.Sim_Break_Linear
            elif address[self.SPACE_IDX] == "l":
                break_type = simics.Sim_Break_Linear
            else:
                break_type = simics.Sim_Break_Virtual
                if is_x86:
                    ctx_handler = cpu.ports.virtual.context_handler
                    obj = ctx_handler.get_current_context()
            if not obj:
                ctx_type = ("linear" if break_type == simics.Sim_Break_Linear
                            else "virtual")
                raise cli.CliError(
                    f"Failed to insert breakpoint. No {ctx_type} context set.")
        return (obj, break_type)

    def _update_breakpoints(self, bps):
        try:
            conf.sim.breakpoints = bps
        except Exception as ex:
            raise cli.CliError(f'Failed changing breakpoints: {ex}')

    def _set_prefix(self, bp_id, prefix):
        attr_data = self._sim_breakpoint_by_id(bp_id)
        attr_data[self.PREFIX_IDX] = prefix.lower()
        self._update_breakpoints([attr_data])

    def _set_substr(self, bp_id, substr):
        attr_data = self._sim_breakpoint_by_id(bp_id)
        attr_data[self.SUBSTR_IDX] = substr.lower()
        self._update_breakpoints([attr_data])

    def _set_pattern(self, bp_id, pattern, mask):
        attr_data = self._sim_breakpoint_by_id(bp_id)
        attr_data[self.PATTERN_IDX] = pattern.lower()
        attr_data[self.MASK_IDX] = mask.lower()
        self._update_breakpoints([attr_data])

    def _set_enabled(self, _, bm_id, enabled):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        attr_data = self._sim_breakpoint_by_id(bp_id)
        attr_data[self.ACTIVE_IDX] = enabled
        self._update_breakpoints([attr_data])

    def _set_ignore_count(self, _, bm_id, count):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        attr_data = self._sim_breakpoint_by_id(bp_id)
        attr_data[self.ACTIVATE_IDX] = attr_data[self.HITS_IDX] + count + 1
        self._update_breakpoints([attr_data])

    def _get_access_type(self, r, w, x):
        access = 0
        mode = ""

        if r:
            access = access | simics.Sim_Access_Read
            mode = mode + "r"
        if w:
            access = access | simics.Sim_Access_Write
            mode = mode + "w"
        if x or access == 0:
            access = access | simics.Sim_Access_Execute
            mode = mode + "x"
        return (access, mode)

    def _check_args(self, length, access, prefix, substr, pattern, mask):
        if length < 1:
            raise cli.CliError("The breakpoint length must be >= 1 bytes.")
        if ((access & simics.Sim_Access_Execute) == 0 and any([prefix, substr,
                                                               pattern])):
            raise cli.CliError(
                'Can only set prefix/substr/pattern on execution breakpoints'
                ' (access type x)')

        if any([pattern, mask]) and not all([pattern, mask]):
            raise cli.CliError('Can only set pattern alongside mask')

        if all([pattern, mask]):
            if len(pattern) % 2 or len(mask) % 2:
                raise cli.CliError(
                    'Pattern and mask must have a length that corresponds'
                    ' to one or several bytes.')

        if len(pattern) != len(mask):
            raise cli.CliError('Pattern and mask must have the same length.')

        if pattern:
            assert mask
            try:
                _ = [int(x, 16) for x in (pattern, mask)]
            except ValueError:
                raise cli.CliError('Pattern and mask must be'
                                   ' hexadecimal strings.')

    def _access_description(self, addr, length, mode, value=None):
        addr_desc = addr if isinstance(addr, str) else (
            cli.number_str(addr, 16))
        length_desc = "" if length == 1 else (
            f" len={cli.number_str(length, 10)}")
        value_desc = f" val=0x{value:x}" if value is not None else ""
        return f"'{mode}' access to {addr_desc}{length_desc}{value_desc}"

    def _message(self, bp_id, obj, address, length, mode):

        # FIXME Implement specific message for script-branch
        access_desc = self._access_description(
            address[self.ADDRESS_IDX], length, mode)
        msg = (f"break on {access_desc} in {obj.name}")

        bp_list = simics.SIM_get_attribute(conf.sim, "breakpoints")
        bpm_iface = conf.bp.iface.breakpoint_type
        for bp_tuple in bp_list:
            curr_obj = bp_tuple[11]
            curr_bp_id = bp_tuple[0]
            if curr_obj == obj and curr_bp_id != bp_id:
                for bp_handle in bp_tuple[12]:
                    bp_info = obj.iface.breakpoint.get_breakpoint(bp_handle)
                    start = bp_info.start
                    stop = bp_info.end
                    if (address[self.ADDRESS_IDX] <= stop
                        and (address[self.ADDRESS_IDX] + length - 1
                             >= start)):
                        other_bm_id = bpm_iface.get_manager_id(self.obj,
                                                               curr_bp_id)
                        msg += f"\nNote: overlaps with breakpoint {other_bm_id}"
        return msg

    def _bp_change_cb(self, bp_id, obj):
        try:
            _ = self._sim_breakpoint_by_id(bp_id)
        except cli.CliError:
            # Breakpoint was removed
            self._unregister_bp(bp_id, False)

    def _create_bp(self, obj, address, length, r, w, x, prefix, substr,
                   pattern, mask, once, internal):
        (access, mode) = self._get_access_type(r, w, x)

        try:
            self._check_args(length, access, prefix, substr, pattern, mask)
            (obj, break_type) = self._get_object(obj, address)
        except cli.CliError as ex:
            print(ex, file=sys.stderr)
            return 0

        flag = simics.Sim_Breakpoint_Temporary if once else 0
        try:
            bp_id = simics.SIM_breakpoint(obj, break_type, access,
                                          address[self.ADDRESS_IDX],
                                          length, flag)
        except simics.SimExc_General as ex:
            print(ex, file=sys.stderr)
            return 0

        try:
            self._set_prefix(bp_id, prefix)
            self._set_substr(bp_id, substr)
            self._set_pattern(bp_id, pattern, mask)
        except cli.CliError as ex:
            print(ex, file=sys.stderr)
            simics.SIM_delete_breakpoint(bp_id)
            return 0

        change_hap_id = simics.SIM_hap_add_callback_obj(
            "Core_Breakpoint_Change", obj, 0, self._bp_change_cb, bp_id)

        hap_id = simics.SIM_hap_add_callback_obj_index(
            "Core_Breakpoint_Memop", obj, 0, self._bp_cb, bp_id, bp_id)
        self.bp_data[bp_id] = Breakpoint(obj, hap_id, change_hap_id, address,
                                         length, access, mode, break_type,
                                         once, internal)
        return bp_id

    # Callback for bp.delete
    def _delete_bp(self, _, bm_id):
        self._delete_bm(bm_id, True)

    def _delete_bm(self, bm_id, remove_lower):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        self._cleanup_bp(bp_id)
        if remove_lower:
            self._remove_sim_bp(bp_id)

    # Used when deleting bp internally, i.e. oneshot breakpoints
    def _unregister_bp(self, bp_id, remove_lower):
        bm_id = conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)
        conf.bp.iface.breakpoint_registration.deleted(bm_id)

    def _cleanup_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        # Object may have been deleted
        if isinstance(bp.obj, simics.conf_object_t):
            simics.SIM_hap_delete_callback_obj_id("Core_Breakpoint_Memop",
                                                  bp.obj, bp.hap_id)
            simics.SIM_hap_delete_callback_obj_id("Core_Breakpoint_Change",
                                                  bp.obj, bp.change_hap_id)
        del self.bp_data[bp_id]

    def _remove_sim_bp(self, bp_id):
        simics.SIM_delete_breakpoint(bp_id)

    def _is_enabled(self, bp_id):
        attr_data = self._sim_breakpoint_by_id(bp_id)
        return bool(attr_data[self.ACTIVE_IDX])

    def _is_ignored(self, bp_id):
        attr_data = self._sim_breakpoint_by_id(bp_id)
        activate_at = attr_data[self.ACTIVATE_IDX]
        hits = attr_data[self.HITS_IDX]
        return activate_at > 0 and activate_at > hits

    def _bp_cb(self, bp_id, obj, idx, memop):
        assert(bp_id == idx)
        bp = self.bp_data[bp_id]
        bp.last_memop = LastMemopInfo(memop)
        bp.last_ini = memop.ini_ptr
        if bp.last_ini:
            if (hasattr(bp.last_ini.iface, "processor_info")
                or hasattr(bp.last_ini.iface, "step")
                or hasattr(bp.last_ini.iface, "cycle")):
                cli.set_current_frontend_object(bp.last_ini, True)
        if not bp.internal:
            # If there is a wait callback this returns True
            hit = conf.bp.iface.breakpoint_type.trigger(
                self.obj, bp_id, obj, None)
            if (not hit and self._is_enabled(bp_id)
                and not self._is_ignored(bp_id)):
                bm_id = conf.bp.iface.breakpoint_type.get_manager_id(
                    self.obj, bp_id)
                break_msg = (f"Breakpoint {bm_id}: {obj.name}"
                             f" {self.trace_msg(bp_id)}")
                simics.VT_stop_message(obj, break_msg)
                hit = True
        else:
            conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, obj, None)
            hit = True
        if bp.once and hit:
            self._unregister_bp(bp_id, True)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bp_iface = conf.bp.iface.breakpoint_registration
        return bp_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None,
            self._set_enabled, None, None, None,
            self._set_ignore_count, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, flags, args):
        (obj, address, length, r, w, x, prefix,
         substr, pattern, mask, once) = args
        return self._create_bp(obj, address, length, r, w, x, prefix,
                               substr, pattern, mask, once,
                               flags != simics.Breakpoint_Type_Break)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._cleanup_bp(bp_id)
        try:
            self._remove_sim_bp(bp_id)
        except simics.SimExc_Index:
            # Lower level breakpoint already removed
            pass


    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        if not bp.last_memop:
            return "access at <unknown>, len=<unknown>, access=<unknown>"
        if bp.break_type == simics.Sim_Break_Physical:
            addr = f"p:{hex(bp.last_memop.physical_address)}"
        else:
            addr = f"v:{hex(bp.last_memop.logical_address)}"
        value = None
        if bp.last_memop.is_instruction:
            mode = 'x'
        elif bp.last_memop.is_read:
            mode = 'r'
        else:
            mode = 'w'
            if bp.last_memop.size <= 8:
                value = bp.last_memop.value
        return self._access_description(addr, bp.last_memop.size, mode, value)

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return self._message(bp_id, bp.obj, bp.address, bp.length, bp.mode)

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        addr = hex(bp.address[self.ADDRESS_IDX])
        disp_len = cli.number_str(bp.length)
        acc = self._access_str(bp.access)
        return (f"{bp.obj.name} waiting on memory access matching"
                f" (addr={addr}, len={disp_len}, access={acc})")

    @cls.iface.breakpoint_type_provider.break_data
    def break_data(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.last_memop and bp.last_memop.is_from_cpu:
            return bp.last_ini
        else:
            return None

    def _is_user_bp(self, bp):
        '''True if breakpoint data 'bp' is a user-defined
        (non-simulation-internal) breakpoint.'''
        return not (bp[self.FLAGS_IDX] & (simics.Sim_Breakpoint_Simulation
                                          | simics.Sim_Breakpoint_Private))

    def _remove_breakpoint_range(self, id, address, length, access):
        try:
            simics.SIM_breakpoint_remove(id, access, address, length)
        except simics.SimExc_General as ex:
            raise cli.CliError('Failed removing breakpoint: %s' % ex)

    def unbreak_range(self, bm_id, address, length, r, w, x):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        if bp_id == 0:
            raise cli.CliError(f"No such breakpoint: {bm_id}")

        # Verify that this is a memory breakpoint
        _bm_id = conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)
        if _bm_id != bm_id:
            raise cli.CliError(f"Not a memory breakpoint: {bm_id}")

        access = 0
        if r:
            access = access | simics.Sim_Access_Read
        if w:
            access = access | simics.Sim_Access_Write
        if x or access == 0:
            access = access | simics.Sim_Access_Execute

        bp = self._sim_breakpoint_by_id(bp_id)
        if not self._is_user_bp(bp):
            raise cli.CliError("Cannot change simulation-internal breakpoints.")
        self._remove_breakpoint_range(bp_id, address, length, access)

    @staticmethod
    def unbreak_cmd(obj, bm_id, address, length, r, w, x):
        obj.object_data.unbreak_range(bm_id, address, length, r, w, x)

def register_memory_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "memory",
                             MemBreakpoints.cls.classname,
                             MemBreakpoints.TYPE_DESC)

    cli.new_command("unbreak", MemBreakpoints.unbreak_cmd,
                    [cli.arg(cli.uint_t, "id"),
                     cli.arg(cli.uint64_t, "address"),
                     cli.arg(cli.uint64_t, "length"),
                     cli.arg(cli.flag_t, "-r"),
                     cli.arg(cli.flag_t, "-w"),
                     cli.arg(cli.flag_t, "-x")],
                    cls=MemBreakpoints.cls.classname,
                    type=["Breakpoints", "Debugging"],
                    short="remove breakpoint range",
                    see_also=['bp.memory.break', 'bp.delete'],
                    doc = """
Removes an address range from a breakpoint, splitting the breakpoint if
necessary.

The address range is specified by the <arg>address</arg> and <arg>length</arg>
arguments.

<tt>-r</tt> (read), <tt>-w</tt> (write) and <tt>-x</tt> (execute)
specify the type of breakpoint that should be removed in the given
address range. Default is <em>execute</em>.

<arg>id</arg> is the ID number of the breakpoint to remove.
""")
