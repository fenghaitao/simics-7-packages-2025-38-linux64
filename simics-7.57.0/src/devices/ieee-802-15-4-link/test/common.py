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

def create_test_bench(clock_name='clk', clock_freq=1,
                      dev_name_base='dev', dev_num=2):
    cell = simics.pre_conf_object('cell', 'cell')

    clk = simics.pre_conf_object(clock_name, 'clock')
    clk.freq_mhz = clock_freq
    clk.cell = cell

    link_impl = simics.pre_conf_object('link_impl', 'ieee_802_15_4_link_impl')
    link_impl.queue = clk
    link_impl.goal_latency = 1e-6

    devs = [None] * dev_num
    eps = [None] * dev_num

    for i in range(dev_num):
        devs[i] = simics.pre_conf_object('%s_%d' % (dev_name_base, i),
                                         'sample_802_15_4_transceiver')
        devs[i].queue = clk

        eps[i] = simics.pre_conf_object('ep_%d' % i,
                                        'ieee_802_15_4_link_endpoint')
        eps[i].device = devs[i]
        devs[i].ep = eps[i]
        eps[i].id = i + 1  # ID cannot be 0 or 0xffffffffffffffff
        eps[i].link = link_impl
        eps[i].queue = clk

    simics.SIM_add_configuration([cell, clk, link_impl] + eps + devs, None)

    return [[simics.SIM_get_object("%s_%d" % (dev_name_base, i))
             for i in range(dev_num)],
            [simics.SIM_get_object("ep_%d" % i) for i in range(dev_num)],
            [simics.SIM_get_object("link_impl")]]

def create_test_bench_by_components(link_name='link0',
                                    node_name_base='node', node_num=2):
    simics.SIM_run_command('load-module clock')
    simics.SIM_run_command('create-cell-and-clocks-comp')
    simics.SIM_run_command('load-module ieee-802-15-4-link')
    simics.SIM_run_command(
        'create-ieee-802-15-4-link name = %s goal_latency = 4e-3' % link_name)
    simics.SIM_run_command('load-module  sample-802-15-4-transceiver-comp')
    for i in range(node_num):
        simics.SIM_run_command(
                 'create-sample-802-15-4-transceiver-comp name = %s_%d'
                 % (node_name_base, i))
        simics.SIM_run_command(
                'connect cnt0 = node_%d.phy cnt1 = link0.device%d' % (i, i))
    simics.SIM_run_command('instantiate-components')
    return [[simics.SIM_get_object("%s_%d.transceiver" % (node_name_base, i))
             for i in range(node_num)], ]
