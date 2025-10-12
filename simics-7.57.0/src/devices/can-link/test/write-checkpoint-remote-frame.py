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


from common import *

tb = TestBench(8, 0.1)

import simmod.can_interface
from simmod.can_interface import can_interface

x             = can_interface.can_frame_t()
x.extended    = True
x.identifier  = 9
x.rtr         = True
x.data_length = 0
x.data        = (1,) * 8
x.crc         = 9

sender = 0
tb.distribute_message(sender, x)

SIM_continue(1)


# Create a checkpoint for remote frame.
import os
import shutil
output_ckpt = os.path.join(conf.sim.project, 'remote_frame')
if os.path.exists(output_ckpt):
    shutil.rmtree(output_ckpt)

SIM_write_configuration_to_file(output_ckpt, Sim_Save_Nobundle)
