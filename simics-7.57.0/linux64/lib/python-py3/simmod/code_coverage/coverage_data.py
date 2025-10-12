# -*- Python -*-

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

import os
import ast
import pickle
from . import common

def add_mapping(report, symbol_file, addr, size, file_offset, file_size,
                relocation, section):
    if symbol_file:
        map_info = {'symbol_file': symbol_file, 'address': addr, 'size': size,
                    'file_offset': file_offset, 'file_size': file_size,
                    'relocation': relocation}
        if section is not None:
            map_info['section'] = section
        target_mappings = 'mappings'
    else:
        map_info = {'address': addr, 'size': size}
        target_mappings = 'unknown_mappings'
    for mapping in report.get(target_mappings, []):
        if mapping['map'] == map_info:
            return
    report.setdefault(target_mappings, []).append({'map': map_info})

def add_addr_to_entry(report, addr, count, access_count, cpu_class):
    def max_1_if_not_access_count(val):
        if (not access_count) and val > 1:
            return 1
        return val

    for map_kind in ('mappings', 'unknown_mappings'):
        for mapping in report.get(map_kind, []):
            if addr_is_in_mapping(mapping, addr):
                covered = mapping.setdefault('covered', {})
                covered[addr] = max_1_if_not_access_count(
                    covered.setdefault(addr, 0) + count)
                if cpu_class is not None:
                    cpu_classes = mapping.setdefault('cpu_classes', [])
                    if cpu_class not in cpu_classes:
                        cpu_classes.append(cpu_class)
                return
    unknown = report.setdefault('unknown', {})
    unknown[addr] = unknown.setdefault(addr, 0) + count

def should_be_included_in_cpu_classes(cpu_class, known_cpu_classes):
    return known_cpu_classes.get(cpu_class, False)

def add_executed_addresses(report, classes, access_count, known_cpu_classes):
    for (cpu_class, addrs) in classes.items():
        if not should_be_included_in_cpu_classes(cpu_class, known_cpu_classes):
            cpu_class = None
        for (addr, count) in addrs.items():
            add_addr_to_entry(report, addr, count, access_count, cpu_class)

def addr_is_in_mapping(mapping, addr):
    start = mapping['map']['address']
    end = start + mapping['map']['size']
    return addr >= start and addr < end

def add_branch_to_entry(report, addr, taken, not_taken):
    # Branches for unknown and missing mappings are ignored.
    for mapping in report.get('mappings', []):
        start = mapping['map']['address']
        end = start + mapping['map']['size']
        if addr >= start and addr < end:
            mapping.setdefault('branches', {})[addr] = {
                "taken": taken, "not_taken": not_taken}
            return
    unknown_branches = report.setdefault('unknown_branches', {})
    unknown_branches[addr] = {"taken": taken, "not_taken": not_taken}

def add_branches(report, branches):
    for (addr, (taken, not_taken)) in branches.items():
        add_branch_to_entry(report, addr, taken, not_taken)

def to_raw_file(file_name, overwrite, report):
    to_raw_pickle_file(file_name, overwrite, report)

def from_raw_file(file_name):
    return from_raw_pickle_file(file_name)

def to_raw_python_file(file_name, overwrite, report):
    if os.path.exists(file_name) and not overwrite:
        raise common.CodeCoverageException(
            "The file already exists: %s" % file_name)
    with open(file_name, 'w') as f:
        f.write('# -*- Python -*-\n' + repr(report) + '\n')

def from_raw_python_file(file_name):
    if not os.path.exists(file_name):
        raise common.CodeCoverageException(
            "The file does not exist: %s" % file_name)

    f = open(file_name, 'r', newline=None)
    with f:
        s = f.read()
        if s.startswith('# -*- Python -*-'):
            try:
                coverage = ast.literal_eval(s)
            except SyntaxError as e:
                raise common.CodeCoverageException(str(e))
            return coverage
        else:
            raise common.CodeCoverageException('Unknown file format')

def to_raw_pickle_file(file_name, overwrite, report):
    if os.path.exists(file_name) and not overwrite:
        raise common.CodeCoverageException(
            "The file already exists: %s" % file_name)
    with open(file_name, 'wb') as f:
        try:
            pickle.dump(report, f, pickle.HIGHEST_PROTOCOL)
        except pickle.PickleError as e:
            if os.path.exists(file_name):
                f.close()
                os.remove(file_name)
            raise common.CodeCoverageException(str(e))

def from_raw_pickle_file(file_name):
    if not os.path.exists(file_name):
        raise common.CodeCoverageException(
            "The file does not exist: %s" % file_name)
    with open(file_name, 'rb') as f:
        try:
            coverage = pickle.load(f)  # nosec
        except pickle.PickleError as e:
            raise common.CodeCoverageException(str(e))
        return coverage
