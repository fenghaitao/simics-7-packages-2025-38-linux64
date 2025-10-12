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


import inspect
import os
from dataclasses import dataclass
import unittest
import asyncio
import traceback
from typing import Callable

from cli_impl import cli_sb_wait, create_branch, get_current_cmdinfo
from cli_impl import CliParseError, CliError
from deprecation import DEPRECATED
import cli
import conf
import simics

# used by cli.doc()
__simicsapi_doc_id__ = 'script_branch_api'

# Contains entries (what, argument) for which reverse warnings has already been
# printed.
commands_reverse_warned = set()

class ScriptBranchError(Exception):
    pass

def warn_reverse_arg(what, arg_name, arg_value):
    global commands_reverse_warned
    if (what, arg_name) in commands_reverse_warned:
        return
    commands_reverse_warned.add((what, arg_name))
    simics.SIM_printf_warning(
        f"The {what} called with {arg_name} (set to {arg_value}) is ignored"
        " since reverse is not supported.")

def check_reverse_args(what, reverse, always):
    """Warn if reverse or always arg is not None."""
    if isinstance(reverse, bool):
        warn_reverse_arg(what, 'reverse', reverse)
    if isinstance(always, bool):
        warn_reverse_arg(what, 'always', always)

def check_script_branch_command(cmd, reverse=None, always=None):
    """Common script-branch checks, raising CliError if the command is
    incorrectly used. Returns True if the script-branch command should run and
    False if it should silently return immediately"""
    if reverse and always:
        raise CliParseError("The -reverse and -always flag cannot both be set")
    check_reverse_args(f'{cmd} command', reverse, always)
    if sb_in_main_branch():
        raise CliError("The %s command is only allowed in script branches."
                       % cmd)
    return True  # old code may expect True to be returned

# Documentation text that was earlier used by wait-for- commands. No longer
# used but kepts for compatibility with old non-base modules.
script_branch_flag_doc = ""

script_pipes = {}

def create_script_pipe():
    pipe = sb_get_wait_id()
    script_pipes[pipe] = []
    return pipe

def script_pipe_has_data(pipe):
    return len(script_pipes[pipe]) > 0

def script_pipe_get_data(pipe):
    return script_pipes[pipe].pop(0)

def script_pipe_add_data(pipe, data):
    script_pipes[pipe].append(data)
    sb_signal_waiting(pipe)

def check_valid_script_pipe(pipe):
    if (not isinstance(pipe, int) or isinstance(pipe, bool)
        or pipe not in script_pipes):
        raise CliError("No script pipe %s" % pipe)

script_barriers = {}

class script_barrier:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

def create_script_barrier(limit):
    barrier = sb_get_wait_id()
    script_barriers[barrier] = script_barrier(limit)
    return barrier

def reset_script_barrier(barrier):
    script_barriers[barrier].count = 0
    sb_signal_waiting(barrier)

def script_barrier_limit(barrier):
    return script_barriers[barrier].limit

def update_script_barrier_limit(barrier, limit):
    script_barriers[barrier].limit = limit
    if script_barrier_ready(barrier):
        reset_script_barrier(barrier)

def script_barrier_count(barrier):
    return script_barriers[barrier].count

def script_barrier_ready(barrier):
    limit = script_barriers[barrier].limit
    count = script_barriers[barrier].count
    if count > limit:
        raise CliError("Too many script branches in barrier %d "
                       "(%d instead of max %d)." % (barrier, count, limit))
    elif count < limit:
        return False
    return True

def add_script_barrier_branch(barrier):
    script_barriers[barrier].count += 1

def check_valid_script_barrier(barrier):
    if barrier not in script_barriers:
        raise CliError("No script barrier %s" % barrier)

# Return the function, filename and line number for the calling function,
# a specified number of levels up the stack, counting from the caller of
# get_py_caller().
def get_py_caller(levels_up):
    try:
        frames = inspect.getouterframes(inspect.currentframe(), levels_up + 2)
    except IndexError:
        # This error has been observed on two different machines under certain
        # conditions, therefore catch and deal with it (bug 24965).
        return ("<unknown function>", "<unknown file>", 0)
    else:
        (filename, line, function) = frames[levels_up + 1][1:4]
    return (function, os.path.abspath(filename), line)

