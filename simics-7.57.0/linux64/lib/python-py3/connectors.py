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


import simics, comp

class StandardConnector:
    '''The StandardConnector class should be used as base when writing new
connector classes. The StandardConnector can be used as argument to
the add_connector method in the StandardConnectorComponent class.'''

    def get_check_data(self, cmp, cnt):
        return self.get_connect_data(cmp, cnt)
    def get_connect_data(self, cmp, cnt):
        return []
    def check(self, cmp, cnt, attr):
        return True
    def connect(self, cmp, cnt, attr):
        raise comp.CompException('missing connect function')
    def disconnect(self, cmp, cnt):
        raise comp.CompException('missing disconnect function')

# Serial (UARTs etc)
class SerialDownConnector(StandardConnector):
    '''The SerialDownConnector class handles serial down connections.
The first argument to the init method is the name of the serial device.
The serial device is expected to have link and console attributes.'''

    type = 'serial'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, uart):
        self.uart = uart

    def get_connect_data(self, cmp, cnt):
        return [None, cmp.get_slot(self.uart), cmp.obj.name + '.%s' % self.uart]

    def check(self, cmp, cnt, attr):
        if isinstance(attr[0], list):
            print('%s only supports new serial links' % cmp.obj.name)
            return False
        return True

    def connect(self, cmp, cnt, attr):
        (link, console) = attr
        uart = cmp.get_slot(self.uart)

        if link:
            uart.console = link
        else:
            uart.console = console

    def disconnect(self, cmp, cnt):
        uart = cmp.get_slot(self.uart)
        if hasattr(uart, 'link'):
            uart.link = None
        uart.console = None

# Ethernet
class EthernetLinkDownConnector(StandardConnector):
    '''The EthernetLinkDownConnector class handles ethernet-link down
connections. The first argument to the init method is the name of the
generic_eth_phy. The phy object is expected to have a link attribute.'''

    type = 'ethernet-link'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, phy):
        self.phy = phy

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.phy)]

    def check(self, cmp, cnt, attr):
        if isinstance(attr[0], list):
            print('%s only supports new Ethernet links' % cmp.obj.name)
            return False
        return True

    def connect(self, cmp, cnt, attr):
        link = attr[0]
        phy = cmp.get_slot(self.phy)
        phy.link = link

    def disconnect(self, cmp, cnt):
        phy = cmp.get_slot(self.phy)
        phy.link = None

# pci-bus
class PciBusDownConnector(StandardConnector):
    '''The PciBusDownConnector class handles pci-bus down connections.
The first argument to the init method is the device number, and the second
argument is the name of the PCI bus object.'''
    type = 'pci-bus'

    def __init__(self, dev_num, bus, hotpluggable=True, required=False):
        if not isinstance(dev_num, int) or dev_num < 0:
            raise comp.CompException('dev_num must be an integer >= 0')
        if not isinstance(bus, str):
            raise comp.CompException('bus must be a string')
        self.dev_num = dev_num
        self.bus = bus
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        return [self.dev_num, cmp.get_slot(self.bus)]

    def connect(self, cmp, cnt, attr):
        (device_list,) = attr
        bus = cmp.get_slot(self.bus)
        legacy_compatible, new_style_compatible = self.__verify_bus_type(bus)
        if not (legacy_compatible or new_style_compatible):
            raise TypeError(f'Unrecognized bus type {bus}')

        for (f_num, dev) in device_list:
            try:
                simics.SIM_get_class_interface(dev.classname, 'pcie_device')
                if not new_style_compatible:
                    raise TypeError(
                        'Trying to connect a new style PCIe component with ' +
                        'bus that only supports legacy PCIe components')
                if not hasattr(bus, 'devices'):
                    bus.devices = []
                bus.devices.append([self.dev_num, f_num, dev])
            except (simics.SimExc_Lookup):
                try:
                    simics.SIM_get_class_interface(dev.classname, 'pci_device')
                    if not legacy_compatible:
                        raise TypeError(
                            'Trying to connect a legacy style PCIe '
                            'component with bus that only supports new ' +
                            'style PCIe components')
                    if not hasattr(bus, 'pci_devices'):
                        bus.pci_devices = []
                    bus.pci_devices.append([self.dev_num, f_num, dev])
                except (simics.SimExc_Lookup):
                    raise TypeError('This bus does not support PCIe endpoints')

    def disconnect(self, cmp, cnt):
        bus = cmp.get_slot(self.bus)

        if hasattr(bus, 'pci_devices'):
            bus.pci_devices = [
                x for x in bus.pci_devices if x[0] != self.dev_num]
        if hasattr(bus, 'devices'):
            bus.devices = [x for x in bus.devices if x[0] != self.dev_num]

    def __verify_bus_type(self, bus):
        legacy_compatible = simics.SIM_class_has_attribute(
            bus.classname, "pci_devices")
        new_style_compatible = simics.SIM_class_has_attribute(
            bus.classname, "devices")
        return (legacy_compatible, new_style_compatible)


