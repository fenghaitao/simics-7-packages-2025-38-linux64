# © 2020 Intel Corporation
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
import conf
import simics
import cli_impl
from cli_impl import Arg_type
# locate() converts string to class
from pydoc import locate

has_tcf = 'tcf-agent' in {x[0] for x in simics.SIM_get_all_modules()}

from . import mem_bp_type
from . import con_bp_type
if has_tcf:
    from . import tcf_bp_type
from . import clock_bp_type
from . import cr_bp_type
from . import log_bp_type
from . import gfx_bp_type
from . import hap_bp_type
from . import notifier_bp_type
from . import exc_bp_type
from . import magic_bp_type
from . import events_bp_type
from . import bank_bp_type
from . import osa_bp_type
from . import msr_bp_type
from . import net_bp_type

from .bp import (bp_triggered, bp_set_provider,
                 add_delete_notifier, delete_notifier_data,
                 bp_do_break, BreakEnum)

# provider name -> provider
bp_types = {}
# provider obj -> (have_obj_arg, list of cli.Arg_type)
bp_args = {}
time_provider_name = "time"

# (provider, bp_id) -> bm_id
bp_bm = {}
# bm_id -> (provider, bp_id)
bm_bp = {}

# Breakpoint callbacks, used by trigger()
# (provider, bp_id) -> [(type, cb, trigger_args, abort_args)]
# i.e. can have several callbacks for one breakpoint
bp_cb = {}

def command_name(purpose, prefix, name):
    assert purpose
    assert purpose in ('break', 'run-until', 'wait-for', 'trace')
    assert prefix in (None, 'bp-')
    prefix = prefix if prefix else ''
    result = prefix + purpose
    if name:
        result += f'-{name}'
    return result

# run-until callback
def bp_stop(is_error, msg, run_until_done, provider, *args):
    if is_error:
        simics.VT_stop_message(provider, msg)
    else:
        simics.VT_stop_finished(msg)
        run_until_done[0] = True
    return False

# timeout callback
def bp_timeout(bm_id, mgr, *args):
    mgr.iface.bp_manager.delete_breakpoint(bm_id)
    return False

# wait-for callback
def bp_end_wait(is_aborted, branch_or_wait_id, bm_id, *args):
    if is_aborted:
        simics.SIM_run_alone(simics.CORE_interrupt_script_branch,
                             branch_or_wait_id)
    else:
        cb = lambda: cli.sb_signal_waiting(branch_or_wait_id)
        ret = bp_do_break(bm_id, cb)
        if ret == BreakEnum.NA:
            cb()
        bp_triggered(bm_id)
    return True

# trace callback
def bp_trace(cmd_name, provider, bp_id, obj, *args):
    msg = provider.iface.breakpoint_type_provider.trace_msg(bp_id)
    name = f" {obj.name}" if obj and obj != provider else ""
    bm_id = bp_bm[(provider, bp_id)]

    do_trace = provider.iface.breakpoint_type_provider.trace
    if not do_trace:
        # Log level 0 => traces cannot be disabled
        do_trace = lambda msg: simics.SIM_log_message(
            provider, 0, 0, simics.Sim_Log_Trace, msg)

    cb = lambda: do_trace(f"[trace:{bm_id}]{name} {msg}")
    ret = bp_do_break(bm_id, cb)
    if ret == BreakEnum.NA:
        cb()
    bp_triggered(bm_id)
    return False

# break callback
def bp_break(bp_id, provider, obj, msg):
    bm_id = bp_bm[(provider, bp_id)]
    name = f"{obj.name} " if obj and obj != provider else ""
    break_msg = f"Breakpoint {bm_id}: {name}{msg}"
    ret = bp_do_break(bm_id, lambda: simics.VT_stop_message(obj, break_msg))
    bp_triggered(bm_id)
    return ret == BreakEnum.Break

# Converts CLI command arguments to attr_value_t compatible data
# e.g. convert tuple to list
def to_attr_value(t):
    if isinstance(t, (tuple, list)):
        return [to_attr_value(x) for x in t]
    # Arg_type implements __repr__
    elif isinstance(t, Arg_type):
        return str(t)
    else:
        return t

