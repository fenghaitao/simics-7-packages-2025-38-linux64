# INTEL CONFIDENTIAL

# -*- python -*-

# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# system_id.py - extract selected software visible id numbers

# Does a best effort to extract enough software visible id register
# values to identify a platform without having to run any target code
# on the platform. Currently only supports x86 platforms.

# On x86 systems, the platform identification is a (cpuid processor,
# bridge pci device id, pch pci device id) tuple.  This mimics what a
# bios usually does to check/select what platform it runs on.
# URLs describing ids in ./identify_platform.py

# Note: system_id.py is imported by tcf-agent module

import simics
import cli

def find_parent(obj):
    p = simics.SIM_port_object_parent(obj)
    return find_parent(p) if p else obj

class Sid:
    X86_CPUID_Family_Model = "x86_cpuid_family_model"
    PCI_Device_ID = "pci_vendor_device_id"
    PCI_Address = "pci_address"
    def __init__(self, iid_type, conf_obj, address = None, access_obj = None):
        self.conf_obj = find_parent(conf_obj)
        self.name = self.conf_obj.name
        self.iid_type = iid_type
        if iid_type == Sid.X86_CPUID_Family_Model:
            self.iid = cpuid_family_model_id(conf_obj)
        elif iid_type == Sid.PCI_Device_ID:
            func_nr = address[2]
            if address == (0,0,0):
                v = ioport_read(access_obj, 0, 0, 0, 0)
                self.iid = (v & 0xffff, v >> 16)
            else:
                self.iid = pci_dev_vendor_device_id(conf_obj, func_nr)
        else:
            assert(False)
        self.address = address # type dependent address in surrounding system

    def attr_val(self):
        a = [[self.iid_type, list(self.iid)]]
        if self.address:
            a.append([Sid.PCI_Address, list(self.address)])
        return a

    def sortkey(self):
        return (self.iid_type, self.address, self.iid)

class Pr:
    verbose = False
    warn = False
    werror = False
    @staticmethod
    def info(str):
        if Pr.verbose:
            print(str)
    @staticmethod
    def warning(str):
        if Pr.werror:
            raise cli.CliError(str)
        elif Pr.warn or Pr.verbose:
            print("Warning: %s" % str)

def device_read(dev, addr, size, port = None, func = 0):
    assert(port == None or func == 0)
    # Should we do inquiry? (will that get past device disable?)
    inquiry = False
    m = simics.SIM_create_object("memory-space", "access0", [])
    mi = simics.map_info_t(base = 0, start = 0, length = 256, function = func)
    m.iface.map_demap.map_simple(dev, port, mi)
    try:
        v = m.iface.memory_space.read(None, addr, size, inquiry)
    except simics.SimExc_Memory as e:
        Pr.warning("Cannot access %s addr=0x%x sz=%d: %s"
                   % (dev.name, addr, size, e))
        v = [0xff] * size
    simics.SIM_delete_object(m)
    return v

def pci_device_by_addr_under_prefix(prefix, bus_nr, id_nr, func_nr):
    bdf = (bus_nr << 5 | id_nr << 3 | func_nr)
    found = []
    for bus in simics.SIM_object_iterator_for_interface(["pci_bus"]):
        if not hasattr(bus, "bridge") or not bus.bridge:
            continue
        if bus.name.startswith(prefix):
            offs = 12 if hasattr(bus.iface, 'pci_express') else 10
            for e in getattr(bus, 'pci_devices', []):
                obj = e[2]
                addr = bus.iface.pci_bus.get_bus_address(obj) >> offs
                if obj.name.startswith(prefix) and addr == bdf:
                    found.append(obj)
    return found

def find_x86_cpus():
    found = []
    for cpu in simics.SIM_object_iterator_for_interface(["processor_info_v2"]):
        if (hasattr(cpu.iface.processor_info_v2, "architecture")
            and cpu.iface.processor_info_v2.architecture
            and cpu.iface.processor_info_v2.architecture() == 'x86-64'):
            found.append(cpu)
    return found

def bit(v, s, e):
    return (v >> e) & ((1 << (s - e + 1)) - 1)

def cpuid_family_model_id(cpu):
    cpuid1 = cpu.iface.x86_cpuid_query.cpuid_query(1, 0)
    eax = cpuid1.a
    fam = bit(eax, 11, 8)
    efam = bit(eax, 27, 20)
    if fam in [6, 15]:
        proc_model = (bit(eax, 19, 16) << 4) + bit(eax, 7, 4)
    else:
        proc_model = bit(eax, 7, 4)
    if fam == 15:
        proc_family = efam + fam
    else:
        proc_family = fam
    return (proc_family, proc_model)

def pci_dev_vendor_device_id(pci_dev, func_nr):
    if hasattr(pci_dev.iface, "pci_multi_function_device"):
        f = dict(pci_dev.iface.pci_multi_function_device.supported_functions())
        if func_nr not in f:
            Pr.warning("Unsupported function %d: %s" % (func_nr, pci_dev.name))
            return (0xffff, 0xffff)
        config_name = f[func_nr]
    else:
        config_name = "pci_config"

    # the skybay.mb.gpu.vga class enh-accel-vga-50 does not have config port
    config = "bank.%s" % config_name
    if hasattr(pci_dev, config):
        v = device_read(getattr(pci_dev, config), 0, 4)
    elif hasattr(pci_dev.ports, config_name):
        v = device_read(pci_dev, 0, 4, port = config_name)
    else:
        # 255 is an old Simics convention for pci config space.
        # It is assumed that pci will not use this function.
        v = device_read(pci_dev, 0, 4, func = 255)
    device_id = (v[3] << 8) + v[2]
    vendor_id = (v[1] << 8) + v[0]
    if device_id == 0xffff and vendor_id == 0xffff:
        vendor = "%s_vendor_id" % config_name
        device = "%s_device_id" % config_name
        if (hasattr(pci_dev, vendor) and hasattr(pci_dev, device)):
            # This is simics internal, and attributes are undocumented
            Pr.info("Access failed, using backdoor for vendor/device id: %s"
                   % pci_dev.name)
            return (getattr(pci_dev, vendor), getattr(pci_dev, device))
        Pr.warning("Cannot get vendor/device id: %s"
                   % pci_dev.name)
    return (vendor_id, device_id)

