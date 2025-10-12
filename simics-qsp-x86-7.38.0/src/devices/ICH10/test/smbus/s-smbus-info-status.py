# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# s-smbus-info-status.py
# tests if info and status command do not crash

from smbus_tb import *

def do_test():
    tb.smbus.cli_cmds.info()
    tb.smbus.cli_cmds.status()

do_test()
