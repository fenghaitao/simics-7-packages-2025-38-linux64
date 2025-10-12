# © 2022 Intel Corporation
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
from deprecation import DEPRECATED

__all__ = ["Dev", "Iface", "iface", "Memory"]

# <add id="dev_util_internal">
# <name>dev_util_internal</name>
#
# Internal and/or legacy classes removed from dev_util.py
#
# </add>


class Error(Exception):
    pass


# <add id="dev_util_internal.Dev">
# A Simics class with a single instance.
# Implements zero or more interfaces based on instances of
# <class>Iface</class>. Presents zero or
# more ports, implementing one or more interfaces each.
#
# The <var>obj</var> attribute contains the instance of the Simics
# class, and the <var>cls_name</var> attribute contains the name of
# the Simics class.
# </add>
class Dev:
    __next_id = {}

    # <add id="dev_util_internal.Dev.register_simics_class">
    # Register the Simics class created by this object.
    # </add>
    def register_simics_class(self):
        sim_cls = simics.class_info_t(
            description = "Fake device for testing")
        try:
            simics.SIM_create_class(self.cls_name, sim_cls)
        except simics.SimExc_General as e:
            raise Error("Could not register class %s: %s"
                        % (self.cls_name, str(e)))

    # <add id="dev_util_internal.Dev.configure_pre_object">
    # Called before <fun>SIM_add_configuration</fun>.
    # Override to e.g. set attributes.
    # </add>
    def configure_pre_object(self, pre_obj):
        pass

    # <add id="dev_util_internal.Dev.finalize">
    # Called after the Simics object has been instantiated.
    # </add>
    def finalize(self):
        pass

    # <add id="dev_util_internal.Dev">
    # Constructor arguments:
    # <dl>
    # <dt>iface_list</dt>
    # <dd>a list of interface classes or pairs of
    #     (port, interface-class)</dd>
    # <dt>create_sim_obj</dt>
    # <dd>if False, no Simics object will be created, but the
    # class will be registered along with all the interfaces, useful
    # e.g. when loading a checkpoint containing fake objects</dd>
    # <dt>name</dt>
    # <dd>if given, specifies the name to use for the fake class and
    # the fake object; otherwise a name will be guessed based on the
    # implemented interfaces</dd>
    # </dl>
    #
    # Each interface will be instantiated and can be accessed through
    # <v>dev</v>.<v>iface-name</v>,
    # or <v>dev</v>.<v>port</v>.<v>iface-name</v>.
    #
    # Example:
    # <pre>
    # dev = Dev([SimpleInterrupt,
    #            ('sreset', Signal),
    #            ('hreset', Signal)])
    #
    # dev.simple_interrupt
    # dev.sreset.signal
    # dev.hreset.signal
    # </pre>
    # </add>
    def __init__(self, iface_list = [], create_sim_obj = True, name = None):
        DEPRECATED(simics.SIM_VERSION_7,
                   'The dev_util.Dev Python class is deprecated.', '')

        # Register Simics class. Note that we use unique class names for
        # every Dev instance. This will ensure interface methods are correctly
        # bound.
        def make_iface_string(iface):
            '''Make up a string corresponding to a interface or port,
            to be used when composing the fake class name'''
            if isinstance(iface, (tuple, list)):
                (port, iface) = iface
                return port
            else:
                return iface.iface

        if name:
            self.cls_name = name
        else:
            basename = '_'.join(['fake'] + [make_iface_string(iface)
                                            for iface in iface_list])
            # too long names are impractical, so chop them off.
            basename = basename[:30].rstrip('-_')
            # avoid name collisions
            index = Dev.__next_id.get(basename, 0)
            Dev.__next_id[basename] = index + 1
            self.cls_name = basename + str(index)

        self.register_simics_class()

        # Create interface instances (will also register the interfaces)
        for iface in iface_list:
            if isinstance(iface, (tuple, list)):
                (port, iface_cls) = iface
                try:
                    attr = getattr(self, port)
                except AttributeError:
                    class Port: pass
                    setattr(self, port, Port())
                    attr = getattr(self, port)
            else:
                port = None
                iface_cls = iface
                attr = self
            iface_inst = iface_cls()
            iface_inst._register_interface(self.cls_name, port)
            iface_inst.dev = self
            setattr(attr, iface_cls.iface, iface_inst)

        # Create Simics object
        if create_sim_obj:
            p_obj = simics.pre_conf_object(self.cls_name, self.cls_name)
            self.configure_pre_object(p_obj)

            simics.SIM_add_configuration([p_obj], None)
            self.obj = simics.SIM_get_object(self.cls_name)

            self.finalize()

