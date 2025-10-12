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

import contextlib
from functools import partial
import os
import re
from binascii import hexlify

import cli
import simics
from deprecation import DEPRECATED
from simicsutils.internal import ensure_binary

from simics import (
    SIM_VERSION_6,

    Sim_Access_Execute,
    Sim_Access_Read,
    Sim_Access_Write,
    TRANSACTION_INTERFACE,
    pr,

    SIM_lookup_file,
)

from cli import (
    addr_t,
    arg,
    filename_t,
    flag_t,
    int_t,
    list_t,
    obj_t,
    poly_t,
    range_t,
    str_t,
    string_set_t,
    uint64_t,
    uint_t,
    new_command,
    new_info_command,
    new_status_command,
    CliError,
    current_cpu_obj,
    current_cpu_obj_null,
    command_return,
    number_str,
    get_completions,

    # script-branch related imports:
    check_script_branch_command,
    sb_signal_waiting,
    sb_wait,
)

from sim_commands import physmem_source

# This ensures that the integer string conversion length limitation in Python is
# not hit, and it also avoids getting other memory-related exceptions.
MAX_SIZE_GET_SET_CMDS = 1024

def get_set_is_big_endian(initiator, size):
    if initiator and hasattr(initiator.iface, "processor_info"):
        p = initiator
    else:
        p = current_cpu_obj_null()
    if p:
        return p.iface.processor_info.get_endian() == simics.Sim_Endian_Big
    if size == 1:
        return False
    raise CliError("When no processor exists, -l or -b has to be specified.")

def get_set_setup(space, size, little_endian, big_endian, initiator):
    has_transaction_interface = False
    if hasattr(space.iface, simics.PORT_SPACE_INTERFACE):
        iface = space.iface.port_space
    elif hasattr(space.iface, simics.TRANSACTION_INTERFACE):
        iface = space.iface.transaction
        has_transaction_interface = True
    elif hasattr(space.iface, simics.MEMORY_SPACE_INTERFACE):
        iface = space.iface.memory_space
    elif hasattr(space.iface, simics.IMAGE_INTERFACE):
        iface = space.iface.image
    else:
        raise CliError("Illegal object %s" % space.name)

    if size < 1 or (size > 8 and not has_transaction_interface):
        raise CliError("Size must be 1-8 bytes.")

    if little_endian and big_endian:
        raise CliError("Cannot use both -l and -b.")

    if not little_endian and not big_endian:
        big_endian = get_set_is_big_endian(initiator, size)

    if hasattr(space.iface, simics.TRANSACTION_INTERFACE):
        def transaction_write(ini, addr, b, inq):
            t = simics.transaction_t(inquiry=inq, data=bytes(b),
                                     write=True, initiator=ini)
            return iface.issue(t, addr)
        def transaction_read(ini, addr, s, inq):
            t = simics.transaction_t(inquiry=inq, size=s, read=True,
                                     initiator=ini)
            ex = iface.issue(t, addr)
            if ex != simics.Sim_PE_No_Exception:
                raise simics.SimExc_Memory(
                    simics.SIM_describe_pseudo_exception(ex))
            return tuple(t.data)
        reader = transaction_read
        writer = transaction_write
    elif hasattr(space.iface, simics.IMAGE_INTERFACE):
        reader = lambda ini, a, s, inq: iface.get(a, s)
        writer = lambda ini, a, b, inq: iface.set(a, b)
    else:
        reader = iface.read
        writer = iface.write

    return (reader, writer, big_endian)

#
# -------------------- set --------------------
#

def throw_cli_error_on_failed_access(address, obj_name, ex, is_write):
    raise CliError(
        f"Failed {'writing' if is_write else 'reading'} memory"
        f" at address {address:#x} in {obj_name}: {ex}")

def obj_set_cmd_convert_value(value, size, is_big_endian, validate_value):
    if not isinstance(value, list):
        value = [value]
    elif not all(isinstance(x, int) for x in value):
        raise CliError("Not all list values are integers")

    if validate_value:
        # Allow wide ranges: for 1-byte integers we allow [-128, 255] range, for
        # 2-byte integers - [-32768, 65535(0xffff)] etc.
        min_allowed = -(1 << (8*size - 1))
        max_allowed = (1 << 8*size) - 1
        for v in value:
            if not (min_allowed <= v <= max_allowed):
                raise CliError(
                    f"the {v:#x} ({v}) doesn't fit into {size} byte(s):"
                    f" accepted range is [{min_allowed}:{max_allowed}]")

    value_list = []
    for v in value:
        item_list = [(v >> (i * 8)) & 0xff for i in range(size)]
        value_list.extend(reversed(item_list) if is_big_endian else item_list)
    return tuple(value_list)

def obj_set_cmd(space, address, value, size, little_endian, big_endian,
                truncate_value, initiator=None, inq=True):
    (_, _, big_endian) = get_set_setup(space, size,
                                       little_endian, big_endian,
                                       initiator)
    value = obj_set_cmd_convert_value(
        value, size, big_endian,
        validate_value = not truncate_value
    )

    try:
        ex = write_space_or_image(space, address, value,
                                  inquiry=inq, initiator=initiator)
        if ex != simics.Sim_PE_No_Exception:
            raise Exception(simics.SIM_describe_pseudo_exception(ex))
    except Exception as ex:
        throw_cli_error_on_failed_access(address, space.name, ex, True)

def set_cmd(address, value, size, le, be, truncate):
    cpu = current_cpu_obj()
    space = cpu.iface.processor_info.get_physical_memory()
    obj_set_cmd(space, address, value, size, le, be, truncate, cpu, True)

def obj_write_cmd(space, address, value, size, le, be, truncate, initiator):
    obj_set_cmd(space, address, value, size, le, be, truncate, initiator, False)

def obj_set_string_cmd(obj, set_str, address, max_size, term, inq = True):
    (_, writer, _) = get_set_setup(obj, 1, False, False, None)
    if not max_size:
        max_size = len(set_str) + 1 # add one for possible null terminator
    chars = bytearray(ensure_binary(set_str[:max_size], encoding='utf-8'))
    if 'null' in term:
        if len(chars) < max_size:
            chars.append(0)
        elif term == 'null':
            chars[-1] = 0
    try:
        writer(None, address, tuple(chars), inq)
    except simics.SimExc_General as ex:
        raise CliError("Failed writing %d byte string to memory at address"
                       " 0x%x in %s: %s" % (len(chars), address, obj.name, ex))

def obj_write_string_cmd(obj, address, value, max_size, term):
    obj_set_string_cmd(obj, address, value, max_size, term, False)

def obj_get_string_cmd(obj, address, max_size, return_list, term, inq = True):
    (reader, *_) = get_set_setup(obj, 1, False, False, None)

    def read_byte(reader, address):
        try:
            return reader(None, address, 1, inq)[0]
        except simics.SimExc_General as ex:
            raise CliError("Failed reading string from memory address"
                           " 0x%x in %s: %s" % (address, obj.name, ex))

    stop_null = 'null' in term
    need_null = 'null' == term
    get_str = bytearray()
    for i in range(max_size):
        if address + i >= 1 << 64:
            break
        val = read_byte(reader, address + i)
        if val == 0 and stop_null:
            break
        get_str.append(val)
    if need_null and len(get_str) == max_size:
        raise CliError("No null-termination found in string at address"
                       " 0x%x in %s" % (address, obj.name))
    return list(get_str) if return_list else bytes(get_str)

def obj_read_string_cmd(obj, address, max_size, return_list, term):
    return obj_get_string_cmd(obj, address, max_size, return_list, term, False)

# transactions_db stores references to issued transactions to protect them
# from Python garbage collector even in case if a script branch is canceled.
transactions_db = set()
def issue_transaction_and_wait_for_completion(obj, t, address, cmdname):
    wait_id = None
    ex_once_completed = [None]
    def completion(obj, t_, ex):
        # NB: due to how Python wrapping works t_ is not equal to t.
        if wait_id is not None:
            sb_signal_waiting(wait_id)
        ex_once_completed[0] = ex
        transactions_db.remove(t)
        return ex
    t.completion = completion
    transactions_db.add(t)

    @contextlib.contextmanager
    def allow_deferring():
        'Manager allowing script branch thread to wait in SIM_transaction_wait'
        simics.CORE_make_script_branch_deferrable_begin()
        try:
            yield
        finally:
            simics.CORE_make_script_branch_deferrable_end()

    with allow_deferring():
        ex = obj.iface.transaction.issue(t, address)
    ex = simics.SIM_monitor_transaction(t, ex)
    if ex == simics.Sim_PE_Deferred:
        # we need to wait for completion
        wait_id = cli.sb_get_wait_id()
        sb_wait(f"{obj.name}.{cmdname}", wait_id,
                wait_data = f"waiting for {obj.name} to complete"
                f" {'an inquiry' if t.inquiry else 'a'}"
                f" {'read' if t.read else 'write'} of"
                f" {t.size} byte(s) @ {address:#x}")
    assert ex_once_completed[0] is not None
    return ex_once_completed[0]

def wait_for_trans_handle_object(obj, initiator):
    if obj is None:
        cpu = current_cpu_obj_null()
        if not cpu:
            raise CliError(
                "The 'object' argument was not specified, but the command"
                " failed to identify the default target. Please specify"
                " it with the 'object' argument.")
        obj = cpu.iface.processor_info.get_physical_memory()
        initiator = initiator or cpu
    elif simics.SIM_object_is_processor(obj):
        initiator = initiator or obj
        obj = obj.iface.processor_info.get_physical_memory()
    return (obj, initiator)

