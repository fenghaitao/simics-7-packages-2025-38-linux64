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


import pyobj
import simics
import stest

class fake_upstream_target:
    cls = simics.confclass("fake_upstream_target")

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        return simics.Sim_PE_No_Exception

    @cls.iface.pcie_map.add_function
    def add_function(self, map_obj, function_id):
        pass


    @cls.iface.pcie_map.add_map
    def add_map(self, map_obj, nfo, space):
        self.validate_members()
        if space == simics.PCIE_Type_Mem:
            return self.mem_map_demap.add_map(map_obj, None, nfo)
        elif space == simics.PCIE_Type_IO:
            return self.io_map_demap.add_map(map_obj, None, nfo)
        else:
            return self.conf_map_demap.add_map(map_obj, None, nfo)

    @cls.iface.pcie_map.del_map
    def del_map(self, map_obj, base, space):
        self.validate_members()
        if space == simics.PCIE_Type_Mem:
            return self.mem_map_demap.unmap_address(map_obj, base, None)
        elif space == simics.PCIE_Type_IO:
            return self.io_map_demap.unmap_address(map_obj, base, None)
        else:
            return self.conf_map_demap.unmap_address(map_obj, base, None)

    @cls.iface.pcie_map.get_device_id
    def get_device_id(self, dev_obj):
        return 0

    def validate_members(self):
        if self.mem_obj:
            self.mem_map_demap = self.mem_obj.iface.map_demap
            self.mem_space = self.mem_obj.iface.memory_space
        else:
            stest.fail('fake upstream target mem space not set')
        if self.io_obj:
            self.io_map_demap = self.io_obj.iface.map_demap
            self.io_space = self.io_obj.iface.memory_space
        else:
            stest.fail('fake upstream target mem space not set')
        if self.conf_obj:
            self.conf_map_demap = self.conf_obj.iface.map_demap
            self.conf_space = self.conf_obj.iface.memory_space
        else:
            stest.fail('fake upstream target mem space not set')

    mem_obj = None
    mem_map_demap = None
    mem_space = None

    io_obj = None
    io_map_demap = None
    io_space = None

    conf_obj = None
    conf_map_demap = None
    conf_space = None

class PCIBus(pyobj.ConfObject):
    '''A pseudo pci bus for testing'''
    def _initialize(self):
        super()._initialize()

        self.mem_obj = None
        self.mem_map_demap = None
        self.mem_space = None

        self.io_obj = None
        self.io_map_demap = None
        self.io_space = None

        self.conf_obj = None
        self.conf_map_demap = None
        self.conf_space = None

        self.irq_level = 0

    def _finalize(self):
        super()._finalize()
        simics.SIM_require_object(self.mem_obj)
        self.mem_map_demap = self.mem_obj.iface.map_demap
        self.mem_space = self.mem_obj.iface.memory_space

        simics.SIM_require_object(self.io_obj)
        self.io_map_demap = self.io_obj.iface.map_demap
        self.io_space = self.io_obj.iface.memory_space

        simics.SIM_require_object(self.conf_obj)
        self.conf_map_demap = self.conf_obj.iface.map_demap
        self.conf_space = self.conf_obj.iface.memory_space

    class pci_bus(pyobj.Interface):
        def add_map(self, dev, space, target, info):
            if space == simics.Sim_Addr_Space_Memory:
                return self._up.mem_map_demap.add_map(dev, target, info)
            elif space == simics.Sim_Addr_Space_IO:
                return self._up.io_map_demap.add_map(dev, target, info)
            else:
                return self._up.conf_map_demap.add_map(dev, target, info)

        def remove_map(self, dev, space, function):
            if space == simics.Sim_Addr_Space_Memory:
                return self._up.mem_map_demap.remove_map(dev, function)
            elif space == simics.Sim_Addr_Space_IO:
                return self._up.io_map_demap.remove_map(dev, function)
            else:
                return self._up.conf_map_demap.remove_map(dev, function)

        def raise_interrupt(self, dev, pin):
            self._up.irq_level = 1
        def lower_interrupt(self, dev, pin):
            self._up.irq_level = 0
        def get_bus_address(self, dev):
            return 88 # Allow only one device to be connected to this PCI bus

    class pci_express(pyobj.Interface):
        def send_message(self, dst, src, type, payload):
            print("pci_express: send_message: ", "dst: ", dst, "src: ", src, \
                  "type: ", type, "payload: ", payload)
            return 0

    class downstream(pyobj.PortObject):
        class transaction(pyobj.Interface):
            def issue(self, t, addr):
                return Sim_PE_No_Exception

    class upstream(pyobj.PortObject):
        class transaction(pyobj.Interface):
            def issue(self, t, addr):
                return Sim_PE_No_Exception

    class io_memory(pyobj.Interface):
        def operation(self, memop, info):
            return self._up.mem_space.access(memop)

    class memory(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Required
        attrtype = 'o'
        def getter(self):
            return self._up.mem_obj
        def setter(self, val):
            self._up.mem_obj = val

    class io(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Required
        attrtype = 'o'
        def getter(self):
            return self._up.io_obj
        def setter(self, val):
            self._up.io_obj = val

    class conf(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Required
        attrtype = 'o'
        def getter(self):
            return self._up.conf_obj
        def setter(self, val):
            self._up.conf_obj = val

    class irq_level(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'i'
        def getter(self):
            return self._up.irq_level
        def setter(self, val):
            self._up.irq_level = val