@cli.doc("create a script branch",
         return_value="script-branch identifier",
         context="Global Context",
         see_also=("script_branch.sb_wait, script_branch.sb_interrupt_branch,"
                   " script_branch.sb_run_in_main_branch"))
def sb_create(func, desc = None):
    """Create a script branch that will start executing <arg>func</arg>
    (which should not take any arguments). The <fun>sb_create</fun>
    function returns a unique script-branch identifier, that can be
    used with <fun>sb_interrupt_branch</fun>. It may be called from a
    script branch to create a new parallel branch. The current branch
    will resume execution when the new script branch is suspended.

    The optional <arg>desc</arg> argument will be displayed by
    <cmd>list-script-branches</cmd> as a description of the script
    branch."""
    (caller, filename, line) = get_py_caller(1)

    def script_branch_func_wrapper():
        """Run script-branch function and report uncaught exceptions."""
        try:
            return func()
        except Exception:
            traceback.print_exc()
            simics.CORE_python_flush()
            simics.CORE_error_interrupt("Error in script-branch")

    def create_branch_wrapper():
        return create_branch(
            script_branch_func_wrapper, desc, caller, filename, line)

    if sb_in_main_branch():
        return create_branch_wrapper()
    else:
        return sb_run_in_main_branch("sb_create", create_branch_wrapper)

# Internal helper function that figures out where the sb_* function was called
# from when used from the Python API. Assumes the script-branch API function
# calls this function directly. use_obj should be true when waiting for
# events related to configuration objects, i.e. non-global events in script
# branches that may support rev-exec
def do_sb_wait(command, wait_id, use_obj, wait_data):
    if simics.CORE_is_cli_script_branch():
        caller = None
        filename = get_current_cmdinfo().get_full_file()
        line = get_current_cmdinfo().get_line()
    else:
        (caller, filename, line) = get_py_caller(2)
    cli_sb_wait(command, wait_id, use_obj, caller, filename, line, wait_data)

@cli.doc("suspend a script branch",
         see_also=("script_branch.sb_create, script_branch.sb_get_wait_id,"
                   " script_branch.sb_signal_waiting"))
def sb_wait(command, wait_id, reverse=None, always=None, wait_data=None,
            use_obj=None):
    """Suspend a script branch in the <arg>command</arg> command (a
    descriptive string) until <fun>sb_signal_waiting</fun> is called
    with <arg>wait_id</arg> as argument. The <arg>reverse</arg> and
    <arg>always</arg> should not be used. The <arg>wait_data</arg> argument
    is a string describing the data being waited for, or
    <tt>None</tt>. The <arg>use_obj</arg> argument is deprecated and
    should never be specified."""
    check_reverse_args('sb_wait function', reverse, always)

    # use_obj used to be the fifth argument. Handle backward compatibility.
    if isinstance(wait_data, bool):
        print("*** Calling sb_wait() with old internal use_obj argument")
        wait_data = None
    if use_obj is not None:
        print("*** Calling sb_wait() with old internal use_obj argument")
    do_sb_wait(command, wait_id, True, wait_data)

next_sb_wait_id = 1 # use 0 as "unused" value

@cli.doc("obtain script branch wait ID",
         return_value="script branch wait-identifier",
         see_also="script_branch.sb_wait, script_branch.sb_signal_waiting")
def sb_get_wait_id():
    """Return a new unique script-branch wait-identifier that can be
    used when suspending a script-branch using <fun>sb_wait</fun>."""
    global next_sb_wait_id
    wait_id = next_sb_wait_id
    next_sb_wait_id += 1
    return wait_id

@cli.doc("wake up a suspended script branch",
         see_also="script_branch.sb_wait, script_branch.sb_get_wait_id")