def wait_for_write_trans(obj, address, value, size, endian, initiator,
                         *, inq, cmdname, is_global_cmd):
    check_script_branch_command(cmdname)

    if is_global_cmd:
        (obj, initiator) = wait_for_trans_handle_object(obj, initiator)

    if not hasattr(obj.iface, simics.TRANSACTION_INTERFACE):
        raise CliError(f"{obj.name} has no '{simics.TRANSACTION_INTERFACE}'"
                       " interface")

    if size <= 0:
        raise CliError(f"'size' should have a positive value (got {size})")

    if endian:
        is_big_endian = endian[2] == "-b"
    else:
        is_big_endian = get_set_is_big_endian(initiator, size)

    value = obj_set_cmd_convert_value(value, size, is_big_endian,
                                      validate_value = True)
    t = simics.transaction_t(write = True,
                             inquiry = inq,
                             data = bytes(value),
                             initiator = initiator)

    ex = issue_transaction_and_wait_for_completion(obj, t, address, cmdname)
    if ex != simics.Sim_PE_No_Exception:
        throw_cli_error_on_failed_access(
            address, obj.name, simics.SIM_describe_pseudo_exception(ex), True)

for name, inq in [["wait-for-write", False],
                  ["wait-for-set", True]]:
    new_command(name,
                partial(wait_for_write_trans,
                        inq = inq, cmdname = name, is_global_cmd = True),
                [arg(obj_t("object"), "object", "?"),
                 arg(uint64_t,"address"),
                 arg(poly_t('value', int_t, list_t), "value"),
                 arg(int_t, "size", "?", 4),
                 arg((flag_t, flag_t), ("-l", "-b"), "?", None),
                 arg(obj_t("initiator"),"initiator", "?")],
                type  = ["Memory"],
                short = (f"issue {'an inquiry' if inq else 'a'} write"
                         " transaction and wait for it to complete"),
                see_also = [f"<{TRANSACTION_INTERFACE}>.wait-for-read",
                            f"<{TRANSACTION_INTERFACE}>.wait-for-write",
                            f"<{TRANSACTION_INTERFACE}>.wait-for-get",
                            f"<{TRANSACTION_INTERFACE}>.wait-for-set"],
                doc = (f"""
The command issues {'an inquiry' if inq else 'a'} write transaction
(via the <arg>object</arg>'s '{TRANSACTION_INTERFACE}' interface)
to <arg>address</arg> with the <arg>value</arg> value and
the length of <arg>size</arg> bytes. The default <arg>size</arg> is 4 bytes,
but it can have any positive value. If the transaction
is not completed immediately the command postpones the execution
of a script branch until the transaction is completed.

The <arg>object</arg> argument is optional. If it is not provided then
a transaction will be sent through the physical memory associated with
the current processor. A CPU object can also be passed in the <arg>object</arg>
argument. In that case, a transaction will be sent through the physical memory
associated with that processor.

If a <arg>value</arg> doesn't fit into the specified size, an error is reported.

Providing <arg>initiator</arg> is rarely needed, but some devices may
only accept accesses from certain initiating objects. If provided,
<arg>initiator</arg> is the object that will be used as the source of the
access.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian and
big-endian byte order, respectively.  If neither is given, the byte
order of the <arg>initiator</arg> is used if specified and a processor, or else
the order of the currently selected processor.

If the <arg>value</arg> argument is a list, then each item is written to memory
as a value of <arg>size</arg> bytes, starting at <arg>address</arg>. The byte
order flags operate on each item in the list.

If a request fails an error is reported."""))

    new_command(name,
                partial(wait_for_write_trans,
                        inq = inq, cmdname = name, is_global_cmd = False),
                [arg(uint64_t,"address"),
                 arg(poly_t('value', int_t, list_t), "value"),
                 arg(int_t, "size", "?", 4),
                 arg((flag_t, flag_t), ("-l", "-b"), "?", None),
                 arg(obj_t("initiator"),"initiator", "?")],
                type  = ["Memory"],
                short = (f"issue {'an inquiry' if inq else 'a'} write"
                         " transaction and wait for it to complete"),
                iface = TRANSACTION_INTERFACE,
                see_also = ["wait-for-read", "wait-for-write",
                            "wait-for-get", "wait-for-set"],
        doc = (f"""
The command issues {'an inquiry' if inq else 'a'} write transaction
(via the '{TRANSACTION_INTERFACE}' interface)
to <arg>address</arg> with the <arg>value</arg> value and
the length of <arg>size</arg> bytes. The default <arg>size</arg> is 4 bytes,
but it can have any positive value.
If the transaction is not completed immediately
the command postpones the execution of a script branch until
the transaction is completed.

If a positive <arg>value</arg> doesn't fit in the specified size,
an error is reported.

Providing <arg>initiator</arg> is rarely needed, but some devices may
only accept accesses from certain initiating objects. If provided,
<arg>initiator</arg> is the object that will be used as the source of the
access.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian and
big-endian byte order, respectively.  If neither is given, the byte
order of the <arg>initiator</arg> is used if specified and a processor, or else
the order of the currently selected processor.

If the <arg>value</arg> argument is a list, then each item is written to memory
as a value of <arg>size</arg> bytes, starting at <arg>address</arg>. The byte
order flags operate on each item in the list.

If a request fails an error is reported."""))

new_command("set", set_cmd,
            [arg(uint64_t,"address"),
             arg(poly_t('value', int_t, list_t), "value"),
             arg(range_t(1, MAX_SIZE_GET_SET_CMDS,
                         f"1..{MAX_SIZE_GET_SET_CMDS}"), "size", "?", 4),
             arg(flag_t,"-l"), arg(flag_t,"-b"), arg(flag_t, "-t")],
            type  = ["Memory"],
            short = "set physical address to specified value",
            see_also = ["get", "x", "pselect"],
            doc = """
Set the <arg>size</arg> bytes of physical memory at location
<arg>address</arg> to <arg>value</arg>.

If <arg>value</arg> is larger than the specified size, an error is given.
This can be ignored with the <tt>-t</tt> flag, which will truncate the
value to size bytes.

If <arg>initiator</arg> is the object that will be used as the source of the
memory access. Supplying an initiator is rarely needed, but some devices may
only accept accesses from certain initiating objects.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian and
big-endian byte order, respectively.  If neither is given, the byte
order of the <arg>initiator</arg> is used if specified and a processor, or else
the order of the currently selected processor.

The <cmd>set</cmd> command variants perform the access in inquiry mode without
triggering any side-effects while <cmd class="memory_space">write</cmd> and
<cmd class="port_space">write</cmd> may trigger side-effects.

If the <arg>value</arg> argument is a list, then each item is written to memory
as a value of <arg>size</arg> bytes, starting at <arg>address</arg>. The byte
order flags operate on each item in the list.

The non-namespace version of this command operates on the physical memory
associated with the current processor.
""")

string_term_kinds = ('null', 'optional-null', 'none')