class PciBusUpConnector(StandardConnector):
    '''The PciBusUpConnector class handles pci-bus up connections.
The first argument to the init method is the PCI device function number,
and the second argument is the name of the PCI device object.'''
    type = 'pci-bus'

    def __init__(self, fun_num, device, hotpluggable=True, required=False,
                 use_upstream=False):
        if not isinstance(fun_num, int) or fun_num < 0:
            raise comp.CompException('fun_num must be an integer >= 0')
        if not isinstance(device, str):
            raise comp.CompException('device must be a string')
        self.fun_num = fun_num
        self.device = device
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up
        self.use_upstream = use_upstream

    def get_connect_data(self, cmp, cnt):
        return [[[self.fun_num, cmp.get_slot(self.device)]]]

    def connect(self, cmp, cnt, attr):
        dev = cmp.get_slot(self.device)
        (_, pci_bus) = attr
        legacy_compatible, new_style_compatible = self.__verify_bus_type(
            pci_bus)
        if not (legacy_compatible or new_style_compatible):
            raise TypeError(f'Unrecognized bus type {pci_bus}')

        try:
            simics.SIM_get_class_interface(dev.classname, 'pcie_device')
            if not new_style_compatible:
                raise TypeError(
                    'Trying to connect a new style PCIe component with bus ' +
                    'that only supports legacy PCIe components')
        except (simics.SimExc_Lookup):
            try:
                simics.SIM_get_class_interface(dev.classname, 'pci_device')
                if not legacy_compatible:
                    raise TypeError(
                        'Trying to connect a legacy style PCIe component ' +
                        'with bus that only supports new style PCIe ' +
                        'components')
                cmp.get_slot(self.device).pci_bus = pci_bus
                if self.use_upstream:
                    cmp.get_slot(self.device).upstream_target = pci_bus
            except (simics.SimExc_Lookup):
                raise TypeError(
                    "The device does not implement the interface pci_device " +
                    "or pcie_device")

    def disconnect(self, cmp, cnt):
        dev = cmp.get_slot(self.device)
        try:
            simics.SIM_get_class_interface(dev.classname, 'pcie_device')
        except (simics.SimExc_Lookup):
            cmp.get_slot(self.device).pci_bus = None
            if self.use_upstream:
                cmp.get_slot(self.device).upstream_target = None

    def __verify_bus_type(self, bus):
        legacy_compatible = simics.SIM_class_has_attribute(
            bus.classname, "pci_devices")
        new_style_compatible = simics.SIM_class_has_attribute(
            bus.classname, "devices")
        return (legacy_compatible, new_style_compatible)

class PciBusUpMultiFunctionConnector(StandardConnector):
    '''The PciBusUpMultiFunctionConnector class handles pci-bus up
connections, when more than one PCI device should be added to the bus.
The first argument to the init method is a list of tuples, each with a
PCI device function number and the name of a PCI device object.'''

    def __init__(self, funcs, hotpluggable = True, required = False,
                 use_upstream=False):
        for (fun_num, device) in funcs:
            if not isinstance(fun_num, int) or fun_num < 0:
                raise comp.CompException('function number must be an integer >= 0')
            if not isinstance(device, str):
                raise comp.CompException('device name must be a string')
        self.funcs = funcs
        self.type = 'pci-bus'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up
        self.use_upstream = use_upstream

    def get_connect_data(self, cmp, cnt):
        ret = []
        for (fun_num, device) in self.funcs:
            ret.append([fun_num, cmp.get_slot(device)])
        return [ret]

    def connect(self, cmp, cnt, attr):
        (slot, pci_bus) = attr
        for (func, device) in self.funcs:
            cmp.get_slot(device).pci_bus = pci_bus
            if self.use_upstream:
                cmp.get_slot(device).upstream_target = pci_bus

    def disconnect(self, cmp, cnt):
        for (func, device) in self.funcs:
            cmp.get_slot(device).pci_bus = None
            if self.use_upstream:
                cmp.get_slot(device).upstream_target = None

