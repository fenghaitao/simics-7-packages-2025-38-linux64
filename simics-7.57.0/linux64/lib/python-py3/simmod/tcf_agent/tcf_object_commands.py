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

import cli
import simics
from simicsutils.host import is_windows
from . import tcf_common as tcfc


def agent_info(obj):
    return [(None, [("Parameters", obj.parameters)])]

def add_info_cmd():
    cli.new_info_command("tcf-agent", agent_info)

def dbghelp_status(obj):
    status = [
        ('Loaded', obj.dbghelp_loaded)]
    if obj.dbghelp_loaded:
        status.append(('Library path', obj.dbghelp_path))
        status.append(('Version', obj.dbghelp_version))
    else:
        status.append(
            (('Error message', obj.dbghelp_error_msg)))
    return ('DBGHELP.DLL Status', status)

def agent_status(obj):
    status = []
    status.append(
        (None, [("Backend Started", obj.properties != None)]))
    status.append(
        ("TCF Peer Properties",
         sorted((k, sorted(v.split(','))) for (k, v) in list(
             obj.properties.items()))
         if obj.properties else []))
    if is_windows():
        status.append(dbghelp_status(obj))

    for ctx in obj.trace_hub_contexts:
        status.append([
            "Trace Hub Device '%s'" % ctx[1].name, [
                ["Context", ctx[0]],
                ["Stream ID", ctx[3]],
                ["Blocked", ctx[4]],
                ["Blocked Message", ctx[5]],
                ["Total Sent", ctx[2]],
                ["Stream Lost", ctx[6]],
                ["Stream Buffered", ctx[7]],
                ["Stream Sent", ctx[8]]]])

    return status

def add_status_cmd():
    cli.new_status_command("tcf-agent", agent_status)


def spaces(nr):
    return " " * nr

def indented_name(indent, indent_steps, name):
    res = spaces(indent * indent_steps)
    if name:
        if indent > 0:
            res += "."
        res = "%s%s " % (res, name)
    return res

def is_str_type(type_str):
    stripped_str = type_str.replace("const", "").strip()
    return stripped_str == "char *"

def is_char_array(type_str, value):
    if not isinstance(value, list):
        return False
    stripped_str = type_str.replace("const", "").strip()
    return stripped_str.startswith("char[")

def str_from_char_array(array, max_len):
    to_end = max_len
    assert isinstance(array, list)
    string = ""
    for char in array:
        if char == 0:
            break
        string += chr(char)
        to_end -= 1
        if to_end == 0:
            break
    return string

def get_contexts_with_state(tcf):
    contexts_with_state = list()
    (err, all_ctxs) = tcf.iface.debug_query.matching_contexts("*")
    if err == simics.Debugger_No_Error:
        for ctx_id in all_ctxs:
            (err, has_state) = tcf.iface.debug_query.context_has_state(ctx_id)
            if err != simics.Debugger_No_Error:
                has_state = False
            if has_state:
                contexts_with_state.append(ctx_id)
    return contexts_with_state

def get_ctx_id_from_name(tcf, searched_name):
    contexts = get_contexts_with_state(tcf)
    for ctx_id in contexts:
        (err, name) = tcf.iface.debug_query.context_name(ctx_id)
        if err == simics.Debugger_No_Error and name == searched_name:
            return ctx_id
    return None

def is_ptr_type(type_str):
    return type_str.endswith("*") or "(*)(" in type_str

def type_format(type_str):
    return " (%s)" % type_str