class BasicIface:
    """A fake interface, for use by the Dev class. Usually it is a good
    idea to subclass Iface to create a new interface, but there are
    examples when Iface isn't generic enough; e.g., if two different
    interfaces are implemented by the same port, and some method name
    is present in both interfaces.  In this case, you will need to
    write a _register_interface method manually, to create the mappings from
    interface function name to Python method."""

    @staticmethod
    def _register_iface(cls_name, port, iface_name, iface_struct):
        '''Registers an interface on cls_name:port'''
        if port:
            simics.SIM_register_port_interface(cls_name, iface_name, iface_struct,
                                        port, '')
        else:
            simics.SIM_register_interface(cls_name, iface_name, iface_struct)

    def _register_interface(self, cls_name, port):
        self.cls_name = cls_name
        self.port = port

# <add id="dev_util_internal.Iface">
# Base class for fake interfaces. To create an interface, inherit
# this class, define a class variable iface to the interface name, and
# define all methods that the interface defines.
# </add>
class Iface(BasicIface):

    def __init__(self):
        DEPRECATED(simics.SIM_VERSION_7,
                   'The dev_util.Iface Python class is deprecated.', '')

    def _register_interface(self, cls_name, port):
        '''Register the interface'''
        super(Iface, self)._register_interface(cls_name, port)

        # Hack: Find all superclasses, and register those that look
        # sensible. The hack allows diamond inheritance (you can
        # inherit two ifaces and it will work automatically), and if
        # you override some methods of one iface, these will be used.
        def all_superclasses(cl):
            """Return all superclasses of f (including f),
            with the childmost class first"""
            return sum((all_superclasses(s) for s in cl.__bases__), [cl])
        # maps iface values to the corresponding Iface subclasses that
        # will register the interfaces.
        iface_dict = dict(
            (cl.iface, cl)
            # If more than one class defines the same iface, then only
            # the childmost one (i.e., the one all_superclasses finds
            # first) is registered. The superclass list is reversed in
            # order to make the childmost one override the others.
            for cl in all_superclasses(self.__class__).__reversed__()
            if (issubclass(cl, Iface)
                and getattr(cl, 'iface', None) != None))

        for (iface_name, iface_class) in ((name, iface_dict[name])
                                          for name in iface_dict):
            BasicIface._register_iface(
                cls_name, port, iface_name,
                self._get_iface_instance(iface_class))

    def _get_iface_instance(self, cl):
        '''Create an instance of a Simics interface we are faking'''
        return cl._get_iface_class(cl)(**self._get_method_dict(cl))

    @staticmethod
    def _get_iface_class(cl):
        '''Get the Simics class of the interface we are faking'''
        iface_class = simics.SIM_get_python_interface_type(cl.iface)
        if not iface_class:
            raise Error("Unknown interface %s" % cl.iface)
        return iface_class

    # <add id="dev_util_internal.Iface.fail">
    # Signal a failure when running an interface method.
    #
    # Called by the default method stubs.
    # </add>
    def fail(self, msg):
        raise Exception(msg)

    def _create_unimplemented_method(self, iface_class, method):
        def unimplemented_method(*args):
            self.fail("The fake interface class %s does not implement"
                      " the method %s.%s"
                      % (self.__class__.__name__, iface_class.__name__, method))
        return unimplemented_method

    def _get_method_dict(self, cl):
        '''Return the (bound) methods to implement in the interface,
        as a name -> method dictionary'''
        iface = cl._get_iface_class(cl)()
        method_names = [f for f in dir(iface) if not f.startswith('__')]
        return dict((f, getattr(self, f, self._create_unimplemented_method(
                        iface.__class__, f)))
                    for f in method_names)

# <add id="dev_util_internal.iface">
# Returns an Iface subclass which implements the interface <var>name</var>.
#
# All the interface methods in the class will raise an exception when
# called. Convenient when creating a fake device that is required to
# implement an interface, but you know that the interface should be
# unused in the given test.  </add>
def iface(name):
    DEPRECATED(simics.SIM_VERSION_7, 'dev_util.iface is deprecated.', '')
    class StubIface(Iface):
        iface = name
    StubIface.__name__ = "".join(name.title().split("_"))
    return StubIface

class SimpleInterrupt(Iface):
    iface = simics.SIMPLE_INTERRUPT_INTERFACE

    def __init__(self):
        self.raised = {}

    def interrupt(self, sim_obj, level):
        self.raised[level] = self.raised.get(level, 0) + 1

    def interrupt_clear(self, sim_obj, level):
        self.raised[level] = self.raised.get(level, 0) - 1

