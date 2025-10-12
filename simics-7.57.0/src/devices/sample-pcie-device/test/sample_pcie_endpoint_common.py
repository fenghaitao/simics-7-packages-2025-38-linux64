# © 2023 Intel Corporation
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


class fake_upstream_target:
    cls = simics.confclass("fake_upstream_target")

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        return simics.Sim_PE_No_Exception

    @cls.iface.pcie_map.add_function
    def add_function(self, map_obj, function_id):
        pass

    @cls.iface.pcie_map.add_map
    def add_map(self, map_obj, nfo, type):
        pass

    @cls.iface.pcie_map.get_device_id
    def get_device_id(self, dev_obj):
        return 0


def create_sample_pcie_device(name=None):
    dev = simics.pre_conf_object(name, "sample-pcie-device")
    clock = simics.pre_conf_object("clock", "clock")
    clock.freq_mhz = 100
    dev.queue = clock
    simics.SIM_add_configuration([dev, clock], None)
    return simics.SIM_get_object(dev.name)


def create_fake_upstream_target(name=None):
    up = simics.pre_conf_object(name, "fake_upstream_target")
    simics.SIM_add_configuration([up], None)
    return simics.SIM_get_object(up.name)


def run_seconds(seconds):
    simics.SIM_continue(seconds * 100e6)