for (space, size) in {
        "memory_space": arg(range_t(
            1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size", "?", 4),
        "port_space": arg(range_t(1, 8, "1..8"), "size", "?", 4)}.items():
    new_command("set", obj_set_cmd,
                [arg(uint64_t,"address"),
                 arg(poly_t('value', int_t, list_t), "value"),
                 size, arg(flag_t,"-l"), arg(flag_t,"-b"),
                 arg(flag_t, "-t"),
                 arg(obj_t("initiator"),"initiator", "?")],
                short = "set physical address to specified value without "
                "side-effects",
                see_also = ["get", "signed"],
                iface = space,
                doc_with = "set")

    new_command("write", obj_write_cmd,
                [arg(uint64_t,"address"),
                 arg(poly_t('value', int_t, list_t), "value"),
                 size, arg(flag_t,"-l"), arg(flag_t,"-b"),
                 arg(flag_t, "-t"),
                 arg(obj_t("initiator"),"initiator", "?")],

                short = "set physical address to specified value",
                see_also = ["get", "signed"],
                iface = space,
                doc_with = "set")

    new_command("set-string", obj_set_string_cmd,
                [arg(str_t, "string"),
                 arg(uint64_t,"address"),
                 arg(uint_t, "max-size", "?"),
                 arg(string_set_t(string_term_kinds), "term", "?", "null")],
                short = "write a string to memory",
                see_also = ["<%s>.get-string" % space,
                            "<%s>.write-string" % space,
                            "<%s>.set" % space,
                            "<%s>.write" % space],
                iface = space,
            doc = """
Write up to <arg>max-size</arg> characters from the string <arg>string</arg> to
physical memory at location <arg>address</arg>. The <arg>term</arg> argument
determines how the string is terminated in memory. If <arg>term</arg> is
&quot;none&quot;, no string terminator is written. If it is &quot;null&quot;
(default), a null-terminator is written at the end of the string (meaning that
at most <arg>max-size</arg> - 1 bytes from the string will be written)
and for &quot;optional-null&quot;, a null-terminator is only added it fits
within the <arg>max-size</arg> character count. Any null characters embedded in
the CLI string will be written to memory and not treated as string terminators.

The <cmd class="%s">set-string</cmd> command performs the access in inquiry
mode without triggering any side-effects while
<cmd class="%s">write-string</cmd> may trigger side-effects.""" % (
    space, space))

    new_command("write-string", obj_write_string_cmd,
                [arg(str_t, "string"),
                 arg(uint64_t,"address"),
                 arg(uint_t, "max-size", "?"),
                 arg(string_set_t(string_term_kinds), "term", "?", "null")],
                short = "write a string to memory",
                see_also = ["<%s>.read-string" % space,
                            "<%s>.set-string" % space,
                            "<%s>.set" % space,
                            "<%s>.write" % space],
                iface = space,
                doc_with = "<memory_space>.set-string")

    new_command("get-string", obj_get_string_cmd,
                [arg(uint64_t,"address"),
                 arg(range_t(1, 1024, "1..1024"), "max-size", "?", 256),
                 arg(flag_t, "-list"),
                 arg(string_set_t(string_term_kinds), "term", "?", "null")],
                short = "read a string from memory",
                see_also = ["<%s>.set-string" % space,
                            "<%s>.read-string" % space,
                            "<%s>.get" % space,
                            "<%s>.read" % space],
                iface = space,
            doc = """
Read up to <arg>max-size</arg> characters (default 256, maximum 1024)
from physical memory at <arg>address</arg>, returning them as a string
or list. The <arg>term</arg> argument controls how the end of the string in
memory is determined. If <arg>term</arg> is &quot;none&quot; then all
<arg>max-size</arg> characters are read and the returned string will contain
any null bytes encountered. If it is &quot;null&quot; (default) the command
stops reading from memory when it finds a null-terminator while an error is
generated if no null-terminator is found within <arg>max-size</arg> characters.
The &quot;optional-null&quot; argument value is similar to &quot;null&quot;
but all <arg>max-size</arg> characters are returned as a string if no
null-terminator is found.

The string is returned as a list of bytes if the <tt>-list</tt> argument is
supplied.

The string read from memory must be in ASCII or UTF-8 encoding to be returned
as a CLI string otherwise an exception is raised.

The <cmd class="%s">get-string</cmd> command performs the access in inquiry
mode without triggering any side-effects while
<cmd class="%s">read-string</cmd> may trigger side-effects.""" % (
    space, space))

    new_command("read-string", obj_read_string_cmd,
                [arg(uint64_t,"address"),
                 arg(range_t(1, 1024, "1..1024"), "max-size", "?", 256),
                 arg(flag_t, "-list"),
                 arg(string_set_t(string_term_kinds), "term", "?", "null")],
                short = "read a string from memory",
                see_also = ["<%s>.write-string" % space,
                            "<%s>.get-string" % space,
                            "<%s>.get" % space,
                            "<%s>.read" % space],
                iface = space,
                doc_with = "<memory_space>.get-string")

#
# -------------------- get --------------------
#

def format_obj_get_cmd_ret_val(val, is_big_endian):
    endian_string = "BE" if is_big_endian else "LE"
    message = "%s (%s)" % (number_str(val), endian_string)
    return command_return(message, val)

def obj_get_cmd(space, address, size, little_endian, big_endian,
                initiator=None, inq=True):
    (_, _, big_endian) = get_set_setup(space, size,
                                       little_endian, big_endian,
                                       initiator)
    try:
        data_bytes = read_space_or_image(space, address, size,
                                         initiator=initiator, inquiry=inq)
    except Exception as ex:
        throw_cli_error_on_failed_access(address, space.name, ex, False)

    val = int.from_bytes(data_bytes, "big" if big_endian else "little")
    return format_obj_get_cmd_ret_val(val, big_endian)

def get_cmd(address, size, le, be):
    cpu = current_cpu_obj()
    space = cpu.iface.processor_info.get_physical_memory()
    return obj_get_cmd(space, address, size, le, be, initiator=cpu)

def obj_read_cmd(space, address, size, le, be, initiator):
    return obj_get_cmd(space, address, size, le, be,
                       initiator=initiator, inq=False)

new_command("get", get_cmd,
            [arg(uint64_t,"address"),
             arg(range_t(1, MAX_SIZE_GET_SET_CMDS,
                         f"1..{MAX_SIZE_GET_SET_CMDS}"), "size", "?", 4),
             arg(flag_t,"-l"), arg(flag_t,"-b")],
            type  = ["Memory", "Inspection"],
            short = "get value of physical address",
            see_also = ["x", "set", "signed", "pselect"],
            doc = """
Get value of physical memory at location <arg>address</arg>. The
<arg>size</arg> argument specifies how many bytes should be read. It defaults
to 4, but can be any number of bytes between 1 and 8 (inclusive).

If <arg>initiator</arg> is the object that will be used as the source of the
memory access. Supplying an initiator is rarely needed, but some devices may
only accept accesses from certain initiating objects.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian or
big-endian byte order, respectively used to determine how the bytes in memory
should be interpreted as a value. If neither is given, the byte order of the
<arg>initiator</arg> is used if specified and a processor, or else the order
of the current frontend processor.

The <cmd>get</cmd> command variants perform the access in inquiry mode without
triggering any side-effects while <cmd class="memory_space">read</cmd> and
<cmd class="port_space">read</cmd> may trigger side-effects.

The non-namespace version of this command operates on the physical memory
associated with the current frontend processor.""")

for (space, size) in {
        "memory_space": arg(range_t(
            1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size", "?", 4),
        "port_space": arg(range_t(1, 8, "1..8"), "size", "?", 4)}.items():
    new_command("get", obj_get_cmd,
                [arg(uint64_t,"address"),
                 size, arg(flag_t,"-l"), arg(flag_t,"-b"),
                 arg(obj_t("initiator"),"initiator", "?")],
                short = "get value from physical address without side-effects",
                iface = space,
                doc_with = "get")

    new_command("read", obj_read_cmd,
                [arg(uint64_t,"address"),
                 size, arg(flag_t,"-l"), arg(flag_t,"-b"),
                 arg(obj_t("initiator"),"initiator", "?")],
                short = "read value from physical address",
                iface = space,
                doc_with = "get")

def wait_for_read_trans(obj, address, size, endian, initiator,
                        *, inq, cmdname, is_global_cmd):
    check_script_branch_command(cmdname)

    if is_global_cmd:
        (obj, initiator) = wait_for_trans_handle_object(obj, initiator)

    if not hasattr(obj.iface, TRANSACTION_INTERFACE):
        raise CliError(f"{obj.name} has no '{TRANSACTION_INTERFACE}' interface")

    if size <= 0:
        raise CliError(f"'size' should have a positive value (got {size})")

    if endian:
        is_big_endian = endian[2] == "-b"
    else:
        is_big_endian = get_set_is_big_endian(initiator, size)

    t = simics.transaction_t(read = True,
                             inquiry = inq,
                             size = size,
                             initiator = initiator)

    ex = issue_transaction_and_wait_for_completion(obj, t, address, cmdname)
    if ex != simics.Sim_PE_No_Exception:
        throw_cli_error_on_failed_access(
            address, obj.name, simics.SIM_describe_pseudo_exception(ex), False)

    ret_val = int.from_bytes(t.data, "big" if is_big_endian else "little")
    return format_obj_get_cmd_ret_val(ret_val, is_big_endian)

for name, inq in [["wait-for-read", False],
                  ["wait-for-get", True]]:

    new_command(
        name,
        partial(wait_for_read_trans,
                inq = inq, cmdname = name, is_global_cmd = True),
        [arg(obj_t("object"), "object", "?"),
         arg(uint64_t,"address"),
         arg(int_t,"size", "?", 4),
         arg((flag_t, flag_t), ("-l", "-b"), "?", None),
         arg(obj_t("initiator"),"initiator", "?")],
        type  = ["Memory"],
        short = (f"issue {'an inquiry' if inq else 'a'} read"
                 " transaction and wait for it to complete"),
        see_also = [f"<{TRANSACTION_INTERFACE}>.wait-for-read",
                    f"<{TRANSACTION_INTERFACE}>.wait-for-write",
                    f"<{TRANSACTION_INTERFACE}>.wait-for-get",
                    f"<{TRANSACTION_INTERFACE}>.wait-for-set"],
        doc = (f"""
The command issues {'an inquiry' if inq else 'a'} read transaction
(via the <arg>object</arg>'s '{TRANSACTION_INTERFACE}' interface)
to <arg>address</arg>. If the transaction is not completed immediately
the command postpones the execution of a script branch until
the transaction is completed.

The <arg>size</arg> argument specifies how many bytes should be read.
It defaults to 4, but can be set to any positive value.

The <arg>object</arg> argument is optional. If it is not provided then
a transaction will be sent through the physical memory associated with
the current processor. A CPU object can also be passed in the <arg>object</arg>
argument. In that case, a transaction will be sent through the physical memory
associated with that processor.

Providing <arg>initiator</arg> is rarely needed, but some devices may
only accept accesses from certain initiating objects. If provided,
<arg>initiator</arg> is the object that will be used as the source of the
access.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian or
big-endian byte order, respectively. They determine how the bytes in memory
should be interpreted as a value. If neither is given, the byte order of the
<arg>initiator</arg> is used if specified and a processor, or else the order
of the current frontend processor.

When used in an expression the command returns the value read.

If a request fails an error is reported."""))

    new_command(
        name,
        partial(wait_for_read_trans,
                inq = inq, cmdname = name, is_global_cmd = False),
        [arg(uint64_t,"address"),
         arg(int_t,"size", "?", 4),
         arg((flag_t, flag_t), ("-l", "-b"), "?", None),
         arg(obj_t("initiator"),"initiator", "?")],
        type  = ["Memory"],
        short = (f"issue {'an inquiry' if inq else 'a'} read"
                 " transaction and wait for it to complete"),
        iface = TRANSACTION_INTERFACE,
        see_also = ["wait-for-read", "wait-for-write",
                    "wait-for-get", "wait-for-set"],
        doc = (f"""
The command issues {'an inquiry' if inq else 'a'} read transaction
(via the '{TRANSACTION_INTERFACE}' interface) to <arg>address</arg>.
If the transaction is not completed immediately the command postpones
the execution of a script branch until the transaction is completed.

The <arg>size</arg> argument specifies how many bytes should be read.
It defaults to 4, but can be set to any positive value.

Providing <arg>initiator</arg> is rarely needed, but some devices may
only accept accesses from certain initiating objects. If provided,
<arg>initiator</arg> is the object that will be used as the source of the
access.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian or
big-endian byte order, respectively. They determine how the bytes in memory
should be interpreted as a value. If neither is given, the byte order of the
<arg>initiator</arg> is used if specified and a processor, or else the order
of the current frontend processor.

When used in an expression the command returns the value read.

If a request fails an error is reported."""))

#
# -------------------- x --------------------
#

def x_cmd_repeat(obj, cpu, addr_spec, length, compressed, group, endian):
    _last_x_addr = cli.get_repeat_data(x_cmd)
    _last_x_addr = (_last_x_addr[0], _last_x_addr[1] + length)
    x_cmd(obj, cpu, _last_x_addr, length, compressed, group, endian)

def x_cmd(obj, cpu, addr_spec, length, compressed, group, endian):
    cli.set_repeat_data(x_cmd, addr_spec)
    if cpu:
        DEPRECATED(SIM_VERSION_6,
                   "The cpu-name parameter is deprecated",
                   "Use the object parameter instead.")
        if obj:
            raise CliError("cpu-name and object cannot both be specified")
        cpu_x_cmd(None, cpu, addr_spec, length, compressed, group, endian)
        return
    if obj:
        if hasattr(obj.iface, simics.PROCESSOR_INFO_INTERFACE):
            cpu_x_cmd(obj, None, addr_spec, length, compressed, group, endian)
        else:
            (kind, addr) = addr_spec
            if kind == 'v':
                raise CliError("virtual addresses can only be"
                               " used on processors")
            memory_space_img_x_cmd(obj, addr, length,
                                   compressed, group, endian)
    else:
        cpu_x_cmd(current_cpu_obj(), None, addr_spec, length, compressed, group, endian)

def cpu_x_cmd(obj, cpu, addr_spec, length, compressed, group, endian):
    le  = endian and endian[2] == '-l'
    cli.set_repeat_data(x_cmd, addr_spec)
    if obj and cpu:
        raise CliError("cpu-name and object cannot both be specified")
    if obj:
        cpu = obj
    (kind, addr) = addr_spec
    if kind == 'p':
        src = physmem_source(cpu.iface.processor_info.get_physical_memory())
    else:
        src = virtmem_source(cpu.iface.processor_info.get_physical_memory(),
                             cpu, kind)
    hexdump(src, addr, length, compressed=compressed, group=group, le=le)

def memory_space_img_x_cmd_repeat(obj, addr, length, compressed, group, endian):
    _last_x_addr = cli.get_repeat_data(memory_space_img_x_cmd)
    _last_x_addr = _last_x_addr + length

    memory_space_img_x_cmd(obj, _last_x_addr, length, compressed, group, endian)

def memory_space_img_x_cmd(obj, address, length, compressed, group, endian):
    le  = endian and endian[2] == '-l'
    cli.set_repeat_data(memory_space_img_x_cmd, address)
    is_space = hasattr(obj.iface, 'memory_space')
    src = physmem_source(obj) if is_space else image_source(obj)
    hexdump(src, address, length, compressed=compressed,
            group=group, le=le, align=is_space)

def img_x_cmd(obj, address, length, compressed, group, endian):
    if address is None:
        raise CliError("address must be specified")
    memory_space_img_x_cmd(obj, address, length, compressed, group, endian)

def get_address_prefix(cpu):
    try:
        prefix_func = cpu.iface.processor_cli.get_address_prefix
    except simics.SimExc_Lookup:
        prefix_func = None
    if prefix_func:
        return prefix_func()
    else:
        return "v"

def translate_to_physical(cpu, addr):
    try:
        translate = cpu.iface.processor_cli.translate_to_physical
    except simics.SimExc_Lookup:
        translate = None
    if translate:
        tagged_addr = translate(addr[0], addr[1])
    else:
        if addr[0] not in ["", "v"]:
            raise CliError("Illegal address prefix '" + addr[0] + "'.")
        try_type = (Sim_Access_Read, Sim_Access_Execute, Sim_Access_Write)
        for access_type in try_type:
            tagged_addr = cpu.iface.processor_info.logical_to_physical(addr[1], access_type)
            if tagged_addr.valid:
                break
    if tagged_addr.valid:
        return tagged_addr.address
    else:
        raise simics.SimExc_Memory(
            "No virtual to physical address translation found")

def hexdump(source, addr, length,
            align=True, compressed=False, group=16, le=False):
    if group not in (8, 16, 32, 64, 128):
        raise CliError("group-by should be 8, 16, 32, 64 or 128 bits")
    group >>= 3    # to bytes
    if le and addr % group:
        raise CliError("Grouping in little-endian mode is only implemented"
                       " for aligned addresses")
    bpl = 16       # bytes per line
    blen = bpl * 2 + bpl // 2
    if addr + length - 1 <= 0xffffffff:
        addr_fmt = "0x%08x"
    else:
        addr_fmt = "0x%016x"
    addr_prefix = source.addr_prefix()
    line = chars = prefix = ""

    def flush():
        if line:
            line_end = ''
            if tags or chars:
                line_end += ' ' * (blen - len(line) + 1) + tags + ' ' + chars
            pr(prefix + line + line_end + '\n')

    def line_prefix(addr):
        if align:
            addr &= ~(bpl - 1)
        return addr_prefix + addr_fmt % addr + ' '

    def get_tag(addr):
        if have_tags:
            return source.get_tag(addr)
        else:
            return ""

    # Look for tagged memory (need to know if tag column should be displayed)
    # Remember that xrange can't handle numbers larger than an 'int' so iterate
    # over the offset instead of the address.
    have_tags = any(source.have_tag(addr + x) for x in range(0, length, 16))

    if align:
        # Align printed lines on a "bytes-per-line" byte boundary
        alignment = addr & (bpl - 1)    # leftmost bytes to skip
        line += ' ' * (alignment * 2 + (alignment + 1) // 2)
        chars = ' ' * alignment
        tags = get_tag(addr)
        prefix = line_prefix(addr)
    else:
        alignment = 0

    line_zero = True
    last_line_zero = False
    for i in range(length):
        if ((i + alignment) % bpl) == 0:
            if not compressed or not(last_line_zero and line_zero):
                if compressed and (last_line_zero and not line_zero):
                    pr("...\n")
                flush()
                if line and line_zero:
                    last_line_zero = True
                else:
                    last_line_zero = False
            line_zero = True
            prefix = line_prefix(addr + i)
            line = chars = ""
            tags = get_tag(addr + i)
        if ((i + alignment) & (group - 1)) == 0:
            line += ' '
        byte_offset = (i + group - 2 * (i % group) - 1) if le else i
        val = source.get_byte(addr + byte_offset)
        ch = "."
        if isinstance(val, str):
            line += val
            try:
                line_zero &= not bool(int(val))
            except ValueError:
                line_zero = False
        else:
            line += "%02x" % val
            line_zero &= not bool(val)
            # Until we know how the terminal will display characters > 0x7e,
            # don't print them (see bug 1177)
            if 0x20 <= val < 0x7f:
                ch = chr(val)
        if not le:
            # The string part will be confusing in little endian mode where
            # it isn't clear if swapped or not. Skip it.
            chars += ch
    if compressed and last_line_zero:
        pr("...\n")
    flush()
    source.finish()

class virtmem_source(physmem_source):
    def __init__(self, obj, cpu, kind):
        self.obj = obj
        self.cpu = cpu
        self.kind = kind
        self.unhandled = self.outside = self.no_translation = 0
        self.tag_unavailable = 0

    def addr_prefix(self):
        if self.kind == "":
            return get_address_prefix(self.cpu) + ":"
        else:
            return self.kind + ":"

    def get_byte(self, addr):
        try:
            paddr = translate_to_physical(self.cpu, (self.kind, addr))
        except simics.SimExc_Memory:
            self.no_translation = 1
            return "--"
        return physmem_source.get_byte(self, paddr)

    def have_tag(self, addr):
        try:
            paddr = translate_to_physical(self.cpu, (self.kind, addr))
        except simics.SimExc_Memory:
            self.no_translation = 1
            return 0
        return physmem_source.have_tag(self, paddr)

    def get_tag(self, addr):
        try:
            paddr = translate_to_physical(self.cpu, (self.kind, addr))
        except simics.SimExc_Memory:
            return "-"
        return physmem_source.get_tag(self, paddr)

    def finish(self):
        physmem_source.finish(self)
        if self.no_translation:
            pr("addresses marked \"--\" have no translation\n")

class image_source:
    def __init__(self, image):
        self.image = image
        self.outside = 0

    def addr_prefix(self):
        return ""

    def get_byte(self, addr):
        try:
            [byte] = self.image.byte_access[[addr,addr]]
            return byte
        except:
            self.outside = 1
            return "--"

    def have_tag(self, addr):
        return 0

    def finish(self):
        if self.outside:
            pr("addresses marked \"--\" are outside the image\n")

def group_by_expander(comp):
    return get_completions(comp, ("8", "16", "32", "64", "128"))

new_command("x", x_cmd,
            [arg(obj_t('object', ('processor_info', 'image', 'memory_space')),
                 "object", "?"),
             arg(obj_t('processor', 'processor_info'), "cpu-name", "?"),
             arg(addr_t, "address"),
             arg(int_t, "size", "?", 16),
             arg(flag_t, "-c"),
             arg(int_t, "group-by", "?", 16, expander = group_by_expander),
             arg((flag_t, flag_t), ("-l", "-b"), "?")],
            type  = ["Memory", "Inspection"],
            short = "examine raw memory contents",
            namespace_copy = ("processor_info", cpu_x_cmd),
            repeat = x_cmd_repeat,
            alias = "examine-memory",
            see_also = ["disassemble", "get", "set"],
            doc = """
Display the contents of a memory space or image, starting at
<arg>address</arg>. The <arg>object</arg> parameter can be an image,
memory-space or processor object, which implicitly uses the memory
space of that processor. There are also namespace versions of the
command; namely, the image <cmd iface="image">x</cmd> command and
the memory-space <cmd iface="memory_space">x</cmd> command. The
global version of the command operates on the memory of the current
frontend processor by default.

If the memory is accessed via a processor, the type of <arg>address</arg> is
specified by a prefix. For physical addresses use
<tt>p:&lt;address&gt;</tt>; for virtual addresses, <tt>v:&lt;address&gt;</tt>
on non-x86 targets. On x86, use
<tt>&lt;segment-register&gt;:&lt;offset&gt;</tt> or <tt>l:&lt;address&gt;</tt>
for x86 linear addresses. If no prefix is given, the address is assumed to be
virtual. On x86 the default is <tt>ds:&lt;address&gt;</tt> (data segment
addressing).

The access will be made in inquiry mode, which means it will have no
side-effects on the processor or the accessed object. Use the
<cmd iface="memory_space">read</cmd> command to do non-inquiry accesses.

The <arg>size</arg> argument specifies the number of bytes to examine. When
reading virtual memory, only addresses which can be found in the TLB or
hardware page tables (if any) are shown. Unmapped addresses are shown
presented "<tt>--</tt>", undefined physical addresses as "<tt>**</tt>".

By default the memory contents, from low address to high, is presented from
left to right, grouped into 16-bit words. In this format the values shown can
be interpreted as big-endian words. The grouping can be modified by the
<arg>group-by</arg> argument and supports 8, 16, 32, 64 and 128 bit words.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian or
big-endian byte order, respectively. If neither is given, the big-endian
byte order is used as the default.

The <tt>-c</tt> flag compresses the output by not displaying sequences of
zeros.""")

new_command("x", memory_space_img_x_cmd,
            [arg(uint64_t, "address"),
             arg(int_t, "size", "?", 16),
             arg(flag_t, "-c"),
             arg(int_t, "group-by", "?", 16, expander = group_by_expander),
             arg((flag_t, flag_t), ("-l", "-b"), "?")],
            type = ["Memory", "Inspection"],
            short = "examine raw memory contents",
            iface = "memory_space",
            repeat = memory_space_img_x_cmd_repeat,
            alias = "examine-memory",
            doc_with = "x")

new_command("x", img_x_cmd,
            [arg(uint64_t, "address", "?"),
             arg(int_t, "size", "?", 16),
             arg(flag_t, "-c"),
             arg(int_t, "group-by", "?", 16, expander = group_by_expander),
             arg((flag_t, flag_t), ("-l", "-b"), "?")],
            type = ["Memory", "Inspection"],
            short = "examine image data",
            iface = "image",
            repeat = memory_space_img_x_cmd_repeat,
            doc_with = "x")

#
# -------------------- load-binary --------------------
#

def mem_space_load_binary_cmd(obj, filename, poff, v, use_pa, no_clear):
    try:
        return simics.CORE_load_binary(obj, filename, poff, use_pa, v, no_clear)
    except simics.SimExc_General as ex:
        raise CliError(str(ex))

def load_binary_cmd(mem, filename, poff, v, use_pa, logical, no_clear):
    if not mem:
        if logical:
            mem = current_cpu_obj()
        else:
            cpu = current_cpu_obj()
            mem = cpu.iface.processor_info.get_physical_memory()
    return mem_space_load_binary_cmd(mem, filename, poff, v, use_pa, no_clear)

new_command("load-binary", load_binary_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space')),
                 "object", "?"),
             arg(filename_t(simpath = 1, exist = 1), "filename"),
             arg(uint64_t, "offset", "?", 0),
             arg(flag_t, "-v"), arg(flag_t, "-pa"), arg(flag_t, "-l"),
             arg(flag_t, "-n")],
            type  = ["Memory"],
            short = "load binary (executable) file into memory",
            see_also = ["load-file", "add-directory"],
            doc = """
Load a binary (executable) file, <arg>filename</arg>, into the
physical or virtual memory space given by <arg>object</arg>. The
supported formats are ELF, Motorola S-Record, PE32 and PE32+. For ELF,
all segments with a PT_LOAD program header are loaded.

By default the virtual load address from the file is used. The physical load
address can be used instead, for file formats supporting both, by specifying
the <tt>-pa</tt> flag. The load address selected does not affect if the
binary is loaded into the virtual or physical address space.

If an <arg>offset</arg> is supplied, it will be added to the load address taken
from the file.

The global <cmd>load-binary</cmd> command will use the currently
selected processor to find the memory space to load the binary into,
unless <arg>object</arg> is specified. If the <tt>-l</tt> flag is
given, it will load it into the virtual memory space, otherwise it
will use the physical memory space. The processor must have a valid
virtual to physical translation set up.

When using the namespace command on a <class>processor</class> object, it will
load the binary into the virtual memory space of that processor.

When using the namespace command on a <class>memory-space</class> object, it
will load the binary directly into that memory space without any virtual to
physical translation.

The <tt>-v</tt> flag turns on verbose mode, printing information about the
loaded file.

The <tt>-n</tt> flags tells the command to not clear <tt>.bss</tt> areas
in the file.

The return value is the address of the execution entry point. This value is
typically used in a call to <cmd>set-pc</cmd>.

<cmd>load-binary</cmd> uses Simics's Search Path and path markers (%simics%,
%script%) to find the file to load. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual
for more information on how Simics's Search Path is used to locate files.
""")

new_command("load-binary", mem_space_load_binary_cmd,
            [arg(filename_t(simpath = 1, exist = 1), "filename"),
             arg(uint64_t, "offset", "?", 0),
             arg(flag_t, "-v"), arg(flag_t, "-pa"), arg(flag_t, "-n")],
            iface = "memory_space",
            short = "load binary (executable) file into memory",
            doc_with = "load-binary")

new_command("load-binary", mem_space_load_binary_cmd,
            [arg(filename_t(simpath = 1, exist = 1), "filename"),
             arg(uint64_t, "offset", "?", 0),
             arg(flag_t, "-v"), arg(flag_t, "-pa"), arg(flag_t, "-n")],
            iface = "processor_info",
            short = "load binary (executable) file into memory",
            doc_with = "load-binary")

#
# -------------------- save-file --------------------
#

def read_space_or_image(obj, addr, length, initiator=None, inquiry=True):
    try:
        if hasattr(obj.iface, simics.IMAGE_INTERFACE):
            return obj.iface.image.get(addr, length)
        elif hasattr(obj.iface, simics.TRANSACTION_INTERFACE):
            t = simics.transaction_t(inquiry=inquiry, read=True,
                                     initiator=initiator, size=length)
            ex = obj.iface.transaction.issue(t, addr)
            if ex != simics.Sim_PE_No_Exception:
                raise simics.SimExc_Memory(
                    simics.SIM_describe_pseudo_exception(ex))
            return t.data
        elif hasattr(obj.iface, simics.MEMORY_SPACE_INTERFACE):
            return bytes(obj.iface.memory_space.read(initiator, addr, length,
                                                     inquiry))
        elif hasattr(obj.iface, simics.PORT_SPACE_INTERFACE):
            return bytes(obj.iface.port_space.read(initiator, addr, length,
                                                   inquiry))
        else:
            raise Exception(
                f"{obj.name} ({obj.classname}) isn't 'image' or 'memory-space'")
    except Exception as ex:
        raise CliError(f"Failed reading from {obj.name} ({obj.classname})"
                       f" at address {addr:#x}: {ex}")

def check_outside_mem_space_or_image(obj, addr, length, obj_is_image):
    highest = obj.size if obj_is_image else 1 << 64
    if addr + length > highest:
        raise CliError("Access outside highest address in %s" % obj.name)

def check_file_exists(filename, overwrite):
    if not overwrite and os.path.exists(filename):
        raise CliError("File %s already exists." % filename)

def name_space_save_file_cmd(obj, filename, start, length, overwrite):
    check_file_exists(filename, overwrite)
    obj_is_image = hasattr(obj.iface, 'image')
    check_outside_mem_space_or_image(obj, start, length, obj_is_image)
    try:
        f = open(filename, 'wb')
    except Exception as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))
    with f:
        addr = start
        while addr < start + length:
            l = min(start + length - addr, 1024)
            f.write(read_space_or_image(obj, addr, l))
            addr += l
    return command_return("Image contents saved to %s file." % filename)

def save_file_cmd(mem, filename, start, length, overwrite):
    check_file_exists(filename, overwrite)
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    return name_space_save_file_cmd(mem, filename, start, length, overwrite)

new_command("save-file", save_file_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(), "filename"),
             arg(uint64_t, "start"),
             arg(uint64_t, "length"),
             arg(flag_t, "-overwrite")],
            type = ["Memory"],
            short = "save memory contents to a binary file",
            see_also = ["load-file", "<image>.save", "save-image-contents"],
            doc = """
Saves the contents of a memory region, defined by <arg>start</arg> address and
<arg>length</arg> to the file <arg>filename</arg> in binary format.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.

The non-namespace version of the command uses the specified
<arg>object</arg>, with the default being the current frontend
processor's physical memory space. The <cmd
class="image">save-file</cmd> command exists for symmetry with the
other <cmd>save-file</cmd> commands. It is more efficient to use the
<cmd>save-image-contents</cmd> or <cmd class="image">save</cmd> commands.
""")

