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
import os
import re
import simics
import subprocess
import tempfile
import threading

from simicsutils.host import is_windows, host_type

from . import tcf_client
from . import standalone_client

def log_modes(ignored=[
        'alloc', 'discovery', 'events', 'asyncreq', 'eventcore']):
    return list(
        set(['alloc',
             'asyncreq',
             'children',
             'context',
             'discovery',
             'elf',
             'eventcore',
             'events',
             'plugin',
             'protocol',
             'proxy',
             'shutdown',
             'stack',
             'tcflog',
             'waitpid']) - set(ignored))

def find_test_proxy():
    from simicsutils.internal import testfiles_path
    from simicsutils.host import is_windows
    import glob
    base = os.path.join(testfiles_path(), 'tcf-agent-test', 'isd', 'isd-proxy')
    if not os.path.isdir(base):
        return None
    proxy_abs_dirs = glob.glob(os.path.join(base, "*"))
    proxy_dirs = [d.split(os.path.sep)[-1] for d in proxy_abs_dirs]
    candidates = [int(d) for d in proxy_dirs if d.isnumeric()]
    while candidates:
        latest = str(candidates.pop())
        binary_name = 'isd-proxy' + ('.exe' if is_windows() else '')
        binary_path = os.path.join(base, latest, binary_name)
        if os.path.isfile(binary_path):
            return binary_path
    return None

def isd_proxy_path():
    test_proxy = find_test_proxy()
    if test_proxy:
        return test_proxy
    raise Exception('Specify isd-proxy binary with proxy_binary argument or'
                    ' by setting ISD_PROXY_BIN environment variable')

def win_kill_process_on_exit(process):
    assert is_windows()

    import win32api
    import win32job
    import win32con
    # When all references to a job are lost then Windows will kill the process
    # associated with that job. This means that if Simics dies the process will
    # be killed.
    proc = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False,
                                process.pid)
    job = win32job.CreateJobObject(None, '')
    e_info = win32job.QueryInformationJobObject(
        job, win32job.JobObjectExtendedLimitInformation)
    e_info['BasicLimitInformation'][
        'LimitFlags'] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(
        job, win32job.JobObjectExtendedLimitInformation, e_info)
    win32job.AssignProcessToJobObject(job, proc)
    return job

