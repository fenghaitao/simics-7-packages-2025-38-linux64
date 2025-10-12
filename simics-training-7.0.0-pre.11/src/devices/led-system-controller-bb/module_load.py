# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


##
## module-load.py for the LED system controller black-box model
##
## Define the custom info and status commands
## 

import cli
import conf
import simics

class_name = 'led_system_controller_bb'

#
# ------------------------ info -----------------------
#
# Uses cli.number_str to nicely format big values
# frequencies are forced to base 10 with 3-digit grouping

def get_info(obj):
    return [("I2C configuration",
             [("I2C link", obj.i2c_link),
              ("I2C device address", obj.i2c_address)]),
            ("Memory configuration",
             [("Local memory",     obj.local_memory),
              ("Framebuffer base", cli.number_str(obj.regs_framebuffer_base_address, radix=16,group=4))]),
            ("Timing", 
             [("Clock frequency", cli.number_str(obj.fw_clock_frequency  ,radix=10,group=3)),
              ("Pixel update time", cli.number_str(obj.pixel_update_time ,radix=10,group=3)),
              ("Toggle check interval", cli.number_str(obj.toggle_check_interval ,radix=10,group=3))])]
cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    return [("Software-visible flags",
             [("Button A status", obj.regs_button_a_status),
              ("Button B status", obj.regs_button_b_status),                 
              ("Toggle 0 status", obj.regs_toggle_status[0]),
              ("Toggle 1 status", obj.regs_toggle_status[1]),
              ("Update display status", obj.regs_update_display_status),
              ("Update display request", obj.regs_update_display_request)
             ]),
            ("Software-provided configuration",
             [("Display width",  obj.regs_display_width),
              ("Display height", obj.regs_display_height),
              ("Display i2c base address", cli.number_str(obj.regs_display_i2c_base)),                
              ("Button A i2c base address", cli.number_str(obj.regs_button_a_i2c_address)),
              ("Button B i2c base address", cli.number_str(obj.regs_button_b_i2c_address)),
              ("Toggle 0 i2c base addresses", cli.number_str(obj.regs_toggle_i2c_address[0])),
              ("Toggle 1 i2c base addresses", cli.number_str(obj.regs_toggle_i2c_address[1])),
                            ])]

cli.new_status_command(class_name, get_status)

#
# -------------------- Common PCI commands -------------------
#
if conf.sim.version < simics.SIM_VERSION_7:
    import pci_common
    pci_common.new_pci_config_regs_command(class_name, None)