for ns in ["memory_space", "image"]:
    new_command("save-file", name_space_save_file_cmd,
                [arg(filename_t(), "filename"),
                 arg(uint64_t, "start"),
                 arg(uint64_t, "length"),
                 arg(flag_t, "-overwrite")],
                type = ["Memory", "Disks"],
                iface = ns,
                short = "save memory contents to a binary file",
                see_also = ["load-file", "<image>.save"],
                doc_with = "save-file")

#
# -------------------- load-file --------------------
#

def name_space_load_file_cmd(obj, the_file, base_address):
    try:
        simics.SIM_load_file(obj, the_file, base_address, 0)
    except simics.SimExc_General as ex:
        raise CliError(str(ex))

def load_file_cmd(mem, the_file, base_address):
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    name_space_load_file_cmd(mem, the_file, base_address)

new_command("load-file", load_file_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(exist = 1, simpath = 1), "filename"),
             arg(uint64_t, "offset", "?", 0)],
            type  = ["Memory"],
            see_also = ["load-binary", "add-directory"],
            short = "load file into memory",
            doc = """
Loads the contents of the file named <arg>filename</arg> into the
memory specified by <arg>object</arg> (defaulting to the current
frontend processor's physical memory space), starting at physical
address <arg>offset</arg>. Default offset is 0.

The file specified by <arg>filename</arg> can be either a raw binary
file or a file in the craff format.

The name space versions of the <cmd>load-file</cmd> command can be used to
load a file directly into a memory space or into an image object.

<cmd>load-file</cmd> uses Simics's Search Path and path markers (%simics%,
%script%) to find the file to load. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual
for more information on how Simics's Search Path is used to locate files.
""")

