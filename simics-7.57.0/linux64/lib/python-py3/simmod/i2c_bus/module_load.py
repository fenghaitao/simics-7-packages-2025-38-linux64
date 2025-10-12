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

from cli import (
    new_info_command,
    new_status_command,
)
import deprecation
import simics

def get_i2c_bus_info(obj):
    try:
        devices = sorted(obj.i2c_devices)
    except:
        devices = []
    return [('I2C devices',
             [("%#.2x" % addr, dev) for (dev, addr) in devices])]

def get_i2c_bus_status(obj):
    slave = obj.current_slave
    if not slave:
        slave = '<none>'
    state = [ 'idle', 'master transmit', 'master receive',
              'slave transmit', 'slave receive' ][obj.current_state]
    return [(None,
             [ ('Current slave', slave),
               ('Current state', state)
               ]
             ) ]

new_info_command("i2c-bus", get_i2c_bus_info)
new_status_command("i2c-bus", get_i2c_bus_status)

def get_adapter_info(obj):
    return [(None,
             [('I2C devices', obj.i2c_bus),
              ('I2c slave', obj.i2c_slave)])]

def get_adapter_status(obj):
    return []

new_info_command("i2c_slave_v2_to_bus_adapter", get_adapter_info)
new_status_command("i2c_slave_v2_to_bus_adapter", get_adapter_status)

deprecation.DEPRECATED(simics.SIM_VERSION_7,
                       "This module i2c_bus and the i2c_bus interface have been deprecated.",
                        "Use the i2c-link-v2 module and interfaces i2c_master_v2 and i2c_slave_v2 instead.")
