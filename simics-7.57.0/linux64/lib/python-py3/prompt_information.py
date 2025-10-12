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
import sys

# Used to remember the frontend id for asynchronous commands, such as continue
# where current_cmdline is unset (-1). Used to print info when Simics stops.
saved_cmdline_id = -1

# List of prompt callbacks, should be functions on the following format:
# f(frontend_id, writer)
prompt_callbacks = []

def register_prompt_callback(f):
    prompt_callbacks.append(f)

def trigger_prompt_callbacks(frontend_id, writer):
    for f in prompt_callbacks:
        f(frontend_id, writer)

def set_sim_started_cmdline(cmdline):
    global saved_cmdline_id
    saved_cmdline_id = cmdline

def is_saved_cmdline(frontend_id):
    return saved_cmdline_id >= 0 and frontend_id == saved_cmdline_id

def async_print_stop_info(frontend_id, write):
    if not is_saved_cmdline(frontend_id):
        return
    # only print on the command line where the simulation was started from
    old_cmdline = cli.set_cmdline(saved_cmdline_id)
    print_stop_info(frontend_id, write)
    cli.set_cmdline(old_cmdline)
    set_sim_started_cmdline(-1)

def print_stop_info(frontend_id, write):
    # May have more than one stop reason, print them all
    for (t, obj, msg, cpu) in simics.VT_get_stop_reasons():
        if t in ["message", "user", "finished"]:
            # For normal stop reasons, be quiet if no msg
            if msg is not None:
                write("%s%s\n" % ("[%s] " % obj.name if obj else "", msg))
        elif t == "error":
            write("%s\033b>%s\033/b>\n"
                  % ("[%s] " % obj.name if obj else "", msg))
        else:
            write('Unknown stop reason %s%s%s\n'
                  % (t, " from %s" % obj.name if obj else "",
                     ' with message "%s"' % msg if msg else ""))

        if simics.VT_get_stop_type() == simics.Sim_Stop_Aborted:
            write("Simulation was aborted; breakpoints may"
                  " have been skipped\n")

    # Print additional stop information (debug context and location)
    trigger_prompt_callbacks(frontend_id, write)
    display_cb(write)

next_expr_id = 1
expr_list = {}

def display_value(expr, type, verbose):
    value = ''
    # Use the command output if any, otherwise the return value. For Python use
    # the @ command to support both expressions and statements in a simple way.
    expr = ('@' if type == 'py' else '') + expr
    try:
        val, ret = cli.quiet_run_command(expr)
    except:
        value = "<display expression raised exception>"
    else:
        if ret:
            value = ret.rstrip()
        elif val:
            if isinstance(val, int):
                value = cli.number_str(val)
            else:
                value = str(val)
    return expr + " : " + value if verbose else value

def display_cb(write):
    for (id, (expr, type, verbose, tag)) in expr_list.items():
        if tag:
            write(">%d<\n" % id)
        write(display_value(expr, type, verbose) + '\n')
        if tag:
            write(">.<\n")

def list_displays():
    if expr_list:
        for id in list(expr_list.keys()):
            (expr, type, _, _) = expr_list[id]
            print("%2d: %s [%s]" % (id, expr, type))
    else:
        print("No display expressions installed")

def display_cmd(expr, l, p, v, t):
    global next_expr_id
    if l:
        list_displays()
    elif expr is None:
        display_cb(sys.stdout.write)
    else:
        expr_list[next_expr_id] = (expr, "py" if p else "cli", v, t)
        print("display %d: %s" % (next_expr_id, expr))
        next_expr_id += 1

def undisplay_cmd(expr_id):
    try:
        del expr_list[expr_id]
    except KeyError:
        print("No such display expression")

cli.new_command("display", display_cmd,
                [cli.arg(cli.str_t, "expression", "?", None),
                 cli.arg(cli.flag_t, "-l"),
                 cli.arg(cli.flag_t, "-p"),
                 cli.arg(cli.flag_t, "-v"),
                 cli.arg(cli.flag_t, "-t")],
                type  = ["CLI"],
                short = "print expression at prompt",
                see_also = ["undisplay"],
                doc = """
Install a CLI or Python expression or statement that will be printed every time
Simics returns to a prompt after having advanced the simulation. The
<tt>-p</tt> flag is used to indicate that the <arg>expression</arg> argument
is in Python. The <tt>-l</tt> flags can be used to list all installed display
expressions together with their assigned identifier. This identifier is used
when removing expressions with the <cmd>undisplay</cmd> command. Calling
<cmd>display</cmd> with no arguments will print the current value of all
expressions. The <tt>-t</tt> flag tags the output of an expression in a way
that simplifies capture by external means. To include the expression itself in
the output, use the <tt>-v</tt> (verbose) flag.""")

cli.new_command("undisplay", undisplay_cmd,
                [cli.arg(cli.int_t, "expression-id")],
                type  = ["CLI"],
                short = "remove expression installed by display",
                see_also = ["display"],
                doc = """
Remove a Python or CLI expression that was previously installed with the
<cmd>display</cmd> command. <arg>expression-id</arg> takes the id number of
the expression, as listed by <tt>display -l</tt>.  """)
