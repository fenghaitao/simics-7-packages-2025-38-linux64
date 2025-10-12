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


import abc
import simics

#
# Simics old-style connector objects providing hotplugging support.
# The connectors are *only* used for hotplugging, not for the initial
# setup.

class Connector:
    cls = simics.confclass()
    _direction = simics.Sim_Connector_Direction_Any
    _type = "ethernet-link"
    _multi = False

    cls.attr.remote("o|n", default = None, doc = "Remote connector.")
    cls.attr.connector_name("s|n", default=None)

    @cls.finalize
    def finalize_instance(self):
        self.new_remote = self.remote

    def add_destination(self, connector):
        self.new_remote = connector
        return True

    def remove_destination(self, _):
        self.new_remote = None
        return True

    def destination(self):
        return [self.new_remote] if self.new_remote else []

    def update(self):
        if self.new_remote != self.remote:
            connect_data = self.get_connect_data()
            if self.remote:
                self.remote.iface.connector.disconnect()
            if self.new_remote:
                self.new_remote.iface.connector.connect(connect_data)
            self.remote = self.new_remote

    def check(self, _):
        return True

    def connect(self, attr):
        self.do_connect(attr)

    def disconnect(self):
        self.do_disconnect()

    cls.iface.connector(
        type = lambda self: self._type,
        hotpluggable = lambda _: True,
        required = lambda _: False,
        multi = lambda self: self._multi,
        direction = lambda self: self._direction,
        add_destination = add_destination,
        remove_destination = remove_destination,
        destination = destination,
        update = update,
        connect = connect,
        check = check,
        disconnect = disconnect,
    )
    @abc.abstractmethod
    def do_connect(self, val):
        pass

    @abc.abstractmethod
    def do_disconnect(self):
        pass

    @abc.abstractmethod
    def get_connect_data(self):
        pass

class EthConnector(Connector):
    "Ethernet hotplug connector for ethernet adapters."
    phy: simics.conf_object_t
    aname: str

    cls = simics.confclass("eth-connector", parent = Connector.cls)
    cls._class_desc = "eth hotplug connector for adapters"

    _direction = simics.Sim_Connector_Direction_Down
    _type = "ethernet-link"

    cls.attr.phy("o|n", doc = "Ethernet PYH object.")
    cls.attr.aname("s", doc = ("Name of PHY attribute which"
                               " holds the link object."))

    def do_connect(self, data):
        link = data[0]
        setattr(self.phy, self.aname, link)

    def do_disconnect(self):
        setattr(self.phy, self.aname, None)

    def get_connect_data(self):
        return [self.phy]

class EthLinkConnector(EthConnector):
    "Ethernet hotplug connector (for ethernet links)."

    cls = simics.confclass("eth-link-connector", parent = EthConnector.cls)
    cls._class_desc = "hotplug connector for links"
    _direction = simics.Sim_Connector_Direction_Any

    def do_disconnect(self):
        def callback(_):
            # Disconnect currently requires the endpoint to be deleted.
            # We remove it and recreate it.
            phy = self.phy
            name = phy.name
            self.remote = None
            self.phy = None
            attrs = ("link", "vlan_id", "vlan_trunk", "id")
            spec = [[name, phy.classname,
                ["device", None],
                *[[attr, getattr(phy, attr)] for attr in attrs]
            ]]
            simics.SIM_delete_object(phy)
            simics.SIM_set_configuration(spec)
            self.phy = simics.SIM_get_object(name)
        simics.SIM_run_alone(callback, None)

class UARTRemoteConnector(Connector):
    "UART remote/console hotplug connector."
    device: simics.conf_object_t
    aname: str

    cls = simics.confclass(
        "uart-remote-connector", parent=Connector.cls,
        short_doc="a UART remote hotplug connector")

    _direction = simics.Sim_Connector_Direction_Up
    _type = "serial"

    cls.attr.device("o", doc="UART remote/console object.")
    cls.attr.aname("s", doc=("Name of UART remote attribute which"
                             " holds the uart device object."))

    def do_connect(self, data):
        uart_device = data[1]
        setattr(self.device, self.aname, uart_device)

    def do_disconnect(self):
        setattr(self.device, self.aname, None)

    def get_connect_data(self):
        return [None, self.device, f'Connected to {self.device.name}']

class UARTDeviceConnector(Connector):
    "UART device hotplug connector."
    uart: simics.conf_object_t

    cls = simics.confclass("uart-device-connector", parent=Connector.cls,
                           short_doc="a UART device hotplug connector")
    _direction = simics.Sim_Connector_Direction_Down
    _type = "serial"

    cls.attr.uart("o")

    def do_connect(self, connect_data):
        console = connect_data[1]
        self.uart.console = console
    def do_disconnect(self):
        pass
    def get_connect_data(self):
        return [None, self.uart, f'Connected to {self.uart.name}']

