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

device_name = 'interrupt_to_signal'

def get_info(obj):
    info_list = [('Description', 'Simple interrupt to Signal converter')]
    signal_targets = obj.signal_targets
    for target in signal_targets:
        id = target[0]
        object = target[1]
        port_name = target[2]
        if port_name == None:
            info_list.append(('Simple interrupt ID %d' % id,
                              '[%s]' % object.name))
        else:
            info_list.append(('Simple interrupt ID %d' % id,
                              '[%s, %s]' % (object.name, port_name)))
    return [(None, info_list)]

def get_status(obj):
    status_list = []
    signal_targets = obj.signal_targets
    for target in signal_targets:
        object = target[1]
        port_name = target[2]
        level = target[3]
        if port_name == None:
            status_list.append(('%s' % object.name, '%d' % level))
        else:
            status_list.append(('[%s, %s]' % (object.name, port_name),
                                '%d' % level))
    return [('Output levels', status_list)]

cli.new_info_command(device_name, get_info)
cli.new_status_command(device_name, get_status)
