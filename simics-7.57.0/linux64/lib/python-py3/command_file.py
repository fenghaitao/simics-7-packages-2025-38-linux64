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
import cli_impl
import conf
import io
import simics
import simics_common
import os
import sys
import scriptdecl
from targets import sim_params
from targets import script_params
import pathlib
from targets import targets

class ScriptError(Exception):
    pass

class ScriptBreak(Exception):
    pass

class ScriptStop(Exception):
    pass

scripts_running = 0

script_history = []

def get_command_file_history():
    return script_history

def script_started(filename, local, script_args):
    script_history.append([filename, "started"])
    if simics.VT_in_main_branch():
        global scripts_running
        if scripts_running == 0:
            simics_common.run_state_script_started()
        scripts_running += 1
    return cli_impl.push_file_scope(local, script_args)

def script_stopped(filename, locals):
    script_history.append([filename, "exited"])
    cli_impl.pop_file_scope(locals)
    if simics.VT_in_main_branch():
        global scripts_running
        assert scripts_running > 0
        scripts_running -= 1
        if scripts_running == 0:
            simics_common.run_state_script_stopped()

def do_script_command(filename, line_number, command, more_commands):
    if conf.sim.echo:
        print("[%s:%d] %s" % (os.path.basename(filename), line_number, command))

    (is_ok, is_error, err_msg, err_line, err_cmd) = cli_impl.cmdfile_run_command(
        filename, line_number, command)

    # Check if interrupted by user
    interrupted = simics.CORE_clear_interrupt_script()

    if not is_ok:
        if is_error:
            # script interrupted by error
            msg = "%s[%s:%i]" % (err_msg + "\n" if err_msg else "",
                                 filename, err_line)
            if err_cmd:
                raise ScriptError("%s error in '%s' command" % (msg, err_cmd))
            else:
                raise ScriptError("%s error parsing command" % msg)
        elif err_msg is not None:
            # script interrupted (not error)
            raise ScriptBreak(err_msg)
        else:
            # script stopped
            raise ScriptStop("")
    elif interrupted:
        # check for user and stop_on_errors breaks last to avoid hiding errors
        if interrupted == 2:
            extra_info = " by the user"
        elif simics.CORE_clear_stopped_on_error():
            extra_info = " by error output with sim->stop_on_error set"
        else:
            extra_info = ""

        if more_commands:
            raise ScriptBreak(f"[{filename}:{err_line}] script interrupted"
                              f"{extra_info}; some commands may not have"
                              " completed properly")
        else:
            raise ScriptBreak(f"script interrupted{extra_info}")

def run_script_lines(filename, cmds, starting_line):
    path = simics.CORE_absolutify_path(filename, os.path.abspath(os.path.curdir))
    line_number = starting_line
    while cmds:
        cmd_len = cli.complete_command_prefix(cmds)
        if cmd_len == 0:
            # At EOF run any buffered lines, complete or not
            cmd_len = len(cmds)
        run_cmd = cmds[:cmd_len]
        cmds = cmds[cmd_len:]
        do_script_command(path, line_number, run_cmd, bool(cmds))
        line_number += run_cmd.count('\n')
        # Avoid starvation of async work. In particular, this allows
        # change of script threads before the next command is run.
        if cli.sb_in_main_branch():
            # Don't run SIM_process_pending_work while in script branches -
            # processing work queue from a script branch may cause issues. See a
            # regression test from the commit that added this comment for
            # details.
            simics.SIM_process_pending_work()

def set_cli_vars(vars):
    cur_locals = cli_impl.get_current_locals()
    for r in vars:
        cur_locals.set_variable_value(r, vars[r], False)

# The CLI print format of a value.
def cli_repr(val):
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    elif val is None:
        return "NIL"
    elif isinstance(val, str):
        return cli_impl.repr_cli_string(val)
    else:
        return str(val)

# Return the list of package install directories, in the order they should
# be searched.
def package_dirs():
    package_dirs = [pi[9] for pi in conf.sim.package_info if pi[12]]
    package_dirs += [pi[9] for pi in conf.sim.package_info if not pi[12]]
    return package_dirs

def simics_paths():
    """Paths that %simics% will expand to."""
    return (([conf.sim.project] if conf.sim.project else [])
            + package_dirs())

def find_encoding_error(f, filename):
    try:
        for _ in f:
            pass
    except UnicodeDecodeError as ex:
        return ("Script file %s contains non-UTF-8 characters on position %d"
                % (filename, ex.start))
    else:
        return None
    finally:
        f.seek(0)

# The number of currently executing (nested) Simics scripts.
script_level = 0

