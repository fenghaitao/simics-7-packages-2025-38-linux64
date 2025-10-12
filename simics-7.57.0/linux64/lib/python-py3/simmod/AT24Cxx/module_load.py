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


import cli

def info(obj):
    i2c_address = obj.i2c_address
    if obj.i2c_bus:
        connector = ('I2C bus', obj.i2c_bus.name)
    else:
        connector = ('I2C link', obj.i2c_link_v2.name)

    return [(None,
             [connector,
              ('Memory size', '%s bytes' % len(obj.memory)),
              ('I2C address', "0x%x" % i2c_address)
              ])]

cli.new_info_command("AT24Cxx", info)

def status(obj):
    state = ['clear', 'got start', 'got start and address'][obj.current_state]
    return [(None,
             [('Current address', obj.current_address),
              ('Device state', state),
              ])]

cli.new_status_command("AT24Cxx", status)