class USBDeviceConnector(Connector):
    "USB device hotplug connector."
    device: simics.conf_object_t
    aname: str

    cls = simics.confclass("usb-device-connector", parent=Connector.cls,
                           short_doc="a USB device hotplug connector")

    _direction = simics.Sim_Connector_Direction_Up
    _type = "usb-port"

    cls.attr.device("o", doc = "USB device object.")
    cls.attr.aname("s", doc = ("Name of USB device attribute which"
                               " holds the usb host object."))

    def do_connect(self, data):
        usb_host = data[0]
        setattr(self.device, self.aname, usb_host)

    def do_disconnect(self):
        setattr(self.device, self.aname, None)

    def get_connect_data(self):
        return [self.device]

class USB3DeviceConnector(USBDeviceConnector):
    "USB3 device hotplug connector."
    _type = "usb3-port"
    cls = simics.confclass("usb3-device-connector",
                           parent=USBDeviceConnector.cls,
                           short_doc="a USB3 device hotplug connector")

class USBHostConnector(Connector):
    "USB host hotplug connector."
    usb: simics.conf_object_t

    cls = simics.confclass("usb-host-connector", parent = Connector.cls,
                           short_doc = "a USB host hotplug connector")
    _direction = simics.Sim_Connector_Direction_Down
    _type = "usb-port"

    cls.attr.usb("o")

    def do_connect(self, _):
        pass
    def do_disconnect(self):
        pass
    def get_connect_data(self):
        return [self.usb]

class SATADeviceConnector(Connector):
    "SATA device hotplug connector."
    device: simics.conf_object_t
    aname: str

    cls = simics.confclass(
        "sata-device-connector", parent=Connector.cls,
        short_doc="a SATA device hotplug connector")

    _direction = simics.Sim_Connector_Direction_Up
    _type = "sata-port"

    cls.attr.device("o", doc="SATA device object.")
    cls.attr.aname("s", doc=("Name of SATA device attribute which"
                             " holds the SATA controller object."))

    def do_connect(self, data):
        setattr(self.device, self.aname, data)

    def do_disconnect(self):
        setattr(self.device, self.aname, None)

    def get_connect_data(self):
        return [self.device]

class SATAControllerConnector(Connector):
    "SATA controller hotplug connector."
    sata: simics.conf_object_t

    cls = simics.confclass("sata-controller-connector", parent=Connector.cls,
                           short_doc="a SATA controller hotplug connector")
    _direction = simics.Sim_Connector_Direction_Down
    _type = "sata-port"

    # The SATA controller is often a port object
    cls.attr.sata("o|[os]")

    def do_connect(self, _):
        pass
    def do_disconnect(self):
        pass
    def get_connect_data(self):
        return self.sata if isinstance(self.sata, list) else [self.sata]

class PCIControllerConnector(Connector):
    "PCI controller hotplug connector."
    cls = simics.confclass("pci-controller-connector", parent=Connector.cls,
                           short_doc="a PCI controller hotplug connector")
    _direction = simics.Sim_Connector_Direction_Down
    _type = "pci-bus"

    # The PCI controller is often a port object
    cls.attr.bus("o|[os]")
    cls.attr.dev_num("i")

    def do_connect(self, data):
        (device_list,) = data
        for (fn, dev) in device_list:
            if hasattr(self.bus, 'pci_devices'):
                if hasattr(dev.iface, 'pcie_device'):
                    self.bus.devices.append([self.dev_num, fn, dev])
                else:
                    self.bus.pci_devices.append([self.dev_num, fn, dev])
            else:
                self.bus.devices.append([self.dev_num, fn, dev])
    def do_disconnect(self):
        self.bus.devices = [dev for dev in self.bus.devices
                            if dev[0] != self.dev_num]
    def get_connect_data(self):
        return [self.dev_num, self.bus]

class PCIDeviceConnector(Connector):
    "PCI device hotplug connector."
    cls = simics.confclass("pci-device-connector", parent=Connector.cls,
                           short_doc="a PCI device hotplug connector")
    _direction = simics.Sim_Connector_Direction_Up
    _type = "pci-bus"

    cls.attr.fn("i")
    cls.attr.dev("o")

    def do_connect(self, data):
        pass

    def do_disconnect(self):
        pass

    def get_connect_data(self):
        return [[self.fn, self.dev]]