def run_command_file(filename, local, args):
    global script_level
    if os.path.isdir(filename):
        return [None, simics.SimExc_IOError.number,
                "%s is a directory, not a command file" % filename]

    pkg_dirs = simics_paths()

    try:
        f = io.open(filename, encoding = "utf-8")
    except OSError as ex:
        return [None, simics.SimExc_IOError.number,
                "Could not open command file %s: %s" % (filename, ex)]

    err = find_encoding_error(f, filename)
    if err:
        return [None, simics.SimExc_General.number, err]
    try:
        r = scriptdecl.get_declspec(f, filename, pkg_dirs)
        if r is not None:
            (ds, n) = r
        else:
            (ds, n) = (None, 0)
            f.seek(0)
    except scriptdecl.DeclError as e:
        f.close()
        return [None, simics.SimExc_General.number, str(e)]

    # Convert command-line parameters to Python values.
    script_args = {}
    for [name, valstr] in args:
        try:
            value = scriptdecl.match_arg_value(ds, name, valstr)
        except scriptdecl.ParseError as ex:
            return [None, simics.SimExc_General.number,
                    "Script argument %s: %s: %s" % (name, ex.args[0], valstr)]
        script_args[name] = value

    try:
        if ds:
            cli_vars = cli_impl.get_current_locals().get_all_variables()
            actual_args = ds.select_args(script_args, cli_vars, pkg_dirs)
            local = True
        else:
            # Script without declaration: set CLI variables from arguments.
            set_cli_vars(script_args)
            actual_args = None
    except scriptdecl.DeclError as e:
        return [None, simics.SimExc_General.number, str(e)]

    # Remove CRLF line endings; they confuse Python/CLI.
    lines = "".join(line.replace("\r", "") for line in f)
    f.close()

    def print_variables(prefix, vars):
        for a in sorted(vars):
            print("%s    %s = %s" % (prefix, a, cli_repr(vars[a])))

    if conf.sim.script_trace:
        prefix = "." * script_level
        print("%sEntering %s" % (prefix, filename), end=' ')
        if actual_args:
            print("with parameters:")
            print_variables(prefix, actual_args)
        else:
            print()

    script_level += 1
    locals = script_started(filename, local, actual_args)
    try:
        run_script_lines(filename, lines, n + 1)
    except ScriptError as ex:
        return [None, simics.SimExc_General.number, str(ex)]
    except ScriptBreak as ex:
        return [None, simics.SimExc_Break.number, str(ex)]
    except ScriptStop:
        return [None, simics.SimExc_Stop.number, ""]
    finally:
        final_cli_vars = cli_impl.get_current_locals().get_all_variables()
        script_stopped(filename, locals)
        script_level -= 1

    results = {}
    if ds is not None:
        try:
            results = ds.select_results(final_cli_vars, pkg_dirs)
        except scriptdecl.DeclError as e:
            return [None, simics.SimExc_General.number, str(e)]

    if conf.sim.script_trace:
        prefix = "." * script_level
        print("%sLeaving %s" % (prefix, filename), end=' ')
        if results:
            print("with results:")
            print_variables(prefix, results)
        else:
            print()

    # Inject the results into the caller's environment.
    set_cli_vars(results)

    return [None, simics.SimExc_No_Exception, ""]

def print_help_for_script(filename, header=True, table_width=None):
    try:
        print_params_for_target(filename, table_width=table_width)
        return True
    except simics.SimExc_General:
        # Probably not a target
        pass

    if not os.path.isfile(filename):
        print("No such file: %s" % (filename,))
        return False
    with io.open(filename, encoding = "utf-8") as f:
        err = find_encoding_error(f, filename)
        if err:
            print(err)
            return False
        try:
            r = scriptdecl.get_declspec(f, filename, simics_paths())
        except scriptdecl.DeclError as e:
            print(e)
            return False
    if r is None:
        print("%s does not have any declared parameters." % (filename,))
        return  False
    else:
        (ds, _) = r
        if header:
            print("Script %s:" % (filename,))
        ds.print_help(sys.stdout)
        return True

# Return target script or raise exception
def get_target_script(tgt: str) -> pathlib.Path:
    target = pathlib.Path(tgt)
    if target.is_file():
        return target
    else:
        # On Windows CMD can replace / with \
        target = tgt.replace("\\", "/")
        script_file = targets.get_script_file(target,
                                              sim_params.get_target_list())
        if script_file is None or not script_file.is_file():
            raise script_params.TargetParamError(f'No target "{target}" found')
        else:
            return script_file

