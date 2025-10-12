# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import itertools
import sys
import cli
import conf
import simics
import device_info
import device_info_cli

common_doc = """
Accesses can be considered on either device or bank objects,
depending on the object that is specified. If a device is specified,
then all banks in the device are considered. Alternatively,
<tt>-all</tt> can be specified to consider all banks in all devices.

To only consider accesses to parts of a bank, either specify a
register name as <arg>register</arg>, or specify <arg>offset</arg> and
<arg>size</arg>, in bytes. One can also specify a mask on the bank, to
only consider accesses that touch the bits specified by the mask. The
mask can either be given by the <arg>mask</arg> parameter, or by
providing a register field name using the <arg>field</arg> parameter.

If <tt>-only-changes</tt> is specified, only those write accesses that
change the part of the bank, specified by offset and size and
potentially the mask, are considered. This option does not affect
considered read accesses.

If <arg>value</arg> is specified, only write accesses that results in
the specified part of the bank having this value are considered, or
read accesses where the bank part already has this value. If
<arg>mask</arg> is specified, this is applied to both the bank part
value and to <arg>value</arg> before comparison.

The default is to consider both read and write accesses, but this can
be changed by specifying <tt>-r</tt> or <tt>-w</tt>.
"""

break_doc = """
Enables breaking the simulation on register bank accesses.
""" + common_doc

run_until_doc = """
Run the simulation until the specified register bank access occurs.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until the specified
register bank access occurs.
""" + common_doc

trace_doc = """
Enables tracing of register bank accesses. When this
is enabled, every time the specified register bank access occurs
during simulation, a message is printed.
""" + common_doc

# This is the instrumentation connection between the breakpoint and each bank.
# It must be a Simics object since it implements an interface.
class BreakpointConnection:
    cls = simics.confclass("bp-manager.bank.bp", pseudo=True)

    def init(self, bank, bp, parent, bp_id):
        self.bank = bank
        self.parent = parent
        self.bp = bp
        self.bp_id = bp_id
        self.last_msg = ""
        self.has_initiator = self._device_has_initiator(self.bank)
        self.last_value = None

    # We can only access the initiator method if the device is new
    @staticmethod
    def _device_has_initiator(bank):
        dev = simics.SIM_port_object_parent(bank)
        for m in simics.SIM_get_all_modules():
            if dev.classname in m[7]:
                abi = simics.CORE_get_extra_module_info(m[0])[2]
                if abi >= 6150:
                    return True
        return False

    @cls.iface.instrumentation_connection.enable
    def enable_instrumentation(self):
        iface = self.bank.iface.bank_instrumentation_subscribe
        if self.bp.is_read:
            iface.register_before_read(
                self.obj, self.bp.offset, self.bp.size, self._read_cb, None)
        if self.bp.is_write:
            iface.register_before_write(
                self.obj, self.bp.offset, self.bp.size, self._write_cb, None)

    @cls.iface.instrumentation_connection.disable
    def disable_instrumentation(self):
        iface = self.bank.iface.bank_instrumentation_subscribe
        iface.remove_connection_callbacks(self.obj)

    @cls.deinit
    def deinit(self):
        self.obj.iface.instrumentation_connection.disable()

    @staticmethod
    def _get_bank_value(bank, offset, size):
        value = 0
        max_offset = offset + size
        # we have no expectations on the order of registers here
        for i in range(bank.iface.register_view.number_of_registers()):
            (_, _, sz, ofs, *_) = bank.iface.register_view.register_info(i)
            if offset in range(ofs, ofs + sz, 1): # start of value is in this reg
                shift = (offset - ofs) * 8
                tmp = bank.iface.register_view.get_register_value(i) >> shift
                if max_offset - 1 in range(ofs, ofs + sz, 1): # full value in this reg
                    tmp &= (1 << (8 * size)) - 1
                    value |= tmp
                    break # only point where we can exit prematurely
                else: # only beginning of value in this reg
                    tmp &= (1 << (8 * (sz - offset + ofs))) - 1
                    value |= tmp
            elif max_offset >= ofs + sz and offset < ofs: # a "middle" register or full final reg
                shift = (ofs - offset) * 8
                value |= bank.iface.register_view.get_register_value(i) << shift
            elif max_offset - 1 in range(ofs, ofs + sz, 1): # "final" partial register
                mask = (1 << (8 * (max_offset - ofs))) - 1
                tmp = bank.iface.register_view.get_register_value(i) & mask
                value |= tmp << ((ofs - offset) * 8)
            else:
                continue
        return value

    def _read_cb(self, obj, iface, handle, arg):
        offset = iface.offset(handle)
        size = iface.size(handle)
        ini = iface.initiator(handle) if (self.has_initiator
                                          and iface.initiator) else None
        self.last_value = self._get_bank_value(self.bank, offset, size)
        self.last_msg = (f"read at offset=0x{offset:x} size=0x{size:x}"
                         + f" value=0x{self.last_value:x}"
                         + (f" ini={ini.name}" if ini else ""))
        self.bp.trigger_read(self, self.last_value)

    def _write_cb(self, obj, iface, handle, arg):
        value = iface.value(handle)
        offset = iface.offset(handle)
        size = iface.size(handle)
        ini = iface.initiator(handle) if (self.has_initiator
                                          and iface.initiator) else None
        self.last_msg = (f"write at offset=0x{offset:x} size=0x{size:x}"
                         + f" value=0x{value:x}"
                         + (f" ini={ini.name}" if ini else ""))
        self.last_value = self._get_bank_value(self.bank, offset, size)
        self.bp.trigger_write(self, value)

    def msg(self):
        return self.last_msg