# Compact PCI (connects devices and bridges alike to the backplane pci bus)
class CompactPciBusDownConnector(StandardConnector):
    '''The CompactPciBusDownConnector class handles pci-bus down connections
for cPCI topologies. This type of connector is used on the backplane. The first
argument to the init method is the device number, the second argument is the
name of the PCI bus object, and the third optional argument controls if this
connector/slot can be used for bridges (default no). Limitations: currently does
not support hot-plug disconnect.'''

    def __init__(self, dev_num, bus, bridge_supported = False,
                 hotpluggable = True, required = False):
        if not isinstance(dev_num, int) or dev_num < 0:
            raise comp.CompException('dev_num must be an integer >= 0')
        if not isinstance(bus, str):
            raise comp.CompException('bus must be a string')
        self.dev_num = dev_num
        self.bus = bus
        self.bridge_supported = bridge_supported
        self.type = 'compact-pci-bus'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        return [self.dev_num, cmp.get_slot(self.bus)]

    def connect(self, cmp, cnt, attr):
        (device_list,) = attr
        bus = cmp.get_slot(self.bus)
        for dev in device_list:
            (fun_num, obj, is_bridge) = dev
            if is_bridge:
                # bridges could route interrupts and system error if this
                # slot/connector supports it
                if self.bridge_supported:
                    if isinstance(bus.bridge, list):
                        bus.bridge += [obj]
                    else:
                        bus.bridge = [bus.bridge, obj] if bus.bridge else obj
            else:
                # only devices are visible on the bus, bridges are not
                bus.pci_devices += [[self.dev_num, fun_num, obj]]


    def disconnect(self, cmp, cnt):
        bus = cmp.get_slot(self.bus)
        # TODO: remove bridge object from bus.bridge attribute, but how?
        bus.pci_devices = [x for x in bus.pci_devices if x[0] != self.dev_num]

class CompactPciBusUpConnector(StandardConnector):
    '''The CompactPciBusUpConnector class handles pci-bus up connections for
cPCI topologies. This type of connector is used for devices/cards connected to
the backplane. The first argument to the init method is the PCI device function
number, the second argument is the name of the PCI device or bridge object, and
the third optional argument indicates if the object is a bridge with it's
secondary bus facing the backplane (default: no).'''

    def __init__(self, fun_num, device, is_bridge = False,
                 hotpluggable = True, required = False,
                 use_upstream = False):
        if not isinstance(fun_num, int) or fun_num < 0:
            raise comp.CompException('fun_num must be an integer >= 0')
        if not isinstance(device, str):
            raise comp.CompException('device must be a string')
        self.fun_num = fun_num
        self.device = device
        self.is_bridge = is_bridge
        self.type = 'compact-pci-bus'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up
        self.use_upstream = use_upstream

    def get_connect_data(self, cmp, cnt):
        return [[[self.fun_num, cmp.get_slot(self.device), self.is_bridge]]]

    def connect(self, cmp, cnt, attr):
        (_, pci_bus) = attr
        if self.is_bridge:
            # a bus-to-bus bridge with its secondary bus facing the backplane
            cmp.get_slot(self.device).secondary_bus = pci_bus
        else:
            # a normal device or bus-to-bus bridge with it's primary bus facing
            # the backplane
            cmp.get_slot(self.device).pci_bus = pci_bus
            if self.use_upstream:
                cmp.get_slot(self.device).upstream_target = pci_bus

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.device).pci_bus = None
        if self.use_upstream:
            cmp.get_slot(self.device).upstream_target = None

