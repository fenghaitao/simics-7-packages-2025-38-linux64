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
import conf
import simics

class_name = 'm_control'
class_name_stall = 'm_control_stall'

#
# ------------------------ info -----------------------
#

def get_stall_time(obj):
    try:
        # Try to read, if it fails it means the attribute
        # was missing -> return zero.  Simpler and more
        # robust in many cases than looking for the existence
        # of the attribute.  Since it is not around unless
        # stalling is compiled into the device model.
        st = obj.attr.status_reg_stall_time
        return int(st*1e12)  # Make into picoseconds
    except:
        return 0

def get_info(obj):
    return [("Control unit configuration",
             [("Number of live compute units", obj.attr.connected_compute_unit_count),
              ("Compute unit control ports", obj.attr.compute_unit_control),
              ("Signal target for done (optional)", obj.attr.operation_done),
              ("Memory space for register banks", obj.attr.register_memory),
              ("Memory space for local memory", obj.attr.local_memory),
              ]),
            ("Performance settings",
             # Note special call to cli.number_str to get number formatted using
             # the output-radix and digit-grouping settings -- but setting the
             # radix to 10 always since time in hexadecimal makes little sense
             [("Stall on status register access (ps)", cli.number_str(get_stall_time(obj),radix=10))]
             )
            ]

cli.new_info_command(class_name, get_info)
cli.new_info_command(class_name_stall, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Current operation state",
             [("Done flag", ( obj.bank.ctrl.status == 0x8000_0000_0000_0000 )),
              ("Processing flag", ( obj.bank.ctrl.status == 0x4000_0000_0000_0000 )),             
              ("Compute units used for current job", obj.bank.ctrl.start),             
             ])]

cli.new_status_command(class_name, get_status)
cli.new_status_command(class_name_stall, get_info)

#
# -------------------- Common PCI commands -------------------
#
# Really only include if PCIe is built into the device.
# 
if conf.sim.version < simics.SIM_VERSION_7:
    import pci_common
    pci_common.new_pci_config_regs_command(class_name, None)
    pci_common.new_pci_config_regs_command(class_name_stall, None)