def run_target_code(code_file, text, code_type, line, local):
    global script_level
    if conf.sim.script_trace:
        prefix = "." * script_level
        print(f"{prefix}Entering {code_file}")

    script_level += 1

    if 'py' in code_type:
        temp_name = None
        try:
            simics.CORE_python_run_code(text, code_file)
        except Exception as ex:
            return [None, simics.SimExc_IOError.number,
                    f"Failed running Python code from {code_file}: {ex}"]
        finally:
            if temp_name:
                os.remove(temp_name)
            script_level -= 1
    else:
        lines = text.replace('\r', '')
        n = line
        locals = script_started(code_file, local, None)
        try:
            run_script_lines(code_file, lines, n + 1)
        except ScriptError as ex:
            return [None, simics.SimExc_General.number, str(ex)]
        except ScriptBreak as ex:
            return [None, simics.SimExc_Break.number, str(ex)]
        except ScriptStop:
            return [None, simics.SimExc_Stop.number, ""]
        finally:
            script_stopped(code_file, locals)
            script_level -= 1

    if conf.sim.script_trace:
        prefix = "." * script_level
        print(f"{prefix}Leaving {code_file}")
    return [None, simics.SimExc_No_Exception, ""]

def construct_target_args(presets, preset_yml, cmdline_args):
    from targets import script_commands
    args = {}

    # Take arguments from presets, later ones override earlier ones
    for entry in presets:
        (fn, ns) = entry
        vals = script_commands.args_from_script(fn, ns)
        args.update({k: (v, fn) for (k, v) in vals.items()})
    if preset_yml:
        preset_args = script_commands.args_from_yaml(
            "<preset>", preset_yml, "")
        args.update({k: (v, "<preset>")
                     for (k, v) in preset_args.items()})

    # Explicitly provided arguments override preset arguments
    args.update({k: (v, "<cmdline>")
                 for (k, v) in cmdline_args.items()})
    return args

def load_target(target, namespace, presets, preset_yml, cmdline_args, local):
    try:
        script_file = get_target_script(target)
    except script_params.TargetParamError as ex:
        return [None, simics.SimExc_IOError.number, str(ex)]

    try:
        input_args = dict(cmdline_args)
    except ValueError as ex:
        return [None, simics.SimExc_General.number, str(ex)]

    if not script_file.is_file():
        return [None, simics.SimExc_IOError.number,
                f"{script_file} is not a Simics script"]

    if not script_params.looks_like_yaml_script(
            script_file,
            pathlib.Path(script_file).read_text(encoding='utf-8')):
        if script_file.suffix == '.py':
            from commands import run_python_file
            try:
                run_python_file(str(script_file))
                return [None, simics.SimExc_No_Exception, ""]
            except Exception as ex:
                return [None, simics.SimExc_General.number, str(ex)]
        else:
            from commands import param_val_to_str
            # Strings are already in the correct format,
            # from attr_value_t conversion.
            decl_args = [[k, param_val_to_str(v)
                          if not isinstance(v, str) else v]
                         for (k, v) in cmdline_args]
            return run_command_file(str(script_file), local, decl_args)
    try:
        args = construct_target_args(presets, preset_yml, input_args)
        data = sim_params.setup_script(script_file, namespace, args)
    except script_params.TargetParamError as ex:
        return [None, simics.SimExc_General.number, str(ex)]
    if not data:
        return [None, simics.SimExc_General.number,
                f"Invalid target: {script_file}"]

    (code, blueprints, ns) = data
    from sim_params import params

    # Run any pre-init code
    if code['pre-init']:
        params._set_code_fn(code['pre-init'])
        ret = run_target_code(
            code['pre-init'],
            pathlib.Path(code['pre-init']).read_text(encoding='utf-8'),
            code['type'], 0, local)
        if ret[1] != simics.SimExc_No_Exception:
            sim_params.finish_script(script_file)
            return ret

    # Instantiate all blueprints
    if blueprints:
        try:
            sim_params.instantiate_bp(target, blueprints,
                                      sim_params.params.view().tree())
        except script_params.TargetParamError as ex:
            sim_params.finish_script(script_file)
            return [None, simics.SimExc_General.number, str(ex)]

    # Run regular (post-init) script code
    params._set_code_fn(code['file'])
    ret = run_target_code(code['file'], code['text'],
                          code['type'], code['line'], local)
    sim_params.finish_script(script_file)
    if ret[1] != simics.SimExc_No_Exception:
        return ret

    return [ns, simics.SimExc_No_Exception, ""]

# Used by command line switches
def print_params_for_target(target: str, table_width=None):
    try:
        script_file = get_target_script(target)
    except script_params.TargetParamError as ex:
        print(ex)
    else:
        desc = sim_params.help_for_script(str(script_file),
                                          table_width=table_width)
        print(desc)
