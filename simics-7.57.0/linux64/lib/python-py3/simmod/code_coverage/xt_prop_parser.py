# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from enum import IntFlag
import simics
from .common import (ExecProps, filename_for_file_ctx)

class ParseException(Exception):
    pass

class MissingSection(ParseException):
    pass


# Values have been retrieved from binutils-gdb: include/elf/xtensa.h
class XTProps(IntFlag):
    LITERAL = 0x0001
    INSN = 0x0002
    DATA = 0x0004
    UNREACHABLE = 0x0008
    INSN_LOOP_TARGET = 0x0010
    INSN_BRANCH_TARGET = 0x0020
    INSN_NO_DENSITY = 0x0040
    INSN_NO_REORDER = 0x0080
    NO_TRANSFORM = 0x0100
    BT_ALIGN_MASK = 0x600
    ALIGN = 0x800
    ALIGNMENT_MASK = 0x1f000
    INSN_ABSLIT = 0x20000


class SimicsXTPropParser:
    def __init__(self, file_id, log_func):
        self.log_func = log_func
        self.addr_width = None

        self._parse_xt_prop_exec_ranges(file_id)

    @staticmethod
    def flags_to_exec_prop(flags):
        if flags & XTProps.INSN:
            return ExecProps.EXEC
        if flags & (XTProps.DATA | XTProps.UNREACHABLE | XTProps.LITERAL):
            return ExecProps.NON_EXEC
        # Other flags shouldn't be alone
        return ExecProps.UNKNOWN


    @staticmethod
    def describe_flags(flags):
        desc = []
        if flags & XTProps.LITERAL:
            desc.append("lit")
        if flags & XTProps.INSN:
            desc.append("insn")
        if flags & XTProps.DATA:
            desc.append("data")
        if flags & XTProps.UNREACHABLE:
            desc.append("unreach")
        if flags & XTProps.INSN_LOOP_TARGET:
            desc.append("loop_target")
        if flags & XTProps.INSN_BRANCH_TARGET:
            desc.append("branch_target")
        if flags & XTProps.INSN_NO_DENSITY:
            desc.append("no_density")
        if flags & XTProps.INSN_NO_REORDER:
            desc.append("no_reorder")
        if flags & XTProps.NO_TRANSFORM:
            desc.append("no_transform")
        if flags & XTProps.BT_ALIGN_MASK:
            desc.append("bt_alignment")
        if flags & XTProps.ALIGN:
            desc.append("alignment")
        if flags & XTProps.ALIGNMENT_MASK:
            desc.append("alignment_mask")
        if flags & XTProps.INSN_ABSLIT:
            desc.append("insn_abslit")
        return ",".join(desc)


    @staticmethod
    def get_xt_prop_section(file_id):
        sect_name = ".xt.prop"
        debugger = simics.SIM_get_debugger()

        filename = filename_for_file_ctx(file_id)
        (e, section_data) = debugger.iface.debug_symbol_file.sections_info(
            file_id)
        if e != simics.Debugger_No_Error:
            raise ParseException(
                f'Failed to get sections info for {filename}": {section_data}')

        (t, sections) = section_data
        # We only care about ELF files for .xt.prop
        if t != 'ELF':
            raise MissingSection(f'Not an ELF file: {filename}')

        wanted_sections = [s for s in sections if s.get('name') == sect_name]
        if not wanted_sections:
            raise MissingSection(f"No .xt.props section found in {filename}")

        if len(wanted_sections) > 1:
            raise ParseException(f'Multiple {sect_name} sections in {filename}')

        return wanted_sections[0]

    @staticmethod
    def describe_exec_prop(exec_prop):
        if exec_prop == ExecProps.EXEC:
            return "executable"
        elif exec_prop == ExecProps.NON_EXEC:
            return "not executable"
        return "unknown"

    def log(self, msg, lvl):
        self.log_func(f".xt.prop parser: {msg}", lvl)

    def _read_raw_xt_prop(self, file_id):
        import simics
        debugger = simics.SIM_get_debugger()
        sect_name = ".xt.prop"

        # The context name matches the file name for a context opened with
        # debug_symbol_file.open_symbol_file.
        (e, filename) = debugger.iface.debug_query.context_name(file_id)
        if e != simics.Debugger_No_Error:
            raise ParseException(
                f'Could not get filename for file context {file_id}')

        (e, file_info) = debugger.iface.debug_symbol_file.symbol_file_info(
            file_id)
        if e != simics.Debugger_No_Error:
            raise ParseException(f"Failed to get file info for {filename}:"
                                 f" {file_info}")
        addr_width = file_info[1].get('address-width')
        if not addr_width:
            raise ParseException(f"Failed to get address width for {filename}")
        if addr_width % 8 != 0:
            raise ParseException(
                f"Bad address width for {filename}: {addr_width}")


        sect = self.get_xt_prop_section(file_id)

        file_offs = sect.get('offset')
        if not file_offs:
            raise ParseException(
                f'Bad or no section offset for {sect_name} in {filename}')

        sect_size = sect.get('size')
        if not sect_size:
            raise ParseException(
                f'Bad or no section size for {sect_name} in {filename}')

        try:
            with open(filename, "rb") as f:
                f.seek(file_offs)
                if f.tell() != file_offs:
                    raise ParseException(
                        f"Failed to seek to position 0x{file_offs:x}"
                        f" in {filename}")
                raw_buf = f.read(sect_size)
                if len(raw_buf) != sect_size:
                    raise ParseException(
                        f"Failed to read {sect_size} bytes from {sect_name}"
                        f" at 0x{file_offs:x} in {filename}")
        except OSError as e:
            raise ParseException(f'filename: {e}')

        return (raw_buf, addr_width)


    def _raw_data_to_props(self, raw_buf, file_id):
        assert self.addr_width and self.addr_width % 8 == 0
        int_size = self.addr_width // 8
        flag_size = 4
        prop_size = int_size * 2 + flag_size
        props = []
        if len(raw_buf) % prop_size != 0:
            raise ParseException("Bad size of .xt.prop section in"
                                 f" {filename_for_file_ctx(file_id)},"
                                 f" not a multiple of {prop_size}")

        byte_order = "little"
        while raw_buf:
            addr = int.from_bytes(raw_buf[0:int_size], byte_order)
            size = int.from_bytes(raw_buf[int_size:2 * int_size], byte_order)
            flags = int.from_bytes(raw_buf[2 * int_size:prop_size], byte_order)
            raw_buf = raw_buf[prop_size:]
            if size == 0:
                # Skip any zero-sized property, unclear why they exist
                self.log(f"Ignoring property of size 0 at 0x{addr:x},"
                          f" flags: {self.describe_flags(flags)}", 3)
                continue
            self.log(f"Inserting 0x{addr:x}-0x{addr+size:x}:"
                     f" {self.describe_flags(flags)}", 4)

            props.append((addr, size, flags))

        if not props:
            return []

        props.sort(key=lambda x: x[0])
        return props

    def _props_to_exec_ranges(self, props):
        def insert_range(exec_ranges, start, end, exec_prop):
            self.log(f"Inserting range 0x{start:x}-0x{end:x} "
                     f" {self.describe_exec_prop(exec_prop)}", 4)
            exec_ranges.append((start, end - start, exec_prop))

        if not props:
            return []

        last_exec_prop = None
        start = None
        prev_end = None
        exec_ranges = []

        for (addr, size, flags) in props:
            self.log(f"property of size {size} at 0x{addr:x},"
                     f" flags: {self.describe_flags(flags)}", 4)
            exec_prop = self.flags_to_exec_prop(flags)
            if exec_prop == ExecProps.UNKNOWN:
                self.log(f"Unknown property at 0x{addr:x}-0x{addr + size:x},"
                         f" flags: {self.describe_flags(flags)}", 2)
            if last_exec_prop is None:
                # First time
                start = addr
                prev_end = addr + size
                last_exec_prop = exec_prop
                continue

            if addr < prev_end:
                self.log(f"Overlapping ranges: 0x{addr:x}-0x{addr + size:x}"
                         f" overlaps with 0x{start:x}-0x{prev_end:x}", 3)
                addr = prev_end

            if exec_prop == last_exec_prop and prev_end == addr:
                # Can combine
                prev_end = addr + size
                continue

            assert addr >= prev_end
            insert_range(exec_ranges, start, prev_end, last_exec_prop)
            if addr > prev_end:
                self.log("A hole in .xt.prop ranges at"
                         f" 0x{prev_end:x}-0x{addr:x}", 3)
                # A hole in the known ranges
                exec_ranges.append((prev_end, addr - prev_end,
                                    ExecProps.UNKNOWN))

            last_exec_prop = exec_prop
            prev_end = addr + size
            start = addr

        if start >= prev_end:
            self.log(f"Incorrect start 0x{start:x} and end 0x{prev_end:x}"
                     " addresses at end of range", 1)
        else:
            # Last property in list, needs to be inserted
            insert_range(exec_ranges, start, prev_end, last_exec_prop)

        assert sorted(exec_ranges, key=lambda x: x[0]) == exec_ranges
        for (i, e) in enumerate(exec_ranges[:-1]):
            if e[0] + e[1] != exec_ranges[i + 1][0]:
                self.log(f"End of index {i} not matching start of {i + 1}:"
                         f" 0x{e[0] + e[1]:x} != 0x{exec_ranges[i + 1][0]:x}",
                         1)
        return exec_ranges

    def _parse_xt_prop_exec_ranges(self, file_id):
        (raw_buf, addr_width) = self._read_raw_xt_prop(file_id)
        self.addr_width = addr_width
        props = self._raw_data_to_props(raw_buf, file_id)
        self.props = props
        self.exec_ranges = self._props_to_exec_ranges(props)

    @staticmethod
    def format_without_enum(exec_ranges):
        """Convert enum flags to int flags in exec_ranges, which is on the
        format [(addr, size, flags),..]"""
        return [(a, s, f.value) for (a, s, f) in exec_ranges]

    def get_exec_ranges(self):
        return self.format_without_enum(self.exec_ranges)


def contains_xt_prop(file_id, logger):
    try:
        SimicsXTPropParser.get_xt_prop_section(file_id)
    except MissingSection:
        return False
    except ParseException as e:
        logger(str(e), level=1)
        return False
    return True


def get_xt_prop_exec_ranges(file_id, logger):
    try:
        parsed_props = SimicsXTPropParser(file_id, logger)
    except (MissingSection, ParseException) as e:
        logger(str(e), level=1)
        return None
    return parsed_props.get_exec_ranges()