class SerialDevice(Iface):
    iface = simics.SERIAL_DEVICE_INTERFACE

    def __init__(self):
        self.value = -1
        self.receive_ready_called = False

    def write(self, sim_obj, value):
        self.value = value
        return 1

    def receive_ready(self, sim_obj):
        self.receive_ready_called = True

class SerialPeripheralInterfaceSlave(Iface):
    iface = simics.SERIAL_PERIPHERAL_INTERFACE_SLAVE_INTERFACE

    def __init__(self):
        self.frames = []
        self.idle = True
        self.master = None
        self.master_port = None

    def connect_master(self, sim_obj, master, port, flags):
        self.master = master
        self.port = port

    def disconnect_master(self, sim_obj, master):
        assert self.master == master
        self.master = None
        self.port = None

    def spi_request(self, sim_obj, first, last, bits, payload):
        assert self.master
        assert len(payload) == (bits + 7) // 8

        def int_to_bitstring(ch, bits):
            if not bits:
                return []
            else:
                return [ch & 1] + int_to_bitstring(ch >> 1, bits - 1)

        extracted_payload = sum([int_to_bitstring(ch, 8) for ch in payload],
                                [])[:bits]
        if first:
            assert self.idle
            self.frames += [extracted_payload]
        else:
            self.frames[-1] += extracted_payload

        self.idle = last

class Signal(Iface):
    iface = simics.SIGNAL_INTERFACE

    def __init__(self):
        self.level = 0
        self.spikes = 0

    def signal_raise(self, sim_obj):
        self.level += 1

    def signal_lower(self, sim_obj):
        if (self.level == 1):
            self.spikes += 1
        self.level -= 1

class MultiLevelSignal(Iface):
    iface = simics.MULTI_LEVEL_SIGNAL_INTERFACE

    def __init__(self):
        self.level = 0

    def signal_level_change(self, sim_obj, level):
        self.level = level

    def signal_current_level(self, sim_obj, level):
        self.level = level

class FrequencyListener(Iface):
    iface = simics.FREQUENCY_LISTENER_INTERFACE

    def __init__(self):
        self.numerator = 1
        self.denominator = 1

    def set(self, sim_obj, numerator, denominator):
        self.numerator = numerator
        self.denominator = denominator

class ScaleFactorListener(FrequencyListener):
    iface = simics.SCALE_FACTOR_LISTENER_INTERFACE

class SimpleDispatcher(Iface):
    iface = simics.SIMPLE_DISPATCHER_INTERFACE

    def __init__(self):
        self.targets = set()

    def subscribe(self, sim_obj, tgt, port):
        assert (tgt, port) not in self.targets
        self.targets.add((tgt, port))

    def unsubscribe(self, sim_obj, tgt, port):
        assert (tgt, port) in self.targets
        self.targets.discard((tgt, port))

class I2cDevice(Iface):
    iface = simics.I2C_DEVICE_INTERFACE

    def __init__(self):
        self.rsps = []
        self.toread = 0

    def set_state(self, m, state, address):
        self.rsps.append(('state', state))
        return 0

    def read_data(self, m):
        self.rsps.append(('read',))
        return self.toread

    def write_data(self, m, value):
        self.rsps.append(('write', value))

class I2cBus(Iface):
    iface = simics.I2C_BUS_INTERFACE

    I2C_flag_exclusive = 0
    I2C_flag_shared    = 1

    I2C_idle            = 0
    I2C_master_transmit = 1
    I2C_master_receive  = 2
    I2C_slave_transmit  = 3
    I2C_slave_receive   = 4

    def __init__(self):
        self.mode = I2cBus.I2C_idle
        self.data = None
        self.slave_addresses = []
        self.selected_slave_address = None

    def start(self, sim_obj, address):
        # Assert that all addresses are 7-bit
        for addr in self.slave_addresses:
            assert addr == (addr & 0x7f)

        if (address >> 1) in self.slave_addresses:
            if address & 1:
                self.mode = I2cBus.I2C_slave_transmit
            else:
                self.mode = I2cBus.I2C_slave_receive
            self.selected_slave_address = address >> 1
            return 0
        else:
            self.mode = I2cBus.I2C_idle
            self.selected_slave_address = None
            return -1

    def stop(self, sim_obj):
        if self.mode == I2cBus.I2C_idle:
            raise Exception('i2c_bus.stop() when already in idle mode')
        self.mode = I2cBus.I2C_idle
        return 0

    def read_data(self, sim_obj):
        if self.mode != I2cBus.I2C_slave_transmit:
            raise Exception('i2c_bus.read() when not in slave transmit mode')
        return self.data

    def write_data(self, sim_obj, value):
        if self.mode != I2cBus.I2C_slave_receive:
            raise Exception('i2c_bus.write() when not in slave receive mode')
        self.data = value

    def register_device(self, sim_obj, dev, address, mask, flags):
        '''Not yet needed and thus not yet implemented'''
        return 0

    def unregister_device(self, sim_obj, dev, address, mask):
        '''Not yet needed and thus not yet implemented'''
        pass

