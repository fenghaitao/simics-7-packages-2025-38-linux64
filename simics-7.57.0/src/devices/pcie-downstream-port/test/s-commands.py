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
import simics
import stest
import random
random.seed("Sun Sinking Low")

dp = simics.SIM_create_object('pcie-downstream-port', 'dp', [])
dummy = simics.SIM_create_object('set-memory', 'dummy', [])

for (port, space) in ((dp.port.cfg, dp.cfg_space),
                      (dp.port.mem, dp.mem_space),
                      (dp.port.io,  dp.io_space),
                      (dp.port.msg, dp.msg_space)):
    space.map = [[random.randrange(1 << 64), dummy, 0, 0, 0x100]]
    stest.expect_equal(port.cli_cmds.map(), space.map)
    stest.expect_equal(cli.quiet_run_command(f'{port.name}.map'),
                       cli.quiet_run_command(f'{space.name}.map'))