def expander(provider, param, obj, value, args):
    obj_args = [obj] + list(args) + list([value])
    return cli.get_completions(
        value,
        provider.iface.breakpoint_type_provider.values(param,
                                                       to_attr_value(obj_args)))

def obtain_expander(provider, param):
    return lambda value, obj, prev_args: expander(provider, param,
                                                  obj, value, prev_args)

def obtain_cli_args(provider, args):
    cli_args = []

    for a in args:
        assert isinstance(a, list)
        arg_params = a[:]
        arg_type = arg_params.pop(0)
        # Providers must specify all parameters, so expander is at the end
        expanders = arg_params.pop()

        if isinstance(arg_type, list):
            if arg_type[0] == "obj_t":
                c = locate(f'cli.{arg_type.pop(0)}')
                assert c is not None
                cli_arg_type = c(*arg_type)
                if expanders is not None:
                    assert provider.iface.breakpoint_type_provider.values
                    expanders = obtain_expander(provider, arg_params[0])
            elif arg_type[0] == "string_set_t":
                c = locate(f'cli.{arg_type.pop(0)}')
                assert c is not None
                strings = dict(arg_type.pop(0))
                cli_arg_type = c(strings, *arg_type)
            elif arg_type[0] == "filename_t":
                c = locate(f'cli.{arg_type.pop(0)}')
                assert c is not None
                cli_arg_type = c(*arg_type)
            else:
                assert expanders is None or isinstance(expanders, list)
                assert isinstance(arg_params[0], list)
                assert expanders is None or len(expanders) == len(arg_params[0])
                cli_arg_types = []
                for at in arg_type:
                    if isinstance(at, list):
                        assert at[0] == "obj_t"
                        c = locate(f'cli.{at[0]}')
                        assert c is not None
                        cli_arg_types.append(c(*at[1:]))
                    else:
                        cli_arg_types.append(locate(f'cli.{at}'))

                cli_arg_type = tuple(cli_arg_types)
                assert all(c is not None for c in cli_arg_type)
                arg_params[0] = tuple(arg_params[0])
                if expanders is not None:
                    expanders = tuple(None if expanders[i] is None else
                                      obtain_expander(provider,
                                                      arg_params[0][i])
                                      for i in range(len(expanders)))
        else:
            assert isinstance(arg_type, str)
            cli_arg_type = locate(f'cli.{arg_type}')
            assert cli_arg_type is not None
            if expanders is not None:
                expanders = obtain_expander(provider, arg_params[0])

        arg_params.append(expanders)
        cli_args.append(cli.arg(cli_arg_type, *arg_params))
    return cli_args

def register_bp(provider, bp_id, obj):
    bm_id = provider.iface.breakpoint_type_provider.register_bp(bp_id)
    if bm_id > 0:
        simics.VT_add_telemetry_data_str("core.features", "breakpoints|",
                                         provider.classname)
        key = (provider, bp_id)
        bm_bp[bm_id] = key
        bp_bm[key] = bm_id

        bp_set_provider(bm_id, provider)

        if obj is not None:
            add_delete_notifier(bm_id, obj)

    return bm_id

# breakpoint_type interface
def get_break_id(mgr, bm_id):
    if bm_id in bm_bp:
        return bm_bp[bm_id][1]
    else:
        return 0

# breakpoint_type interface
def get_manager_id(mgr, provider, bp_id):
    key = (provider, bp_id)
    # TCF breaks handle the mapping internally
    if key in bp_bm:
        return bp_bm[key]
    else:
        return 0

def bp_mapping_cleanup(bm_id):
    # TCF breaks handle the mapping internally
    if bm_id in bm_bp:
        key = bm_bp[bm_id]
        del bm_bp[bm_id]
        del bp_bm[key]
        assert key in bp_cb
        del bp_cb[key]

