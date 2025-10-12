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
import io
import json
import os
import select
import simics
import sys
import threading
import time
import traceback
from queue import Queue
from . import standalone_client

def curr_time_str():
    t = time.localtime()
    return (f'{t.tm_year}{t.tm_mon:02}{t.tm_mday:02}-'
            f'{t.tm_hour:02}{t.tm_min:02}{t.tm_sec:02}')

def get_host_and_port():
    tcf = simics.SIM_get_debugger()
    props = tcf.properties.copy()
    if props is None:
        cli.quiet_run_command('start-eclipse-backend')
        props = tcf.properties.copy()
    if props is None:
        raise standalone_client.TCFClientError('No TCF properties found')
    simics_port = props.get('Port')
    if simics_port is None:
        cli.quiet_run_command('start-eclipse-backend')
        props = tcf.properties.copy()
        simics_port = props.get('Port')
        if simics_port is None:
            raise standalone_client.TCFClientError('No port found')
    simics_host = props.get('Host')
    if simics_host is None:
        simics_host = 'localhost'
    return (simics_host, simics_port)

class TCF(standalone_client.TCF):
    def in_client(self, f, *args, **kwargs):
        """Runs f in the tcf-agent client, ie in a separate thread

        This does not return until f is done, and then it returns the result
        of f. The function f should take one argument, which is the
        basic_tcf.TCF instance it can use to communicate with tcf-agent.
        """
        queue = Queue()
        def abort_if_needed(dummy):
            if simics.SIM_simics_is_running():
                print('Aborting Simics due to TCF client failure',
                      file=sys.stderr)
                simics.VT_abort_error(None, "TCF client failed")

        def client(*args, **kwargs):
            try:
                queue.put((True, f(self, *args, **kwargs)))
            except Exception as e:
                # The work failed. Abort Simics if needed and signal failure.
                # We need to abort. A SIM_continue in process_pending_work will
                # not return until the simulation is stopped.
                simics.SIM_thread_safe_callback(abort_if_needed, None)
                traceback.print_exc(file=sys.stderr)
                queue.put((False, e))

        thread = threading.Thread(target=client, args=args, kwargs=kwargs)
        thread.start()
        while thread.is_alive():
            simics.SIM_process_pending_work()
        thread.join()
        (ok, res) = queue.get(False)
        if ok:
            return res
        else:
            raise standalone_client.TCFClientError(
                f'Exception in TCF client: {res}')

class TCFClient:
    def __init__(self, log_dir, log_file=None, host=None, port=None, sync=True):
        self.host = host
        self.port = port
        self.sync = sync
        if log_file is None:
            log_file = self.default_log_file()
        self.client = self.create_client(log_dir, log_file)
        self.in_client = self.client.in_client

    def default_log_file(self):
        timestamp = curr_time_str()
        return f'client-{timestamp}.log'

    def create_client(self, log_dir, log_file):
        if not os.path.isdir(log_dir):
            raise standalone_client.TCFClientError(f'Not a dir: {log_dir}')
        client_log = os.path.join(log_dir, log_file)

        (simics_host, simics_port) = get_host_and_port()
        if self.host is None:
            self.host = simics_host
        if self.port is None:
            self.port = simics_port
        client = TCF(self.host, self.port, client_log)
        if self.sync:
            client.in_client(lambda tcf: tcf.std_command('Locator', 'sync'))
        return client

    def std_command(self, service, cmd, *payload, **kwargs):
        if self.in_client is None:
            raise standalone_client.TCFClientError(
                'Must call create_client prior to running command')
        return self.in_client(lambda tcf: tcf.std_command(service, cmd,
                                                          *payload, **kwargs))

    def command(self, service, cmd, *payload, **kwargs):
        if self.in_client is None:
            raise standalone_client.TCFClientError(
                'Must call create_client prior to running command')
        return self.in_client(lambda tcf: tcf.command(service, cmd, *payload,
                                                      **kwargs))
