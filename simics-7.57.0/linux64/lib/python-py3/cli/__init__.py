# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


'''The cli module contains the API for interacting with the Simics
Command Line Interface.'''

# interface module, re-exporting stuff from cli_impl.py

# see reference manual for list of supported symbols

# This module is part of the 'python cli' API.
__simicsapi_doc_id__ = 'python cli'

# All modules in the CLI package
from . import tokenizer, tee, number_utils

# documented and supported
__simics_api__ = [
    "addr_t",
    "arg",
    "bool_t",
    "boolean_t",
    "CliError",
    "command_quiet_return",
    "command_return",
    "command_verbose_return",
    "filename_t",
    "flag_t",
    "float_t",
    "get_available_object_name",
    "get_output_grouping",
    "get_output_radix",
    "global_cmds",
    "int_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "int8_t",
    "integer_t",
    "ip_port_t",
    "list_t",
    "new_command",
    "new_info_command",
    "new_status_command",
    "nil_t",
    "number_str",
    "obj_t",
    "object_expander",
    "poly_t",
    "quiet_run_command",
    "range_t",
    "register_command_category",
    "run_command",
    "set_output_grouping",
    "set_output_radix",
    "simenv",
    "sint16_t",
    "sint32_t",
    "sint64_t",
    "sint8_t",
    "str_number",
    "str_t",
    "string_set_t",
    "uint_t",
    "uint16_t",
    "uint32_t",
    "uint64_t",
    "uint8_t",
]

from .errors import (
    CliError
)

from .number_utils import (
    number_str, str_number,
    # undocumented but should be supported
    set_output_radix, get_output_radix,
    get_output_grouping, set_output_grouping,
)

from .impl import (
    arg,
    get_available_object_name,
    new_command, new_info_command, new_status_command,
    object_expander,
    run_command, quiet_run_command,
    global_cmds, simenv,
    addr_t, bool_t, filename_t, flag_t, float_t, boolean_t,
    int8_t, int16_t, int32_t, int64_t,
    sint8_t, sint16_t, sint32_t, sint64_t,
    uint8_t, uint16_t, uint32_t, uint64_t,
    nil_t, poly_t, int_t, uint_t, integer_t,
    list_t, obj_t, range_t, ip_port_t, str_t, string_set_t,
    command_return, command_quiet_return, command_verbose_return,
    register_command_category, get_primary_cmdline
)

# undocumented but should be supported
from .impl import (
    get_completions,
    get_component_object,
    CliQuietError,
    interactive_command,
    current_frontend_object, set_current_frontend_object,
    current_cpu_obj, current_cpu_obj_null,
    current_step_obj, current_step_obj_null,
    current_cycle_obj, current_cycle_obj_null,
    current_step_queue, current_step_queue_null,
    current_cycle_queue, current_cycle_queue_null,
    current_ps_queue_null,
    object_exists,
    output_modes,
    quiet_run_function,
)

# unsupported internal symbols
from .impl import (
    is_component, is_top_component,
    is_connector,
    CliBreakError, CliContinueError,
    old_is_component, old_is_drive,
    terminal_width, terminal_height,
    cmdline_run_command, cmdline_set_size,
    get_synopsis, get_synopses,
    cpu_expander, file_expander,
    assert_not_running, distributed_simulation,
    Markup,
    pr,  # kept in cli just for compatibility, should go to simics
    complete_command_prefix,
    expand_path_markers,
    format_print,
    format_seconds,
    print_columns,
    tab_completions,
    hap_c_arguments,
    format_commands_as_html,
    format_commands_as_cli,
    simics_commands, get_simics_command,
    matches_class_or_iface,
    new_operator,
    register_cmdline,
    other_cmdline_active,
    current_cmdline_interactive,
    disable_command_repeat,
    set_interactive_command_ctx,
    get_repeat_data, set_repeat_data,
    get_current_cmdline,
    get_script_pos,
    set_cmdline,
    async_cmdline,
    primary_cmdline,
    print_info,
    print_wrap_code,
    get_last_loaded_module,
    resolve_script_path,
    simics_command_exists,
    get_current_locals,
    Just_Right, Just_Center, Just_Left,
    get_format_string,
    add_class_func, get_obj_func,
    format_attribute,
    stop_traceback, simics_print_stack,
    get_component_path,
    current_component,
    current_namespace,
    set_current_namespace,
    visible_objects,
    get_object,
    common_prefix,
    register_new_filename_validator,
    doc,
    enable_tech_preview, disable_tech_preview,
    tech_preview_enabled, tech_preview_exists, add_tech_preview,
    enable_unsupported, disable_unsupported,
    unsupported_enabled, unsupported_exists, add_unsupported,
    enable_cmd, disable_cmd, BOTH_ENABLED_AND_DISABLED,
    get_class_commands,
    get_iface_commands,
    get_object_commands,
    use_old_object_naming,
    expand_expression_to_dnf,
    new_unsupported_command, new_tech_preview_command,
    check_variable_name,
    get_shortest_unique_object_names
)

# Script branch functions. Most should be documented and become supported.
from script_branch import (
    script_pipe_has_data, script_pipe_get_data,
    check_valid_script_pipe,
    check_script_branch_command,
    create_script_barrier, reset_script_barrier,
    script_barrier_ready, add_script_barrier_branch,
    script_barrier_limit, update_script_barrier_limit, script_barrier_count,
    check_valid_script_barrier,
    create_script_pipe, script_pipe_add_data,
    sb_create,
    sb_get_wait_id, sb_wait, sb_signal_waiting, sb_wait_for_hap,
    sb_run_in_main_branch, sb_in_main_branch, sb_interrupt_branch,
    script_branch_flag_doc, sb_wait_for_log, sb_wait_for_breakpoint,
    sb_wait_for_step, sb_wait_for_cycle, sb_wait_for_time,
    sb_wait_for_global_time, sb_wait_for_global_sync,
    sb_wait_for_register_read, sb_wait_for_register_write,
    sb_wait_for_simulation_started, sb_wait_for_simulation_stopped,
    sb_wait_for_notifier,
)

# We support 'from cli import *'. When this is used also include conf.
import conf

# force help() to list all contents
__all__ = sorted(k for k in locals() if not k.startswith('_'))
