# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from typing import NamedTuple
from blueprints import (Builder, ConfObject, State, MemMap, Namespace,
                        Port, Binding)

class Queue(State):
    queue = ConfObject()
    "The queue object"

class UARTConnectionState(Binding):
    "Type for the 'serial-connector' context."
    remote = ConfObject()
    "Object talking with the UART (normally the console)"
    uart = ConfObject()
    "The UART object."
    uart_connector = ConfObject()
    "UART device connector object (used for hotplug support)"
    remote_connector = ConfObject()
    "Remote/console connector object (used for hotplug support)"

class SATAConnectionState(Binding):
    "Type for the 'sata-connector' context."
    controller = Port()
    "The SATA host controller object."
    device = ConfObject()
    "The SATA device object."
    controller_connector = ConfObject()
    "SATA controller connector object (used for hotplug support)"
    device_connector = ConfObject()
    "SATA device connector object (used for hotplug support)"

    # Connector type when used with legacy components
    def legacy_type(self):
        return 'sata-slot'

    # connect_data for legacy components
    def legacy_data(self, is_up, comp, cnt, data):
        return [comp.get_slot(str(self.device))]

    # preset when used with legacy components
    def legacy_connect(self, is_up, comp, cnt, attr):
        return [(self._key + ('controller',), Port(Namespace(attr[0][0].name),
                                                   str(attr[0][1]))),]

class USBConnectionState(Binding):
    "Type for the 'usb-connector' context."
    host = ConfObject()
    "The USB host controller."
    device = ConfObject()
    "The device object (used for hotplug support)"
    host_connector = ConfObject()
    "Host connector object (used for hotplut support)"
    device_connector = ConfObject()
    "Device connector object (used for hotplug support)"

class EthConnectionState(State):
    "Type for the 'eth-connector' context."
    local = ConfObject()
    "The PHY object for the NIC."
    remote = ConfObject()
    "The (remote) device the PHY communicates with."
    # The following fields are only needed for hotplug support
    local_connector = ConfObject()
    local_attr_name = "link"
    "Attribute on the 'local' object which points to the 'remote' object."
    remote_connector = ConfObject()

class GFXConsoleConnectionState(State):
    """Type for the part of the 'gfx-connector' context that covers the connection
    to the console."""
    gfx_device = ConfObject()
    console = ConfObject()

class GFXInputConnectionState(State):
    """Type for the part of the 'gfx-connector' context that covers the connection
    to the input devices."""
    abs_pointer = ConfObject()
    keyboard = ConfObject()
    mouse = ConfObject()
    console = ConfObject()

class PCIEDevice(NamedTuple):
    device_id: int
    function_id: int
    bank: Namespace|Port|ConfObject

class PCIEFunction(NamedTuple):
    function_id: int
    bank: Namespace|Port|ConfObject

class PCIEBus(State):
    "Type for the PCIEBus connector"
    bus = ConfObject()
    "The pcie-bus object."
    devices: list[PCIEDevice] = []
    pcie_devices: list[PCIEDevice] = []
    "List with PCI devices, with element [device_id, function_id, bank]."
    # The following fields should really be removed, but some legacy devices
    # access the spaces directly.
    mem = ConfObject()
    io = ConfObject()
    mem_map: list[MemMap] = []
    io_map: list[MemMap] = []

class PCIESlotConnectionState(Binding):
    "Type for the pcie-slot-connector"
    bus = PCIEBus()
    device = 0
    functions: list[PCIEFunction] = []
    "List with functions provided by the device."
    is_new = False

    device = ConfObject()
    "The device object (used for hotplug support)"
    controller_connector = ConfObject()
    "Host connector object (used for hotplut support)"
    device_connector = ConfObject()
    "Device connector object (used for hotplug support)"

    # Connector type when used with legacy components
    def legacy_type(self):
        return 'pci-bus'

    # connect_data for legacy components
    def legacy_data(self, is_up, comp, cnt, data):
        if is_up:
            return [[f.function_id, comp.get_slot(str(f.bank))]
                    for f in self.functions]
        else:
            return [self.device, comp.get_slot(str(self.bus.bus))]

    # preset when used with legacy components
    def legacy_connect(self, is_up, comp, cnt, attr):
        if is_up:
            return [(self._key + ('device',), attr[0]),
                    (self._key + ('bus', 'bus'), attr[1])]
        else:
            (devs,) = attr
            return [(self._key + ('functions',),
                     [PCIEFunction(a[0], Namespace(a[1].name)) for a in devs])]

# Connector blueprints. A connector is a node in the object hierarchy where
# a specific interface is provided.

def uart_connection(bp: Builder, name: Namespace, com: UARTConnectionState):
    bp.expose_state(name, com)
    # UART hotplug support
    com.uart_connector = bp.obj(name, "uart-device-connector",
        uart=com.uart,
        remote=com.remote_connector,
        connector_name=str(name).split('.')[-1]
    )

def sata_connection(bp: Builder, name: Namespace, sata: SATAConnectionState):
    bp.expose_state(name, sata)
    # SATA hotplug support
    sata.controller_connector = bp.obj(name, "sata-controller-connector",
        sata=sata.controller,
        remote=sata.device_connector,
        connector_name=str(name).split('.')[-1]
    )

def usb_connection(bp: Builder, name: Namespace, usb: USBConnectionState):
    bp.expose_state(name, usb)

    # USB hotplug support
    usb.host_connector = bp.obj(name, "usb-host-connector",
        usb = usb.host,
        remote = usb.device_connector,
        connector_name=str(name).split('.')[-1]
    )

def eth_connection(bp: Builder, name: Namespace, eth: EthConnectionState,
        connector_class="eth-connector"):
    bp.expose_state(name, eth)

    # Ethernet hotplug support
    eth.local_connector = bp.obj(name, connector_class,
        phy = eth.local,
        remote = eth.remote_connector,
        aname = eth.local_attr_name,
        connector_name=str(name).split('.')[-1]
    )

uart = uart_connection
sata = sata_connection
usb = usb_connection
eth = eth_connection

def pcie_slot(bp: Builder, name: Namespace, dev: int, bus: PCIEBus,
              is_downstream_port_legacy=True):
    "PCIe connector for device id 'dev' and PCIe bus 'bus'."
    slot = bp.expose_state(name, PCIESlotConnectionState)
    slot.bus = bus
    slot.device = dev
    if not slot.is_new or not is_downstream_port_legacy:
        bus.devices.extend(
            PCIEDevice(dev, fn, bank) for (fn, bank) in slot.functions)
    else:
        bus.pcie_devices.extend(
            PCIEDevice(dev, fn, bank) for (fn, bank) in slot.functions)
    # PCI hotplug support
    slot.controller_connector = bp.obj(name, "pci-controller-connector",
                                       bus=bus.bus,
                                       dev_num=slot.device,
                                       remote=slot.device_connector,
                                       connector_name=str(name).split('.')[-1])

def pcie_device_slot(builder: Builder, name: Namespace, fn: PCIEFunction,
                     slot: PCIESlotConnectionState=None, is_new: bool=False):
    slot = slot or builder.read_state(name, PCIESlotConnectionState,
                                      allow_local=True)
    slot.functions.append(fn)
    slot.is_new = is_new
    # PCI hotplug support
    slot.device_connector = builder.obj(name, "pci-device-connector",
                                        fn=fn.function_id, dev=fn.bank,
                                        remote=slot.controller_connector,
                                        connector_name=str(name).split('.')[-1])
