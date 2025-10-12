# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# These tools are used to create TCF clients that connect to Simics TCF.
# These are for internal use.

import os.path
import sys
import tempfile
import time

def connect_simics_tcf(log_dir=None):
    """Create a TCF client and connect to Simics TCF agent."""
    from .tcf_client import tcf_client
    if log_dir is None:
        log_dir = tempfile.gettempdir()
    return tcf_client.TCFClient(log_dir)

def connect_isd_proxy(proxy_binary=None, proxy_port=None, log_dir=None):
    """Create a client, connect to isd-proxy and redirect to Simics TCF agent.

    If proxy_port is specified, either by the argument or ISD_PROXY_PORT
    environment variable, then connect to a running proxy. Otherwise start a
    new isd-proxy. The binary can be specified using the proxy argument or by
    setting the environment variable ISD_PROXY_BIN.
    """
    from .tcf_client import isd_proxy

    if log_dir is None:
        log_dir = tempfile.gettempdir()
    if proxy_port is None:
        proxy_port = os.environ.get('ISD_PROXY_PORT')
    if proxy_binary is None:
        proxy_binary = os.environ.get('ISD_PROXY_BIN')

    return isd_proxy.create_proxy_and_connect(
        log_dir=log_dir, proxy_port=proxy_port, proxy_binary=proxy_binary)


def launch_isd_proxy(proxy_binary=None, log_dir=None):
    if proxy_binary is None:
        proxy_binary = os.environ.get('ISD_PROXY_BIN')
    from .tcf_client import isd_proxy
    p = isd_proxy.create_proxy_only(log_dir, proxy_binary)
    print(f"isd-proxy launched with port {p.proxy_port}")
    return p