def bp_deleted(bm_id):
    # TCF breaks handle the mapping internally
    if bm_id in bm_bp:
        (provider, bp_id) = bm_bp[bm_id]
        provider.iface.breakpoint_type_provider.remove_bp(bp_id)
        bp_mapping_cleanup(bm_id)

def break_cmd(provider, has_object, args):
    data = to_attr_value(args)
    once = data[-1]
    bp_id = provider.iface.breakpoint_type_provider.add_bp(
        simics.Breakpoint_Type_Break, data)
    if bp_id > 0:
        # Object is always first argument if it exists
        bm_id = register_bp(provider, bp_id, args[0] if has_object else None)
        if bm_id > 0:
            key = (provider, bp_id)
            bp_cb[key] = [(simics.Breakpoint_Type_Break, bp_break,
                           [bp_id, provider], [])]
            conf.bp.iface.bp_manager.set_temporary(bm_id, once)
            msg = provider.iface.breakpoint_type_provider.break_msg(bp_id)
            return cli.command_return(value=bm_id,
                                      message=f"Breakpoint {bm_id}: {msg}")
        else:
            provider.iface.breakpoint_type_provider.remove_bp(bp_id)
    raise cli.CliError("Could not add breakpoint")

def set_timeout(cmd_name, timeout, provider, bp, clk_obj):
    assert time_provider_name in bp_types
    time_provider = bp_types[time_provider_name]
    assert time_provider

    # Object is the first parameter, if given
    if isinstance(clk_obj, simics.conf_object_t):
        clk = simics.SIM_object_clock(clk_obj)
    else:
        clk = cli.current_cycle_obj_null()

    if not clk:
        raise simics.SimExc_General(
            f"Cannot set timeout in {cmd_name}: no clock found")

    time_bp = time_provider.iface.breakpoint_type_provider.add_bp(
        simics.Breakpoint_Type_Run_Until, [clk, timeout, False, False])
    if time_bp == 0:
        raise simics.SimExc_General(f"Failure setting timeout in {cmd_name}")
    return time_bp

def run_until_cmd(provider, name, has_object, args):
    (timeout, real_timeout) = args[-2:]
    assert isinstance(timeout, float)
    assert isinstance(real_timeout, float)
    data = to_attr_value(args[:-2])
    # Add -once parameter
    data.append(False)
    bp_id = provider.iface.breakpoint_type_provider.add_bp(
        simics.Breakpoint_Type_Run_Until, data)
    cmd_name = command_name('run-until', None, name)
    if bp_id == 0:
        raise cli.CliError(f"Failure in {cmd_name}")

    if timeout > 0:
        try:
            time_bp = set_timeout(cmd_name, timeout, provider, bp_id, data[0])
        except simics.SimExc_General as ex:
            provider.iface.breakpoint_type_provider.remove_bp(bp_id)
            raise cli.CliError(str(ex))

    # Object is always first argument if it exists
    bm_id = register_bp(provider, bp_id, args[0] if has_object else None)
    if bm_id == 0:
        provider.iface.breakpoint_type_provider.remove_bp(bp_id)
        raise cli.CliError(f"Failure in {cmd_name}")

    run_until_done = [
        False,  # Set to True on normal run-until exit
        False,  # Set to True on abnormal run-until exit
    ]

    def run_until_hap_cb(arg, obj, exc, err):
        # Mark abnormal exit if not already finished normally
        arg[1] = not arg[0]
        return True

    hap_id = simics.SIM_hap_add_callback("Core_Simulation_Stopped",
                                         run_until_hap_cb, run_until_done)
    key = (provider, bp_id)
    bp_cb[key] = [(simics.Breakpoint_Type_Run_Until,
                   bp_stop, [False, None, run_until_done, provider],
                   [True, f"{cmd_name} aborted",
                    run_until_done, provider])]
    data = None

    if timeout > 0:
        assert time_provider_name in bp_types
        time_provider = bp_types[time_provider_name]
        assert time_provider
        time_key = (time_provider, time_bp)
        bp_cb[time_key] = [(simics.Breakpoint_Type_Run_Until,
                            bp_timeout, [bm_id, conf.bp], [])]
    if real_timeout > 0:
        if real_timeout * 1000 >= 2**32:
            raise cli.CliError("Too large value for -timeout-rt")

        event_id = simics.SIM_realtime_event(
            int(real_timeout * 1000), lambda bm_id: bp_timeout(bm_id, conf.bp),
            bm_id, 0, f"{cmd_name} real timeout")
    try:
        simics.SIM_continue(0)
        if run_until_done[1]:
            raise cli.CliQuietError(f"{cmd_name} interrupted")
        if provider.iface.breakpoint_type_provider.break_data:
            data = provider.iface.breakpoint_type_provider.break_data(bp_id)
    except simics.SimExc_General as e:
        raise cli.CliError(str(e))
    finally:
        if real_timeout > 0:
            simics.SIM_cancel_realtime_event(event_id)
        conf.bp.iface.breakpoint_registration.deleted(bm_id)
        if timeout > 0:
            del bp_cb[time_key]
            time_provider = bp_types[time_provider_name]
            time_provider.iface.breakpoint_type_provider.remove_bp(time_bp)
        simics.SIM_hap_delete_callback_id("Core_Simulation_Stopped", hap_id)
    return data

