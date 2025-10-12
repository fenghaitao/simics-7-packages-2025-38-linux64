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
import pci_common

def get_x58_remap_unit_status(o):
    ret = []
    if o.vtd_pmem & 1:
        # protected regions enabled
        low = "0x%08x - 0x%08x" % (o.vtd_plmbase, o.vtd_plmlimit + 0xffffff)
        high = "0%016x - 0%016x " % (o.vtd_phmbase, o.vtd_phmlimit + 0xfffff)
        ret = [('Protected Regions',
                [('Low', low),
                 ('High', high)]),
               ]
    return ret

def get_x58_info(o):
    return pci_common.get_pci_info(o)

def get_x58_status(o):
    return []

def get_info_nothing(o):
    return []


cli.new_info_command('x58-dmi-legacy', get_x58_info)
cli.new_status_command('x58-dmi-legacy', get_x58_status)

cli.new_info_command('x58-core-f0-legacy', get_x58_info)
cli.new_status_command('x58-core-f0-legacy', get_x58_status)

cli.new_info_command('x58-core-f1-legacy', get_x58_info)
cli.new_status_command('x58-core-f1-legacy', get_x58_status)

cli.new_info_command('x58-core-f2-legacy', get_x58_info)
cli.new_status_command('x58-core-f2-legacy', get_x58_status)

cli.new_info_command('x58-core-f3-legacy', get_x58_info)
cli.new_status_command('x58-core-f3-legacy', get_x58_status)

cli.new_info_command('x58-ioxapic-legacy', get_x58_info)
cli.new_status_command('x58-ioxapic-legacy', get_x58_status)

cli.new_info_command('x58-qpi-port0-f0-legacy', get_x58_info)
cli.new_status_command('x58-qpi-port0-f0-legacy', get_x58_status)

cli.new_info_command('x58-qpi-port0-f1-legacy', get_x58_info)
cli.new_status_command('x58-qpi-port0-f1-legacy', get_x58_status)

cli.new_info_command('x58-qpi-port1-f0-legacy', get_x58_info)
cli.new_status_command('x58-qpi-port1-f0-legacy', get_x58_status)

cli.new_info_command('x58-qpi-port1-f1-legacy', get_x58_info)
cli.new_status_command('x58-qpi-port1-f1-legacy', get_x58_status)

cli.new_info_command('x58-pcie-port-legacy', get_x58_info)
cli.new_status_command('x58-pcie-port-legacy', get_x58_status)

cli.new_info_command('x58-remap-unit0-legacy', get_info_nothing)
cli.new_status_command('x58-remap-unit0-legacy', get_x58_remap_unit_status)

cli.new_info_command('x58-remap-unit1-legacy', get_info_nothing)
cli.new_status_command('x58-remap-unit1-legacy', get_x58_remap_unit_status)

cli.new_info_command('x58-remap-dispatcher-legacy', get_info_nothing)
cli.new_status_command('x58-remap-dispatcher-legacy', get_x58_status)

cli.new_info_command('x58-qpi-sad-f1-legacy', get_info_nothing)
cli.new_status_command('x58-qpi-sad-f1-legacy', get_x58_status)

cli.new_info_command('x58-qpi-ncr-f0-legacy', get_info_nothing)
cli.new_status_command('x58-qpi-ncr-f0-legacy', get_x58_status)