def sb_signal_waiting(wait_id):
    """Wake up a suspended script-branch, with <arg>wait_id</arg> as wait
    identifier, letting it run again."""
    simics.CORE_wake_script_branch(wait_id)

# script branches waiting for a specific object. Used to interrupt script
# branches if the object the're waiting for is deleted.
obj_branches = {}

def add_obj_branch(obj, script_id):
    if obj not in obj_branches:
        obj_branches[obj] = set()
    obj_branches[obj].add(script_id)

def delete_obj_branch(obj, script_id):
    obj_branches[obj].remove(script_id)
    if not obj_branches[obj]:
        del obj_branches[obj]

# Listen for object deletions and interrupt any script-branch waiting
def del_object(arg, obj):
    if obj not in obj_branches:
        return
    # copy the object list since delete_obj_branch() will modify it
    for branch in list(obj_branches[obj]):
        sb_interrupt_branch(branch)
    if obj in obj_branches:
        # cleanup just in case (should have been removed already)
        del obj_branches[obj]

simics.SIM_hap_add_callback("Core_Conf_Object_Pre_Delete", del_object, None)

# Transform a hap argument to a form that can be used by CLI.
def transform_hap_arg(a):
    # Arguments of generic_transaction_t cannot be used by CLI directly.
    # Moreover, an argument of that type is only valid during the dynamic
    # extent of the hap callback, so in order to save one for later on we have
    # to extract the data from it.
    if isinstance(a, simics.generic_transaction_t):
        return [a.logical_address, a.physical_address,
                a.size, a.type, a.ini_ptr]
    else:
        return a


def sb_wait_for_sloop_awaitable(
        coro,
        # fisketur[syntax-error]
        *, loop=None, wait_data=None):
    import sloop
    if loop is None:
        loop = sloop.global_event_loop()
    if wait_data is None:
        wait_data = str(coro)
    wait_id = sb_get_wait_id()
    error = None
    async def wrapper(coro):
        nonlocal error
        try:
            return await coro
        except Exception as e:
            traceback.print_exc()
            error = repr(e)
        finally:
            sb_signal_waiting(wait_id)
    task = loop.create_task(wrapper(coro))
    do_sb_wait(f'wait_for_sloop_awaitable({coro})', wait_id, None, wait_data)
    try:
        _ = task.exception()
    except asyncio.CancelledError as e:
        traceback.print_exc()
        error = repr(e)
    if error is None:
        return task.result()
    else:
        raise ScriptBranchError(error)


def sb_wait_for_snooper(
        snooper,
        # fisketur[syntax-error]
        *, wait_data=None):
    import sloop
    return sb_wait_for_sloop_awaitable(sloop.wait(snooper))


def sb_hap_callback(*args):
    (hap, wait_id) = args[0]
    ret = list(args[1:])
    if wait_id not in hap_data_returned:
        # hap may trigger multiple times when replaying, keep original data
        hap_data_returned[wait_id] = list(map(transform_hap_arg, ret))
    sb_signal_waiting(wait_id)

# indexed by wait-id
hap_data_returned = {}

def sb_wait_for_hap(command, hap, obj, idx, reverse = None, always = None,
                    wait_data = None):
    """Help function for script-branch commands that should suspend until a
    certain hap occurs. 'hap' is the name of the hap. 'obj' is object or None
    that the hap is associated with. 'idx' is the hap index or -1 when the index
    should be ignored. reverse and always correspond to the script-branch
    arguments with the same names. The wait_data argument is a string describing
    the data being waited for, or None."""
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_hap is"
               " deprecated.", "Use the function"
               " conf.bp.hap.cli_cmds.wait_for instead.")
    return sb_wait_for_hap_internal(command, hap, obj, idx,
                                    wait_data = wait_data)

