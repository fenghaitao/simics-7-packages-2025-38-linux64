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
    return [('Connection info', [('Bus', obj.firewire_bus)])]

def context_state(ctrlRegVal):
    if ctrlRegVal & 0x400: return 'Active'
    if ctrlRegVal & 0x800: return 'Dead'
    if not (ctrlRegVal & 0x8000): return 'Enabled'
    return 'Disabled'

def contexts(obj):
    return [("%s Context" % (name,), context_state(reg))
            for name, reg in [('ATRQ', obj.ohci_ATRQ_ContextControl_reg),
                              ('ARRS', obj.ohci_ARRS_ContextControl_reg)]]
def status(obj):
    return [('Firewire status', [('ID', obj.firewire_config_registers_node_ids >> 16)]),
            ('Contexts', contexts(obj))]

cli.new_info_command('TSB12LV26', info)
cli.new_status_command('TSB12LV26', status)