def wait_for_breakpoint(bm_id, name, cmd_name, timeout, real_timeout):
    cli.check_script_branch_command(cmd_name)
    (provider, bp_id) = bm_bp[bm_id]

    # If the breakpoint has an object, it also has notifier data
    notifier_data = delete_notifier_data(bm_id)
    clk_obj = notifier_data[0] if notifier_data else None

    if timeout > 0:
        try:
            time_bp = set_timeout(cmd_name, timeout,
                                  provider, bp_id, clk_obj)
        except simics.SimExc_General as ex:
            provider.iface.breakpoint_type_provider.remove_bp(bp_id)
            raise cli.CliError(str(ex))

    # Is this wait-for-breakpoint for an existing breakpoint?
    wait_for_bp = (name == "breakpoint")

    branch_id = simics.CORE_get_script_branch_id()
    wait_id = cli.sb_get_wait_id()
    key = (provider, bp_id)
    entry = (simics.Breakpoint_Type_Wait_For, bp_end_wait,
             [False, wait_id, bm_id], [True, branch_id, bm_id])
    # Insert callback at the beginning, to override "break" command
    bp_cb.setdefault(key, []).insert(0, entry)
    msg = provider.iface.breakpoint_type_provider.wait_msg(bp_id)

    data = None
    if timeout > 0:
        assert time_provider_name in bp_types
        time_provider = bp_types[time_provider_name]
        assert time_provider
        time_key = (time_provider, time_bp)
        if wait_for_bp:
            bp_cb[time_key] = [(simics.Breakpoint_Type_Wait_For,
                                bp_end_wait, [True, branch_id, bm_id], [])]
        else:
            bp_cb[time_key] = [(simics.Breakpoint_Type_Wait_For,
                                bp_timeout, [bm_id, conf.bp], [])]
    if real_timeout > 0:
        if real_timeout * 1000 >= 2**32:
            raise cli.CliError("Too large value for -timeout-rt")

        def real_timeout_cb(bm_id):
            if wait_for_bp:
                bp_end_wait(True, branch_id, bm_id)
            else:
                bp_timeout(bm_id, conf.bp)
        event_id = simics.SIM_realtime_event(
            int(real_timeout * 1000),
            real_timeout_cb, bm_id, 0, f"{cmd_name} real timeout")
    try:
        cli.sb_wait(cmd_name, wait_id, wait_data=msg)
        if provider.iface.breakpoint_type_provider.break_data:
            data = provider.iface.breakpoint_type_provider.break_data(bp_id)
    except cli.CliQuietError:
        raise cli.CliQuietError(f"{cmd_name} interrupted")
    finally:
        if real_timeout > 0:
            simics.SIM_cancel_realtime_event(event_id)
        if not wait_for_bp:
            conf.bp.iface.breakpoint_registration.deleted(bm_id)
        else:
            # Breakpoint may have been removed already
            if key in bp_cb:
                bp_cb[key].remove(entry)
        if timeout > 0:
            del bp_cb[time_key]
            time_provider = bp_types[time_provider_name]
            time_provider.iface.breakpoint_type_provider.remove_bp(time_bp)
    return data

