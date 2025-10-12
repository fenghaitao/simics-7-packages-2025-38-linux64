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


import cli
from simics import *

Sim_Save_Gzip_Config = 4

def SIM_is_loading_micro_checkpoint(obj):
    return SIM_object_is_configured(obj) and SIM_is_restoring_state(obj)

def SIM_current_processor():
    return VT_get_current_processor()