class ISDProxy:
    def __init__(self, isd_proxy_file, proxy_tcf_log, client_tcf_log,
                 timeout=3600, proxy_port=None, proxy_stderr_file=None):
        # If proxy_port is set this will connect to and existing proxy instead
        # of creating a new one.
        if proxy_port is None:
            self.proxy_port = self._start_isd_proxy(
                isd_proxy_file, proxy_tcf_log, client_tcf_log,
                proxy_stderr_file, timeout)
        else:
            self.proxy_port = proxy_port
        self.tcf_client = self.create_client(client_tcf_log)
        self.in_client = self.tcf_client.in_client

    def _start_isd_proxy(self, isd_proxy_file, proxy_tcf_log, client_tcf_log,
                         proxy_stderr_file, timeout):
        env = os.environ.copy()
        if is_windows():
            # Reaper will not kill orphants on Windows, so that cannot be used.
            reaper_cmd = []
        else:
            reaper_path = simics.SIM_lookup_file(
                f'%simics%/{host_type()}/bin/reaper')
            assert reaper_path
            reaper_cmd = [reaper_path, "-t", str(timeout)]
            env['LD_LIBRARY_PATH'] = os.path.dirname(isd_proxy_file)
        self.process_cmd = reaper_cmd + [isd_proxy_file, '-L%s' % proxy_tcf_log,
                                        '-l%s' % ','.join(log_modes()), '-S']
        self.process = subprocess.Popen(
            self.process_cmd, stdout=subprocess.PIPE, stderr=proxy_stderr_file,
            encoding='utf-8', env=env)
        port_search_res = re.findall('"Port":"([0-9]+)"',
                                     self.process.stdout.readline())
        if not port_search_res:
            if self.process.poll() is not None:
                raise Exception('isd-proxy exited with code'
                                f' {self.process.returncode}')
            self.process.terminate()
            raise Exception('No "Port" output from isd-proxy')

        proxy_port = int(port_search_res[0])
        if is_windows():
            # Need to keep reference to process_job, the process will be killed
            # once the reference is lost.
            self.process_job = win_kill_process_on_exit(self.process)
        self.supervisor = threading.Thread(target=self.proc_supervisor)
        self.supervisor.start()
        assert(self.supervisor.is_alive)
        return proxy_port

    def proc_supervisor(self):
        status = None
        while status is None:
            stdout_txt = self.process.stdout.readline()
            if stdout_txt:
                print('{}'.format(stdout_txt))
            status = self.process.poll()
        raise Exception('isd-proxy exited unexpectedly with return code'
                        f' {status}')

    def create_client(self, client_tcf_log):
        (simics_host, simics_port) = tcf_client.get_host_and_port()
        self.simics_port = simics_port
        self.simics_host = simics_host
        return tcf_client.TCF(simics_host, self.proxy_port, client_tcf_log)

    def std_command(self, service, cmd, *payload, **kwargs):
        if self.in_client is None:
            raise Exception('Must call create_client prior to running command')
        return self.in_client(lambda tcf: tcf.std_command(service, cmd,
                                                          *payload, **kwargs))

    def command(self, service, cmd, *payload, **kwargs):
        if self.in_client is None:
            raise Exception('Must call create_client prior to running command')
        return self.in_client(lambda tcf: tcf.command(service, cmd, *payload,
                                                      **kwargs))

    def sync_proxy_rc_state(self):
        ctx_id = self.std_command('ContextQuery', 'query', '"*"')[0]
        # getCapabilities will trigger id2ctx will which wait until run control
        # sync has completed in isd-proxy before replying.
        self.std_command('Disassembly', 'getCapabilities', ctx_id)

    def run_until_proxy_ready(self):
        self.tcf_client.run_until_event('Locator', 'Hello')
        #self.sync_proxy_rc_state()  # Remove once DEBGGR-14593 is fixed

    def redirect(self, host=None, port=None):
        if host is None:
            host = self.simics_host
        if port is None:
            port = self.simics_port
        peer_data = {'Host': host, 'Port': str(port)}
        return self.std_command('Locator', 'redirect', peer_data)

    def connect_proxy(self):
        self.redirect()
        self.run_until_proxy_ready()

    def resume_and_wait(self, ctx, mode=standalone_client.RM_RESUME,
                        timeout=30):
        return self.in_client(lambda tcf: tcf.resume_and_wait(
            ctx, mode, timeout=timeout))


def _launch_proxy_common(log_dir, proxy_binary, proxy_port=None):
    if log_dir is None:
        log_dir = tempfile.gettempdir()
    if not os.path.isdir(log_dir):
        raise Exception(f'Not a dir: {log_dir}')
    timestamp = tcf_client.curr_time_str()
    client_log = os.path.join(log_dir, f'client-{timestamp}.log')
    proxy_log = os.path.join(log_dir, f'proxy-{timestamp}.log')
    if proxy_binary is None:
        proxy_binary = isd_proxy_path()
    if not os.path.isfile(proxy_binary):
        raise Exception(f'Proxy binary {proxy_binary} is not a file')
    proxy = ISDProxy(proxy_binary, proxy_log, client_log,
                     proxy_port=proxy_port)
    return proxy

def create_proxy_and_connect(log_dir=None, proxy_port=None,
                             proxy_binary=None):
    proxy = _launch_proxy_common(log_dir, proxy_binary, proxy_port)
    proxy.connect_proxy()
    return proxy


def create_proxy_only(log_dir=None, proxy_binary=None):
    return _launch_proxy_common(log_dir, proxy_binary)