new_command("load-file", name_space_load_file_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename"),
             arg(uint64_t, "offset", "?", 0)],
            iface = "memory_space",
            short = "load file into memory",
            doc_with = "load-file")

new_command("load-file", name_space_load_file_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename"),
             arg(uint64_t, "offset", "?", 0)],
            iface = "image",
            short = "load file into an image",
            doc_with = "load-file")

#
# -------------------- save-intel-obj --------------------
#

def name_space_save_intel_obj_cmd(obj, filename, start, length, skip_zeros,
                                  dirty_only, overwrite, obj32 = False):
    check_file_exists(filename, overwrite)
    obj_is_image = hasattr(obj.iface, 'image')
    if obj_is_image:
        if length is None:
            length = obj.size - start
    else:
        if dirty_only:
            raise CliError("The -dirty-only flag is only available when"
                           " saving image objects.")

    check_outside_mem_space_or_image(obj, start, length, obj_is_image)
    try:
        f = open(filename, 'wb')
    except Exception as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))
    addr_shift = 2 if obj32 else 0
    print_origin = True
    addr = start
    final = start + length
    while addr < final:
        l = min(final - addr, 16)
        if (obj_is_image
            and ((skip_zeros
                  and not simics.CORE_image_page_exists(obj, addr))
                 or (dirty_only
                     and not simics.CORE_image_page_dirty(obj, addr)))):
            # image page size is at least 4k
            next_page = (addr & 0xfffffffffffff000) + 0x1000
            if next_page < final:
                addr = next_page
            else:
                addr += l
            print_origin = True # need to print address again on next iteration
            continue
        data = read_space_or_image(obj, addr, l)
        if skip_zeros and all(x == 0 for x in data):
            print_origin = True # need to print address again on next iteration
            addr += l
            continue
        if print_origin:
            f.write(b"/origin %08x\n" % (addr >> addr_shift))
            print_origin = False
        if obj32:
            data += b"\0" * ((4 - len(data)) % 4) # extend to 32-bit word
            f.write(b" ".join(
                hexlify(data[i * 4:i * 4 + 4][::-1])
                for i in range(len(data) // 4)) + b'\n')
        else:
            f.write(b" ".join([b"%02x" % x for x in data]) + b'\n')
        addr += l
    f.write(b"/eof\n")
    f.close()
    return command_return("Image contents saved to %s file." % filename)

def save_intel_obj_cmd(mem, filename, start, length, skip_zeros, dirty_only,
                       overwrite, obj32 = False):
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    return name_space_save_intel_obj_cmd(mem, filename, start, length,
                                         skip_zeros, dirty_only,
                                         overwrite, obj32)

new_command("save-intel-obj", save_intel_obj_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(), "filename"),
             arg(uint64_t, "start"),
             arg(uint64_t, "length"),
             arg(flag_t, "-skip-zeros"),
             # only on image, but added here since doc is shared
             arg(flag_t, "-dirty-only"),
             arg(flag_t, "-overwrite")],
            type = ["Memory"],
            short = "save memory contents to an Intel .obj file",
            see_also = ["load-intel-obj", "save-intel-32-obj"],
            doc = """
Saves the contents of a memory region, defined by <arg>start</arg> address and
<arg>length</arg> to the file <arg>filename</arg> in the Intel .obj or
.32.obj format.

The <tt>-skip-zeros</tt> argument makes the command skip regions of zeros,
16 bytes or more, in the output file.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.

Due to the flexible mapping support in memory-spaces, it can take a
long time to save large memory areas. The <class>image</class> variant
of the command is much faster, assuming it is used with
<tt>-skip-zeros</tt>.

When used on an image object, the <tt>-dirty-only</tt> argument can be
used to save dirty pages only, i.e. pages which have not been written
to one of the image backing files.

The non-namespace version of the command uses the specified
<arg>object</arg>, defaulting to the current frontend processor's
physical memory space.""")

for ns in ["memory_space", "image"]:
    new_command("save-intel-obj", name_space_save_intel_obj_cmd,
                [arg(filename_t(), "filename"),
                 arg(uint64_t, "start", '?' if ns == "image" else '1', 0),
                 arg(uint64_t, "length", '?' if ns == "image" else '1'),
                 arg(flag_t, "-skip-zeros"),
                 # only on image, but added for both to avoid duplication
                 arg(flag_t, "-dirty-only"),
                 arg(flag_t, "-overwrite")],
                type = ["Memory", "Disks"],
                iface = ns,
                short = "save memory contents to an Intel .obj file",
                see_also = ["load-intel-obj", "save-intel-32-obj"],
                doc_with = "save-intel-obj")

def name_space_save_intel_32_obj_cmd(obj, filename, start, length, skip_zeros,
                                     dirty_only, overwrite):
    return name_space_save_intel_obj_cmd(obj, filename, start, length,
                                         skip_zeros, dirty_only,
                                         overwrite, obj32 = True)

def save_intel_32_obj_cmd(mem, filename, start, length, skip_zeros,
                          dirty_only, overwrite):
    return save_intel_obj_cmd(mem, filename, start, length, skip_zeros,
                              dirty_only, overwrite, obj32 = True)

new_command("save-intel-32-obj", save_intel_32_obj_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(), "filename"),
             arg(uint64_t, "start"),
             arg(uint64_t, "length"),
             arg(flag_t, "-skip-zeros"),
             # only on image, but added here since doc is shared
             arg(flag_t, "-dirty-only"),
             arg(flag_t, "-overwrite")],
            type = ["Memory"],
            short = "save memory contents to an Intel .32.obj file",
            see_also = ["load-intel-obj", "save-intel-obj"],
            doc_with = "save-intel-obj")

