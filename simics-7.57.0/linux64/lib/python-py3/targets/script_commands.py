# © 2021 Intel Corporation
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
import sys
from pathlib import Path

import simics
import cli
import conf
from cli_impl import CliArgNameError

from . import targets
from . import script_params
from . import sim_params

preview_name = "script-params"
cli.add_tech_preview(preview_name)

def non_existing_target_msg(target):
    return f"Non-existing target '{target}'"

# Obtain flattened declarations names from script
# suitable for using as CLI command parameter names
def decls_from_script(fn: Path):
    if not fn or not fn.is_file():
        return {}
    try:
        script_data = sim_params.parse_script(fn)
    except script_params.TargetParamError as ex:
        # Warnings already printed from parse_script
        if script_params.looks_like_yaml_script(
                fn, fn.read_text(encoding='utf-8'),
                warnings=False):
            raise cli.CliError(ex)
        else:
            return {}
    return sim_params.flatten_declarations(script_data['params'])

def lookup_file_non_required(f: str, **kwargs):
    kwargs.setdefault('required', False)
    return sim_params.lookup_file(f, **kwargs)

# Used to obtain argument values from preset on the command line.
# Should not require all files to exist since it is used before the target runs.
def args_from_yaml(fn: str, data: str, ns: str):
    # Allow %simics% and replace %script% with script directory
    script_data = script_params.parse_script(
        data, lookup_file_non_required, sim_params.get_target_list())
    # arg values are Param objects, but here we must have their values only
    return {k: v.value for (k, v) in script_params.flatten_params(
        script_data['args'], ns).items()}

# Used to obtain argument values from preset on the command line.
# Should not require all files to exist since it is used before the target runs.
def args_from_script(fn: str, ns: str):
    return args_from_yaml(fn, Path(fn), ns)

# Decl type -> CLI type
cli_decl_types = {
    str: cli.str_t,
    int: cli.int_t,
    bool: cli.boolean_t,
    float: cli.float_t,
    list: cli.list_t,
}

unspecified_arg = object()

def cli_arg_for_decl(name, decl):
    # Always allow string, for parameter references
    if decl.allow_empty:
        arg_type = cli.poly_t(name, cli_decl_types[decl.type], cli.str_t,
                              cli.nil_t)
    else:
        arg_type = cli.poly_t(name, cli_decl_types[decl.type], cli.str_t)
    return cli.arg(arg_type, name, "?", default=unspecified_arg)

# return list of CLI arguments matching parameters in a script
def cmd_args_from_script(filename: Path, no_execute: bool):
    from commands import cmd_args_from_script as legacy_cmd_args_from_script

    if not filename:
        return []
    decls = decls_from_script(filename)
    params = [cli_arg_for_decl(name, decl) for (name, decl) in decls.items()]
    if params:
        return params
    else:
        return legacy_cmd_args_from_script(str(filename), no_execute)

# return list of CLI argument names in a script
# the order matches cmd_args_from_script
def arg_name_from_script(filename: Path):
    from commands import arg_name_from_script as legacy_arg_name_from_script
    decls = decls_from_script(filename)
    if decls:
        return list(decls.keys())
    else:
        return legacy_arg_name_from_script(str(filename))

# create command arguments dynamically depending on the script argument
def script_dynamic_args(script_file: str, no_execute: bool):
    # Allow %simics% and replace %script% with script directory
    try:
        fn = sim_params.lookup_file(script_file, required=False)
        if fn is not None:
            return cmd_args_from_script(Path(fn).absolute(), no_execute)
        else:
            return []
    except script_params.TargetParamError:
        return []

def target_dynamic_args(target: str, no_execute: bool):
    script_file = targets.get_script_file(target, sim_params.get_target_list())
    if script_file is None:
        if no_execute:
            return []
        raise CliArgNameError(non_existing_target_msg(target))
    return cmd_args_from_script(script_file.absolute(), no_execute)

#
# -------------------- load-target --------------------
#

def obtain_script_args(script_file: Path, presets_args, *cmdline_args):
    if not script_file.is_file():
        raise cli.CliError(f"Non-existing script file '{script_file}'")

    if presets_args:
        if presets_args[2] == 'preset_yml':
            preset_yml = presets_args[1]
            presets = []
        else:
            preset_list = sim_params.get_preset_list()
            if presets_args[2] == 'presets':
                if all(isinstance(x, list) and len(x) == 2
                       for x in presets_args[1]):
                    explicit_ns = True
                elif all(isinstance(x, str) for x in presets_args[1]):
                    explicit_ns = False
                else:
                    raise cli.CliError(
                        'The "presets" argument must be a list of strings or'
                        " 2-tuples [preset, namespace]")

                presets = []
                for x in presets_args[1]:
                    (p, n) = x if explicit_ns else (x, "")
                    f = Path(p)
                    if not f.is_file():
                        f = targets.get_script_file(p, preset_list)
                    if not (f is not None and f.is_file()):
                        raise cli.CliError(f"Non-existing preset '{p}'")
                    presets.append([str(f.absolute()), n])
            else:
                f = Path(presets_args[1])
                if not f.is_file():
                    f = targets.get_script_file(presets_args[1], preset_list)
                if not (f is not None and f.is_file()):
                    raise cli.CliError("Non-existing preset"
                                       f" '{presets_args[1]}'")
                presets = [[str(f.absolute()), ""]]
            preset_yml = ""
    else:
        presets = []
        preset_yml = ""

    args = {}
    from commands import unspecified_arg as legacy_unspecified_arg
    if any(c not in [unspecified_arg, legacy_unspecified_arg]
           for c in cmdline_args):
        for (i, arg) in enumerate(arg_name_from_script(script_file)):
            if cmdline_args[i] not in [unspecified_arg, legacy_unspecified_arg]:
                val = cmdline_args[i]
                args[arg] = val

    # Convert to attr_value_t compatible type
    args = [[k, v] for (k, v) in args.items()]

    return (presets, preset_yml, args)

