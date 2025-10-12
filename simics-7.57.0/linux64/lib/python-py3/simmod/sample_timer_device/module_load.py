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


from cli import new_info_command, new_status_command

def info(obj):
    return [(None,
             [("Interrupt Device", obj.attr.irq_dev)])]

def status(obj):
    return [(None,
             [('Reference', obj.attr.regs_reference),
              ('Counter start time', obj.attr.regs_counter_start_time),
              ('Counter start value', obj.attr.regs_counter_start_value)])]

new_info_command("sample_timer_device", info)
new_status_command("sample_timer_device", status)
