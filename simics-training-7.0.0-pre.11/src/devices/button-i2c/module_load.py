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
## module-load.py for the button on I2C
##
## Define the info and status commands for the module. 
## 
import cli

def info(obj):
    return [("I2C configuration",
             [("I2C device address", obj.address),
              ("I2C address to notify ", obj.notify_address),
              ("I2C link", obj.i2c_link)])]
    # add attached LED display unit

def status(obj):
    return [("Current button state",
             [("Pressed", obj.i2cregs_button_pressed)]),
            ("I2C transaction",
             [("Bus busy", (obj.i2cregs_i2c_slave_state & 0x02 != 0))])]

cli.new_info_command("button_i2c", info)
cli.new_status_command("button_i2c", status)