for ns in ["memory_space", "image"]:
    new_command("save-intel-32-obj", name_space_save_intel_32_obj_cmd,
                [arg(filename_t(), "filename"),
                 arg(uint64_t, "start", '?' if ns == "image" else '1', 0),
                 arg(uint64_t, "length", '?' if ns == "image" else '1'),
                 arg(flag_t, "-skip-zeros"),
                 arg(flag_t, "-dirty-only"),
                 arg(flag_t, "-overwrite")],
                type = ["Memory", "Disks"],
                iface = ns,
                short = "save memory contents to an Intel .32.obj file",
                see_also = ["load-intel-obj", "save-intel-obj"],
                doc_with = "save-intel-obj")

#
# -------------------- load-intel-obj --------------------
#

def write_space_or_image(obj, addr, byte_list,
                         initiator=None, inquiry=True):
    try:
        if hasattr(obj.iface, simics.IMAGE_INTERFACE):
            obj.iface.image.set(addr, bytes(byte_list))
            return simics.Sim_PE_No_Exception
        elif hasattr(obj.iface, simics.TRANSACTION_INTERFACE):
            t = simics.transaction_t(inquiry=inquiry, data=bytes(byte_list),
                                     write=True, initiator=initiator)
            return obj.iface.transaction.issue(t, addr)
        elif hasattr(obj.iface, simics.MEMORY_SPACE_INTERFACE):
            return obj.iface.memory_space.write(initiator, addr,
                                                byte_list, inquiry)
        elif hasattr(obj.iface, simics.PORT_SPACE_INTERFACE):
            return obj.iface.port_space.write(initiator, addr, byte_list,
                                              inquiry)
        else:
            raise Exception(
                f"{obj.name} ({obj.classname}) isn't 'image' or 'memory-space'")
    except Exception as ex:
        raise CliError(f"Failed writing to {obj.name} ({obj.classname})"
                       f" at address {addr:#x}: {ex}")

def name_space_load_intel_obj_cmd(obj, filename):
    actual_file = SIM_lookup_file(filename)
    if not actual_file:
        raise CliError("File %s not found in search path" % filename)

    err_msg = simics.CORE_load_intel_obj_file(obj, actual_file)
    if err_msg:
        raise CliError(f"Error while loading {filename}: {err_msg}")

def load_intel_obj_cmd(mem, filename):
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    name_space_load_intel_obj_cmd(mem, filename)