def wait_for_cmd(provider, name, has_object, args):
    (timeout, real_timeout) = args[-2:]
    cmd_name = command_name('wait-for', None, name)
    cli.check_script_branch_command(cmd_name)
    assert isinstance(timeout, float)
    assert isinstance(real_timeout, float)

    # Remove added parameters
    data = to_attr_value(args[:-2])
    # Add -once parameter
    data.append(False)
    bp_id = provider.iface.breakpoint_type_provider.add_bp(
        simics.Breakpoint_Type_Wait_For, data)
    if bp_id == 0:
        raise cli.CliError(f"Failure in {cmd_name}")

    # Object is always first argument if it exists
    bm_id = register_bp(provider, bp_id, args[0] if has_object else None)
    if bm_id == 0:
        provider.iface.breakpoint_type_provider.remove_bp(bp_id)
        raise cli.CliError(f"Failure in {cmd_name}")

    return wait_for_breakpoint(bm_id, name, cmd_name, timeout, real_timeout)


def trace_cmd(provider, name, has_object, args):
    data = to_attr_value(args)
    # Add -once parameter
    data.append(False)
    bp_id = provider.iface.breakpoint_type_provider.add_bp(
        simics.Breakpoint_Type_Trace, data)
    assert isinstance(bp_id, int)
    cmd_name = command_name('trace', None, name)
    if bp_id == 0:
        raise cli.CliError(f"Failure in {cmd_name}")

    # Object is always first argument if it exists
    bm_id = register_bp(provider, bp_id, args[0] if has_object else None)
    if bm_id == 0:
        provider.iface.breakpoint_type_provider.remove_bp(bp_id)
        raise cli.CliError(f"Failure in {cmd_name}")

    bp_cb[(provider, bp_id)] = [(simics.Breakpoint_Type_Trace, bp_trace,
                                 [f"trace-{name}", provider, bp_id], [])]
    return cli.command_return(value=bm_id, message=f"{bm_id}")

def bp_abort(bm_id):
    # TCF breakpoints are not registered here
    if bm_id in bm_bp:
        key = bm_bp[bm_id]
        assert key in bp_cb
        ok = False
        for (flags, cb, _, args) in bp_cb[key]:
            if flags in {simics.Breakpoint_Type_Run_Until,
                         simics.Breakpoint_Type_Wait_For}:
                params = args + [None, None]
                cb(*params)
                ok = True
            else:
                ok = False
        return ok
    return False

timeout_doc = """
If <arg>timeout</arg> is a positive number, the command will
run for at most that many seconds of virtual time.

If <arg>timeout-rt</arg> is a positive number, the command will run
for at most that many seconds of real time.

A time-out will be signaled by throwing a CLI exception, which can be captured
using try/except in order to take specific action, or to let it pass unhandled.
"""