class I2cLink(Iface):
    '''Fake I2C link object. Stores all calls from the connected
    device(s). You have to manually send requests to a connected slave
    device, the response calls will be logged in the link. A request
    from a master device will also be logged, and you can call the
    respond() method to send an appropriate response.'''

    iface = simics.I2C_LINK_INTERFACE

    I2c_Idle           = 0
    I2c_Slave_Transmit = 1
    I2c_Slave_Receive  = 2

    I2C_status_success = 0
    I2C_status_noack = 1
    I2C_status_bus_busy = 2

    def respond(self, expect_type):
        assert(self.master)
        if not self.requests:
            raise Error("I2C master device did not send a "
                        + expect_type + " request when it should")
        (type, value) = self.requests.pop()
        if expect_type != type:
            raise Error("Previous request on this link was a " + type
                        + ", expected " + expect_type)
        if type == "start":
            self.master.iface.i2c_master.start_response(
                [I2cLink.I2C_status_success, I2cLink.I2C_status_noack][
                self.mode == I2cLink.I2c_Idle])
        elif type == "read":
            self.master.iface.i2c_master.read_response(self.data)
        elif type == "ack_read":
            self.master.iface.i2c_master.ack_read_response()
        elif type == "write":
            self.master.iface.i2c_master.write_response(self.ack_write)
        else: assert(False)

    def __init__(self):
        self.mode = I2cLink.I2c_Idle
        self.data = None
        self.ack_write = I2cLink.I2C_status_success
        self.slave_addresses = set()
        self.selected_slave_address = None
        self.status = []
        self.requests = []
        self.master = None

    def start_request(self, sim_obj, sender, address):
        assert(self.master == sender or self.master == None)

        # Assert that all addresses are 7-bit
        for addr in self.slave_addresses:
            assert addr == (addr & 0x7f)

        if (address >> 1) in self.slave_addresses:
            if address & 1:
                self.mode = I2cLink.I2c_Slave_Transmit
            else:
                self.mode = I2cLink.I2c_Slave_Receive
            self.selected_slave_address = address >> 1
        else:
            self.mode = I2cLink.I2c_Idle
            self.selected_slave_address = 0
        self.requests.append(("start", address >> 1))
        self.master = sender

    def stop(self, sim_obj, sender):
        assert(self.master == sender)
        self.master = None
        self.mode = I2cLink.I2c_Idle

    def read_request(self, sim_obj, sender):
        assert(self.master == sender)
        self.requests.append(("read", None))

    def ack_read_request(self, sim_obj, sender, ack):
        assert(self.master == sender)
        self.requests.append(("ack_read", ack))

    def write_request(self, sim_obj, sender, value):
        assert(self.master == sender)
        self.data = value
        self.requests.append(("write", value))

    def read_response(self, sim_obj, sender, value):
        self.data = value

    def ack_read_response(self, sim_obj, sender):
        self.status.append(None)

    def start_response(self, sim_obj, sender, value):
        self.status.append(value)

    def write_response(self, sim_obj, sender, value):
        self.status.append(value)

    def register_slave_address(self, sim_obj, dev, address, mask):
        self.slave_addresses |= set((addr for addr in range(0, 256, 2)
                                     if (address ^ addr) & mask == 0))

    def unregister_slave_address(self, sim_obj, dev, address, mask):
        self.slave_addresses -= set((addr for addr in range(0, 256, 2)
                                     if (address ^ addr) & mask == 0))

    def disconnect_device(self, sim_obj, dev):
        '''Not yet needed and thus not yet implemented'''
        pass

    def register_bridge(self, sim_obj, bridge):
        '''Not yet needed and thus not yet implemented'''
        pass

class Mii(Iface):
    iface = simics.MII_INTERFACE

    def read_register(self, sim_obj, index):
        raise NotImplementedError

    def write_register(self, sim_obj, index, value):
        raise NotImplementedError

    def serial_access(self, sim_obj, data, clock):
        raise NotImplementedError

class MiiManagement(Iface):
    iface = simics.MII_MANAGEMENT_INTERFACE

    def serial_access(self, sim_obj, data_in, clock):
        raise NotImplementedError

    def read_register(self, sim_obj, phy, reg):
        raise NotImplementedError

    def write_register(self, sim_obj, phy, reg, value):
        raise NotImplementedError

