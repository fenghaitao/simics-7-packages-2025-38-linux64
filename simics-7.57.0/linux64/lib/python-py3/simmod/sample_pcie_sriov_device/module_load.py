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


import simics
from cli import new_info_command, new_status_command
import re

def info(obj):
    f0 = simics.SIM_object_descendant(obj, 'f0')
    f5 = simics.SIM_object_descendant(obj, 'f5')
    pfs = [f0.PF.bank.pcie_config, f5.PF.bank.pcie_config]
    return ([(None,
             [('Number of supported Physical Functions', len(pfs))])] +
             [('%s' % pf,
              [('Function Number', i),
               ('First VF Offset', pf.sriov_first_vf_offset),
               ('Total VF Number', pf.sriov_total_vfs),
               ('Initial VFs', pf.sriov_initial_vfs),
               ('VF Stride', pf.sriov_vf_stride),
               ('VF Device ID', '0x%x' % pf.sriov_vf_device_id),
               ('Supported Page Sizes', '0x%x' % pf.sriov_supported_page_sizes)])
              for i, pf in enumerate(pfs)])

def status(obj):
    f0 = simics.SIM_object_descendant(obj, 'f0')
    f5 = simics.SIM_object_descendant(obj, 'f5')
    pfs = [f0.PF.bank.pcie_config, f5.PF.bank.pcie_config]
    return [('%s' % pf,
             [('VF Enable', ['False', 'True'][pf.sriov_control & 0x1]),
              ('VF Number', pf.sriov_num_vfs),
              ('System Page Size', pf.sriov_system_page_size << 12),
             ])
             for pf in pfs]

new_info_command('sample_pcie_sriov_device', info)
new_status_command('sample_pcie_sriov_device', status)
