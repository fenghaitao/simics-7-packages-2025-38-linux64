# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import sys
import json
import os
import pathlib
import shutil
import subprocess
from subprocess import Popen, PIPE, DEVNULL
from simicsutils.host import is_windows

import conf
import pyobj
import simics

class telemetry_manager(pyobj.ConfObject):
    """Manager for telemetry collected by Simics."""
    _class_desc = 'the Simics telemetry manager'
    _class_kind = simics.Sim_Class_Kind_Pseudo
    def _status(self):
        started, pid, alive = "No", "N/A", "N/A"
        if hasattr(self, "stats_sender"):
            started = "Yes"
            pid = self.stats_sender.pid
            if self.stats_sender.poll() is None:
                alive = "Yes"
            else:
                alive = f"No (return code = {self.stats_sender.poll()})"

        return [(None, [("Sender process started", started),
                        ("Sender process Python", self.python_exe),
                        ("Sender process pid", pid),
                        ("Sender process alive", alive)])]

    _info = _status  # make info command to be the same as status command

    def _initialize(self):
        super()._initialize()

        self.python_exe = pathlib.PurePath(sys.executable)
        # In the case of an embedded Simics, sys.executable may not point to
        # Python but to some other binary that actually runs Simics. Such
        # run would execute this code again, and we get a fork bomb. As
        # a protection, we simply ignore telemetry in this case.
        env = os.environ.copy()
        if "python" not in self.python_exe.name:
            self.python_exe = shutil.which("python" if is_windows()
                                           else "python3")
            env.pop('PYTHONHOME', None)
            env.pop('PYTHONPATH', None)
            if not self.python_exe:
                simics.SIM_log_info(
                    2, self.obj, 0,
                    "No Python interpreter found, ignoring telemetry data")
                return
        sender_path = os.path.join(os.path.dirname(__file__), 'sender.py')
        if not os.path.exists(sender_path):
            simics.SIM_log_info(2, self.obj, 0,
                                "No sender.py found, ignoring telemetry data")
            return
        python_args = [sender_path]
        if is_windows():
            from subprocess import CREATE_NEW_PROCESS_GROUP
            # When you use the py launcher or a virtual environment on
            # Windows DEATCHED_PROCESS is not passed on to the actual python
            # process the python launcher runs. Instead we use
            # CREATE_NO_WINDOW.
            # See https://github.com/python/cpython/issues/85785
            CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
            extra_args = {'creationflags':
                          CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}
            # Set cwd to allow Simics directory be deleted before sender exits.
            # Try a few things to be more sure that the directory exists.
            for d in [os.path.expanduser("~"), os.path.realpath("/")]:
                if os.path.exists(d):
                    cwd_arg = d
                    break
            else:
                cwd_arg = "C:\\"
            extra_args['cwd'] = cwd_arg
        else:
            extra_args = {'preexec_fn': os.setsid}
            # Add "-B" not to create .pyc files. Thus, we avoid races observed
            # when the "rm -fr <simics-install>" command is executed immediately
            # after Simics exit. In this case, a still running sender process
            # may create .pyc files and confuse "rm" process.
            python_args.insert(0, "-B")

        self.stats_sender = Popen([self.python_exe] + python_args,
                                  stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL,
                                  bufsize=1, shell=False,
                                  text=True, env=env,
                                  close_fds = True, **extra_args)

    def print_notice(self):
        notice = pathlib.Path(conf.sim.settings_dir) / 'telemetry_notice'
        if not notice.is_file():
            notice.touch()
            print("Intel-internal collection of telemetry data enabled."
                  " For details see: https://circuit.intel.com/content/corp/"
                  "Global_Employee_and_Global_Contingent_Worker_Privacy.html")

    class telemetry_manager(pyobj.Interface):
        def add_data(self, group, key, val):
            if not hasattr(self._up, "stats_sender"):
                return
            try:
                self._up.stats_sender.stdin.write(
                    json.dumps(
                        {'group': group, 'key': key, 'value': val}) + '\n')
                # flush explicitly (bufsize doesn't affect stdin pipe)
                self._up.stats_sender.stdin.flush()
            except IOError:
                pass  # ignore any errors with sending since it is not critical