class Mdio45Bus(Iface):
    iface = simics.MDIO45_BUS_INTERFACE

    def read_register(self, sim_obj, phy, mmd, reg):
        raise NotImplementedError

    def write_register(self, sim_obj, phy, mmd, reg, value):
        raise NotImplementedError

class Mdio45Phy(Iface):
    iface = simics.MDIO45_PHY_INTERFACE

    def read_register(self, sim_obj, mmd, reg):
        raise NotImplementedError

    def write_register(self, sim_obj, mmd, reg, value):
        raise NotImplementedError

class Microwire(Iface):
    iface = simics.MICROWIRE_INTERFACE

    def set_cs(self, sim_obj, cs):
        raise NotImplementedError

    def set_sk(self, sim_obj, sk):
        raise NotImplementedError

    def set_di(self, sim_obj, di):
        raise NotImplementedError

    def get_do(self, sim_obj):
        raise NotImplementedError

    def read_word(self, sim_obj, offset):
        raise NotImplementedError

    def write_word(self, sim_obj, offset, value):
        raise NotImplementedError

class Ieee_802_3_mac(Iface):
    iface = simics.IEEE_802_3_MAC_INTERFACE

    def __init__(self):
        self.received_frames = []

    def receive_frame(self, sim_obj, phy, frame, crc_ok):
        self.received_frames += [frame]
        return 0

    def link_status_changed(self, sim_obj, phy, status):
        pass

    def tx_bandwidth_available(self, sim_obj, phy):
        pass


class Ieee_802_3_mac_v3(Ieee_802_3_mac):
    iface = simics.IEEE_802_3_MAC_V3_INTERFACE

class Ieee_802_3_phy(Iface):
    iface = simics.IEEE_802_3_PHY_INTERFACE

    def __init__(self):
        self.promiscuous_mode = False

    def send_frame(self, sim_obj, buf, replace_crc):
        raise NotImplementedError

    def check_tx_bandwidth(self, sim_obj):
        raise NotImplementedError

    def set_promiscous_mode(self, sim_obj, enable):
        self.promiscuous_mode = (False, True)[enable]

class Ieee_802_3_phy_v2(Ieee_802_3_phy):
    iface = simics.IEEE_802_3_PHY_V2_INTERFACE

    def add_mac(self, sim_obj, mac):
        raise NotImplementedError

    def del_mac(self, sim_obj, mac):
        raise NotImplementedError

    def add_mac_mask(self, sim_obj, mac, mask):
        raise NotImplementedError

    def del_mac_mask(self, sim_obj, mac, mask):
        raise NotImplementedError

class Ieee_802_3_phy_v3(Iface):
    iface = simics.IEEE_802_3_PHY_V3_INTERFACE

    def send_frame(self, sim_obj, frame, replace_crc):
        raise NotImplementedError

    def check_tx_bandwidth(self, sim_obj):
        raise NotImplementedError


class IoMemory(Iface):
    iface = simics.IO_MEMORY_INTERFACE

    def _deprecated_map(self, sim_obj, memory_or_io, map_info):
        return 0

    def operation(self, sim_obj, mop, map_info):
        raise NotImplementedError

class PciBus(Iface):
    iface = simics.PCI_BUS_INTERFACE

    def __init__(self):
        self._conf_space = None
        self._io_space = None
        self._mem_space = None

    def memory_access(self, sim_obj, mop):
        raise NotImplementedError

    def raise_interrupt(self, sim_obj, dev, pin):
        raise NotImplementedError

    def lower_interrupt(self, sim_obj, dev, pin):
        raise NotImplementedError

    def interrupt_acknowledge(self, sim_obj):
        raise NotImplementedError

    def add_map(self, sim_obj, dev, space, target, map_info):
        raise NotImplementedError

    def remove_map(self, sim_obj, dev, space, function):
        raise NotImplementedError

    def set_bus_number(self, sim_obj, bus_id):
        raise NotImplementedError

    def set_sub_bus_number(self, sim_obj, bus_id):
        raise NotImplementedError

    def add_default(self, sim_obj, dev, space, target, map_info):
        raise NotImplementedError

    def remove_default(self, sim_obj, space):
        raise NotImplementedError

    def bus_reset(self, sim_obj):
        raise NotImplementedError

    def special_cycle(self, sim_obj, value):
        raise NotImplementedError

    def system_error(self, sim_obj):
        raise NotImplementedError

    def get_bus_address(self, sim_obj, dev):
        raise NotImplementedError

    def set_device_timing_model(self, sim_obj, dev, timing_model):
        raise NotImplementedError

    def set_device_status(self, sim_obj, dev, function, enabled):
        raise NotImplementedError

    def configuration_space(self, sim_obj):
        return self._conf_space

    def io_space(self, sim_obj):
        return self._io_space

    def memory_space(self, sim_obj):
        return self._mem_space

