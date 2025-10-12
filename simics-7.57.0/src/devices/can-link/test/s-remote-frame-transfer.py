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


import stest

from common import *

tb = TestBench(8)

import simmod.can_interface
from simmod.can_interface import can_interface

default             = can_interface.can_frame_t()
default.extended    = False
default.identifier  = 0
default.rtr         = False
default.data_length = 0
default.data        = (0,)*8
default.crc         = 0

x             = can_interface.can_frame_t()
x.extended    = True
x.identifier  = 9
x.rtr         = True
x.data_length = 0
x.data        = (1,) * 8
x.crc         = 9

sender = 0
tb.distribute_message(sender, x)

SIM_continue(1000000)
rev_message = can_interface.can_frame_t()
for i in range(8):
    rev_message.extended    = tb.dev_array[i].frame_extended
    rev_message.identifier  = tb.dev_array[i].frame_identifier
    rev_message.rtr         = tb.dev_array[i].frame_rtr
    rev_message.data_length = tb.dev_array[i].frame_data_length
    rev_message.data        = tuple(tb.dev_array[i].frame_data)
    rev_message.crc         = tb.dev_array[i].frame_crc

    if i != sender:
        expect_can_frame(x,rev_message)
    else:
        expect_can_frame(default,rev_message)
