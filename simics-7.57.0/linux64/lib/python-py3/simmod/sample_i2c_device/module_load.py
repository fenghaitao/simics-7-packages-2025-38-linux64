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
             [("I2C Device Address", obj.attr.address),
              ("I2C Link", obj.attr.i2c_link_v2)])]

def status(obj):
    return [(None,
             [("Read Value", obj.attr.read_value),
              ("Written Value", obj.attr.written_value)])]

new_info_command("sample_i2c_device", info)
new_status_command("sample_i2c_device", status)