new_command("load-intel-obj", load_intel_obj_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Memory"],
            short = "load Intel .obj or .32.obj file into memory",
            see_also = ["load-binary", "load-file", "load-intel-hex",
                        "<memory_space>.load-intel-obj", "add-directory"],
            doc = """
Loads the contents of the file named <arg>filename</arg> into the
memory specified by <arg>object</arg> (defaulting to the current
frontend processor's physical memory space). The file is assumed to be
in the Intel .obj or .32.obj format.

<cmd>load-intel-obj</cmd> uses Simics's Search Path and path markers (%simics%,
%script%) to find the file to load. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual
for more information on how Simics's Search Path is used to locate files.
""")

new_command("load-intel-obj", name_space_load_intel_obj_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Memory"],
            iface = "memory_space",
            short = "load Intel .obj or .32.obj file into memory",
            see_also = ["load-binary", "load-file", "load-intel-hex",
                        "load-intel-obj", "add-directory"],
            doc_with = "load-intel-obj")

new_command("load-intel-obj", name_space_load_intel_obj_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Image"],
            iface = "image",
            short = "load Intel .obj or .32.obj file into an image",
            see_also = ["load-binary", "load-file", "load-intel-hex",
                        "load-intel-obj", "add-directory"],
            doc_with = "load-intel-obj")

#
# -------------------- save-intel-hex --------------------
#

def write_hex_file_line(f, record_type, address, data):
    # data-length, 16-bit address, record-type, data, checksum
    line = b":%02x%04x%02x" % (len(data), address, record_type)
    #line += "".join(["%02x" % ord(x) for x in data])
    line += ensure_binary(hexlify(data))
    line += b"00" # dummy checksum for calculation
    line = line[:-2] + b"%02x\n" % hex_file_checksum(line)
    f.write(line)

def name_space_save_intel_hex_cmd(obj, filename, start, length, skip_zeros,
                                  dirty_only, overwrite):
    check_file_exists(filename, overwrite)
    obj_is_image = hasattr(obj.iface, 'image')
    if obj_is_image:
        if length is None:
            length = obj.size - start
    else:
        if dirty_only:
            raise CliError("The -dirty-only flag is only available when"
                           " saving image objects.")
    check_outside_mem_space_or_image(obj, start, length, obj_is_image)
    try:
        f = open(filename, 'wb')
    except Exception as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))
    addr = start
    prev_high_address = -1
    final = start + length
    while addr < final:
        # up to 16 bytes per line (standard allows for more)
        l = min(final - addr, 16)
        if (obj_is_image
            and ((skip_zeros
                  and not simics.CORE_image_page_exists(obj, addr))
                 or (dirty_only
                     and not simics.CORE_image_page_dirty(obj, addr)))):
            # image page size is at least 4k
            next_page = (addr & 0xfffffffffffff000) + 0x1000
            if next_page < final:
                addr = next_page
            else:
                addr += l
            continue
        data = read_space_or_image(obj, addr, l)
        if skip_zeros and all(x == 0 for x in data):
            addr += l
            continue
        high_address = (addr >> 16) & 0xffff
        low_address = addr & 0xffff
        if high_address != prev_high_address:
            # record-type 4 "extended address"
            write_hex_file_line(
                f, 4, 0,
                bytes((high_address >> 8,)) + bytes((high_address & 0xff,)))
            prev_high_address = high_address
            # record-type 0 "data"
        write_hex_file_line(f, 0, low_address, data)
        addr += l
    # record-type 1 "end of file"
    write_hex_file_line(f, 1, 0, b"")
    f.close()
    return command_return("Image contents saved to %s file." % filename)

def save_intel_hex_cmd(mem, filename, start, length, skip_zeros, dirty_only,
                       overwrite):
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    return name_space_save_intel_hex_cmd(mem, filename, start, length,
                                         skip_zeros, dirty_only, overwrite)

new_command("save-intel-hex", save_intel_hex_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(), "filename"),
             arg(uint64_t, "start"),
             arg(uint64_t, "length"),
             arg(flag_t, "-skip-zeros"),
             # only on image, but added here since doc is shared
             arg(flag_t, "-dirty-only"),
             arg(flag_t, "-overwrite")],
            type = ["Memory"],
            short = "save memory contents to an Intel HEX file",
            see_also = ["load-intel-hex"],
            doc = """
Saves the contents of a memory region, defined by <arg>start</arg> address and
<arg>length</arg> to the file <arg>filename</arg> in the Intel HEX file
format.

The <tt>-skip-zeros</tt> argument makes the command skip regions of zeros,
16 bytes or more, in the output file.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.

Due to the flexible mapping support in memory-spaces, it can take a
long time to save large memory areas. The <class>image</class> variant
of the command is much faster, assuming it is used with
<tt>-skip-zeros</tt>.

When used on an image object, the <tt>-dirty-only</tt> argument can be
used to save dirty pages only, i.e. pages which have not been written
to one of the image backing files.

The non-namespace version of the command uses the specified
<arg>object</arg>, defaulting to the current frontend processor's
physical memory space.""")

for ns in ["memory_space", "image"]:
    new_command("save-intel-hex", name_space_save_intel_hex_cmd,
                [arg(filename_t(), "filename"),
                 arg(uint64_t, "start", '?' if ns == "image" else '1', 0),
                 arg(uint64_t, "length", '?' if ns == "image" else '1'),
                 arg(flag_t, "-skip-zeros"),
                 # only on image, but added for both to avoid duplication
                 arg(flag_t, "-dirty-only"),
                 arg(flag_t, "-overwrite")],
                type = ["Memory", "Disks"],
                iface = ns,
                short = "save memory contents to an Intel HEX file",
                see_also = ["load-intel-hex"],
                doc_with = "save-intel-hex")

#
# -------------------- load-intel-hex --------------------
#

def hex_file_checksum(line):
    sum = 0
    check_line = line[1:-2]
    for i in range(0, len(check_line), 2):
        sum += int(check_line[i:i+2], 16)
    return -sum & 0xff

def check_hex_byte_cnt(byte_count, expected, field, line_number):
    if byte_count != expected:
        raise CliError('Byte count should be %d in %s record on line %d'
                       % (expected, field, line_number))

def parse_hex_file_line(filename, line, line_number):
    if not re.match(':[0-9a-fA-F]{10,}', line):
        raise CliError('Malformed data in file %s on line %d.' %
                       (filename, line_number))

    byte_count = int(line[1:3], 16)
    address = int(line[3:7], 16)
    record_type = int(line[7:9], 16)
    checksum = int(line[-2:], 16)
    data = line[9:-2]

    line_checksum = hex_file_checksum(line)
    if line_checksum != checksum:
        raise CliError("Incorrect checksum 0x%x on line %d (expected 0x%x)"
                       % (checksum, line_number, line_checksum))

    if record_type == 1:
        check_hex_byte_cnt(byte_count, 0, "end of file", line_number)
    elif record_type == 2:
        check_hex_byte_cnt(byte_count, 2, "ext. segment address", line_number)
    elif record_type == 3:
        check_hex_byte_cnt(byte_count, 4, "start segment address", line_number)
    elif record_type == 4:
        check_hex_byte_cnt(byte_count, 2, "ext. linear address", line_number)
    elif record_type == 5:
        check_hex_byte_cnt(byte_count, 4, "start linear address", line_number)
    elif record_type != 0:
        raise CliError("Unsupported record type %d in file %s on line %d"
                       % (record_type, filename, line_number))
    if len(data) != byte_count * 2:
        raise CliError("Incorrect data length in file %s on line %d"
                       % (filename, line_number))

    return (record_type, address, data)

def name_space_load_intel_hex_cmd(obj, filename):
    actual_file = SIM_lookup_file(filename)
    if not actual_file:
        raise CliError("File %s not found in search path" % filename)
    try:
        f = open(actual_file, 'r')
    except Exception as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))

    got_eof = False
    high_address = 0
    low_address = 0

    with f:
        for (line_number, line) in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            (record_type, data_address, data) = parse_hex_file_line(
                filename, line, line_number)
            if record_type == 1:
                got_eof = True
            elif record_type == 2:
                # extended segment address
                low_address = int(data, 16) << 4
            elif record_type == 4:
                # extended linear address
                high_address = int(data, 16) << 16
            elif record_type == 0:
                # data
                addr = high_address | (low_address + data_address)
                seq = [int(data[i:i+2], 16) for i in range(0, len(data), 2)]
                write_space_or_image(obj, addr, tuple(seq))
        if not got_eof:
            raise CliError("No end of file record found in %s" % filename)

def load_intel_hex_cmd(mem, filename):
    if not mem or hasattr(mem.iface, 'processor_info'):
        cpu = mem if mem else current_cpu_obj()
        mem = cpu.iface.processor_info.get_physical_memory()
        if not mem:
            raise CliError(f"No physical memory associated with {cpu.name}")
    name_space_load_intel_hex_cmd(mem, filename)

