# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import ast
import copy
import os
import re

import simics


from . import coverage_data
from . import common
from . import html_report
from . import combine_reports
from .xt_prop_parser import (contains_xt_prop, get_xt_prop_exec_ranges)

class AnalyzerModeNotHandledException(Exception):
    pass

class Analyzer:
    def __init__(self, cov_data, log_func, data_label_patterns):
        self.cov_data = cov_data
        self.tcf = simics.SIM_get_debugger()
        self.log = log_func
        self.data_label_patterns = data_label_patterns
        self.__set_arm_mapping_symbols_re()
        self.file_id_types = {}
        # Disassembly flags are sticky, re-use last flag unless there is an
        # update to flag. This is because ARM binaries only have $a and $t
        # symbols once format changes.
        self.da_flags = common.Disassemble_Flag_None
        self.normalized_paths = {}
        self.cached_addr_src = {}
        self.cached_addr_end = -1  # Inclusive, -1 means no cache.

    def __load_report(self, report_file):
        return coverage_data.from_raw_file(report_file)

    def read_report(self, report_file, ignore_addresses):
        if self.cov_data is None:
            self.cov_data = self.__load_report(report_file)
        else:
            report = self.__load_report(report_file)
            combine_reports.combine_two(self.cov_data, report, ignore_addresses)

    def __get_prioritized_list_of_cpu_classes(self, mapping):
        local_cpu_classes = mapping.get('cpu_classes', [])
        global_cpu_classes = self.cov_data.get('cpu_classes', [])
        lower_prio_cpu_classes = list(set(global_cpu_classes)
                                      - set(local_cpu_classes))
        return local_cpu_classes + lower_prio_cpu_classes

    def __get_class_for_disassembling_file(self, file_id, mapping):
        previous_disassembly_class = mapping.get('disassembly_class')
        if previous_disassembly_class:
            return previous_disassembly_class

        for cpu_class in self.__get_prioritized_list_of_cpu_classes(mapping):
            (err, handled) = self.tcf.iface.debug_internal.can_disassemble_file(
                cpu_class, file_id)
            if err != simics.Debugger_No_Error:
                self.log(f'Cannot disassemble {cpu_class} using interface:'
                         f' {handled}')
            elif handled:
                return cpu_class
        return None

    def __disassemble_using_class(self, file_id, cpu_class, file_offset, size,
                                  addr):
        (err, da_buf) = self.tcf.iface.debug_internal.disassemble_file_buffer(
            cpu_class, file_id, file_offset, size, addr, self.da_flags)
        if self.da_flags and err == simics.Debugger_Unknown_Id:
            # This will happen when the mode specified by flags is not handled
            # by the class. For example ARM mode on a Cortex-m class.
            raise AnalyzerModeNotHandledException(
                'Could not disassemble {cpu_class} with {self.da_flags} flags')
        if err != simics.Debugger_No_Error:
            raise common.CodeCoverageException(
                f'Failed to disassemble using {cpu_class}: {da_buf}')
        return da_buf

    def __set_used_disassembly_class(self, mapping, cpu_class):
        previous_da_class = mapping.get('disassembly_class')
        if previous_da_class is None:
            mapping['disassembly_class'] = cpu_class
            return

        assert previous_da_class == cpu_class, 'disassembly_class changed'

    def __init_disassembly(self, file_id, file_offset, size, addr):
        (err, err_str) = self.tcf.iface.debug_internal.init_disassemble(
            file_id, file_offset, size, addr, self.da_flags)
        if err != simics.Debugger_No_Error:
            raise common.CodeCoverageException(
                "Unable to initialize disassembly: %s" % err_str)

    def __disassembly_info(self, cc_helper, file_id, mapping, file_offset, size,
                           section_address):
        cpu_class = self.__get_class_for_disassembling_file(file_id, mapping)
        if cpu_class:
            da_buf = self.__disassemble_using_class(file_id, cpu_class,
                                                    file_offset, size,
                                                    section_address)
            self.__set_used_disassembly_class(mapping, cpu_class)
            return da_buf

        cpu_classes = mapping.get('cpu_classes')
        if cpu_classes:
            self.__report_missing_cpu_classes_exception(mapping, cpu_classes)
        # Fall back to disassemble object
        self.__init_disassembly(file_id, file_offset, size, section_address)
        (err, res) = cc_helper.iface.code_coverage.disassemble(self.tcf,
                                                               file_id)
        if err != simics.Debugger_No_Error:
            raise common.CodeCoverageException(
                "Failed to disassemble: %s" % res)
        return res

    def __contains_error(self, errors, error_type):
        for e in errors:
            if e[0] == error_type:
                return True
        return False

    def __remove_errors(self, errors, error_type):
        err_indexes = []
        for (i, e) in enumerate(errors):
            if e[0] == error_type:
                err_indexes.append(i)
        err_indexes.reverse()
        for i in err_indexes:
            errors.pop(i)

    def __handle_file_errors(self, mapping, err, file_id):
        if err is not simics.Debugger_No_Error:
            errors = mapping.setdefault("errors", [])
            if not self.__contains_error(errors, common.CC_Error_Opening_File):
                errors.append([common.CC_Error_Opening_File, file_id])
            return False
        # Remove previous file open error if we can open the file.
        if self.__contains_error(mapping.get("errors", []),
                                 common.CC_Error_Opening_File):
            self.__remove_errors(mapping["errors"],
                                 common.CC_Error_Opening_File)
            if not mapping["errors"]:
                # Remove errors if empty
                mapping.pop("errors")

        return True

    def __report_code_coverage_exception(self, mapping, e, err_type):
        mapping.setdefault("errors", list()).append(
            [err_type, str(e)])

    def __report_disassemble_exception(self, mapping, e):
        self.__report_code_coverage_exception(mapping, e,
                                              common.CC_Error_Disassemble)

    def __report_functions_exception(self, mapping, e):
        self.__report_code_coverage_exception(mapping, e,
                                              common.CC_Error_Functions)

    def __report_source_info_exception(self, mapping, e):
        self.__report_code_coverage_exception(mapping, e,
                                              common.CC_Error_Source_Info)

    def __report_first_code_coverage_exception_of_type(self, mapping, e,
                                                       err_type):
        errors = mapping.get('errors')
        if errors:
            for (entry_err_type, _) in errors:
                if entry_err_type == err_type:
                    return
        self.__report_code_coverage_exception(mapping, e, err_type)

    def __report_missing_cpu_classes_exception(self, mapping, cpu_classes):
        msg = ('Disassembly not supported by any of the classes collected with:'
               f' {cpu_classes}')
        self.__report_first_code_coverage_exception_of_type(
            mapping, msg, common.CC_Error_Missing_Disassembly_Classes)

    def __mapping_str(self, mapping):
        return "%s @ 0x%x" % (mapping["map"]["symbol_file"],
                              mapping["map"]["address"])

    def __section_info_in_error(self, section):
        addr = section["address"]
        size = section['size']
        range_str = "0x%x-0x%x" % (addr, addr + size - 1)
        name = section.get('name')
        if name:
            return "(%s @ %s)" % (name, range_str)
        return "(%s)" % range_str

    def __arm_disassembly_flags(self, symbol):
        if symbol.startswith("$a"):
            return common.Disassemble_Flag_ARM
        if symbol.startswith("$t"):
            return common.Disassemble_Flag_Thumb
        if symbol.startswith("$x"):
            return common.Disassemble_Flag_Aarch64
        return common.Disassemble_Flag_None

    # Returned section_end is exclusive.
    def __get_exec_section_range(self, mapping, section, address, size):
        if not section['executable']:
            return (None, None)
        section_start = section["address"]
        # end is exclusive
        section_end = section["address"] + section['size']
        if (section_end <= address
            or section_start >= address + size):
            # section outside of mapping
            return (None, None)

        if section_start < address:
            self.__report_disassemble_exception(
                mapping, "A mapping starts at 0x%x which is in the"
                " middle of a section %s, only the section part"
                " inside the mapping is disassembled"
                % (address, self.__section_info_in_error(section)))
            section_start = address
        if section_end > address + size:
            self.__report_disassemble_exception(
                mapping, "A mapping ends at 0x%x which is in the middle"
                " of a section %s, only the section part inside the"
                " mapping is disassembled"
                % (address + size,
                   self.__section_info_in_error(section)))
            section_end = address + size
        return (section_start, section_end)

    def __append_to_removed_data(self, removed_data, file_id, file_offs,
                                 start_addr, range_size, reason):

        range_data = removed_data.setdefault(start_addr, {})
        range_data["size"] = range_size

        if file_id and range_size:
            fn = common.filename_for_file_ctx(file_id)
            try:
                with open(fn, "rb") as f:
                    f.seek(file_offs)
                    data_bytes = f.read(range_size)
            except OSError as e:
                raise common.CodeCoverageException(
                    f'Failed reading from file with context id "{file_id}":'
                    f' {e}')

        if data_bytes:
            range_data["data"] = tuple(data_bytes)

        if reason:
            range_data["reason"] = reason


    def __remove_data_unhandled_mode(self, file_id, mapping, start_addr,
                                     range_size, file_offs, functions,
                                     data_labels, removed_data):
        try:
            self.__append_to_removed_data(removed_data, file_id, file_offs,
                                          start_addr, range_size,
                                          "unhandled_mode")
        finally:
            if start_addr in functions:
                data_labels[start_addr] = functions.pop(start_addr)

            self.__report_disassemble_exception(
                mapping, 'Removed data at 0x%x-0x%x as it could not'
                ' be disassembled using the current class'
                % (start_addr, start_addr + range_size - 1))

    def __remove_data(self, mapping, removed_data, file_id, file_offs,
                      start_addr, range_size):
        self.__append_to_removed_data(removed_data, file_id, file_offs,
                                      start_addr, range_size, "data")
        for addr in range(start_addr, start_addr + range_size):
            if addr in mapping.get('covered', {}):
                self.__report_disassemble_exception(
                    mapping, "execution in data range"
                    f" 0x{start_addr:x}-0x{start_addr + range_size:x}")
                break

    def __add_disassembly_one_mapping(self, cc_helper, path_maps, mapping,
                                      by_function):
        symbol_file = mapping['map']['symbol_file']
        mapped_section = mapping['map'].get('section')
        relocation = mapping['map']['relocation']
        address = mapping['map']['address']
        size = mapping['map']['size']
        functions = mapping.get('functions', {})
        data_labels = mapping.get('data_labels', {})
        removed_data = mapping.get('removed_data', {})
        arm_mapping_symbols = mapping.get('arm_mapping_symbols', {})
        exec_ranges = mapping.get('exec_ranges', [])

        with open_debug_symbol_file(
                symbol_file, relocation, path_maps, mapped_section) as (
                    err, file_id):
            if not self.__handle_file_errors(mapping, err, file_id):
                return
            file_iface = self.tcf.iface.debug_symbol_file
            (err, sections) = file_iface.sections_info(file_id)
            if err != simics.Debugger_No_Error:
                raise common.CodeCoverageException(
                    "Failed to get section information: %s" % sections)
            assert sections[0] in ("PE", "ELF")
            for section in sections[1]:
                (section_start, section_end) = self.__get_exec_section_range(
                    mapping, section, address, size)
                if section_start is None:
                    continue
                exec_ranges_data = [r[0] for r in exec_ranges if
                                    r[2] == common.ExecProps.NON_EXEC]
                exec_ranges_insn = [r[0] for r in exec_ranges if
                                    r[2] != common.ExecProps.NON_EXEC]
                if by_function and (functions or data_labels
                                    or arm_mapping_symbols):
                    function_addrs = common.function_start_addresses_in_range(
                        set(functions) | set(data_labels)
                        | set(arm_mapping_symbols)
                        | set(exec_ranges_data) | set(exec_ranges_insn),
                        section_start, section_end - 1, True)
                else:
                    # Data labels are not handled here, that requires by
                    # function handling in order to work.
                    function_addrs = [section_start]
                for (start_addr, end_addr) in zip(
                        function_addrs, function_addrs[1:] + [section_end]):
                    range_size = end_addr - start_addr
                    if range_size == 0:
                        continue
                    if (start_addr in data_labels
                        or start_addr in exec_ranges_data):
                        self.__remove_data(
                            mapping, removed_data, file_id,
                            section['offset'] + start_addr - section_start,
                            start_addr, range_size)
                        continue
                    if start_addr in arm_mapping_symbols:
                        self.da_flags = self.__arm_disassembly_flags(
                            arm_mapping_symbols[start_addr].get("name", ""))

                    try:
                        range_info = self.__disassembly_info(
                            cc_helper, file_id, mapping,
                            section['offset'] + start_addr - section_start,
                            range_size, start_addr)
                    except AnalyzerModeNotHandledException:
                        self.__remove_data_unhandled_mode(
                            file_id, mapping, start_addr, range_size,
                            section['offset'] + start_addr - section_start,
                            functions, data_labels, removed_data)
                        continue
                    info = mapping.setdefault('info', [])
                    info += range_info

        if removed_data:
            mapping["removed_data"] = removed_data
        if data_labels and not mapping.get('data_labels'):
            mapping["data_labels"] = data_labels

    def __machine_has_disassemble_module(self, machine):
        return machine in ('X86', 'X86-64', 'ARM', 'AARCH64')

    def can_disassemble(self, path_maps):
        "Will return True if any symbol file can be disassembled"
        all_mappings = self.cov_data.get('mappings', [])
        if not all_mappings:
            return False
        for mapping in all_mappings:
            symbol_file = mapping['map'].get('symbol_file')
            if symbol_file is None:
                # No disassembly for mapping with unknown symbol file
                continue
            relocation = mapping['map']['relocation']
            with open_debug_symbol_file(
                    symbol_file, relocation, path_maps, None) as (err, file_id):
                if err is not simics.Debugger_No_Error:
                    continue
                (err, info) = self.tcf.iface.debug_symbol_file.symbol_file_info(
                    file_id)
                if err is not simics.Debugger_No_Error:
                    continue

                if self.__get_class_for_disassembling_file(
                        file_id, mapping) is not None:
                    return True

                (binary_type, file_data) = info
                if binary_type not in ('ELF', 'PE'):
                    continue
                machine = file_data.get('machine')
                if self.__machine_has_disassemble_module(machine):
                    return True
        return False

    def __remove_source_info_errors_from_mapping(self, mapping):
        common.remove_errors_of_type_from_mapping(
            mapping, common.CC_Error_Source_Info)

    def __remove_disassemble_errors_from_mapping(self, mapping):
        for err_type in common.disassembly_error_types():
            common.remove_errors_of_type_from_mapping(mapping, err_type)

    def __remove_functions_errors_from_mapping(self, mapping):
        common.remove_errors_of_type_from_mapping(
            mapping, common.CC_Error_Functions)

    def add_disassembly(self, cc_helper, path_maps, by_function):
        all_mappings = self.cov_data.setdefault('mappings', [])
        if not all_mappings:
            return (False, "No mappings")
        new_added = False
        added_info = False
        for mapping in all_mappings:
            if 'info' in mapping:
                # Already got disassembly
                continue
            if mapping['map']['symbol_file'] is None:
                # No disassembly for mapping with unknown symbol file
                continue
            self.log('Adding disassembly for %s' % self.__mapping_str(mapping))
            self.__remove_disassemble_errors_from_mapping(mapping)
            try:
                self.__add_disassembly_one_mapping(cc_helper, path_maps,
                                                   mapping, by_function)
            except common.CodeCoverageException as e:
                self.__report_disassemble_exception(mapping, e)
            new_added = True
            if 'info' in mapping:
                added_info = True

        if not new_added:
            return (False,
                    "Disassembly information already exists for all mappings")
        if not added_info:
            return (False,
                    "No disassembly information was added")
        return (True, None)

    def __is_arm_file(self, file_id):
        cached_type = self.file_id_types.get(file_id)
        assert cached_type is not None
        return cached_type == "ARM" or cached_type == "AARCH64"

    def __set_arm_mapping_symbols_re(self):
        # $d = data is handled as a data label.
        # match "$<symbol>", "$<symbol>.*" or "$v*" where <symbol> is a, t or x.
        #
        # Information about mapping symbols can be found at:
        # https://developer.arm.com/documentation/dui0474/m/
        #   accessing-and-managing-symbols-with-armlink/about-mapping-symbols
        self.arm_mapping_symbols_re = re.compile(r"^\$([atx]($|\.)|(v.*))")

    def __is_arm_mapping_symbol(self, name):
        if name is None:
            return False
        return self.arm_mapping_symbols_re.match(name) is not None

    def __is_data_label_name(self, name, file_id):
        if not name:
            return False
        for pattern in self.data_label_patterns:
            if pattern.match(name):
                return True
        if (self.__is_arm_file(file_id) and
            (name == "$d" or name.startswith("$d."))):
            # Hard code $d as data for ARM binaries in the same way as other
            # symbols starting with $ that are specified as ARM mapping symbols.
            # The documentation (see reference in __set_arm_mapping_symbols_re)
            # also mentions $d.realdata so interpret all $d.* as data as well.
            return True
        return False

    def __function_info(self, mapping, file_id, module_address, module_size,
                        keep_data):
        def initial_underscores(name):
            count = 0
            while len(name) > 0 and name[0] == "_":
                count += 1
                name = name[1:]
            return count

        def fun_in_range(addr, start, end):
            return addr >= start and addr < end
        debug_iface = self.tcf.iface.debug_symbol
        (err, err_or_funs) = debug_iface.list_functions(file_id)
        if err != simics.Debugger_No_Error:
            raise common.CodeCoverageException("Unable to get function list: %s"
                                    % err_or_funs)
        functions = dict()
        data_labels = dict()
        arm_mapping_symbols = dict()
        for entry in err_or_funs:
            addr = entry["address"]
            if not fun_in_range(addr, module_address,
                                module_address + module_size):
                continue
            name = entry.get("symbol")
            if (not keep_data and entry["size"] == 0
                and self.__is_data_label_name(name, file_id)):
                data_labels[addr] = {'name': name}
            elif (self.__is_arm_file(file_id)
                  and self.__is_arm_mapping_symbol(name)):
                arm_mapping_symbols[addr] = {'name': name}
            else:
                if addr in functions:
                    func_entry = functions[addr]
                    # If multiple entries at same address and one has size zero,
                    # ignore that one.
                    if entry["size"] == 0:
                        continue
                    if func_entry["size"] != 0:
                        if func_entry["size"] != entry["size"]:
                            self.__report_functions_exception(
                                mapping,
                                f"Multiple functions at address 0x{addr:x}"
                                " with different size:"
                                f' "{functions[addr]["name"]}" and "{name}"')
                            # Keep the one with largest size
                            if func_entry["size"] > entry["size"]:
                                continue
                        # Keep the one with least initial underscores
                        if (initial_underscores(name) >=
                            initial_underscores(func_entry["name"])):
                            continue
                functions[addr] = {'name': name, 'size': entry["size"]}

        # Remove data labels that are also present in functions. This can occur
        # if there is both a data symbol and an other symbol at an address and
        # TCF treats both these symbols as functions.
        for data_addr in data_labels:
            if data_addr in functions:
                del functions[data_addr]

        return (functions, data_labels, arm_mapping_symbols)

    def __get_exec_ranges(self, file_id):
        if contains_xt_prop(file_id, self.log):
            return get_xt_prop_exec_ranges(file_id, self.log)
        return None

    # Function returns True on success and False on error.
    def __set_file_type(self, mapping, file_id):
        if self.file_id_types.get(file_id) is not None:
            # Already cached.
            return True

        (err, file_info) = self.tcf.iface.debug_symbol_file.symbol_file_info(
            file_id)
        if not self.__handle_file_errors(mapping, err, file_id):
            return False
        # First element of file_info is symbol file type, second element is
        # dictionary with info specific to the type, "machine" key exists in
        # info for both ELF and PE.
        self.file_id_types[file_id] = file_info[1]["machine"]
        return True

    def __add_functions_one_mapping(self, path_maps, mapping, keep_data):
        symbol_file = mapping['map']['symbol_file']
        mapped_section = mapping['map'].get('section')
        relocation = mapping['map']['relocation']
        address = mapping['map']['address']
        size = mapping['map']['size']

        if self.__error_opening_symbol_file(mapping):
            return

        with open_debug_symbol_file(
                symbol_file, relocation, path_maps, mapped_section) as (
                    err, file_id):
            if not self.__handle_file_errors(mapping, err, file_id):
                return
            if not self.__set_file_type(mapping, file_id):
                return
            (functions, data_labels,
             arm_mapping_symbols) = self.__function_info(
                 mapping, file_id, address, size, keep_data)
            if functions:
                mapping['functions'] = functions
            if data_labels:
                mapping['data_labels'] = data_labels
            if arm_mapping_symbols:
                mapping['arm_mapping_symbols'] = arm_mapping_symbols
            # Some architectures can define properties for different ranges in
            # the code, such as instruction, data etc. See if the binary has
            # such data and extract it in that case for better disassembly
            # output.
            exec_ranges = self.__get_exec_ranges(file_id)
            if exec_ranges:
                mapping['exec_ranges'] = exec_ranges

    def add_functions(self, path_maps, keep_data):
        all_mappings = self.cov_data.setdefault('mappings', [])
        if not all_mappings:
            return (False, "No mappings")
        new_added = False
        added_function = False
        for mapping in all_mappings:
            if 'functions' in mapping or 'data_labels' in mapping:
                # Already added functions
                continue
            if mapping['map']['symbol_file'] is None:
                # No functions for mapping with unknown symbol file
                continue
            self.log('Adding functions for %s%s' % (
                self.__mapping_str(mapping),
                " (keeping data)" if keep_data else ""))
            self.__remove_functions_errors_from_mapping(mapping)
            try:
                self.__add_functions_one_mapping(path_maps, mapping, keep_data)
            except common.CodeCoverageException as e:
                self.__report_functions_exception(mapping, e)
            new_added = True
            if 'functions' in mapping or 'data_labels' in mapping:
                added_function = True
        if not new_added:
            return (False, "Functions have already been added for all mappings")
        if not added_function:
            return (False, "No functions were added, missing symbol info?")
        keep_data_feature_is_set = self.cov_data['features'].get('keep_data',
                                                                 False)
        if keep_data and not keep_data_feature_is_set:
            self.cov_data['features']['keep_data'] = True
        elif not keep_data and keep_data_feature_is_set:
            self.cov_data['features'].pop('keep_data')
        return (True, None)

    def __error_opening_symbol_file(self, mapping):
        errors = mapping.get("errors", [])
        file_not_found = False
        for (err_code, _) in errors:
            if err_code == common.CC_Error_Opening_File:
                file_not_found = True
                break
        return file_not_found

    def normalize_path(self, org_path):
        if not org_path:
            return org_path
        cached_path = self.normalized_paths.get(org_path)
        if cached_path:
            return cached_path

        first_fwd = org_path.find('/')
        first_back = org_path.find('\\')
        if first_fwd < 0:
            if first_back < 0:
                # No separators, use provided path.
                self.normalized_paths[org_path] = org_path
                return org_path
            separator = '\\'
        else:
            if first_back < 0 or first_fwd < first_back:
                separator = '/'
            else:
                separator = '\\'

        if separator == '\\':
            # For Windows paths, replace any forward slash with back slash as
            # the forward slash is not a valid character in a Windows path.
            new_path = org_path.replace('/', separator)
            # Keep multiple initial slashes on Windows as that indicates a
            # network drive or similar.
            kept_initial_slashes = (len(new_path)
                                    - len(new_path.lstrip(separator)))
        else:
            new_path = org_path
            kept_initial_slashes = 0

        # replace double slashes with single
        new_path = new_path[kept_initial_slashes:]
        while separator * 2 in new_path:
            parts = new_path.split(separator * 2)
            new_path = separator.join(parts)

        new_path = separator * kept_initial_slashes + new_path

        # Remove "/./" and
        parts = new_path.split(separator)
        while '.' in parts:
            parts.remove('.')

        initial_dotdots = 0
        # Replace /x/y/.. with /x
        while '..' in parts[initial_dotdots:]:
            idx = parts[initial_dotdots:].index('..')
            if idx == 0:
                initial_dotdots += 1
            else:
                del parts[idx + initial_dotdots]
                del parts[idx + initial_dotdots - 1]

        new_path = separator.join(parts)

        self.normalized_paths[org_path] = new_path
        return new_path

    def __file_name_to_index(self, file_table, fn):
        for (file_id, file_name) in file_table.items():
            if file_name == fn:
                return file_id
        file_id = "%d" % len(file_table)
        file_table[file_id] = fn
        return file_id

    def __cache_addrs_to_src(self, ctx_id, addr_range, cc_helper):
        (ok, addr_src) = cc_helper.iface.code_coverage.addr_range_source(
            self.tcf, ctx_id, addr_range)
        self.log('Caching address source for range 0x%x-0x%x: %s' % (
            addr_range[0], addr_range[-1],
            "%d addresses" % len(addr_src) if ok else addr_src))
        if not ok:
            return (simics.Debugger_Lookup_Failure, addr_src)
        self.cached_addr_src = addr_src
        self.cached_addr_end = addr_range[-1]
        return (simics.Debugger_No_Error, None)

    def __clear_addr_src_cache(self):
        self.cached_addr_src = []
        self.cached_addr_end = -1

    def __address_source_no_range(self, ctx_id, addr, addr_info, index,
                                  cc_helper):
        # Use a C helper function to cache many address to source lookups at
        # once, for performance reasons.
        if addr > self.cached_addr_end:
            nr_addrs_to_cache = 50000
            new_end = min(index + nr_addrs_to_cache, len(addr_info))
            addrs_to_cache = [x["address"] for x in addr_info[index: new_end]]
            (err, err_str) = self.__cache_addrs_to_src(ctx_id, addrs_to_cache,
                                                       cc_helper)
            if err != simics.Debugger_No_Error:
                return (err, err_str)
        src = self.cached_addr_src.get(addr)
        if src:
            return (simics.Debugger_No_Error, src)

        return (simics.Debugger_Source_Not_Found,
                "No source found for 0x%x" % addr)

    def __add_source_info_one_mapping(self, cc_helper, path_maps, mapping):
        if self.__error_opening_symbol_file(mapping):
            return
        self.__remove_source_info_errors_from_mapping(mapping)
        addr_info = mapping.get('info')
        if addr_info is None:
            raise common.CodeCoverageException(
                "Coverage report must have disassembly information before"
                " adding source information")
        symbol_file = mapping['map']['symbol_file']
        mapped_section = mapping['map'].get('section')
        relocation = mapping['map']['relocation']
        file_table = mapping.setdefault('file_table', {})
        self.__clear_addr_src_cache()
        with open_debug_symbol_file(
                symbol_file, relocation, path_maps, mapped_section) as (
                    err, file_id):
            if not self.__handle_file_errors(mapping, err, file_id):
                return
            self.log('Adding source info for %s: %d entries'
                     % (self.__mapping_str(mapping), len(addr_info)))
            for (index, entry) in enumerate(addr_info):
                if index and index % 50000 == 0:
                    self.log("At entry %d" % index)
                (err, err_or_line_info) = self.__address_source_no_range(
                    file_id, entry['address'], addr_info, index, cc_helper)
                if err != simics.Debugger_No_Error:
                    # No source information available, usually for
                    # instructions that are used as padding of functions.
                    continue
                filename = self.normalize_path(err_or_line_info["filename"])
                start_line = err_or_line_info["start-line"]
                executable_lines = entry.setdefault('executable_lines', {})
                executable_lines[start_line] = True
                entry['file_id'] = self.__file_name_to_index(
                    file_table, filename)
                addr_info[index] = entry

    def add_source_info(self, cc_helper, path_maps):
        all_mappings = self.cov_data.setdefault('mappings', [])
        if not all_mappings:
            return (False, "No mappings")
        new_added = False
        added_source_info = False
        for mapping in all_mappings:
            if mapping.get("file_table"):
                # Already got source information.
                continue
            try:
                self.__add_source_info_one_mapping(cc_helper, path_maps,
                                                   mapping)
            except common.CodeCoverageException as e:
                self.__report_source_info_exception(mapping, e)
            new_added = True
            if mapping.get("file_table"):
                added_source_info = True
        if not new_added:
            return (False,
                    "Source info has already been added for all mappings")
        if not added_source_info:
            return (False, "No source info was added, missing symbol info?")
        return (True, None)

    def __addr_src_cb(self, data, code_area):
        (src_info, file_table) = data
        src_file = code_area.get('filename')
        line = code_area.get('start-line')
        start_addr = code_area.get('start-address')
        end_addr = code_area.get('end-address')
        if (line is None or start_addr is None or end_addr is None
            or not src_file):
            return
        assert end_addr >= start_addr

        filename = self.normalize_path(src_file)
        file_id = self.__file_name_to_index(file_table, filename)
        lines = src_info.setdefault(file_id, {})
        line_to_ranges = lines.setdefault(line, [])

        line_to_ranges.append([start_addr, end_addr])

    def __add_source_only_info_one_mapping(self, cc_helper, path_maps, mapping):
        symbol_file = mapping['map']['symbol_file']
        mapped_section = mapping['map'].get('section')
        relocation = mapping['map']['relocation']
        map_address = mapping['map']['address']
        map_size = mapping['map']['size']
        with open_debug_symbol_file(
                symbol_file, relocation, path_maps, mapped_section) as (
                    err, file_id):
            if not self.__handle_file_errors(mapping, err, file_id):
                return
            file_iface = self.tcf.iface.debug_symbol_file
            (err, sections) = file_iface.sections_info(file_id)
            if err != simics.Debugger_No_Error:
                raise common.CodeCoverageException(
                    "Failed to get section information: %s" % sections)
            assert sections[0] in ("PE", "ELF")
            symbol_iface = self.tcf.iface.debug_symbol
            file_table = mapping.setdefault('file_table', {})
            src_info = mapping.setdefault('src_info', {})
            for section in sections[1]:
                (start_addr, end_addr) = self.__get_exec_section_range(
                    mapping, section, map_address, map_size)
                if start_addr is None:
                    continue
                (err, err_msg) = symbol_iface.address_source(
                    file_id, start_addr, end_addr - start_addr,
                    self.__addr_src_cb, (src_info, file_table))
                if err != simics.Debugger_No_Error:
                    self.__report_source_info_exception(
                        mapping, "Address to source lookup failed for section"
                        " '%s' at 0x%x-0x%x"
                        % (section.get('name', '<unknown>'), start_addr,
                           end_addr))

    def add_source_only_info(self, cc_helper, path_maps):
        all_mappings = self.cov_data.setdefault('mappings', [])
        if not all_mappings:
            return (False, "No mappings")
        new_added = False
        added_source_info = False
        for mapping in all_mappings:
            if mapping.get("src_info") or mapping.get('file_table'):
                # Already got source only information.
                continue
            try:
                self.__add_source_only_info_one_mapping(cc_helper, path_maps,
                                                        mapping)
            except common.CodeCoverageException as e:
                self.__report_source_info_exception(mapping, e)
            new_added = True
            if mapping.get("src_info"):
                added_source_info = True
        if not new_added:
            return (False,
                    "Source info has already been added for all mappings")
        if not added_source_info:
            return (False, "No source info was added, missing symbol info?")
        return (True, None)

class open_debug_symbol_file:
    def __init__(self, file_name, relocation, path_maps, section):
        tcf = simics.SIM_get_debugger()
        self.symbol_iface = tcf.iface.debug_symbol_file
        self.file_name = html_report.path_map(tcf, file_name, path_maps)
        self.relocation = relocation
        self.file_id = None
        self.section = section
    def __enter__(self):
        if self.section:
            (err, file_id_or_err) = self.symbol_iface.open_symbol_section(
                self.file_name, self.section, self.relocation, False)
        else:
            (err, file_id_or_err) = self.symbol_iface.open_symbol_file(
                self.file_name, self.relocation, False)

        self.file_id = (file_id_or_err if err == simics.Debugger_No_Error
                        else None)
        return (err, file_id_or_err)
    def __exit__(self, exc_type, exc_value, traceback):
        if self.file_id is None:
            return
        (err, err_str) = self.symbol_iface.close_symbol_file(self.file_id)
        if err != simics.Debugger_No_Error and exc_type is None:
            raise common.CodeCoverageException("Unable to close file: %s (%s)"
                                    % (self.file_name, err_str))
