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


# A PCI(e) proxy
# The proxy can be inserted between a PCI(e) bus and a PCI(e)
# device/endpoint and then forwards all interface calls to the other
# end in both directions.
# For multi-function PCI(e) device implementing the pci_multi_function
# interface; please use pci_pcoxy_mf.

import pyobj
import simics

class pci_proxy(pyobj.ConfObject):
    """
    A PCI(e) proxy inserted between a PCI(e) bus and PCI(e) device.
    For multi-functions PCI(e) device, pci_proxy_mf should be used.
    """
    _class_desc = "model of PCI(e) proxy"

    def _status(self):
        return [(None,
                 [("Bus target:", self.pci_bus_target.val),
                  ("Device target:", self.pci_device_target.val)])]

    # PCI bus counterpart
    class pci_bus_target(pyobj.SimpleAttribute(None, 'o')):
        '''PCI bus target to route the transaction to'''

    def get_bus_iface(self, iface):
        if self.pci_bus_target.val is None:
            raise Exception('pci_bus_target not configured yet')
        return simics.SIM_get_interface(self.pci_bus_target.val, iface)

    # Interface call forwards to the PCI bus target
    class pci_bus(pyobj.Interface):
        def add_map(self, dev, space, target, info):
            iface = self._up.get_bus_iface('pci_bus')
            return iface.add_map(self._up.obj, space, target, info)

        def remove_map(self, dev, space, function):
            iface = self._up.get_bus_iface('pci_bus')
            return iface.remove_map(self._up.obj, space, function)

        def raise_interrupt(self, dev, pin):
            iface = self._up.get_bus_iface('pci_bus')
            return iface.raise_interrupt(self._up.obj, pin)

        def lower_interrupt(self, dev, pin):
            iface = self._up.get_bus_iface('pci_bus')
            return iface.lower_interrupt(self._up.obj, pin)

        def get_bus_address(self, dev):
            iface = self._up.get_bus_iface('pci_bus')
            return iface.get_bus_address(self._up.obj)

    class pci_upstream_operation(pyobj.Interface):
        def read(self, initiator, rid, space, address, data):
            iface = self._up.get_bus_iface('pci_upstream_operation')
            return iface.read(initiator, rid, space, address, data)

        def write(self, initiator, rid, space, address, data):
            iface = self._up.get_bus_iface('pci_upstream_operation')
            return iface.write(initiator, rid, space, address, data)

    # PCI device counterpart
    class pci_device_target(pyobj.SimpleAttribute(None, 'o|[os]')):
        '''PCI device target to route the transaction to'''

    def get_device_iface(self, iface):
        target = self.pci_device_target.val
        if target is None:
            raise Exception('pci_device_target not configured yet')
        if isinstance(target, list):
            if len(target) != 2:
                raise Exception('pci_device_target type mismatch with o|[os]')
            try:
                dev_iface = simics.SIM_get_port_interface(target[0], iface, target[1])
            except simics.SimExc_Lookup:
                # We support sharing io_memory at object level
                dev_iface = simics.SIM_get_interface(target[0], iface)
        else:
            dev_iface = simics.SIM_get_interface(target, iface)
        return dev_iface

    # Interface call forwards to the PCI device target
    class io_memory(pyobj.Interface):
        def operation(self, memop, info):
            iface = self._up.get_device_iface('io_memory')
            return iface.operation(memop, info)

    class pci_express(pyobj.Interface):
        def send_message(self, src, type, payload):
            iface = self._up.get_device_iface('pci_express')
            return iface.send_message(src, type, payload)

    class pci_device(pyobj.Interface):
        def bus_reset(self):
            iface = self._up.get_device_iface('pci_device')
            return iface.bus_reset()

        def system_error(self):
            iface = self._up.get_device_iface('pci_device')
            return iface.system_error()

        def interrupt_raised(self, pin):
            iface = self._up.get_device_iface('pci_device')
            return iface.interrupt_raised(pin)

        def interrupt_lowered(self, pin):
            iface = self._up.get_device_iface('pci_device')
            return iface.interrupt_lowered(pin)


class pci_proxy_mf(pci_proxy):
    '''
    A PCI(e) proxy inserted between a PCI(e) bus and PCI(e) device.
    For single function PCI(e) device, pci_proxy should be used.
    '''
    class pci_multi_function_device(pyobj.Interface):
        def supported_functions(self):
            iface = self._up.get_device_iface('pci_multi_function_device')
            funcs = iface.supported_functions()
            for func in funcs:
                if len(func) == 2:
                    func.insert(1, self._up.obj.pci_device_target)
            return funcs
