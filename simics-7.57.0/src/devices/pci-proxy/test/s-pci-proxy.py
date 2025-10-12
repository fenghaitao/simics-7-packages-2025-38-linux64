# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test pci_proxy and pci_proxy_mf

import dev_util as du
import simics
import pyobj
import stest
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

def create_bus():
    pci_bridge = du.Dev([du.PciBridge])  # Non-used PCI bridge, required by bus
    pci_conf = SIM_create_object('memory-space', 'pci_conf')
    pci_io = SIM_create_object('memory-space', 'pci_io')
    pci_mem = SIM_create_object('memory-space', 'pci_mem')

    pci_bus = SIM_create_object('pci-bus', 'pci_bus', [['conf_space', pci_conf],
                                                       ['io_space', pci_io],
                                                       ['memory_space', pci_mem],
                                                       ['bridge', pci_bridge.obj]])
    return pci_bus

class FakePciDevice(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class io_memory(pyobj.Interface):
        def operation(self, memop, info):
            self._up.reqs.append('io_memory')
            if simics.SIM_mem_op_is_read(memop):
                simics.SIM_set_mem_op_value_le(memop, 0)
            return simics.Sim_PE_No_Exception

    class pci_device(pyobj.Interface):
        def bus_reset(self):
            self._up.reqs.append('bus_reset')

        def system_error(self):
            self._up.reqs.append('system_error')

        def interrupt_raised(self, pin):
            self._up.reqs.append('interrupt_raised')

        def interrupt_lowered(self, pin):
            self._up.reqs.append('interrupt_lowered')

    class pci_express(pyobj.Interface):
        def send_message(self, src, type, payload):
            self._up.reqs.append('send_message')
            return 0

class FakePciMfDevice(FakePciDevice):
    class pci_multi_function_device(pyobj.Interface):
        def supported_functions(self):
            return [[0, "F0"], [1, "F1"]]

    class F0(pyobj.Port):
        class io_memory(pyobj.Interface):
            def operation(self, memop, info):
                self._up._up.reqs.append('F0:io_memory')
                if simics.SIM_mem_op_is_read(memop):
                    simics.SIM_set_mem_op_value_le(memop, 0)
                return simics.Sim_PE_No_Exception

    class F1(pyobj.Port):
        class io_memory(pyobj.Interface):
            def operation(self, memop, info):
                self._up._up.reqs.append('F1:io_memory')
                if simics.SIM_mem_op_is_read(memop):
                    simics.SIM_set_mem_op_value_le(memop, 0)
                return simics.Sim_PE_No_Exception

class FakePciPortDevice(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()
        self.reqs = []

    class io_memory(pyobj.Interface):
        def operation(self, memop, info):
            self._up.reqs.append('io_memory')
            if simics.SIM_mem_op_is_read(memop):
                simics.SIM_set_mem_op_value_le(memop, 0)
            return simics.Sim_PE_No_Exception

    class portA(pyobj.Port):
        class pci_device(pyobj.Interface):
            def bus_reset(self):
                self._up._up.reqs.append('A:bus_reset')

            def system_error(self):
                self._up._up.reqs.append('A:system_error')

            def interrupt_raised(self, pin):
                self._up._up.reqs.append('A:interrupt_raised')

            def interrupt_lowered(self, pin):
                self._up._up.reqs.append('A:interrupt_lowered')

        class pci_express(pyobj.Interface):
            def send_message(self, src, type, payload):
                self._up._up.reqs.append('A:send_message')
                return 0

    class portB(pyobj.Port):
        class pci_device(pyobj.Interface):
            def bus_reset(self):
                self._up._up.reqs.append('B:bus_reset')

            def system_error(self):
                self._up._up.reqs.append('B:system_error')

            def interrupt_raised(self, pin):
                self._up._up.reqs.append('B:interrupt_raised')

            def interrupt_lowered(self, pin):
                self._up._up.reqs.append('B:interrupt_lowered')

        class pci_express(pyobj.Interface):
            def send_message(self, src, type, payload):
                self._up._up.reqs.append('B:send_message')
                return 0

bus = create_bus()

# Set up a PCI bus and a PCI device
def setup_test():
    dev = simics.pre_conf_object('dev', 'FakePciDevice')

    proxy = simics.pre_conf_object('proxy', 'pci_proxy')
    proxy.pci_bus_target = bus
    proxy.pci_device_target = dev

    simics.SIM_add_configuration([dev, proxy], None)

    bus.pci_devices = [[0, 0, conf.proxy]]

def run_test():
    iface = conf.proxy.iface.pci_device
    iface.bus_reset()
    stest.expect_equal(conf.dev.object_data.reqs.pop(), 'bus_reset')
    iface.system_error()
    stest.expect_equal(conf.dev.object_data.reqs.pop(), 'system_error')

    iface = conf.proxy.iface.pci_express
    iface.send_message(None, PCIE_HP_Power_Indicator_On, "")
    stest.expect_equal(conf.dev.object_data.reqs.pop(), 'send_message')

    iface = conf.proxy.iface.pci_bus
    iface.add_map(conf.dev, simics.Sim_Addr_Space_Memory,
                  None, map_info_t(base = 0x300, length = 4))
    stest.expect_equal(conf.pci_mem.attr.map[0][1], conf.proxy,
                       "PCI proxy should have been mapped")
    iface.remove_map(conf.dev, simics.Sim_Addr_Space_Memory, 0)
    stest.expect_equal(conf.pci_mem.attr.map, [],
                       "PCI proxy should have been unmapped")

setup_test()
run_test()

# Set up a PCI bus and a PCI device with ports
def setup_test_ports():
    dev = simics.pre_conf_object('dev_port', 'FakePciPortDevice')

    proxy0 = simics.pre_conf_object('proxy0', 'pci_proxy')
    proxy0.pci_bus_target = bus
    proxy0.pci_device_target = [dev, 'portA']

    proxy1 = simics.pre_conf_object('proxy1', 'pci_proxy')
    proxy1.pci_bus_target = bus
    proxy1.pci_device_target = [dev, 'portB']

    simics.SIM_add_configuration([dev, proxy0, proxy1], None)

    bus.pci_devices = [[0, 0, conf.proxy0], [1, 0, conf.proxy1]]

def run_test_ports():
    iface0 = conf.proxy0.iface.pci_device
    iface0.bus_reset()
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'A:bus_reset')
    iface0.system_error()
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'A:system_error')
    iface0 = conf.proxy0.iface.pci_express
    iface0.send_message(None, PCIE_HP_Power_Indicator_On, "")
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'A:send_message')

    iface1 = conf.proxy1.iface.pci_device
    iface1.bus_reset()
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'B:bus_reset')
    iface1.system_error()
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'B:system_error')
    iface1 = conf.proxy1.iface.pci_express
    iface1.send_message(None, PCIE_HP_Power_Indicator_On, "")
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'B:send_message')

    conf_read = conf.pci_conf.iface.memory_space.read
    stest.expect_equal(du.tuple_to_value_le(conf_read(None, 0x0, 0x2, 0)), 0)
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'io_memory')
    stest.expect_equal(du.tuple_to_value_le(conf_read(None, 0x800, 0x2, 0)), 0)
    stest.expect_equal(conf.dev_port.object_data.reqs.pop(), 'io_memory')

setup_test_ports()
run_test_ports()

def setup_test_mf():
    dev = simics.pre_conf_object('dev_mf', 'FakePciMfDevice')

    proxy_mf = simics.pre_conf_object('proxy_mf', 'pci_proxy_mf')
    proxy_mf.pci_bus_target = bus
    proxy_mf.pci_device_target = dev

    simics.SIM_add_configuration([dev, proxy_mf], None)

    bus.pci_devices = [[0, 0, conf.proxy_mf]]

def run_test_mf():
    conf_read = conf.pci_conf.iface.memory_space.read
    stest.expect_equal(du.tuple_to_value_le(conf_read(None, 0x0, 0x2, 0)), 0)
    stest.expect_equal(conf.dev_mf.object_data.reqs.pop(), 'F0:io_memory')
    stest.expect_equal(du.tuple_to_value_le(conf_read(None, 0x100, 0x2, 0)), 0)
    stest.expect_equal(conf.dev_mf.object_data.reqs.pop(), 'F1:io_memory')

setup_test_mf()
run_test_mf()
