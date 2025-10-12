# © 2014 Intel Corporation
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

def create_ieee_802_15_4_probe(name=None,
                               probe_base='probe',
                               link_name='link0',
                               goal_latency=1e-3,
                               device_base="device",
                               device_num=2):
    '''Create a new ieee_802_15_4_probe object'''
    simics.SIM_run_command('load-module ieee-802-15-4-link')
    simics.SIM_run_command('load-module sample-802-15-4-transceiver-comp')
    simics.SIM_run_command('load-module ieee-802-15-4-probe')
    simics.SIM_run_command('load-module clock')
    simics.SIM_run_command('create-cell-and-clocks-comp')

    simics.SIM_run_command(
                'create-ieee-802-15-4-link name = %s goal_latency = %f'
                % (link_name, goal_latency))

    for i in range(device_num):
        simics.SIM_run_command(
                'create-sample-802-15-4-transceiver-comp name = %s_%d'
                % (device_base, i))
        simics.SIM_run_command(
                'connect cnt0 = %s_%d.phy cnt1 = %s.device%d'
                % (device_base, i, link_name, i))


    simics.SIM_run_command('instantiate-components')

    for i in range(device_num):
        simics.SIM_run_command(
                               'insert-ieee-802-15-4-probe name = %s_%d'
                               ' device = %s_%d.transceiver'
                               % (probe_base, i, device_base, i))

    return [[simics.SIM_get_object('%s_%d' % (probe_base, i))
             for i in range(device_num)],
            [simics.SIM_get_object('%s_%d.transceiver' % (device_base, i))
             for i in range(device_num)],
            [simics.SIM_get_object(link_name)]]