def longest_prefix(objs):
    pfx = objs[0].name
    for c in objs[1:]:
        while not c.name.startswith(pfx):
            s = pfx.rsplit('.',1)
            if len(s) == 1:
                return ''
            pfx = s[0]
    return pfx

def ioport_read(port_space_obj, bus, dev, func, offset):
    # Inquiry write does not work
    inquiry = False
    # https://wiki.osdev.org/PCI
    d = 1 << 31 | (bus & 0xff) << 16 | (dev & 0x1f) << 11 | (func & 0x3) << 8 | offset
    w = [(d >> (i * 8)) & 0xff for i in range(4)]
    orig = port_space_obj.iface.port_space.read(None, 0xcf8, 4, inquiry)
    ex = port_space_obj.iface.port_space.write(None, 0xcf8, tuple(w), inquiry)
    if ex != simics.Sim_PE_No_Exception:
        raise Exception("ioport write failed: %d" % ex)
    v = port_space_obj.iface.port_space.read(None, 0xcfc, 4, inquiry)
    # Try to hide our tracks by writing back original value
    port_space_obj.iface.port_space.write(None, 0xcf8, orig, inquiry)
    return (v[3] << 24) + (v[2] << 16) + (v[1] << 8) + v[0]

def find_ioport(space, addr):
    # Finds object that terminates a port space access to addr.
    # Search is incomplete and may fail more often than necessary.
    if isinstance(space, list):
        Pr.warning("ioport, simics port not supported: %s" % space[0].name)
        return None
    #print("IN %s" % space.name)
    if space.classname == "memory-space":
        sel_obj = None
        cur_prio = 100
        for m in space.map:
            (base, obj, func, offs, length, target, prio) = m[:7]
            if addr >= base and addr + 4 <= base + length and prio < cur_prio:
                sel_obj = obj
                cur_prio = prio
        if sel_obj:
            return find_ioport(sel_obj, addr)
        elif space.default_target:
            return find_ioport(space.default_target[0], addr)
        Pr.warning("ioport, no matching map: %s" % space.name)
        return None
    elif space.classname == "port-space":
        for m in space.map:
            (base, obj, func, offs, length) = m
            if addr >= base and addr + 3 <= base + length - 1:
                if base == offs and length == 4:
                    # space has better iface to read/write
                    if isinstance(obj, list):
                        obj = getattr(obj[0], "port.%s" % obj[1])
                        print("redir to %s" % obj.name)
                    return (space, obj)
        Pr.warning("No matching port-space map: %s" % space.name)
        return None
    Pr.warning("Unknown object class: %s" % space.name)
    return None

def find_system_id(show_all):
    # list of Sid indexed by system name
    system = {}
    # list of Sid not grouped into any system
    outside_systems = []

    # Indexed by (io_port space, io_port) tuple. Contains list of x86 cpus
    x86_host_bridge_io_port = {}
    for cpu in find_x86_cpus():
        r = find_ioport(cpu.port_space, 0xcf8)
        w = find_ioport(cpu.port_space, 0xcfc)
        if r and r == w:
            x86_host_bridge_io_port.setdefault(r, []).append(cpu)
        else:
            outside_systems.append(Sid(Sid.X86_CPUID_Family_Model, cpu))

    for ((iop_space, iop), cpus) in x86_host_bridge_io_port.items():
        name = longest_prefix([iop] + cpus)
        if name in system:
            Pr.warning("Multiple systems by name %s" % name)

        # Root complex a.k.a host bridge.
        # Represented by the object post space object found by discovery
        system[name] = [Sid(Sid.PCI_Device_ID, iop, (0, 0, 0), iop_space)]
        for cpu in cpus:
            system[name].append(Sid(Sid.X86_CPUID_Family_Model, cpu))
        # Before pci bus enumeration, we could get false hits if
        # x:31:0 exists on some other bus
        pch = pci_device_by_addr_under_prefix(name, 0, 31, 0)
        if len(pch) == 1:
            # pch controller
            system[name].append(Sid(Sid.PCI_Device_ID, pch[0], (0, 31, 0)))
        else:
            Pr.warning("Multiple pch controllers")
            for p in pch:
                outside_systems.append(Sid(Sid.PCI_Device_ID, p, (0, 31, 0)))

        # Sort identifiers after id type, address, name
        # so order in json files is predictable.
        system[name].sort(key = lambda x : x.sortkey())

    if show_all:
        for s in outside_systems:
            system[s.name] = [s]
    return system

# This function is called by tcf-agent Simics module.
# For compatibility, keep all arguments optional.
def list_system_id(show_all = False, verbose = False,
                   warning = False, werror = False):
    Pr.verbose = verbose
    Pr.warn = warning
    Pr.werror = werror
    system = find_system_id(show_all)

    # Create a list based structure that can be used as return value
    # from command (and possibly exported to ISD in json format).
    rv = []
    for n in sorted(system.keys()):
        ids = [["@%s" % sid.name, sid.attr_val()] for sid in system[n]]
        rv.append(["@%s" % n, ids])
    return rv
