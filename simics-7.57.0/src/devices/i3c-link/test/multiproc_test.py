# © 2017 Intel Corporation
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
import random
import sys
import subprocess
import testparams
import tempfile

__all__ = ['add_multiproc_test']

def start_node(script, total_nodes, node_id, timeout):
    os.environ['TOTAL_NODES'] = str(total_nodes)
    os.environ['NODE_ID'] = str(node_id)
    if script.endswith('.py'):
        args = ["-p", script]
    else:
        args = [script]
    out = tempfile.SpooledTemporaryFile()
    proc = testparams.run_simics(args, timeout, asynchronous=True, outfile=sys.stdout)
    return (proc, out)

def run_multi_simics(script, total_nodes, timeout):
    nodes = [start_node(script, total_nodes, i, timeout)
             for i in  range(total_nodes)]
    fails = 0
    for (proc, out) in nodes:
        ret = proc.wait()
        if ret != 0:
            fails += 1
        out.seek(0)
        for line in out:
            sys.stdout.write('=%d= %s' % (proc.pid, line))
        out.close()
    if fails:
        raise testparams.TestFailure('%d process failed' % (fails, ))

def add_multiproc_test(suite, script, total_nodes, name = None,
                       timeout = 120):
    if not name:
        name = testparams.script_to_name(script)
    suite.add_test(
            name,
            lambda: run_multi_simics(script, total_nodes, timeout))