class PciBridge(Iface):
    iface = simics.PCI_BRIDGE_INTERFACE

    def system_error(self, sim_obj):
        raise NotImplementedError

    def raise_interrupt(self, sim_obj, irq_obj, device, pin):
        raise NotImplementedError

    def lower_interrupt(self, sim_obj, irq_obj, device, pin):
        raise NotImplementedError

class PciExpress(Iface):
    iface = simics.PCI_EXPRESS_INTERFACE

    def send_message(self, sim_obj, src, type, payload):
        raise NotImplementedError

class PciUpstream(Iface):
    iface = simics.PCI_UPSTREAM_INTERFACE

    def operation(self, sim_obj, mop, addr_space):
        raise NotImplementedError

class PciDownstream(Iface):
    iface = simics.PCI_DOWNSTREAM_INTERFACE

    def operation(self, sim_obj, mop, addr_space):
        raise NotImplementedError

class Translate(Iface):
    iface = simics.TRANSLATE_INTERFACE

    def translate(self, sim_obj, mop, mapinfo):
        raise NotImplementedError

class MemorySpace(Iface):
    iface = simics.MEMORY_SPACE_INTERFACE

    def access(self, sim_obj, mop):
        raise NotImplementedError

    def read(self, sim_obj, initiator, addr, length, inquiry):
        raise NotImplementedError

    def write(self, sim_obj, initiator, addr, data, inquiry):
        raise NotImplementedError

    def space_lookup(self, sim_obj, mop, mapinfo):
        raise NotImplementedError

    def timing_model_operate(self, sim_obj, mop):
        raise NotImplementedError

class FirewireDevice(Iface):
    iface = simics.FIREWIRE_DEVICE_INTERFACE

    def transfer(self, sim_obj, source, packet, crc_calculated):
        raise NotImplementedError

    def reset(self, sim_obj, new_id, root_id, self_ids):
        raise NotImplementedError

    def get_self_id_template(self, sim_obj):
        raise NotImplementedError

    def get_rhb(self, sim_obj):
        raise NotImplementedError

    def get_port_count(self, sim_obj):
        raise NotImplementedError

    def get_port_mask(self, sim_obj):
        raise NotImplementedError

class FirewireBus(Iface):
    iface = simics.FIREWIRE_BUS_INTERFACE

    def connect_device(self, sim_obj, dev_obj):
        raise NotImplementedError

    def disconnect_device(self, sim_obj, dev_obj):
        raise NotImplementedError

    def set_id_mask(self, sim_obj, dev_obj, mask):
        raise NotImplementedError

    def transfer(self, sim_obj, packet, crc_calculated):
        raise NotImplementedError

    def register_channel(self, sim_obj, dev_obj, channel):
        raise NotImplementedError

    def unregister_channel(self, sim_obj, dev_obj, channel):
        raise NotImplementedError

    def reset(self, sim_obj):
        raise NotImplementedError

    def set_device_bus_id(self, sim_obj, dev_obj, bus_id):
        raise NotImplementedError

class CacheControl(Iface):
    iface = simics.CACHE_CONTROL_INTERFACE

    def cache_control(self, sim_obj, op, mop):
        raise Exception('not yet implemented')

class MapDemap(Iface):
    iface = simics.MAP_DEMAP_INTERFACE

    def add_map(self, space, dev, target, map_info):
        raise NotImplementedError

    def remove_map(self, space, dev, func):
        raise NotImplementedError

    def add_default(self, space, dev, target, map_info):
        raise NotImplementedError

    def remove_default(self, space):
        raise NotImplementedError

    def map_simple(self, space, dev, port, map_info):
        raise NotImplementedError

    def map_bridge(self, space, dev, port, target, target_port, map_info):
        raise NotImplementedError

    def unmap(self, space, dev, port):
        raise NotImplementedError

    def unmap_address(self, space, dev, base, port):
        raise NotImplementedError

class StepQueue(Iface):
    iface = simics.STEP_INTERFACE

    def get_step_count(self, sim_obj):
        raise NotImplementedError

    def post_step(self, sim_obj, event_cls, obj, steps, user_data):
        raise NotImplementedError

    def cancel_step(self, sim_obj, event_cls, obj, pred, match_data):
        raise NotImplementedError

    def find_next_step(self, sim_obj, event_cls, obj, pred, match_data):
        raise NotImplementedError

    def events(self, sim_obj):
        raise NotImplementedError

    def advance(self, sim_obj, steps):
        raise NotImplementedError

