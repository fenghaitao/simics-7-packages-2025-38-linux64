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

class_name = 'i_mailbox'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    return [("",
             [("Far mailboxes' base address", hex(obj.shared_mem_mailbox_base_attr)),
              ("Connected memory", obj.phys_mem),
              ("Connected interrupt", obj.irq)])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    
    if obj.bank.c_regs.far_end_id != 0:
        role = f"Send requests to mailbox at subsystem index {obj.bank.c_regs.far_end_id - 1}."
        state = None
    else:
        role = "Respond to mailbox requests."
        if obj.rsp_requested_attr and obj.irq_state_attr:
            state = "Request received. Waiting for request to be read."
        elif obj.rsp_requested_attr and not obj.rsp_valid_attr:
            state = "Request read. Waiting for response to be written."
        elif obj.rsp_requested_attr and obj.rsp_valid_attr:
            state = "Response written. Waiting for response to be read by requester."
        elif not obj.rsp_requested_attr:
            state = "Waiting for request to be sent by requester."
        else:
            state = "Unexpected state."
    
    status = [("Role", role)]
    if state:
        status += [("State", state)]
    rv = [("", status)]
    return rv

cli.new_status_command(class_name, get_status)
