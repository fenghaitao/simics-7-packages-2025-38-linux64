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

from cli import (
    CliError,
    get_available_object_name,
    new_command,
)
from simics import *

from real_ethernet_network import get_service_node_impl

def enable_ftp_alg_cmd(sn, check_enabled = True):
    sn = get_service_node_impl(sn)
    try:
        in_obj = SIM_get_object("%s_port_forward_in" % sn.name)
    except:
        raise CliError("The service node %s does not have incoming port "
                       "forwarding enabled." % sn.name)
    try:
        out_obj = SIM_get_object("%s_port_forward_out" % sn.name)
    except:
        raise CliError("The service node %s does not have outgoing port "
                       "forwarding enabled." % sn.name)

    if len([x for x in in_obj.algs if x.classname == 'ftp-alg']):
        if check_enabled:
            print("FTP ALG already enabled for service-node %s." % sn.name)
        return

    alg_name = get_available_object_name(sn.name + "_ftp_alg")
    alg_obj = SIM_create_object("ftp-alg", alg_name,
                                [["forward_handler", out_obj],
                                 ["incoming_handler", in_obj]])
    in_obj.algs = in_obj.algs + [alg_obj]
    out_obj.algs = out_obj.algs + [alg_obj]

# Add enable-ftp-alg command to service node namespace

def register_ftp_alg_cmd(cls):
    new_command("enable-ftp-alg", enable_ftp_alg_cmd,
                [],
                type = ["Networking"],
                short = "enable FTP ALG",
                cls = cls,
                doc = """
                Enable the FTP ALG. FTP ALG processing is needed to support
                port forwarded FTP from the outside network to simulated
                machines.
                """)