class CycleQueue(Iface):
    iface = simics.CYCLE_INTERFACE

    def __init__(self):
        self.freq_mhz = 1
        self.time = 0

    def get_cycle_count(self, sim_obj):
        raise NotImplementedError

    def get_time(self, sim_obj):
        return self.time

    def cycles_delta(self, sim_obj, when):
        raise NotImplementedError

    def get_frequency(self, sim_obj):
        return self.freq_mhz

    def post_cycle(self, sim_obj, event_cls, obj, cycles, user_data):
        raise NotImplementedError

    def post_time(self, sim_obj, event_cls, obj, seconds, user_data):
        raise NotImplementedError

    def cancel(self, sim_obj, event_cls, obj, pred, match_data):
        raise NotImplementedError

    def find_next_cycle(self, sim_obj, event_cls, obj, pred, match_data):
        return 0

    def events(self, sim_obj):
        raise NotImplementedError

    def advance(self, sim_obj, cycles):
        raise NotImplementedError

    def get_execute_object(self, sim_obj, cycles):
        raise NotImplementedError

class ProcessorInfo(Iface):
    iface = simics.PROCESSOR_INFO_INTERFACE

    def disassemble(self, sim_obj, address, instruction_data, sub_operation):
        raise NotImplementedError

    def set_program_counter(self, sim_obj, pc):
        raise NotImplementedError

    def get_program_counter(self, sim_obj):
        raise NotImplementedError

    def logical_to_physical(self, sim_obj, address, access_type):
        raise NotImplementedError

    def enable_processor(self, sim_obj):
        raise NotImplementedError

    def disable_processor(self, sim_obj):
        raise NotImplementedError

    def get_enabled(self, sim_obj):
        raise NotImplementedError

    def get_endian(self, sim_obj):
        raise NotImplementedError

    def get_physical_memory(self, sim_obj):
        raise NotImplementedError

    def get_logical_address_width(self, sim_obj):
        raise NotImplementedError

    def get_physical_address_width(self, sim_obj):
        raise NotImplementedError


    def architecture(self, sim_obj):
        raise NotImplementedError

class Ppc(Iface):
    iface = simics.PPC_INTERFACE

    PPC_Sleep_Awake = 0
    PPC_Sleep_MSR = 1
    PPC_Sleep_Doze = 2
    PPC_Sleep_Nap = 3
    PPC_Sleep_Sleep = 4
    PPC_Sleep_Rvwinkle = 5
    PPC_Sleep_Wait = 6
    PPC_Sleep_Waitrsv = 7

    def clear_atomic_reservation_bit(self, sim_obj):
        raise NotImplementedError

    def raise_machine_check_exception(self, sim_obj, exc):
        raise NotImplementedError

    def register_spr_user_handlers(self, spr_number,
                                   getter, user_getter_data,
                                   setter, user_setter_data,
                                   priv_checks):
        raise NotImplementedError

    def unregister_spr_user_handlers(self, spr_number):
        raise NotImplementedError

    def spr_set_target_value(self, sim_obj, value):
        raise NotImplementedError

    def spr_stash_value(self, sim_obj, spr_number, value):
        raise NotImplementedError

    def spr_fetch_value(self, sim_obj, spr_number):
        raise NotImplementedError

    def spr_default_getter(self, sim_obj, spr_number, access_type):
        raise NotImplementedError

    def spr_default_setter(self, sim_obj, spr_number, value, access_type):
        raise NotImplementedError

    def spr_get_name(self, spr_number):
        raise NotImplementedError

    def spr_get_number(self, name):
        raise NotImplementedError

    def get_timebase_enabled(self, sim_obj):
        raise NotImplementedError

    def set_timebase_enabled(self, sim_obj, enabled):
        raise NotImplementedError

    def get_sleep_state(self, sim_obj):
        raise NotImplementedError

class Sata(Iface):
    iface = simics.SATA_INTERFACE

    def __init__(self):
        self.reqs = []

    def receive_fis(self, o, bytes_str):
        got_list = []
        for i in range(len(bytes_str)):
            got_list.append(bytes_str[i])
        self.reqs.append(["receive_fis", tuple(got_list)])

