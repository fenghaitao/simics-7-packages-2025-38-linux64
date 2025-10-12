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

import simics
from enum import IntEnum

CC_Error_Opening_File = 1
CC_Error_Disassemble = 2
CC_Error_Functions = 3
CC_Error_Source_Info = 4
CC_Error_Other = 5
CC_Error_Missing_Disassembly_Classes = 6

# Same as in agent_interfaces.h, for which enums do not get Python wrapped.
# Make sure to keep these in sync.
Disassemble_Flag_None = 0
Disassemble_Flag_ARM = 1
Disassemble_Flag_Thumb = 2
Disassemble_Flag_Aarch64 = 4

class ExecProps(IntEnum):
    EXEC = 1
    NON_EXEC = 2
    UNKNOWN = 3

def disassembly_error_types():
    return (CC_Error_Disassemble, CC_Error_Missing_Disassembly_Classes)

# If there is only one context in the list, then return that context.
# If the context lists contains multiple contexts with one common
# parent, plus the parent itself then return that parent context.
# For other cases when there is no common parent available a failure
# will be returned.
# Success is returned as (True, context) and failure is returned as
# (False, error msg).
def get_unique_ctx(tcf, contexts):
    if len(contexts) == 0:
        return (False, "No context found")

    if len(contexts) == 1:
        return (True, contexts[0])

    query_iface = tcf.iface.debug_query
    possible_top = list()
    for ctx_id in contexts:
        (err_code, parent_id) = query_iface.get_context_parent(ctx_id)
        if ((err_code != simics.Debugger_No_Error)
            or (parent_id not in contexts)):
            # Either reached the root node so no parent could be found
            # or found a node that has no parent among the contexts.
            possible_top.append(ctx_id)

    no_unique_err_str = "Could not find unique context tree"
    if len(possible_top) != 1:
        return (False, no_unique_err_str)

    top_id = possible_top[0]
    (err_code, tree_query) = query_iface.query_for_context_tree(top_id)
    if err_code != simics.Debugger_No_Error:
        return (False, no_unique_err_str + ": " + tree_query)

    (err_code, all_children) = query_iface.matching_contexts(tree_query)
    if err_code != simics.Debugger_No_Error:
        return (False, no_unique_err_str + ": " + all_children)

    # Check so that all contexts are under the top_id tree, otherwise
    # the top_id will not be a unique parent to all other contexts.
    for ctx_id in contexts:
        if ctx_id not in all_children:
            return (False, no_unique_err_str)

    return (True, top_id)

class CodeCoverageException(Exception):
    pass

def init_disassembly(tcf, file_id, file_offset, size, addr):
    (err, err_str) = tcf.iface.debug_internal.init_disassemble(
        file_id, file_offset, size, addr)
    if err != simics.Debugger_No_Error:
        raise CodeCoverageException("Unable to initialize disassembly: %s"
                                % err_str)

# The end address is inclusive
def function_start_addresses_in_range(function_addrs, start_addr, end_addr,
                                      include_range_start):
    assert function_addrs
    addrs_in_range = []
    function_at_start = False
    for addr in function_addrs:
        if start_addr <= addr <= end_addr:
            if addr == start_addr:
                function_at_start = True
            addrs_in_range.append(addr)
    if include_range_start and not function_at_start:
        # Include start of section as well.
        addrs_in_range = [start_addr] + addrs_in_range
    return sorted(addrs_in_range)

def remove_errors_of_type_from_mapping(mapping, type_to_remove):
    errors = mapping.get('errors')
    if not errors:
        return

    to_remove = []
    for (i, (err_type, _)) in enumerate(errors):
        if err_type == type_to_remove:
            to_remove.append(i)

    to_remove.reverse()
    for i in to_remove:
        errors.pop(i)
    # Remove 'errors' key if all errors have been removed.
    if not errors:
        mapping.pop('errors')

def filename_for_file_ctx(file_id):
    debugger = simics.SIM_get_debugger()
    (e, fn) = debugger.iface.debug_query.context_name(file_id)
    if e != simics.Debugger_No_Error:
        raise CodeCoverageException(
            f'Could not get filename from "{file_id}" file context.')
    return fn