# agp
class AgpDownConnector(PciBusDownConnector):
    '''The AgpDownConnector class handles agp-bus down connections. It is
identical to the PciBusDownConnector class except for the connection
type.'''

    def __init__(self, dev_num, bus,
                 hotpluggable = True, required = False):
        PciBusDownConnector.__init__(self, dev_num, bus, hotpluggable, required)
        self.type = 'agp-bus'

# mem-bus
class MemBusDownConnector(StandardConnector):
    '''The MemBusDownConnector class handles mem-bus down connections.
The first argument to the init method is the name of the I2C bus object,
and the second argument is the address to connect to.'''

    def __init__(self, i2c_bus, address,
                 connect_callback = None,
                 required = False):
        if not isinstance(i2c_bus, str):
            raise comp.CompException('i2c_bus must be a string')
        if not isinstance(address, int) or address < 0:
            raise comp.CompException('address must be an integer >= 0')
        self.i2c_bus = i2c_bus
        self.address = address
        self.connect_callback = connect_callback
        self.type = 'mem-bus'
        self.hotpluggable = False
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.i2c_bus), self.address]

    def connect(self, cmp, cnt, attr):
        if self.connect_callback:
            self.connect_callback(cnt, attr)

    def disconnect(self, cmp, cnt):
        raise comp.CompException('disconnecting mem-bus connection not allowed')

# ide-slot
class IdeSlotDownConnector(StandardConnector):
    '''The IdeSlotDownConnector class handles ide-slot down connections.
The first argument to the init method is the name of the IDE device object,
and the second argument is True if it is a master connection.
The IDE device is expected to have master and slave attributes.'''

    def __init__(self, device, master,
                 hotpluggable = True, required = False):
        if not isinstance(device, str):
            raise comp.CompException('device must be a string')
        if not isinstance(master, bool):
            raise comp.CompException('master must be a bool')
        self.device = device
        self.master = master
        self.type = 'ide-slot'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        return []

    def connect(self, cmp, cnt, attr):
        (ide_dev,) = attr
        if self.master:
            cmp.get_slot(self.device).master = ide_dev
        else:
            cmp.get_slot(self.device).slave = ide_dev

    def disconnect(self, cmp, cnt):
        if self.master:
            cmp.get_slot(self.device).master = None
        else:
            cmp.get_slot(self.device).slave = None

class IdeSlotUpConnector(StandardConnector):
    """The IdeSlotUpConnector class handles ide-slot up connections. The
first argument to the init method is the IDE device object."""

    def __init__(self, device):
        self.device = device
        self.type = 'ide-slot'
        self.hotpluggable = True
        self.required = False
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.device)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

# sata-slot
class SataSlotDownConnector(StandardConnector):
    '''The SataSlotDownConnector class handles sata-slot down connections.
The first argument to the init method is the name of the SATA controller
device. The device is expected to have a sata_device attribute.'''

    def __init__(self, device, port = None, port_num = None,
                 hotpluggable = True, required = False):
        if not isinstance(device, str):
            raise comp.CompException('device must be a string')
        self.device = device
        self.port = port
        self.port_num = port_num
        self.type = 'sata-slot'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        if self.port != None:
            return [[cmp.get_slot(self.device), self.port]]
        else:
            return [cmp.get_slot(self.device)]

    def connect(self, cmp, cnt, attr):
        (sata_dev, ) = attr
        if self.port_num != None:
            try:
                sata_devs = cmp.get_slot(self.device).sata_device
            except:
                sata_devs = [None] * 32
            finally:
                sata_devs[self.port_num] = sata_dev
                cmp.get_slot(self.device).sata_device = sata_devs
        else:
            cmp.get_slot(self.device).sata_device = sata_dev

    def disconnect(self, cmp, cnt):
        if self.port_num != None:
            cmp.get_slot(self.device).sata_device[self.port_num] = None
        else:
            cmp.get_slot(self.device).sata_device = None

class SataSlotUpConnector(StandardConnector):
    '''The SataSlotUpConnector class handles sata-slot up connections.
The first argument to the init method is the name of the SATA device.'''

    def __init__(self, device,
                 hotpluggable = True, required = False):
        self.device = device
        self.type = 'sata-slot'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.device)]

    def connect(self, cmp, cnt, attr):
        (sata_ctl, ) = attr
        cmp.get_slot(self.device).hba = sata_ctl

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.device).hba = None