def sb_wait_for_hap_internal(command, hap, obj, idx, wait_data=None):
    branch_id = simics.CORE_get_script_branch_id()
    wait_id = sb_get_wait_id()
    args = (hap, wait_id)
    if obj:
        add_obj_branch(obj, branch_id)
        if idx >= 0:
            hap_id = simics.SIM_hap_add_callback_obj_index(
                hap, obj, 0, sb_hap_callback, args, idx)
        else:
            hap_id = simics.SIM_hap_add_callback_obj(
                hap, obj, 0, sb_hap_callback, args)
    elif idx >= 0:
        hap_id = simics.SIM_hap_add_callback_index(
            hap, sb_hap_callback, args, idx)
    else:
        hap_id = simics.SIM_hap_add_callback(hap, sb_hap_callback, args)
    try:
        do_sb_wait(command, wait_id, obj is not None, wait_data)
    finally:
        # remove hap callback on failures as well unless the object has been
        # deleted, then the hap callback has been removed already
        if not obj or isinstance(obj, simics.conf_object_t):
            simics.SIM_hap_delete_callback_id(hap, hap_id)
        if obj and isinstance(obj, simics.conf_object_t):
            delete_obj_branch(obj, branch_id)
    # return the data associated with the hap
    if wait_id in hap_data_returned:
        ret = hap_data_returned[wait_id]
        del hap_data_returned[wait_id]
    else:
        ret = []
    return ret

def sb_notifier_callback(subscriber, notifier, data):
    (notifier_type, wait_id) = data
    sb_signal_waiting(wait_id)


def sb_wait_for_notifier(command, notifier, what, reverse, always,
                         wait_data=None):
    """Suspends script branch execution until the specified notifier occurs.

   The arguments 'notifier' and 'what' correspond to the
   arguments with the same names to SIM_add_notifier. 'reverse' and 'always'
   correspond to the script-branch arguments with the same names
   (see the help on e.g. the bp.wait-for-breakpoint command).
   The optional wait_data argument is a string describing the data being waited
   for (will be visible in the list-script-branches command).

   Raises CLiError if 'what' is not an integer (a notifier_type_t), if
   'notifier' is not a Simics object, or if 'what' is not registered on
   'notifier'."""
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_notifier is"
               " deprecated.", "Use the function"
               " conf.bp.notifier.cli_cmds.wait_for instead.")
    sb_wait_for_notifier_internal(
        command, notifier, what, wait_data = wait_data)

def sb_wait_for_notifier_internal(command, notifier, what, wait_data=None):
    if not isinstance(what, int):
        raise CliError("sb_wait_for_notifier requires a notifier type")
    if not isinstance(notifier, simics.conf_object_t):
        raise CliError("sb_wait_for_notifier requires a notifier object")
    if not simics.SIM_has_notifier(notifier, what):
        raise CliError(f"Object '{notifier.name}' has no notifier '{what}'")

    wait_id = sb_get_wait_id()
    args = (what, wait_id)
    notifier_id = simics.SIM_add_notifier(notifier, what, None,
                                          sb_notifier_callback, args)

    try:
        do_sb_wait(command, wait_id, None, wait_data)
    finally:
        # remove notifier callback on failures
        simics.SIM_delete_notifier(notifier, notifier_id)

# indexed by wait-id
run_in_main_error = {}
run_in_main_return = {}

@cli.doc("run function in the main thread",
         return_value="return value of <arg>func</arg>",
         see_also="script_branch.sb_create, script_branch.sb_in_main_branch")
def sb_run_in_main_branch(command, func):
    """Schedule <arg>func</arg> (which should not take
    any arguments) to run in the main thread and block the calling script-branch
    thread until the function has run. A <tt>CliError</tt> exception will
    be raised if an error occurs while running <arg>func</arg>, otherwise
    its return value is returned."""

    wait_id = sb_get_wait_id()

    def func_main_branch_cb(_):
        try:
            run_in_main_return[wait_id] = func()
        except Exception as ex:
            run_in_main_error[wait_id] = str(ex)
        sb_signal_waiting(wait_id)

    simics.SIM_run_alone(func_main_branch_cb, None)
    try:
        do_sb_wait(command, wait_id, True, None)
    finally:
        # remove return value and error even if sb_wait() fails
        if wait_id in run_in_main_return:
            ret = run_in_main_return.pop(wait_id)
        if wait_id in run_in_main_error:
            raise CliError(run_in_main_error.pop(wait_id))
    return ret

