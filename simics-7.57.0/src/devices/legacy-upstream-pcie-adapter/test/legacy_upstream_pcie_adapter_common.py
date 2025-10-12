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


PCIE_Type_Mem = 1

Sim_Addr_Space_Conf = 0
Sim_Addr_Space_Memory = 2


class fake_legacy_pcie_upstream:
    cls = simics.confclass('fake_legacy_pcie_upstream')
    cls.iface.pci_express()
    cls.attr.conf_space('o', default=None)
    cls.attr.mem_space('o', default=None)
    cls.attr.io_space('o', default=None)
    cls.attr.pci_devices("[[iio]|[iioi]*]", default=[])
    cls.attr.upstream_request_space('i', default=0)
    cls.attr.upstream_request_address('i', default=0)
    cls.attr.upstream_request_size('i', default=0)
    cls.attr.upstream_rid('i', default=0)
    cls.attr.secondary_bus_number('i', default=1)

    @cls.attr.pci_devices.setter
    def pci_devices_setter(self, pci_devices):
        self.pci_devices = pci_devices
        for dev in self.pci_devices:
            dev[2].iface.pcie_adapter_compat.set_secondary_bus_number(
                self.secondary_bus_number)

    @cls.iface.io_memory.operation
    def operation(self): pass

    @cls.iface.pci_bus.get_bus_address
    def get_bus_address(self, dev):
        return 0

    @cls.iface.pci_bus.add_map
    def add_map(self, dev, space, target, info):
        if space == Sim_Addr_Space_Memory:
            return self.mem_space.iface.map_demap.map_simple(dev, None, info)
        elif space == Sim_Addr_Space_Conf:
            return self.conf_space.iface.map_demap.map_simple(dev, None, info)
        return 0

    @cls.iface.pci_bus.remove_map
    def remove_map(self, dev, space, function):
        if space == Sim_Addr_Space_Memory:
            return self.mem_space.iface.map_demap.unmap(dev, None)
        elif space == Sim_Addr_Space_Conf:
            return self.conf_space.iface.map_demap.unmap(dev, None)
        return 0

    @cls.iface.pci_bus.bus_reset
    def bus_reset(self):
        for device in self.pci_devices:
            device[2].iface.pci_device.bus_reset()

    @cls.iface.pci_upstream_operation.read
    def read(self, initiator, rid, space, address, buffer):
        self.upstream_request_space = space
        self.upstream_request_address = address
        self.upstream_rid = rid
        self.upstream_request_size = len(buffer)
        return 0


class fake_pcie_ep:
    cls = simics.confclass('fake_pcie_ep')
    cls.attr.ut('o|n', default=None)
    cls.attr.pcie_config('o', default=None)
    cls.attr.bar_mapped('o', default=None)
    cls.attr.has_been_reset('b', default=False)

    @cls.iface.pcie_device.hot_reset
    def hot_reset(self):
        self.has_been_reset = True

    @cls.iface.pcie_device.connected
    def connected(self, ut, devid):
        self.ut = ut
        ut.iface.pcie_map.add_function(self.pcie_config, devid)


def create_legacy_upstream_pcie_adapter(name=None):
    '''Create a new legacy_upstream_pcie_adapter object'''
    legacy_upstream_pcie_adapter = simics.pre_conf_object(
        name, 'legacy-upstream-pcie-adapter')
    simics.SIM_add_configuration([legacy_upstream_pcie_adapter], None)
    return simics.SIM_get_object(legacy_upstream_pcie_adapter.name)


def create_fake_pcie_ep(name=None):
    ep = simics.pre_conf_object(name, 'fake_pcie_ep')
    pcie_config_img = simics.pre_conf_object(f"{name}.pcie_config_img",
                                             'image', size=0x1000)
    bar_mapped_bank_img = simics.pre_conf_object(f"{name}.bar_mapped_bank_img",
                                                 'image', size=0x100)
    pcie_config_bank = simics.pre_conf_object(f"{name}.pcie_config_bank",
                                              'ram', image=pcie_config_img)
    bar_mapped_bank = simics.pre_conf_object(f"{name}.bar_mapped_bank",
                                             'ram', image=bar_mapped_bank_img)
    ep.pcie_config = simics.pre_conf_object(f"{name}.pcie_config_map",
                                            'memory-space')
    ep.bar_mapped = simics.pre_conf_object(f"{name}.bar_mapped_bank_map",
                                           'memory-space')
    ep.pcie_config.map = [[0, pcie_config_bank, 0, 0, 0x1000]]
    ep.bar_mapped.map = [[0, bar_mapped_bank, 0, 0, 0x100]]
    simics.SIM_add_configuration([ep, pcie_config_bank, bar_mapped_bank,
                                  pcie_config_img, bar_mapped_bank_img,
                                  ep.pcie_config, ep.bar_mapped], None)
    return simics.SIM_get_object(ep.name)


def create_fake_legacy_upstream(name=None):
    up = simics.pre_conf_object(name, 'fake_legacy_pcie_upstream')
    up.conf_space = simics.pre_conf_object(f"{name}.conf_space",
                                           'memory-space')
    up.mem_space = simics.pre_conf_object(f"{name}.mem_space", 'memory-space')
    up.io_space = simics.pre_conf_object(f"{name}.io_space", 'memory-space')
    simics.SIM_add_configuration([up, up.conf_space, up.mem_space,
                                  up.io_space], None)
    return simics.SIM_get_object(up.name)