def print_expr_info_dict(tcf, ctx_id, info_dict, no_type, show_struct_end,
                         indent_steps, level=0, add_comma=False):
    for (name, data) in info_dict.items():
        (value, type_str) = data
        if isinstance(value, dict):
            start_str = "%s{" % (indented_name(level, indent_steps, name))
            if not no_type:
                start_str = "%-55s%s" % (start_str, type_format(type_str))
            print(start_str)
            print_expr_info_dict(tcf, ctx_id, value, no_type, show_struct_end,
                                 indent_steps, level + 1)
            if show_struct_end:
                end_name_str = "'%s'" % name if name else "<anonymous>"
                end_tag_extras = "  // End %s" % end_name_str
            else:
                end_tag_extras = ""
            print("%s}%s%s" % (spaces(level * indent_steps),
                               "," if add_comma else "", end_tag_extras))
            continue
        elif (isinstance(value, list) and len(value) > 0
              and isinstance(value[0], dict) and len(value[0]) > 0):
            print("%s[" % (indented_name(level, indent_steps, name)))
            for (i, member) in enumerate(value):
                print_expr_info_dict(tcf, ctx_id, member, False, False,
                                     indent_steps, level + 1, True)
            print("]")
            continue
        extras = ""
        str_max_len = 20
        extras_str = None
        if is_str_type(type_str):
            if not isinstance(value, int):
                raise cli.CliError("Bad pointer value: '%s'" % (value,))
            (err, tstr) = tcf.iface.debug_symbol.address_string(ctx_id, value,
                                                                str_max_len + 1)
            if err == simics.Debugger_No_Error:
                extras_str = tstr
        elif is_char_array(type_str, value):
            extras_str = str_from_char_array(value, str_max_len + 1)

        if extras_str:
            extras_str = repr(extras_str)  # Get rid of bad characters
            if len(extras_str) > str_max_len:
                extras_str = extras_str[:str_max_len - 2] + ".."
            extras = '(%s)' % extras_str

        if is_ptr_type(type_str):
            value = hex(value)
        if extras:
            value = "%s %s" % (value, extras)
        line_str = "%s= %s" % (indented_name(level, indent_steps, name), value)
        if not no_type:
            line_str = "%-55s%s" % (line_str, type_format(type_str))
        print(line_str)

def tcf_expr_info(tcf, ctx_finder, expr, frame, addr, no_type, show_struct_end,
                  indent_steps):
    if ctx_finder[-1] == "ctx_name":
        ctx_id = get_ctx_id_from_name(tcf, ctx_finder[1])
    elif ctx_finder[-1] == "cpu":
        (err, ctx_id) = tcf.iface.debug_query.context_id_for_object(
            ctx_finder[1])
        if err != simics.Debugger_No_Error:
            raise cli.CliError(ctx_id)
    else:
        ctx_id = ctx_finder[1]
    if not ctx_id:
        raise cli.CliError("Context not found")
    (err, res) = tcfc.expression_info(ctx_id, expr, frame, addr)
    if err != simics.Debugger_No_Error:
        raise cli.CliError(res)
    print_expr_info_dict(tcf, ctx_id, res, no_type, show_struct_end,
                         indent_steps)

def ctx_id_expander(prefix):
    tcf = simics.SIM_get_debugger()
    contexts_with_state = get_contexts_with_state(tcf)
    return cli.get_completions(prefix, contexts_with_state)

def ctx_name_expander(prefix):
    tcf = simics.SIM_get_debugger()
    contexts_with_state = get_contexts_with_state(tcf)
    names = set()
    for ctx_id in contexts_with_state:
        (err, name) = tcf.iface.debug_query.context_name(ctx_id)
        if err == simics.Debugger_No_Error:
            names.add(name)
    return cli.get_completions(prefix, names)

def add_expression_info_cmd():
    cli.new_unsupported_command("expression-info", "internals", tcf_expr_info,
                                ([cli.arg((cli.str_t, cli.str_t,
                                           cli.obj_t('processor',
                                                     'processor_info')),
                                          ('ctx_name', 'ctx_id', 'cpu'),
                                          expander = (ctx_name_expander,
                                                      ctx_id_expander, None)),
                                  cli.arg(cli.str_t, 'expression'),
                                  cli.arg(cli.integer_t, 'frame', '?', 0),
                                  cli.arg(cli.integer_t, 'address', '?', 0),
                                  cli.arg(cli.flag_t, "-no-type"),
                                  cli.arg(cli.flag_t, "-show-struct-end"),
                                  cli.arg(cli.integer_t, 'indentation',
                                          '?', 2)]),
                                cls = "tcf-agent",
                                short = "show information about a symbol",
                                doc = """
Displays the type and value for an <arg>expression</arg>.

The command requires a context, this can be specified by either giving
and ID with the <arg>ctx_id</arg> argument, providing a processor with
the <arg>cpu</arg> argument or giving a context name with the
<arg>ctx_name</arg> argument. In the case where a name is given the
first matching context with state will be used.

The <arg>frame</arg> can be used to specify in which frame the to look
for the expression, this defaults to the current frame.

The <arg>address</arg> can be used to specify an address to use as the
scope to look for the expression in.

If the <tt>-no-type</tt> argument is provided then the type will not
be printed.

The <tt>-show-struct-end</tt> argument is used to display which
structure ended at a <tt>}</tt> structure end tag.

The <arg>indentation</arg> argument specifies how many spaces a new
structure should be indented.""")


def register_cmds():
    add_info_cmd()
    add_status_cmd()
    add_expression_info_cmd()

    if is_windows():
        from . import dbghelp_lib
        dbghelp_lib.add_copy_command()