@cli.doc("indicate if the main branch is running",
         see_also="script_branch.sb_run_in_main_branch")
def sb_in_main_branch():
    """Return <tt>true</tt> if the main branch is currently active, and not
    one of the script branches."""
    return simics.VT_in_main_branch()

@cli.doc("interrupt suspended script branch",
         see_also="script_branch.sb_create, script_branch.sb_wait")
def sb_interrupt_branch(branch_id):
    """Interrupt a script branch that is currently suspended. The
    <arg>branch_id</arg> should be the script-branch identifier
    (returned by <fun>sb_create</fun>) of a suspended script branch,
    otherwise an exception is raised.

    As a side effect, the <fun>sb_wait</fun> function called in the
    script branch will raise a <tt>CliQuietError</tt> exception.

    """
    simics.CORE_interrupt_script_branch(branch_id)

# Helper functions for common wait-for commands. Currently using the CLI
# command implementations, but it should be the other way around.

def run_sb_cmd(fun):
    try:
        return fun()
    except CliError as ex:
        raise ScriptBranchError(str(ex))

def sb_wait_for_log(obj, is_regex, substring = "", log_type = None):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_log is"
               " deprecated.", "Use the function"
               " conf.bp.log.cli_cmds.wait_for instead.")
    return sb_wait_for_log_internal(obj, is_regex, substring = "",
                                    log_type = log_type)

def sb_wait_for_log_internal(obj, is_regex, substring = "", log_type = None):
    from sim_commands import wait_for_log
    def wrap_wait_for_log():
        ret = wait_for_log(obj, is_regex, substring, log_type)
        if ret:
            return ret.get_value()
    return run_sb_cmd(wrap_wait_for_log)

def sb_wait_for_breakpoint(bp_id, reverse = False, always = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_breakpoint is"
               " deprecated.", "Use the function"
               " conf.bp.memory.cli_cmds.wait_for to wait for memory a memory"
               " access or conf.bp.cli_cmds.wait_for_breakpoint to wait for"
               " a breakpoint created by the breakpoint manager.")
    return sb_wait_for_breakpoint_internal(bp_id)

def sb_wait_for_breakpoint_internal(bp_id):
    from sim_commands import wait_for_breakpoint_command
    return run_sb_cmd(lambda : wait_for_breakpoint_command(bp_id))

def sb_wait_for_step(
        obj, step, reverse = False, always = False, relative = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_step is"
               " deprecated.", "Use the function"
               " conf.bp.step.cli_cmds.wait_for instead.")
    sb_wait_for_step_internal(obj, step, relative = relative)

def sb_wait_for_step_internal(obj, step, relative = False):
    from sim_commands import wait_for_step
    run_sb_cmd(lambda :
               wait_for_step(obj, step, relative))

def sb_wait_for_cycle(
        obj, cycle, reverse = False, always = False, relative = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_cycle is"
               " deprecated.", "Use the function"
               " conf.bp.cycle.cli_cmds.wait_for instead.")
    sb_wait_for_cycle_internal(obj, cycle, relative = relative)

def sb_wait_for_cycle_internal(obj, cycle, relative = False):
    from sim_commands import wait_for_cycle_command
    run_sb_cmd(lambda :
               wait_for_cycle_command(obj, cycle, relative))


def sb_wait_for_time(
        obj, seconds, reverse = False, always = False, relative = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_time is"
               " deprecated.", "Use the function"
               " conf.bp.time.cli_cmds.wait_for instead.")
    sb_wait_for_time_internal(obj, seconds, relative = relative)

def sb_wait_for_time_internal(obj, seconds, relative = False):
    from sim_commands import wait_for_time_command
    run_sb_cmd(lambda :
               wait_for_time_command(obj, seconds, relative))

def sb_wait_for_global_time(obj, seconds, relative = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_global_time is"
               " deprecated.", "Use the function"
               " conf.bp.time.cli_cmds.wait_for or"
               " cli.global_cmds.wait_for_global_time instead.")
    sb_wait_for_global_time_internal(obj, seconds, relative = relative)