# <add id="dev_util_internal.Memory">
# A Simics memory space in which every slot can contain a byte, or be empty.
#
# Each byte sized slot in this memory can either contain a byte of data or
# be empty. Empty slots cannot be read.
#
# The <var>obj</var> attribute contains the object implementing the Simics
# interface to the memory. It implements the <iface>memory_space</iface>
# interface.
# </add>
class Memory(Dev):
    __next_proxy_id = 0

    class MemorySpace(Iface):
        iface = simics.MEMORY_SPACE_INTERFACE

        def read(self, sim_obj, initiator, addr, length, inquiry):
            try:
                return tuple(self.dev.read(addr, length))
            except Memory.MemoryException:
                return # Return non-tuple to signal I/O not taken

        def write(self, sim_obj, initiator, addr, data, inquiry):
            try:
                self.dev.write(addr, data)
            except Memory.MemoryException:
                return simics.Sim_PE_IO_Not_Taken

            return simics.Sim_PE_No_Exception

    # Thrown on errors during memory accesses
    class MemoryException(Exception): pass

    # Thrown when reading from uninitialized memory
    class UninitializedException(MemoryException): pass

    # <add id="dev_util_internal.Memory">
    # Constructor arguments:
    # <dl>
    # <dt>test</dt>
    # <dd>set to True to not create any Simics objects, optional,
    #     defaults to False</dd>
    # </dl>
    # </add>
    def __init__(self, test=False):
        if not test:
            super(Memory, self).__init__([Memory.MemorySpace])
            self.real_obj = self.obj
            self.obj = simics.SIM_create_object(
                'fake-space',
                'fake_space_proxy%d' % Memory.__next_proxy_id,
                [['target_space', self.real_obj]])
            Memory.__next_proxy_id += 1
        self.clear()

    # <add id="dev_util_internal.Memory.clear">
    # Clear the contents of the memory.
    # </add>
    def clear(self):
        self.mem = []

    # <add id="dev_util_internal.Memory.read">
    # Read bytes from this memory.
    #
    # Arguments:
    # <dl>
    # <dt>addr</dt>
    # <dd>the start address of the range to read</dd>
    # <dt>n</dt>
    # <dd>length in bytes of the range to read</dd>
    # </dl>
    #
    # This method throws an exception if any byte in the read range is empty.
    # </add>
    def read(self, addr, n):
        '''Returns a list of n bytes, starting at addr'''

        if n == 0:
            return []

        for (chunk_start, chunk) in self.mem:
            chunk_size = len(chunk)
            if (chunk_start <= addr < chunk_start + chunk_size
                and addr + n <= chunk_start + chunk_size):
                return chunk[addr - chunk_start : addr + n - chunk_start]
        raise Memory.UninitializedException("read from uninitialised memory: "
                                            "0x%x, %d bytes" % (addr, n))

    # <add id="dev_util_internal.Memory.write">
    # Write bytes to this memory.
    #
    # Arguments:
    # <dl>
    # <dt>addr</dt>
    # <dd>the start address of the range to write</dd>
    # <dt>n</dt>
    # <dd>the bytes to write</dd>
    # </dl>
    #
    # Fills in empty slots in the memory and overwrites already existing data.
    # </add>
    def write(self, addr, bytes):
        '''Writes the data in the bytes tuple to addr'''
        for b in bytes:
            assert isinstance(b, int)
            assert not (b >> 8)
        for (i, (chunk_start, chunk)) in enumerate(self.mem):
            chunk_size = len(chunk)
            if chunk_start <= addr <= chunk_start + chunk_size:
                ofs = addr - chunk_start
                chunk[ofs : ofs + len(bytes)] = bytes
                self._merge_chunks(i)
                return

            if chunk_start > addr:
                break                   # insert new chunk here
        else:
            i = len(self.mem)
        # create new chunk
        self.mem[i : i] = [(addr, list(bytes))]
        self._merge_chunks(i)

    def _merge_chunks(self, index):
        '''Merge a chunk with the following one if they overlap/are adjacent'''
        (chunk_start, chunk) = self.mem[index]
        chunk_end = chunk_start + len(chunk)
        next = index + 1
        while next < len(self.mem):
            (next_start, next_chunk) = self.mem[next]
            if next_start > chunk_end:
                break
            # this chunk subsumed by the one at index
            if chunk_end < next_start + len(next_chunk):
                chunk += next_chunk[chunk_end - next_start :]
            del self.mem[next]

    # <add id="dev_util_internal.Memory.is_range_touched">
    # Return True if any of this memory's slots in the range contain data.
    # </add>
    def is_range_touched(self, start, length):
        def overlaps(s1, l1, s2, l2):
            return not (s1 + l1 <= s2) and not (s2 + l2 <= s1)

        for chunk_start, chunk in self.mem:
            if overlaps(chunk_start, len(chunk), start, length):
                return True
        return False