def register_type(mgr, name, provider, args, cls, iface, docs,
                  object_required, temporary_default, recursive):
    # Cannot register commands on both class and interface
    if (cls is not None and iface is not None):
        return False

    # Verify CLI command arguments
    if not (simics.DBG_check_typing_system(
            "[[s|[s|n|b|[s|[si]*]*]s|[s*]ss|i|ns|nss|n|b|[b|n*]]*]",
            args) == simics.Sim_Set_Ok):
        return False

    # Need documentation for all commands except untrace
    if not (simics.DBG_check_typing_system("[ssssssss]",
                                           docs) == simics.Sim_Set_Ok):
        return False

    # Can only register a type once
    if name in bp_types:
        return False
    else:
        bp_types[name] = provider

    # Convert to cli.arg objects
    cli_args = obtain_cli_args(provider, args)

    # Should commands be registered elsewhere (with object parameter)?
    object_param = cls is not None or iface is not None

    # Add object parameter on object specific commands.
    # If not 'recursive':
    #   the requested object class and iface will be used for the 'object'
    #   argument, which means the cli will guarantee correctness.
    # If 'recursive':
    #   the 'object' argument will have no class or iface qualifier, which means
    #   that the bp type must check (in expander and add_bp) the object to have
    #   correct class and iface.
    if object_param:
        (obj_cls, obj_iface) = (None, None) if recursive else (cls, iface)
        desc = ("object" + (f" of class '{obj_cls}'" if obj_cls else "")
                + (f" with interface '{obj_iface}'" if obj_iface else ""))
        obj_arg = [cli.arg(cli.obj_t(desc, cls=obj_cls, iface=obj_iface),
                           name="object", spec=('' if object_required else '?'),
                           expander=obtain_expander(provider, 'object') if (
                               recursive) else None)]
        if object_required:
            obj_doc = ("This command uses breakpoint functionality on"
                       " <arg>object</arg>, with the following description:\n")
        else:
            obj_doc = ("\nIf <arg>object</arg> is provided, then the breakpoint"
                       " functionality is added on that object.")
    else:
        obj_arg = []
        obj_doc = ""

    if recursive:
        recursive_arg = [cli.arg(cli.flag_t, "-recursive", '?', False)]
        recursive_doc = (
            "\nIf <tt>-recursive</tt> is used, not only the object, but the"
            " objects hierarchically below the object will be considered when"
            " adding the breakpoint.")
    else:
        recursive_arg = []
        recursive_doc = ""

    bp_args[provider] = (bool(obj_arg), obj_arg + cli_args + recursive_arg)

    once_doc = """
The <tt>-once</tt> flag causes the breakpoint to automatically be
removed after it has triggered.
"""

    break_args = cli_args + recursive_arg + ([cli.arg(cli.flag_t, "-once")]
                             if (not temporary_default) else [])
    break_doc = docs[1] + (once_doc if not temporary_default else "")
    cli.new_command(command_name('break', None, None),
                    lambda *a: break_cmd(provider, object_param,
                                         a[1:] + ((True,) if temporary_default
                                                  else ())),
                    obj_arg + break_args, cls=provider.classname,
                    short=docs[0],
                    doc=(obj_doc + break_doc + recursive_doc if object_required
                         else break_doc + recursive_doc + obj_doc),
                    type=["Breakpoints", "Debugging"])

    run_until_args = (cli_args + recursive_arg
                      + [cli.arg(cli.float_t, "timeout", '?', 0.0)]
                      + [cli.arg(cli.float_t, "timeout-rt", '?', 0.0)])
    cli.new_command(command_name('run-until', None, None),
                    lambda *a: run_until_cmd(provider, name,
                                             object_param, a[1:]),
                    obj_arg + run_until_args, cls=provider.classname,
                    short=docs[2],
                    doc=(obj_doc + docs[3] + recursive_doc + timeout_doc
                         if object_required
                         else docs[3] + recursive_doc + timeout_doc + obj_doc),
                    type=["Breakpoints"])

    # Add script branch parameters
    wait_for_args = (cli_args + recursive_arg
                     + [cli.arg(cli.float_t, "timeout", '?', 0.0)]
                     + [cli.arg(cli.float_t, "timeout-rt", '?', 0.0)])
    cli.new_command(command_name('wait-for', None, None),
                    lambda *a: wait_for_cmd(provider, name,
                                            object_param, a[1:]),
                    obj_arg + wait_for_args, cls=provider.classname,
                    short=docs[4],
                    doc=((obj_doc + docs[5] + recursive_doc + timeout_doc)
                         if object_required else
                         (docs[5] + recursive_doc + timeout_doc + obj_doc)),
                    type=["Breakpoints"])

    trace_args = (cli_args + recursive_arg)
    cli.new_command(command_name('trace', None, None),
                    lambda *a: trace_cmd(provider, name, object_param, a[1:]),
                    obj_arg + trace_args, cls=provider.classname, short=docs[6],
                    doc=(obj_doc + docs[7] + recursive_doc if object_required
                         else docs[7] + recursive_doc + obj_doc),
                    type=["Breakpoints", "Debugging", "Tracing"])

    # Add commands in object namespace
    if object_param:
        cli.new_command(command_name('break', 'bp-', name),
                        lambda *a: break_cmd(provider, True,
                                             a + ((True,) if temporary_default
                                                  else ())),
                        break_args, iface=iface, cls=cls, short=docs[0],
                        doc=break_doc + recursive_doc,
                        type=["Breakpoints", "Debugging"])
        cli.new_command(command_name('run-until', 'bp-', name),
                        lambda *a: run_until_cmd(provider, name, True, a),
                        run_until_args, iface=iface, cls=cls, short=docs[2],
                        doc=docs[3] + recursive_doc + timeout_doc,
                        type=["Breakpoints"])
        cli.new_command(command_name('wait-for', 'bp-', name),
                        lambda *a: wait_for_cmd(provider, name, True, a),
                        wait_for_args, iface=iface, cls=cls, short=docs[4],
                        doc=(docs[5] + recursive_doc + timeout_doc),
                        type=["Breakpoints"])
        cli.new_command(command_name('trace', 'bp-', name),
                        lambda *a: trace_cmd(provider, name, True, a),
                        trace_args, iface=iface, cls=cls, short=docs[6],
                        doc=docs[7] + recursive_doc, type=["Breakpoints",
                                                           "Debugging"])

    return True

