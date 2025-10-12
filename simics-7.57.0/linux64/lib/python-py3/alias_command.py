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

import re

import cli
import cli_impl
import simics
import table

from alias_util import (
    cmd_aliases,
    obj_aliases,
    user_defined_aliases,
)

def dict_to_list(d):
    return [list(x) for x in sorted(d.items())]

def curr_aliases(user_aliases, built_in_aliases):
    aliases = dict(built_in_aliases)
    aliases.update(user_aliases)
    return aliases

def alias_result(aliases, text=None, added_or_changed=None, removed=None,
                 show=None):
    msg_args = [text, added_or_changed, removed, show]
    assert msg_args.count(None) == len(msg_args) - 1
    verbose = text or show
    if text:
        message = text
    if added_or_changed:
        message = f'{added_or_changed} = {aliases[added_or_changed]}'
    elif removed:
        message = f"Removed alias '{removed}'"
    elif show:
        message = f'{show} = {aliases[show]}'
    return_class = cli.command_verbose_return if verbose else cli.command_return
    return return_class(message=message, value=dict_to_list(aliases))

def create_alias_table(title, aliases, alias_width=None, cmd_width=None):
    (alias_header, command_header) = ['Alias', 'Command']
    if alias_width is None:
        alias_width = len(max(aliases.keys(), key=len))
    if cmd_width is None:
        cmd_width = len(max(aliases.values(), key=len))
    alias_width = max([len(title), len(alias_header), alias_width])
    cmd_width = max([len(title), len(command_header), cmd_width])

    data = dict_to_list(aliases)
    properties = [
        (table.Table_Key_Columns, [
            [(table.Column_Key_Name, alias_header),
             (table.Column_Key_Width, alias_width)],
            [(table.Column_Key_Name, command_header),
             (table.Column_Key_Width, cmd_width)]]),
        (table.Table_Key_Extra_Headers, [
            (table.Extra_Header_Key_Row, [
                [(table.Extra_Header_Key_Name, title)],
            ])])]
    tbl = table.Table(properties, data)
    return tbl.to_string(rows_printed=0, no_row_column=True)

def find_aliases_by_value(aliases, value):
    matching = {alias[0]: alias[1] for alias in aliases.items() if (
        alias[1] == value)}
    return matching

def alias_cmd(alias, orig, r):
    user_aliases = user_defined_aliases()
    built_in_aliases = cmd_aliases()
    built_in_aliases.update(obj_aliases().descriptions())

    if alias:
        if not re.match(r'^[_a-zA-Z][_\-a-zA-Z0-9]*$', alias):
            raise cli.CliError(
                "Aliases must only contain letters, digits, hyphens and"
                " underscores. The first character is not allowed to be a digit"
                " or a hyphen.")

    if alias and not orig:
        if alias in user_aliases:
            if r:
                del user_aliases[alias]
                aliases = {} if alias not in built_in_aliases else {
                    alias: built_in_aliases[alias]}
                return alias_result(aliases, removed=alias)
            else:
                return alias_result({alias: user_aliases[alias]}, show=alias)
        elif alias in built_in_aliases:
            if r:
                raise cli.CliError("Cannot remove a build-in alias.")
            return alias_result({alias: built_in_aliases[alias]}, show=alias)
        else:
            raise cli.CliError(f"'{alias}' is not an alias.")

    if not alias:
        if not orig:
            aliases = curr_aliases(user_aliases, built_in_aliases)
            alias_width = len(max(aliases, key=len))
            cmd_width = len(max(aliases.values(), key=len))
            text = ''
            if user_aliases:
                text += create_alias_table(
                    'List of user defined aliases', user_aliases,
                    alias_width=alias_width, cmd_width=cmd_width)
            if built_in_aliases:
                if text:
                    text += '\n'
                text += create_alias_table(
                    'List of built-in aliases', built_in_aliases,
                    alias_width=alias_width, cmd_width=cmd_width)
            return alias_result(curr_aliases(user_aliases, built_in_aliases),
                                text=text)
        else:
            aliases = find_aliases_by_value(curr_aliases(
                user_aliases, built_in_aliases), orig)
            if not aliases:
                raise cli.CliError(f"There is no defined alias for '{orig}'.")
            return alias_result(aliases, text=create_alias_table(
                f'List of aliases of {orig}', aliases))

    if (alias in user_aliases
            and not r
            and user_aliases[alias] != orig  # it is a different definition
            ):
        raise cli.CliError(f"A user defined alias '{alias}' already exists,"
                           " use -r to replace it.")

    user_aliases[alias] = orig
    return alias_result({alias: orig}, added_or_changed=alias)

def object_command_expander(prefix):
    '''Expands to all commands on all objects'''
    get_obj_commands = cli_impl.all_commands.get_object_commands
    return cli.get_completions(
        prefix, list(
            obj.name + '.' + cmd
            for obj in simics.SIM_object_iterator(None)
            for obj_cmds in get_obj_commands(obj)
            for cmd in obj_cmds.all_methods()))

def global_command_expander(prefix):
    '''Expands to all global (i.e. non-namespace) commands.'''
    return cli.get_completions(prefix, cli_impl.get_global_command_names())

def combined_expander(expanders):
    '''Combine a list of one or more expanders into a single
    expander. Any expansion supported by one of the combined expanders
    will be accepted.'''
    return lambda prefix: list(exp for expnsns in expanders
                               for exp in expnsns(prefix))

cli.new_command('alias', alias_cmd,
            args = [cli.arg(cli.str_t, "alias", "?", ""),
                    cli.arg(cli.str_t, "as", "?", "",
                        expander = combined_expander([cli.object_expander(None),
                                                      global_command_expander,
                                                      object_command_expander
                                                      ])),
                    cli.arg(cli.flag_t, "-r")],
            type = ["CLI"],
            short = "add an alias",
            doc = """
Make an alias for a command or an object reference. The <arg>alias</arg>
argument is the name of the new alias and the <arg>as</arg> argument the
command or reference to make an alias for. For example:

<cmd>alias</cmd> ds disassemble-settings

will create an alias 'ds' for the command 'disassemble-settings'. So instead of
writing disassemble-setting you can write 'ds' at the command line or in a
Simics script.

You can also define an alias for an object reference like:

<cmd>alias</cmd> cpu0 system_cmp0.board1.cpu[0]

which allows you to write, for example, 'cpu0.print-processor-registers'
instead of 'system_cmp0.board1.cpu[0].print-processor-registers' to print the
registers for the cpu[0] processor in the component board1 in the component
system_cmp0.

Use <cmd>alias</cmd> <arg>alias</arg> <arg>as</arg> <tt>-r</tt> if you want to
replace an existing alias with a new one, or <cmd>alias</cmd> <arg>alias</arg>
<tt>-r</tt> if you want to remove the alias.

Aliases defined by this command have higher priority then build-in aliases.
This allows you to redefine the built-ins.

If no arguments are given a list of all aliases, including the built-ins, will
be printed.

Aliases must only contain letters, digits and underscores. The first character
is not allowed to be a digit.
""")