def sb_wait_for_global_time_internal(obj, seconds, relative = False):
    from sim_commands import wait_for_global_time_command
    run_sb_cmd(lambda : wait_for_global_time_command(seconds, relative))

def sb_wait_for_global_sync():
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_global_sync is"
               " deprecated.", "Use the function"
               " cli.global_cmds.wait_for_global_sync instead.")
    sb_wait_for_global_sync_internal()

def sb_wait_for_global_sync_internal():
    from sim_commands import wait_for_global_sync_command
    run_sb_cmd(lambda : wait_for_global_sync_command())

def sb_wait_for_register_read(obj, reg, reverse = False, always = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_register_read"
               " is deprecated.", "Use the function"
               " conf.bp.control_register.cli_cmds.wait_for and set _r to"
               " True.")
    return sb_wait_for_register_read_internal(obj, reg)

def sb_wait_for_register_read_internal(obj, reg):
    from sim_commands import wait_for_register_read_command
    return run_sb_cmd(lambda : wait_for_register_read_command(obj, reg))

def sb_wait_for_register_write(obj, reg, reverse = False, always = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_register_write"
               " is deprecated.", "Use the function"
               " conf.bp.control_register.cli_cmds.wait_for and set _w to"
               " True.")
    return sb_wait_for_register_write_internal(obj, reg)

def sb_wait_for_register_write_internal(obj, reg):
    from sim_commands import wait_for_register_write_command
    return run_sb_cmd(lambda : wait_for_register_write_command(obj, reg))

def sb_wait_for_simulation_started():
    DEPRECATED(simics.SIM_VERSION_7, "The function"
               " sb_wait_for_simulation_started is deprecated.",
               "Use the function cli.global_cmds.wait_for_simulation_started"
               " instead.")
    return sb_wait_for_simulation_started_internal()

def sb_wait_for_simulation_started_internal():
    from sim_commands import wait_for_simulation_started_command
    return run_sb_cmd(lambda : wait_for_simulation_started_command())

def sb_wait_for_simulation_stopped():
    DEPRECATED(simics.SIM_VERSION_7, "The function"
               " sb_wait_for_simulation_stopped is deprecated.",
               "Use the function cli.global_cmds.wait_for_simulation_started"
               " instead.")
    return sb_wait_for_simulation_stopped_internal()

def sb_wait_for_simulation_stopped_internal():
    from sim_commands import wait_for_simulation_stopped_command
    return run_sb_cmd(lambda : wait_for_simulation_stopped_command())

def sb_wait_for_exception(
        obj, wait_for_all, name, reverse = False, always = False):
    DEPRECATED(simics.SIM_VERSION_7, "The function sb_wait_for_exception is"
               " deprecated.", "Use the function"
               " conf.bp.exception.cli_cmds.wait_for instead.")
    return sb_wait_for_exception_internal(obj, wait_for_all, name)

def sb_wait_for_exception_internal(obj, wait_for_all, name):
    from sim_commands import wait_for_exception_command
    return run_sb_cmd(lambda : wait_for_exception_command(
        obj, wait_for_all, name, -1))


# Importing `snoop` emits a tech-preview warning; this function is a
# dirty workaround to avoid this warning when script_branch is imported,
# instead delaying it until the first ScriptBranch snooper is instantiated.
def ScriptBranch(sb_wait_fun, *args, **kwargs):
    import snoop
    global ScriptBranch
    if not isinstance(ScriptBranch, snoop.Snooper):
        ScriptBranch = _snooper_class()
    return ScriptBranch(sb_wait_fun, *args, **kwargs)