# This represents each breakpoint, potentially with many connections to banks.
class Breakpoint:
    __slots__ = ('bank_name', 'connections', 'offset', 'size', 'is_read',
                 'is_write', 'only_changes', 'value', 'mask', 'once',
                 'last_con')
    def __init__(self, bank_name, offset, size,
                 is_read, is_write, only_changes, value, mask, once):
        self.bank_name = bank_name
        self.once = once
        self.offset = offset
        self.size = size
        self.is_read = is_read
        self.is_write = is_write
        self.only_changes = only_changes
        self.value = value
        self.mask = mask
        self.once = once
        self.connections = None
        self.last_con = None

    def __str__(self):
        if self.is_read:
            if self.is_write:
                access = "R/W"
            else:
                access = "read"
        else:
            access = "write"
        return f"{access} access"

    # Static description
    def desc(self):
        whole_bank = self.offset == 0 and self.size == 0
        return (f"{self} on {self.bank_name}"
                + (f" at offset=0x{self.offset:x}" if not whole_bank else "")
                + (f" size=0x{self.size:x}" if not whole_bank else "")
                + (f" mask=0x{self.mask:x}" if self.mask is not None else "")
                + (f" value=0x{self.value:x}" if self.value != -1 else "")
                + (" (changing writes only)" if self.only_changes else ""))

    # Dynamic message, e.g. for trace
    def msg(self):
        # Maybe no last connection, e.g. when using test-trigger
        if self.last_con:
            return self.last_con.msg()
        else:
            return self.desc()

    def trigger_read(self, con, cur_val):
        if self.value != -1:
            # Only break if value matches
            cmp_val = self.value
            if self.mask is not None:
                cmp_val &= self.mask
                cur_val &= self.mask

            if cur_val == cmp_val:
                self.trigger(con)
        else:
            self.trigger(con)

    def trigger_write(self, con, new_val):
        if self.value != -1:
            # Only break if new value matches
            cmp_val = self.value
            if self.mask is not None:
                cmp_val &= self.mask
                new_val &= self.mask

            if new_val == cmp_val:
                self.trigger(con)
        elif self.only_changes:
            # Only break if changes affect specified mask
            cmp_val = con.last_value
            if self.mask is not None:
                cmp_val &= self.mask
                new_val &= self.mask

            if new_val != cmp_val:
                self.trigger(con)
        else:
            self.trigger(con)

    def trigger(self, con):
        self.last_con = con
        conf.bp.iface.breakpoint_type.trigger(con.parent, con.bp_id,
                                              con.bank, con.last_msg)