# isa-bus
class IsaBusDownConnector(StandardConnector):
    '''The IsaBusDownConnector class handles isa-bus down connections.
The arguments to the init method are the names of the port_space, the
memory_space, the interrupt device, and the dma device, in that order.'''

    def __init__(self, port_space, memory_space,
                 interrupt_device, dma_device,
                 hotpluggable = True, required = False):
        if not isinstance(port_space, str):
            raise comp.CompException('port_space must be a str')
        if not isinstance(interrupt_device, str):
            raise comp.CompException('interrupt_device must be a str')
        if not isinstance(dma_device, str):
            raise comp.CompException('dma_device must be a str')
        self.port_space = port_space
        self.memory_space = memory_space
        self.interrupt_device = interrupt_device
        self.dma_device = dma_device
        self.type = 'isa-bus'
        self.hotpluggable = hotpluggable
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        # memory_space is only needed for legacy VGA
        return [cmp.get_slot(self.port_space),
                cmp.get_slot(self.memory_space) if self.memory_space else None,
                cmp.get_slot(self.interrupt_device),
                cmp.get_slot(self.dma_device)]

    def check(self, cmp, cnt, attr):
        (ports,) = attr
        port_space = cmp.get_slot(self.port_space)
        occupied_ports = [x[0] for x in port_space.map]
        for p in ports:
            if p in occupied_ports:
                simics.SIM_log_info(
                    1, cmp.obj, 0, 'ISA port %d already occupied' % p)
                return False
        return True

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

# USB port
class UsbPortDownConnector(StandardConnector):
    '''The UsbPortDownConnector class handles usb-port down connections.
The first argument to the init method is the name of the USB device.'''

    type = 'usb-port'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, usb):
        self.usb = usb

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.usb)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class UsbPortUpConnector(StandardConnector):
    '''The UsbPortUpConnector class handles usb-port up connections.
The first argument to the init method is the name of the USB device.'''

    type = 'usb-port'
    direction = simics.Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, usb):
        self.usb = usb

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.usb)]

    def connect(self, cmp, cnt, attr):
        (usb_host,) = attr
        cmp.get_slot(self.usb).usb_host = usb_host

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.usb).usb_host = None

class AbsMouseDownConnector(StandardConnector):
    '''The AbsMouseDownConnector class handles abs-mouse down connections.
The first argument to the init method is the name of abs mouse device.'''
    type = 'abs-mouse'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, abs_mouse):
        self.abs_mouse = abs_mouse

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.abs_mouse)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

# MAC -> PHY
class PhyDownConnector(StandardConnector):
    '''The PhyDownConnector class handles phy down connections.
The first argument to the init method is the name of the mac object
(ethernet device), and the second argument is optional and is the name
of the MII bus object.'''

    type = 'phy'
    direction = simics.Sim_Connector_Direction_Down
    hotpluggable = False
    multi = False

    def __init__(self, mac, mii_bus=None, required=False):
        self.mac = mac
        self.mii_bus = mii_bus
        self.required = required

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.mac)]

    def connect(self, cmp, cnt, attr):
        (phy, addr) = attr
        cmp.get_slot(self.mac).phy = phy

        if self.mii_bus:
            cmp.get_slot(self.mii_bus).devices += [[phy, addr]]

# MAC <- PHY
class PhyUpConnector(StandardConnector):
    '''The PhyUpConnector class handles phy up connections.
The first argument to the init method is the name of the phy object,
and the second argument is the phy address.'''

    type = 'phy'
    direction = simics.Sim_Connector_Direction_Up
    hotpluggable = False
    multi = False

    def __init__(self, phy, addr, required=False):
        self.phy = phy
        self.addr = addr
        self.required = required

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.phy), self.addr]

    def connect(self, cmp, cnt, attr):
        mac = attr[0]
        cmp.get_slot(self.phy).mac = mac

