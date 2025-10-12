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
## module-load.py for the Toggle on I2C
##
## Define the custom info and status commands for the toggle devices
## 
## Tested in pure Python 3 in Simics 6, and works
##
import cli  

def info(obj):
    return [(None,
             [("I2C Device Address", obj.address),
              ("I2C Link", obj.i2c_link)])]

def status(obj):
    return [("Current toggle value",
             [("value", obj.i2cregs_toggle_state)])]

cli.new_info_command("toggle_i2c", info)
cli.new_status_command("toggle_i2c", status)
