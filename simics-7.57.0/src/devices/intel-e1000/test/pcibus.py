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


class fake_upstream_target:
    """
    Transaction based fake PCIe upstream for devices using the new PCIe modeling library
    """
    cls = simics.confclass("fake_upstream_target")

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        if t.pcie_type == simics.PCIE_Type_Mem:
            return simics.SIM_issue_transaction(self.memory, t, addr)
        elif t.pcie_type == simics.PCIE_Type_Msg:
            if t.pcie_msg_type == simics.PCIE_Msg_Assert_INTA:
                self.irq_level = 1
            elif t.pcie_msg_type == simics.PCIE_Msg_Deassert_INTA:
                self.irq_level = 0
            else:
                print("PCIBus: unknown pcie_msg_type: ", t.pcie_msg_type)
        else:
            print(f"PCIBus: discarding transaction with unknown pcie_type {t.pcie_type} to addr {addr}")

        return simics.Sim_PE_No_Exception

    # memory-space objects
    cls.attr.memory("o")
    cls.attr.io("o")
    cls.attr.conf("o")

    # exposes the interrupt level for inspection by tests
    cls.attr.irq_level("i", pseudo=True)

    @cls.iface.pcie_map.add_function
    def add_function(self, map_obj, function_id):
        # Stubbed out because the tests statically memory map the device under test.
        pass

    @cls.iface.pcie_map.add_map
    def add_map(self, map_obj, nfo, type):
        if type == simics.PCIE_Type_Mem:
            return self.memory.iface.map_demap.map_simple(map_obj, None, nfo)

    @cls.iface.pcie_map.get_device_id
    def get_device_id(self, dev_obj):
        return 0


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