# i2c-link
class I2cLinkAnyConnector(StandardConnector):
    '''The I2cLinkAnyConnector class handles i2c-link-v2 down and up connections.
The first argument to the init method is the name of the device object,
and the second argument is the device port. The device object is expected
to have an i2c_link_v2 attribute.'''

    type = 'i2c-link'
    direction = simics.Sim_Connector_Direction_Any
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev, port=None):
        self.dev = dev
        self.port = port

    def get_connect_data(self, cmp, cnt):
        if self.port:
            try:
                return [cmp.get_slot("%s.port.%s" % (self.dev, self.port))]
            except:
                return [[cmp.get_slot(self.dev), self.port]]
        else:
            return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        link = attr[0]
        try:
            cmp.get_slot(self.dev).i2c_link_v2 = link
        except:
            cmp.get_slot(self.dev).i2c_link_v2[0] = link

    def disconnect(self, cmp, cnt):
        try:
            cmp.get_slot(self.dev).i2c_link_v2 = None
        except:
            cmp.get_slot(self.dev).i2c_link_v2[0] = None

class I2cLinkDownConnector(I2cLinkAnyConnector):
    direction = simics.Sim_Connector_Direction_Down

class I2cLinkUpConnector(I2cLinkAnyConnector):
    direction = simics.Sim_Connector_Direction_Up

class MMCUpConnector(StandardConnector):
    '''The MMCUpConnector class handles MMC/SD card up connections.
The first argument to the init method is the name of the device object.'''

    type = 'mmc'
    direction = simics.Sim_Connector_Direction_Up
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.dev)]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        pass

class MMCDownConnector(StandardConnector):
    '''The MMCDownConnector class handles MMC/SD card down connections.
The first argument to the init method is the name of the device object,
and the device object is expected to have a "card" attribute.'''

    type = 'mmc'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev):
        self.dev = dev

    def get_connect_data(self, cmp, cnt):
        return []

    def connect(self, cmp, cnt, attr):
        card = attr[0]
        cmp.get_slot(self.dev).card = card

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.dev).card = None

class GfxDownConnector(StandardConnector):
    '''The GfxDownConnector class handles Graphics down connections.
The first argument to the init method is the name of the device object, and
the second argument is the name of the attaching external graphics console.
The third argument is optional and should be set to False if the device
does not implement the video interface. The fourth argument is optional and
should be set to the name of the sub object of the device object that implements
the video interface.'''

    type = 'graphics-console'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev, con, video=True, sub_obj=None):
        self.dev = dev
        self.con = con
        self.video = video
        self.sub_obj = sub_obj

    def get_connect_data(self, cmp, cnt):
        if self.sub_obj:
            return [getattr(cmp.get_slot(self.dev), self.sub_obj)]
        else:
            return [cmp.get_slot(self.dev)] if self.video else [None]

    def connect(self, cmp, cnt, attr):
        con = attr[0]
        setattr(cmp.get_slot(self.dev), self.con, con)

    def disconnect(self, cmp, cnt):
        setattr(cmp.get_slot(self.dev), self.con, None)

# TODO: the documentation needs to be improved
class I3CLinkAnyConnector(StandardConnector):
    '''I3C link connector'''
    type = 'i3c-link'
    direction = simics.Sim_Connector_Direction_Any
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, dev, cnt_name, port_name=None):
        self.dev = dev
        self.port_name = port_name
        self.cnt_name = cnt_name

    def get_connect_data(self, cmp, cnt):
        dev = cmp.get_slot(self.dev)
        return [[dev, self.port_name]] if self.port_name else  [dev]

    def connect(self, cmp, cnt, attr):
        self.set_target(cmp, attr[0])

    def disconnect(self, cmp, cnt):
        self.set_target(cmp, None)

    def set_target(self, cmp, target):
        import re
        m = re.match(r'([_a-zA-Z0-9]+)\[(\d+)\]', self.cnt_name)
        dev = cmp.get_slot(self.dev)
        if m:
            name = m.group(1)
            values = getattr(dev, name)
            values[int(m.group(2))] = target
            setattr(dev, name, values)
        else:
            setattr(dev, self.cnt_name, target)

class I3CLinkUpConnector(I3CLinkAnyConnector):
    direction = simics.Sim_Connector_Direction_Up

class I3CLinkDownConnector(I3CLinkAnyConnector):
    direction = simics.Sim_Connector_Direction_Down