new_command("load-intel-hex", load_intel_hex_cmd,
            [arg(obj_t('object', ('processor_info', 'memory_space', 'image')),
                 "object", "?"),
             arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Memory"],
            short = "load Intel HEX file into memory",
            see_also = ["load-binary", "load-file", "load-intel-obj",
                        "<memory_space>.load-intel-hex", "add-directory"],
            doc = """
Loads the contents of the file named <arg>filename</arg> into the
memory specified by <arg>object</arg> (defaulting to the current
frontend processor's physical memory space). The file is assumed to be
in the Intel HEX format.

<cmd>load-intel-obj</cmd> uses Simics's Search Path and path markers (%simics%,
%script%) to find the file to load. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual
for more information on how Simics's Search Path is used to locate files.
""")

new_command("load-intel-hex", name_space_load_intel_hex_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Memory"],
            iface = "memory_space",
            short = "load Intel HEX file into memory",
            see_also = ["load-binary", "load-file", "load-intel-hex",
                        "load-intel-obj", "add-directory"],
            doc_with = "load-intel-hex")

new_command("load-intel-hex", name_space_load_intel_hex_cmd,
            [arg(filename_t(exist = 1, simpath = 1), "filename")],
            type = ["Image"],
            iface = "image",
            short = "load Intel HEX file into an image",
            see_also = ["load-binary", "load-file", "load-intel-hex",
                        "load-intel-obj", "add-directory"],
            doc_with = "load-intel-hex")

def load_vmem_cmd(obj, filename, start, word_size, be):
    def parse_vmem_line(filename, line, line_number):
        match = re.match(r'(@(?P<address>[0-9a-fA-F]+))?'
                         r'(?P<data>(\s*[0-9a-fA-F]{2,})+)?$', line)
        if not match:
            raise CliError('Malformed data in file %s on line %d.' %
                           (filename, line_number))
        data = match.groupdict()
        if data['data']:
            # Avoid creating list of all matches
            blocks = (x.group(0) for x in re.finditer(r"[0-9a-fA-F]{2,}",
                                                      data['data']))
        else:
            blocks = []
        return (data['address'], blocks)

    line_strip = re.compile(r"/\*.*\*/|//.*")
    offset_words = 0
    offset = 0
    print_bad_data_warning = True

    actual_file = SIM_lookup_file(filename)
    if not actual_file:
        raise CliError("File %s not found in search path" % filename)

    try:
        f = open(actual_file, 'r')
    except IOError as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))
    with f:
        # Don't read the whole file at once - read line after line:
        for (line_num, line) in enumerate(f, 1):
            # Remove comments (TODO: allow multiline comments):
            line = line_strip.sub("", line).strip()
            if not line:
                continue

            (address, blocks) = parse_vmem_line(filename, line, line_num)
            # Continue at current offset unless specified
            if address:
                offset_words = int(address, 16)
                offset = 0

            for block in blocks:
                b = bytearray.fromhex(block if len(block) % 2 == 0
                                      else "0" + block)
                if word_size is None:
                    word_size = len(b)
                    print("No word size was specified. Using autodetected"
                          f" word size: {word_size} byte(s).")

                if len(b) < word_size:
                    b = bytearray(word_size - len(b)) + b
                elif len(b) > word_size:
                    if print_bad_data_warning:
                        print(f"{filename}:{line_num}: malformed data item"
                              f" ('{block}') doesn't fit into the word size"
                              f" which is {word_size}. Truncating this data"
                              " item and any other too large items which"
                              " may be seen in the file.")
                        print_bad_data_warning = False  # warn only once
                    b = b[:word_size]
                if not be:
                    b.reverse()
                write_space_or_image(
                    obj, start + offset_words*word_size + offset, tuple(b))
                offset += len(b)  # move forward by the number of bytes written

def save_vmem_cmd(obj, filename, start, length, bytes_per_line,
                  skip_offsets, skip_zeros, be, overwrite):
    check_file_exists(filename, overwrite)
    obj_is_image = hasattr(obj.iface, 'image')
    highest = obj.size if obj_is_image else 1 << 64
    max_size = highest - start + 1
    if length == 0:
        length = max_size
    check_outside_mem_space_or_image(obj, start, length, obj_is_image)

    # We do some alignment checks here to ensure that the generated file
    # is valid: e.g., that it can be parsed correctly by the load-vmem command.
    # It looks that having the word-size parameter instead of
    # the bytes-per-line parameter would make more sense.
    if (start % bytes_per_line) != 0:
        raise CliError(
            f"The 'offset' argument ({start:#x}) must be a multiple"
            f" of the 'bytes-per-line' argument ({bytes_per_line:#x}).")
    if ((start + length) % bytes_per_line) != 0:
        raise CliError(
            f"The sum of the 'offset' argument ({start:#x}) and"
            f" the 'length' argument ({length:#x}) must be a multiple of"
            f" the 'bytes-per-line' argument ({bytes_per_line}).")

    try:
        f = open(filename, 'w')
    except Exception as ex:
        raise CliError("Failed to open file '%s': %s" % (filename, ex))

    with f:
        offset = start
        include_offset = offset > 0
        while offset < min(start + length, max_size):
            l = min(start + length - offset, bytes_per_line)
            data = read_space_or_image(obj, offset, l)
            if skip_zeros and all(x == 0 for x in data):
                include_offset = True
                offset += l
                continue

            if not be:
                data = data[::-1]
            if not include_offset and skip_offsets:
                print(f"{data.hex()}", file=f)
            else:
                print(f"@{(offset - start)//bytes_per_line:x} {data.hex()}",
                      file=f)
            offset += l
            include_offset = False
    return command_return("Memory contents saved to %s file." % filename)

for (ns, tp) in [("memory_space", "Memory"), ("image", "Image")]:
    new_command("load-vmem", load_vmem_cmd,
                [arg(filename_t(exist = 1, simpath = 1), "filename"),
                 arg(uint64_t, "offset", "?", 0),
                 arg(uint_t, "word-size", "?", None),
                 arg(flag_t, "-b")],
                type = [tp],
                iface = ns,
                short = "load Verilog VMEM file into memory",
                see_also = ["<%s>.save-vmem" % ns,
                            "<%s>.load-intel-hex" % ns],
                doc = """
Loads the contents of the Verilog VMEM file <arg>filename</arg> into
memory. Simics tries to guess the word size based on the number of digits
it sees in the numbers, but this is only a guess. One can specify
the word size by passing the <arg>word-size</arg> argument.

Offsets in the file are interpreted relative to
<arg>offset</arg> and as multiples of <arg>word-size</arg>.

By default, numbers are assumed to be in little endian format. For example,
the following Verilog VMEM file contains the data which will be
loaded at address 0x1000:
<pre>
@00000400 48656D6C 6F2C2057 6F726C64 0AFFFFFF
</pre>

Byte of the memory at address 0x1000 will get value 0x6c and byte at
address 0x1001 will get value 0x6d. If <tt>-b</tt> is specified,
numbers are instead interpreted in big endian format and byte at address 0x1000
will get value 0x48.

This command uses Simics's Search Path and path markers (%simics%,
%script%) to find the file to load. Refer to <cite>The Command Line
Interface</cite> chapter of the <cite>Simics User's Guide</cite> manual
for more information on how Simics's Search Path is used to locate files.
""")

    new_command("save-vmem", save_vmem_cmd,
                [arg(filename_t(), "filename"),
                 arg(uint64_t, "offset", "?", 0),
                 arg(uint64_t, "length", "?", 0),
                 arg(uint_t, "bytes-per-line", "?", 16),
                 arg(flag_t, "-skip-offsets"),
                 arg(flag_t, "-skip-zeros"),
                 arg(flag_t, "-b"),
                 arg(flag_t, "-overwrite")],
                type = [tp],
                iface = ns,
                short = "save VMEM file of memory",
                see_also = ["<%s>.load-vmem" % ns,
                            "<%s>.save-intel-hex" % ns],
                doc = """
Saves <arg>length</arg> bytes of the memory at offset
<arg>offset</arg> to the file named <arg>filename</arg>, in the
Verilog VMEM format.

If <arg>length</arg> is 0, the whole memory content from <arg>offset</arg> is
stored.

The <arg>bytes-per-line</arg> argument specifies how many bytes to
write on each line, defaulting to 16. Each line is written in little
endian format, unless <tt>-b</tt> is specified, in which big endian
format is used. An explicit offset is written on each line, unless
<tt>-skip-offsets</tt> is specified, in which case only necessary
offsets are written. If <tt>-skip-zeros</tt> is specified, lines with
only zero data will not be written.

The command will fail if the destination file already exists, unless
<tt>-overwrite</tt> is specified.
""")

#
# -------------------- other memory-space commands --------------------
#

def get_memory_space_info(obj):
    return [(None,
             [("Snoop device", obj.snoop_device),
              ("Timing model", obj.timing_model)])]

new_info_command("memory-space", get_memory_space_info)
new_status_command("memory-space", lambda obj: None)

new_info_command("port-space", lambda obj: None)
new_status_command("port-space", lambda obj: None)

new_command("set", obj_set_cmd,
            [arg(uint64_t,"address"),
             arg(poly_t('value', int_t, list_t), "value"),
             arg(range_t(1, MAX_SIZE_GET_SET_CMDS,
                         f"1..{MAX_SIZE_GET_SET_CMDS}"), "size", "?", 4),
             arg(flag_t,"-l"), arg(flag_t,"-b"), arg(flag_t, "-t")],
            type = ["Image"],
            short = "set bytes in image to specified value",
            see_also = ["set", "get", "signed"],
            iface = "image",
            doc = """
Sets <arg>size</arg> bytes in an image at offset <arg>address</arg> to
<arg>value</arg>. The default <arg>size</arg> is 4 bytes, but can be anywhere
between 1 and 8 inclusive.

If <arg>value</arg> is larger than the specified size, an error is given.
This can be ignored with the <tt>-t</tt> flag, which will truncate the
value to size bytes.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian and
big-endian byte order, respectively. If neither is given, the byte order of the
currently selected processor is used.""")

new_command("get", obj_get_cmd,
            [arg(uint64_t,"address"),
             arg(range_t(
                 1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
                 "size", "?", 4),
             arg(flag_t,"-l"), arg(flag_t,"-b")],
            type = ["Image"],
            short = "get bytes from image",
            see_also = ["set", "get", "signed"],
            iface = "image",
            doc = """
Returns <arg>size</arg> bytes from an image at offset
<arg>address</arg>. The default <arg>size</arg> is 4 bytes, but can be
anywhere between 1 and 8 inclusive.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian and
big-endian byte order, respectively. If neither is given, the byte order of the
currently selected processor is used.""")
