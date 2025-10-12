# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import subprocess
import os
import tempfile
import errno

import simics
import simicsutils
import conf
from cli import CliError

# This file contains the low-level communication with VTune, which
# arguments that are passed etc.

def vtune_full_path(prog):
    pref_iface = conf.prefs.iface.preference
    try:
        vtune_path = pref_iface.get_preference_for_module_key(
            "vtune-measurement", "vtune_path")
    except simics.SimExc_General:
        vtune_path = None

    if simicsutils.host.is_windows():
        if not vtune_path and 'PATH' in os.environ:
            for x in os.environ['PATH'].split(';'):
                p = os.path.join(x, prog + ".exe")
                if os.path.exists(p):
                    return p
    if vtune_path:
        prog = os.path.join(vtune_path, prog)
    return prog


def try_start_program(args, **kwords):
    try:
        return subprocess.Popen(args, **kwords)
    except OSError as e:
        raise CliError(f'OSError: {e}')

def run_cmd(obj, args):
    def preexec():
        if 'setsid' in dir(os):
            os.setsid()

    prog = vtune_full_path("vtune")
    win = simicsutils.host.is_windows()
    simics.SIM_log_info(2, obj, 0, "executing: %s" % (" ".join([prog] + args)))

    return try_start_program(
        [prog] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        close_fds=not win,
        encoding='utf-8',
        preexec_fn=preexec if not win else None)

def launch_gui(obj, args):
    def preexec():
        if 'setsid' in dir(os):
            os.setsid()

    prog = vtune_full_path("vtune-gui")
    win = simicsutils.host.is_windows()
    simics.SIM_log_info(2, obj, 0, "executing: %s" % (" ".join([prog] + args)))

    return try_start_program(
        [prog] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        close_fds=not win,
        encoding='utf-8',
        preexec_fn=preexec if not win else None)

# Run a vtune command and extract the data which are not information
# from vtune itself, marked with 'vtune:'
def run_vtune_and_return_filtered_output(obj, args):
    p = run_cmd(obj, args)
    (out, err) = p.communicate()
    lines = out.split('\n')
    data = []
    for i, l in enumerate(lines):
        simics.SIM_log_info(2, obj, 0, "output: %s" % (l,))
        if l.find("vtune:") < 0:
            data.append(l)
    return data

def run_vtune_and_return_output(obj, args):
    p = run_cmd(obj, args)
    (out, err) = p.communicate()
    output = out.split('\n')
    simics.SIM_log_info(2, obj, 0, "output: %s" % (output,))
    return output

def wait_for_exit(obj, p):
    (out, err) = p.communicate()
    lines = out.split('\n')
    for l in lines:
        simics.SIM_log_info(2, obj, 0, "output: %s" % (l,))

def create_temp_file():
    (fd, fname) = tempfile.mkstemp(".csv")
    os.close(fd)
    return fname

def start(obj, collect, result_dir):
    win = simicsutils.host.is_windows()
    args = ["-run-pass-thru=--no-altstack"] if not win else []
    args += [
        "-collect", collect,
        "-mrte-mode native",
        "-no-follow-child",
        "-r", result_dir,
        "-target-pid %d" % (os.getpid())
    ]

    p = run_cmd(obj, args)
    if not p:
        return (False, None)
    recorded_lines = []
    while p.poll() is None:
        output = p.stdout.readline()
        simics.SIM_log_info(2, obj, 0, "output: %s" % (output,))
        if output:
            recorded_lines.append(output)
        if output.find('vtune: Collection started') >= 0:
            return (True, p)

    # Failed, show the collected_output if it reveals anything
    for l in recorded_lines:
        simics.SIM_log_info(1, obj, 0, l.replace("\n", ""))
    return (False, p)

def stop(obj, result_dir):
    args = [
        "-command", "stop",
        "-r", result_dir,
    ]
    return run_vtune_and_return_output(obj, args)

def profile(obj, result_dir, thread_filter, no_inline):
    outfile = create_temp_file()
    args = [
        "-report", "hotspots",
        f"-inline-mode={'off' if no_inline else 'on'}",
        "-format=csv",
        "-csv-delimiter=comma",
        "-column=CPU Time:Self",
        "-column=Module",
        "-column=Source File",
        "-report-output=%s" % (outfile,),
        "-r", result_dir,
    ]
    if thread_filter:
        for t in thread_filter:
            args.append("-filter=thread-id=%d" % t)
    _ = run_vtune_and_return_filtered_output(obj, args)
    with open(outfile, "r") as f:
        org = f.readlines()
    os.remove(outfile)
    if len(org) and org[0] == "war:Column filter is ON.\n":
        return org[1:] # Skip the warning
    return org

def module_profile(obj, result_dir, thread_filter):
    outfile = create_temp_file()
    args = [
        "-report", "hotspots",
        "-format=csv",
        "-csv-delimiter=comma",
        "-column=CPU Time:Self",
        "-group-by=module",
        "-report-output=%s" % (outfile,),
        "-r", result_dir,
    ]
    if thread_filter:
        for t in thread_filter:
            args.append("-filter=thread-id=%d" % t)
    _ = run_vtune_and_return_filtered_output(obj, args)
    with open(outfile, "r") as f:
        org = f.readlines()
    os.remove(outfile)
    if len(org) and org[0] == "war:Column filter is ON.\n":
        return org[1:] # Skip the warning
    return org

def callstack(obj, result_dir, thread_filter):
    outfile = create_temp_file()
    args = [
        "-report", "top-down",
        "-call-stack-mode", "user-only",
        "-inline-mode=off",
        "-format=csv",
        "-csv-delimiter=comma",
        "-column=CPU Time:Self",
        "-column=Module",
        "-report-output=%s" % (outfile,),
        "-r", result_dir,
    ]
    if thread_filter:
        for t in thread_filter:
            args.append("-filter=thread-id=%d" % t)
    _ = run_vtune_and_return_filtered_output(obj, args)
    with open(outfile, "r") as f:
        org = f.readlines()
    os.remove(outfile)
    if len(org) and org[0] == "war:Column filter is ON.\n":
        return org[1:] # Skip the warning
    return org


def thread_profile(obj, result_dir, thread_dict):
    outfile = create_temp_file()
    args = [
        "-report", "hotspots",
        "-format=csv",
        "-csv-delimiter=comma",
        "-column=CPU Time:Self",
        "-group-by=thread",
        "-report-output=%s" % (outfile,),
        "-r", result_dir,
    ]
    _ = run_vtune_and_return_filtered_output(obj, args)
    with open(outfile, "r") as f:
        org = f.readlines()
    os.remove(outfile)
    if len(org) and org[0] == "war:Column filter is ON.\n":
        return org[1:] # Skip the warning
    return org


def summary(obj, result_dir):
    args = [
        "-report", "summary",
        "-r", result_dir,
    ]
    return run_vtune_and_return_output(obj, args)


# Get the simics-common associated threads which VTune have discovered,
# with the name of the thread.
def get_threads(obj, result_dir):
    outfile = create_temp_file()
    args = [
        "-report", "hotspots",
        "-format=csv",
        "-csv-delimiter=comma",
        "-group-by=thread",
        "-column=Thread,TID",
        "-column=CPU Time:Self",
        "-q",
        "-report-output=%s" % (outfile,),
        "-r", result_dir,
    ]
    _ = run_vtune_and_return_filtered_output(obj, args)
    with open(outfile, "r") as f:
        org = f.readlines()
    os.remove(outfile)
    if len(org) and org[0] == "war:Column filter is ON.\n":
        return org[1:] # Skip the warning
    return org
