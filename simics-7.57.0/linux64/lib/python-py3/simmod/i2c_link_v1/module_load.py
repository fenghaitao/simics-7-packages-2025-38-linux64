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

import simics
import deprecation

def get_info(obj):
    devices = sorted(obj.slave_devices)
    return [('Connected I2C slave devices',
             [("%#.2x" % addr, dev) for (dev, addr) in devices])]

def get_status(obj):
    slave = obj.current_slave
    master = obj.current_master
    if not slave:
        slave = '<none>'
    if not master:
        master = '<none>'
    return [(None,
             [ ('Current slave', slave),
               ('Current master', master),
               ('State', obj.link_state)]
             ) ]

new_info_command("i2c_link_v1", get_info)
new_status_command("i2c_link_v1", get_status)

deprecation.DEPRECATED(simics.SIM_VERSION_7,
                       "This module i2c_link_v1 and the i2c_master, i2c_slave interfaces have been deprecated.",
                        "Use the i2c-link-v2 module and interfaces i2c_master_v2 and i2c_slave_v2 instead.")