def _snooper_class():
    import snoop
    class ScriptBranch(snoop.Snooper):
        '''Repeatedly waiting for an `sb_wait_*` function in a script
        branch with the given args.  The snooper yields each return value
        from the passed function.
        '''
        def __init__(self, sb_wait_fun, *args, **kwargs):
            self.sb_wait_fun = sb_wait_fun
            self.args = args
            self.kwargs = kwargs

        @dataclass
        class Handle(snoop.Handle):
            snooper : 'ScriptBranch'
            yield_value : Callable
            yield_exc : Callable
            sb_id : int = None
            stopping : bool = False
            wait_for_start = None
            def branch(self):
                self.wait_for_start = sb_get_wait_id()
                (caller, filename, line) = get_py_caller(0)
                cli_sb_wait(f'wait for starting {self.snooper.sb_wait_fun}',
                            self.wait_for_start, None, caller, filename, line,
                            None)
                while not self.stopping:
                    try:
                        ret = self.snooper.sb_wait_fun(
                            *self.snooper.args, **self.snooper.kwargs)
                    except cli.CliQuietError as ex:
                        if not self.stopping:
                            # script-branch interrupted by something
                            # else than `cancel`, might e.g. be a user
                            # requesting `interrupt-script-branch`
                            # from CLI.  This disrupts the waiter's
                            # intent, so re-raise the exception into
                            # the exception bridge but still obey the
                            # request to make sure the script branch
                            # exits cleanly, but re-raise the
                            # exception into the exception bridge.
                            self.stopping = True
                            self.yield_exc(ex)
                            raise
                    except Exception as ex:
                        self.stopping = True
                        self.yield_exc(ex)
                        raise
                    else:
                        if not self.stopping:
                            self.yield_value(ret)
            def cancel(self):
                if not self.stopping:
                    self.stopping = True
                    sb_interrupt_branch(self.sb_id)

        def add_callback(self, yield_value, yield_exc):
            handle = self.Handle(self, yield_value, yield_exc)
            handle.sb_id = sb_create(handle.branch)
            # sb_create may launch the branch immediately, which we
            # actually don't want
            assert handle.wait_for_start is not None
            sb_signal_waiting(handle.wait_for_start)
            return handle

        def exec_context(self):
            return snoop.GlobalContext()

    return ScriptBranch