def trigger(mgr, provider, bp_id, obj, msg):
    key = (provider, bp_id)
    assert key in bp_cb
    hit = False
    (bp_type, cb, args, _) = bp_cb[key][0]
    params = args + [obj, msg]
    hit = cb(*params) or hit
    # Trigger all callbacks of the same type
    # E.g. there may be multiple wait-for-breakpoint on the same breakpoint ID
    # This extends the handling done in 9c5d4c9e
    if len(bp_cb[key]) > 1:
        for (t, cb, args, _) in bp_cb[key][1:]:
            if t == bp_type:
                params = args + [obj, msg]
                hit = cb(*params) or hit

    # Timeout breakpoints not registered
    if key in bp_bm:
        props = mgr.iface.bp_manager.get_properties(bp_bm[key])
        assert 'temporary' in props
        if props['temporary'] and hit:
            mgr.iface.breakpoint_registration.deleted(bp_bm[key])
    return hit

# Helper function for bp-manager interface
def get_provider_list():
    return list(bp_types.values())

def setup_breakpoint_types(bpm_class):
    simics.SIM_register_interface(
        bpm_class,
        'breakpoint_type',
        simics.breakpoint_type_interface_t(
            register_type=register_type,
            trigger=trigger,
            get_break_id=get_break_id,
            get_manager_id=get_manager_id,
        ))

    mem_bp_type.register_memory_breakpoints(bpm_class)
    con_bp_type.register_console_breakpoints(bpm_class)
    if has_tcf:
        tcf_bp_type.register_tcf_breakpoints(bpm_class)
    clock_bp_type.register_clock_breakpoints(bpm_class)
    cr_bp_type.register_cr_breakpoints(bpm_class)
    log_bp_type.register_log_breakpoints(bpm_class)
    gfx_bp_type.register_gfx_breakpoints(bpm_class)
    hap_bp_type.register_hap_breakpoints(bpm_class)
    notifier_bp_type.register_notifier_breakpoints(bpm_class)
    exc_bp_type.register_exc_breakpoints(bpm_class)
    magic_bp_type.register_magic_breakpoints(bpm_class)
    events_bp_type.register_event_breakpoints(bpm_class)
    bank_bp_type.register_bank_breakpoints(bpm_class)
    osa_bp_type.register_osa_breakpoints(bpm_class)
    msr_bp_type.register_msr_breakpoints(bpm_class)
    net_bp_type.register_network_breakpoints(bpm_class)
