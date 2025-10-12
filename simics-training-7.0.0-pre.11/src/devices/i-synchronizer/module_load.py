# © 2024 Intel Corporation
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
from simics import SIM_get_object

class_name = 'i_synchronizer'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("",
             [("IRQ target", obj.irq),
              ("IRQ delay", f"{obj.irq_delay} cycles"),
              ("Number of subsystems", obj.num_sub_systems)])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("",
             [("Decrementer value", obj.bank.regs.decrementer_value)])]

cli.new_status_command(class_name, get_status)

class_name = 'i_synchronizer_e2l'

#
# ------------------------ info -----------------------
#

def get_info_e2l(obj):
    return [("",
             [("IRQ target", obj.level_out)])]

cli.new_info_command(class_name, get_info_e2l)

#
# ------------------------ status -----------------------
#

def get_status_e2l(obj):
    return [("",
             [("IRQ state", obj.irq_state_attr)])]

cli.new_status_command(class_name, get_status_e2l)
