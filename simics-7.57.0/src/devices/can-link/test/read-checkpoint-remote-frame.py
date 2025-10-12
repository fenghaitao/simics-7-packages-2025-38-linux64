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
import os
import shutil

from common import *
from device import *

output_ckpt = os.path.join(conf.sim.project, 'remote_frame')
if os.path.exists(output_ckpt) == False:
    stest.fail(output_ckpt + ' does not exist!')

# Make sure we can load the checkpoints.
SIM_read_configuration(output_ckpt)

SIM_continue(10000)

if os.path.exists(output_ckpt):
    shutil.rmtree(output_ckpt)