class DeviceBreakpoints:
    TYPE_DESC = "device access"
    cls = simics.confclass("bp-manager.bank", short_doc=TYPE_DESC,
                           doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1
        self.next_con_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "bank", self.obj,
            [["flag_t", "-all", '1', None, None, "", None],
             ["str_t", "register", '?', None, None, "", True],
             ["uint64_t", "offset", '?', 0, None, "", None],
             ["uint64_t", "size", '?', 0, None, "", None],
             ["flag_t", "-r", '1', None, None, "", None],
             ["flag_t", "-w", '1', None, None, "", None],
             ["flag_t", "-only-changes", '1', None, None, "", None],
             ["uint64_t", "value", '?', -1, None, "", None],
             [["uint_t", "str_t"], ["mask", "field"], '?',
              None, None, "", [None, True]]],
            None, "bank_instrumentation_subscribe", [
                "set device access break", break_doc,
                "run until specified device access occurs", run_until_doc,
                "wait for specified device access", wait_for_doc,
                "enable tracing of device accesses", trace_doc],
            False, False, True)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"break on {bp.desc()}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.bank_name,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, root, banks, offset, size, is_read, is_write,
                   only_changes, value, mask, once):
        assert is_read or is_write
        bp_id = self.next_id
        self.next_id += 1

        if not root:
            bank_name = "all devices"
        elif len(banks) == 1:
            bank_name = root.name
        else:
            bank_name = f"devices in sub-tree rooted at '{root.name}'"
        bp = Breakpoint(bank_name, offset, size, is_read, is_write,
                        only_changes, value, mask, once)
        self.bp_data[bp_id] = bp

        connect_args = [self.obj, bp_id]
        bp.connections = [self.obj.iface.instrumentation_tool.connect(
            bank, connect_args) for bank in banks]
        return bp_id

    @staticmethod
    def _get_bank_size(bank):
        bank_size = 0
        for i in range(bank.iface.register_view.number_of_registers()):
            (_, _, size, *_) = bank.iface.register_view.register_info(i)
            bank_size += size
        return bank_size

    @staticmethod
    def _mask_from_field_name(reg_spec, reg, field_name):
        f = [f for f in reg.fields if f.name == field_name]
        if not f:
            print(f"No field {field_name} in register {reg_spec}",
                  file=sys.stderr)
            return None
        field = f[0]
        return (1 << (field.msb + 1)) - (1 << field.lsb)

    @staticmethod
    def _unpack_reg_spec(reg_spec, field_name):
        (dev, reg) = device_info_cli.split_device_bank_reg(reg_spec)
        if not dev or not reg:
            print(f"Not a valid register definition: {reg_spec}",
                  file=sys.stderr)
            return (None, None, None, None)
        try:
            (_, _, r) = device_info_cli.lookup_register(dev, reg)
        except cli.CliError as ex:
            print(str(ex), file=sys.stderr)
            return (None, None, None, None)

        if field_name:
            mask = DeviceBreakpoints._mask_from_field_name(
                reg_spec, r, field_name)
            if not mask:
                return (None, None, None, None)
        else:
            mask = None
        return (dev, r.offset, r.size, mask)

    @staticmethod
    def _unpack_reg(root, reg_spec, field_name):
        assert root
        try:
            (_, _, r) = device_info_cli.lookup_register(root, reg_spec)
            mask = None
            if field_name:
                mask = DeviceBreakpoints._mask_from_field_name(
                    reg_spec, r, field_name)
                if not mask:
                    return (None, None, None)
            return (r.offset, r.size, mask)
        except cli.CliError:
            # reg_spec may be a complete register name including bank
            (dev, offset, size, mask) = DeviceBreakpoints._unpack_reg_spec(
                reg_spec, field_name)
            if dev is None:
                return (None, None, None)

            if dev != root and simics.SIM_port_object_parent(dev) != root:
                print(f"Register {reg_spec} not in device {root}",
                      file=sys.stderr)
                return (None, None, None)
            return (offset, size, mask)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (root, is_all, reg_spec, offset, size, is_read, is_write,
         only_changes, value, mask_arg, recursive, once) = args

        is_ofs_set = is_size_set = lambda s: s > 0
        is_val_set = lambda v: v != -1

        if is_all:
            if root:
                print("-all cannot be combined with an explicit bank",
                      file=sys.stderr)
                return 0
            if reg_spec or is_ofs_set(offset) or is_size_set(size) or mask_arg:
                print("-all cannot be combined with an explicit"
                      " register, offset or mask", file=sys.stderr)
                return 0
            if recursive:
                print("-recursive cannot be combined with -all",
                      file=sys.stderr)
                return 0

        if reg_spec is not None and (is_ofs_set(offset) or is_size_set(size)):
            print("Register name and offset+size must not both be specified",
                  file=sys.stderr)
            return 0

        if not is_size_set(size) and is_ofs_set(offset):
            print("If offset is specified, size must also be.", file=sys.stderr)
            return 0

        if mask_arg:
            if mask_arg[2] == 'field':
                if not reg_spec:
                    print("Specifying a field requires a register.",
                          file=sys.stderr)
                    return 0
                assert mask_arg[0] == 'str_t'
                field = mask_arg[1]
                mask = None
            else:
                assert mask_arg[2] == 'mask' and mask_arg[0] == 'uint_t'
                mask = mask_arg[1]
                if not mask:
                    print("mask must be a positive integer.", file=sys.stderr)
                field = None
        else:
            mask = None
            field = None

        if root and not recursive:
            # A bank object is ok
            if not hasattr(root.iface,
                           simics.BANK_INSTRUMENTATION_SUBSCRIBE_INTERFACE):
                # A single device is ok
                if hasattr(root, 'bank'):
                    root = root.bank
                else:
                    print(f"{root.name} has no register banks"
                          " that support breakpoints", file=sys.stderr)
                    return 0


        if reg_spec:
            if root:
                (offset, size, reg_mask) = self._unpack_reg(
                    root, reg_spec, field)
                if offset is None:
                    return 0
                if mask is None:
                    mask = reg_mask
            else:
                (root, offset, size, reg_mask) = self._unpack_reg_spec(
                    reg_spec, field)
                if root is None:
                    return 0
                if mask is None:
                    mask = reg_mask

        # Default is both read and write
        if not is_read and not is_write:
            is_read = is_write = True

        if not is_write:
            if only_changes or (mask is not None and not is_val_set(value)):
                print("Specifying mask without corresponding value, or"
                      " specifying -only-changes, is only applicable"
                      " for breakpoints on write access", file=sys.stderr)
                return 0

        banks = [o for o in simics.SIM_object_iterator(root)
                 if hasattr(o.iface,
                            simics.BANK_INSTRUMENTATION_SUBSCRIBE_INTERFACE)]
        if root and hasattr(root.iface,
                            simics.BANK_INSTRUMENTATION_SUBSCRIBE_INTERFACE):
            banks.append(root)

        if len(banks) > 1 and reg_spec is not None:
            print("Register must not both be specified"
                  " when breaking on multiple banks", file=sys.stderr)
            return 0

        if ((is_val_set(value) or mask is not None)
            and (size > 8 or
                 (size == 0 and sum(self._get_bank_size(b)
                                    for b in banks) > 8))):
            print("Cannot use value and mask/field if size > 8",
                  file=sys.stderr)
            return 0

        return self._create_bp(root, banks, offset, size, is_read, is_write,
                               only_changes, value, mask, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        # Turn off instrumentation callbacks immediately (might be Cell Context)
        for con in bp.connections:
            con.iface.instrumentation_connection.disable()
        # Object deletion might happen a bit later
        simics.SIM_run_alone(simics.SIM_delete_objects, bp.connections)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.msg()

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Will break on {bp.desc()}"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Waiting on {bp.desc()}"

    @staticmethod
    def _regs_for_device(dev):
        return ["{name}.{reg}".format(
            name=dev.name, reg=dev.iface.register_view.register_info(i)[0])
            for i in range(dev.iface.register_view.number_of_registers())]

    @cls.iface.breakpoint_type_provider.values
    def values(self, param, prev_args):
        assert len(prev_args) >= 9

        # Command is either global or on a bank object
        if prev_args[0] == self.obj:
            (obj, is_all, reg_spec, offset,
             size, _, _, recursive) = prev_args[1:9]
        else:
            (obj, is_all, reg_spec, offset,
             size, _, _, recursive) = prev_args[:8]

        if param == 'object':
            if is_all:
                return []
            # If recursive is used, expand to any object
            if recursive:
                return [o.name for o in simics.SIM_object_iterator(None)]
            else:
                return [o.name for o in simics.SIM_object_iterator(None)
                        if (device_info.is_iomem_device(o)
                            and device_info.has_device_info(o))]
        elif param == 'register':
            if offset or size or is_all or recursive:
                return []
            return list(itertools.chain.from_iterable(
                self._regs_for_device(o)
                for o in itertools.chain([obj] if obj else [],
                                         simics.SIM_object_iterator(obj))
                if hasattr(o.iface, simics.REGISTER_VIEW_INTERFACE)))
        elif param == 'field':
            if not reg_spec or offset or size or is_all or recursive:
                return []
            (dev, reg) = device_info_cli.split_device_bank_reg(reg_spec)
            if not dev or not reg:
                return []
            try:
                (_, _, r) = device_info_cli.lookup_register(dev, reg)
            except cli.CliError:
                return []
            return [f.name for f in r.fields]
        else:
            return []


    @cls.iface.instrumentation_tool.connect
    def connect_bp(self, bank, args):
        bp_id = args[-1]
        con_id = self.next_con_id
        self.next_con_id += 1

        con = simics.SIM_create_object(BreakpointConnection.cls.classname,
                                       f"bp.bank.bp_{con_id}", [])
        bp = self.bp_data[bp_id]
        con_args = [bank, bp] + args
        con.object_data.init(*con_args)
        con.iface.instrumentation_connection.enable()
        return con

    @cls.iface.instrumentation_tool.disconnect
    def disconnect_bp(self, bp):
        self.remove_bp(bp.bp_id)

def register_bank_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "bank",
                             DeviceBreakpoints.cls.classname,
                             DeviceBreakpoints.TYPE_DESC)