# Run by t264_script_branches/s-unittest
class _test_snooper(unittest.TestCase):
    def test_sb_wait_for_snooper(self):
        import snoop
        class MockHandle(snoop.Handle):
            cancelled = []
            def cancel(self):
                self.cancelled.append(self)
        class MockSnooper(snoop.Snooper):
            cbs = []
            def __init__(self, arg):
                self.arg = arg
            def add_callback(self, yield_value, yield_exc):
                handle = MockHandle()
                self.cbs.append((yield_value, self.arg, handle, yield_exc))
                return handle
            def exec_context(self):
                return snoop.GlobalContext()

        def flush(ls):
            x = ls[:]
            del ls[:]
            return x
        ls = []
        def branch1():
            ls.append('a')
            ls.append(('await', sb_wait_for_snooper(MockSnooper(1))))
        def branch2():
            ls.append('b')
            try:
                ls.append(('value', sb_wait_for_snooper(MockSnooper(3))))
            except ScriptBranchError as e:
                ls.append(('exc', str(e)))
        sb_create(branch1)
        sb_create(branch2)
        self.assertEqual(set(flush(ls)), {'a', 'b'})
        simics.SIM_process_pending_work()
        [(cb1, cb2), args, handles, (exc_cb1, exc_cb2)] = zip(*MockSnooper.cbs)
        self.assertEqual(args, (1, 3))
        del MockSnooper.cbs[:]
        cb1(1)
        # ignored
        exc_cb1(Exception('horse'))
        simics.SIM_process_pending_work()
        self.assertEqual(flush(ls), [('await', 1)])
        exc_cb2(Exception('banana'))
        # ignored
        cb2(2)
        simics.SIM_process_pending_work()
        [(kind, value)] = flush(ls)
        self.assertEqual(kind, 'exc')
        self.assertIn('banana', value)
        self.assertEqual(flush(MockHandle.cancelled), list(handles))

    def test_sb_wait_for_sloop_awaitable(self):
        import sloop
        # Exercise a corner not covered by sb_wait_for_snooper, namely that
        # cancelled
        loop = sloop.global_event_loop()
        async def hang():
            ls.append('hang')
            await loop.create_future()

        task = loop.create_task(hang())
        ls = []
        def b():
            try:
                ls.append('b')
                sb_wait_for_sloop_awaitable(task)
            except Exception as e:
                ls.append(e)
        sb_create(b)
        simics.SIM_process_pending_work()
        assert set(ls) == {'hang', 'b'}
        del ls[:]
        task.cancel()
        simics.SIM_process_pending_work()
        [exc] = ls
        del ls[:]
        self.assertIsInstance(exc, ScriptBranchError)
        self.assertIn('CancelledError', str(exc))

    def test_script_branch_snooper(self):
        import snoop
        not_type = simics.SIM_notifier_type('test-notifier')
        simics.SIM_register_notifier('sim', not_type, '')
        calls = []
        assert conf.sim.script_branches == []
        handle = ScriptBranch(
            sb_wait_for_notifier_internal, 'donkey', conf.sim,
            not_type).add_callback(calls.append, calls.append)
        simics.SIM_process_pending_work()
        simics.SIM_notify(conf.sim, not_type)
        simics.SIM_process_pending_work()
        self.assertEqual(calls, [None])
        del calls[:]
        handle.cancel()
        simics.SIM_notify(conf.sim, not_type)
        self.assertEqual(calls, [])
        self.assertEqual(conf.sim.script_branches, [])

        # cancelling the snoop handle quietly stops the script branch with
        # no exception
        handle = ScriptBranch(
            sb_wait_for_notifier_internal, 'sheep', conf.sim,
            not_type).add_callback(calls.append, calls.append)
        self.assertEqual(len(conf.sim.script_branches), 1)
        simics.SIM_process_pending_work()
        handle.cancel()
        self.assertEqual(conf.sim.script_branches, [])
        self.assertEqual(calls, [])
        handle = ScriptBranch(
            sb_wait_for_notifier_internal, 'sheep', conf.sim,
            not_type).add_callback(calls.append, calls.append)
        self.assertEqual(len(conf.sim.script_branches), 1)
        handle.cancel()
        simics.SIM_process_pending_work()
        self.assertEqual(conf.sim.script_branches, [])
        self.assertEqual(calls, [])


        # interrupting a script branch causes an exception in the snoop
        handle = ScriptBranch(
            sb_wait_for_notifier_internal, 'rabbit', conf.sim,
            not_type).add_callback(calls.append, calls.append)
        simics.SIM_process_pending_work()
        self.assertEqual(len(conf.sim.script_branches), 1)
        simics.SIM_run_command(
            f'interrupt-script-branch {conf.sim.script_branches[0][0]}')
        self.assertEqual(conf.sim.script_branches, [])
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0], cli.CliQuietError)
        self.assertIn('rabbit', str(calls[0]))
        del calls[:]
        handle.cancel()

        # the sb_wait function's return value is propagated
        handle = ScriptBranch(
            sb_wait_for_log_internal, conf.sim, False).add_callback(
                calls.append, calls.append)
        simics.SIM_process_pending_work()
        simics.SIM_log_info(1, conf.sim, 0, 'horse')
        simics.SIM_process_pending_work()
        self.assertEqual(calls, [[None, -1, -1, 1, 0, 1, conf.sim, 'horse']])
        del calls[:]
        handle.cancel()

        count = 4
        exc = Exception()
        def immediate_script_branch():
            nonlocal count
            if count:
                count -= 1
                return count
            else:
                raise exc
        # The script-branch function is immediately called again after
        # returning. This would cause the script-branch to hang if we
        # didn't terminate it with an exception. Incidentally, this
        # also tests that exceptions from broken script branches are
        # propagated.
        handle = ScriptBranch(immediate_script_branch).add_callback(
            calls.append, calls.append)
        simics.SIM_process_pending_work()
        self.assertEqual(calls, [3, 2, 1, 0, exc])
        del calls[:]
        handle.cancel()

        self.assertEqual(ScriptBranch(lambda: None).exec_context(),
                         snoop.GlobalContext())
