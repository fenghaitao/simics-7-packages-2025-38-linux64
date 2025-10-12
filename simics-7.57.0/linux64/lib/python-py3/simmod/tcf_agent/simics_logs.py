# INTEL CONFIDENTIAL

# © 2021 Intel Corporation
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

def enable_logs_in_eclipse_console(enable):
    try:
        cli.global_cmds.log_setup()
        return None
    except cli.CliError as e:
        return str(e)
