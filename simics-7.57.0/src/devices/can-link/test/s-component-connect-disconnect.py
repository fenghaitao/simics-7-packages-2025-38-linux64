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


import stest
from can_link_comp import can_link_comp
import simics

for m in ['clock', 'can-link']:
    SIM_load_module(m)

def run(c):
    print("run: %s" % c)
    SIM_run_command(c)

def assert_link_connections(n):
    dyn_cnts = list(simics.SIM_object_iterator_for_class(
        'dynamic_link_connector'))
    l = sum([d.iface.connector.destination()[:] for d in dyn_cnts], [])
    stest.expect_equal(len(l), n)
    stest.expect_equal(len(dyn_cnts),n + 1)

def run_and_assert(cmd, link_connections):
    run(cmd)
    assert_link_connections(link_connections)

run('create-cell-and-clocks-comp cc')
run('create-can-link-comp dev0')
run('create-can-link-comp dev1')
run('create-can-link-comp dev2')

run('create-can-link link0')

run('dev0.get-connector-list')
run_and_assert('connect dev0.link link0.device0', 1)
run_and_assert('disconnect dev0.link link0.device0', 0)
run_and_assert('connect dev0.link link0.device1', 1)

run('instantiate-components')

run_and_assert('disconnect dev0.link link0.device1', 0)
run_and_assert('connect dev0.link link0.device0', 1)
run_and_assert('disconnect dev0.link link0.device0', 0)

run_and_assert('connect dev1.link link0.device1', 1)
run_and_assert('disconnect dev1.link link0.device1', 0)
run_and_assert('connect dev1.link link0.device0', 1)
run_and_assert('connect dev2.link link0.device1', 2)
run_and_assert('disconnect dev1.link link0.device0', 1)
run_and_assert('disconnect dev2.link link0.device1', 0)

run_and_assert('connect dev1.link link0.device2', 1)
run_and_assert('connect dev0.link link0.device0', 2)
run_and_assert('connect dev2.link link0.device1', 3)
run_and_assert('disconnect dev0.link link0.device0', 2)
run_and_assert('disconnect dev1.link link0.device2', 1)
run_and_assert('disconnect dev2.link link0.device1', 0)