def run_script_cmd(script_file, namespace, main_branch, local,
                   presets_args, *cmdline_args):
    from commands import report_script_error

    fn = Path(script_file).absolute()
    (presets, preset_yml, args) = obtain_script_args(
        fn, presets_args, *cmdline_args)

    if not cli.sb_in_main_branch():
        if main_branch:
            # run the new script file in the main branch
            cli.sb_run_in_main_branch(
                'run-script', lambda : simics.CORE_run_target(
                    str(fn), namespace, presets, preset_yml, args, local))
            return
    else:
        if main_branch:
            raise cli.CliError("The -main-branch flag can only be used in"
                               " a script-branch")
    try:
        ns = simics.CORE_run_target(str(fn), namespace, presets,
                                    preset_yml, args, local)
        return cli.command_return(value=ns)
    except simics.SimExc_General as ex:
        report_script_error(sys.exc_info()[0], ex)

def load_target_cmd(target, namespace,
                    presets_args, *cmdline_args):
    from commands import report_script_error

    script_file = targets.get_script_file(target, sim_params.get_target_list())

    if script_file is None or not script_file.is_file():
        raise cli.CliError(non_existing_target_msg(target))
    else:
        fn = script_file.absolute()

    (presets, preset_yml, args) = obtain_script_args(
        script_file, presets_args, *cmdline_args)
    try:
        ns = simics.CORE_run_target(str(fn), namespace, presets,
                                    preset_yml, args, True)
        return cli.command_return(value=ns)
    except simics.SimExc_General as ex:
        report_script_error(sys.exc_info()[0], ex)

cmd_desc = """
Paths to preset files with arguments can be provided using the
<arg>preset</arg> or <arg>presets</arg> arguments. An already loaded
preset can be given as a string using the <arg>preset_yml</arg>
argument.

When providing a list of presets using <arg>presets</arg>, arguments
in later presets override earlier ones. In this case, each element in
the list should be a 2-tuple [<tt>file</tt>, <tt>namespace</tt>],
identifying the preset file name and the namespace in the parameter
tree where it should be applied.

The <arg>preset</arg> argument and the first element in each list of
the <arg>presets</arg> argument can either point to a file or be a
preset name, as returned by <cmd>list-presets</cmd>.

Arguments can also be provided on the command line. These override
arguments in presets.

When this command is called from a script, the <arg>namespace</arg>
argument is mandatory and specifies the name of the inner node in the
parameter tree whose corresponding sub-tree should be provided to the
target.

When this command is called interactively from the top level, the
<arg>namespace</arg> argument specifies the parameter system namespace
where the resulting arguments are placed, after the command has
finished. In this case the argument is optional and defaults to the
script or target name, plus a suffix in case the script/target has
already run, so that the same command can be run multiple times.
"""

def preset_expander(prefix):
    preset_info = sim_params.get_preset_list()
    return cli.get_completions(prefix, set(preset_info.keys()))

cli.new_command(
    "load-target", load_target_cmd,
    args=[cli.arg(cli.str_t, 'target', expander=sim_params.target_expander),
          cli.arg(cli.str_t, "namespace", '?'),
          cli.arg((cli.str_t, cli.list_t, cli.str_t), ('preset', 'presets',
                                                       'preset_yml'), '?',
                  expander=(preset_expander, None, None))],
    dynamic_args=('target', target_dynamic_args),
    type=["CLI", "Files", "Parameters"],
    short="load a target system",
    see_also=["run-script", "list-targets", "<script-params>.help"],
    doc="""
Load and execute the target system named <arg>target</arg>,
which should be one of the configurations returned by the
<cmd>list-targets</cmd> command.""" + cmd_desc + """

The namespace used, or the calculated default namespace, is returned.

Examples:

<tt>
load-target "my-target"
</tt>

<tt>
load-target "my-other-target" namespace = "ns"
</tt>

<tt>
load-target "my-big-target" namespace = "ns" preset = "my-preset"
</tt>

<tt>
load-target "my-big-target" namespace = "ns" presets = [["sub-preset1", ""], ["sub-preset2", ""]]
</tt>""")

cli.new_command(
    "run-script", run_script_cmd,
    args=[cli.arg(cli.filename_t(exist=True, simpath=True,
                                 keep_simics_ref=True), 'script'),
          cli.arg(cli.str_t, "namespace", '?'),
          cli.arg(cli.flag_t, "-main-branch"),
          cli.arg(cli.flag_t, "-local"),
          cli.arg((cli.filename_t(exist=True, simpath=True,
                                  keep_simics_ref=True),
                   cli.list_t, cli.str_t), ('preset', 'presets',
                                            'preset_yml'), '?',
                  expander=(preset_expander, None, None))],
    dynamic_args=('script', script_dynamic_args),
    type=["CLI", "Files", "Parameters"],
    short="run a script file",
    see_also=["load-target", "<script-params>.help"],
    doc="""
Run the target script file named <arg>script</arg>.
""" + cmd_desc + """
Examples:

<tt>
run-script "targets/qsp-x86/qsp-clear-linux.target.yml"
</tt>

The <tt>-local</tt> flag is provided for compatibility with
<cmd>run-command-file</cmd>. It only has effect when running scripts
with old style script declarations blocks and works as specified by
<cmd>run-command-file</cmd>.

If <cmd>run-script</cmd> is issued in a script-branch and the
<tt>-main-branch</tt> flag is specified, then the code in the file will
execute in the main script branch the next time it is scheduled.

The namespace used, or the calculated default namespace, is returned,
unless <tt>-main-branch</tt> was specified.""")
