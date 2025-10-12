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

import simics
import sys
import re
from . import pci_bus_parser

def get_pci_log_group(debugger):
    return 1 << debugger.log_groups.index('pci')

def pci_trace(level, msg):
    debugger = simics.SIM_get_debugger()
    debugger.iface.tcf_trace.trace_info_lvl(get_pci_log_group(debugger), level,
                                            f'PCI: {msg}')

def pci_log_error(msg):
    debugger = simics.SIM_get_debugger()
    simics.SIM_log_error(debugger, get_pci_log_group(debugger), f'PCI: {msg}')

def data_to_value(data):
    val = 0
    for (i, part) in enumerate(data):
        val |= part << (i * 8)
    return val

def pci_device_string(bus, dev, func, offs):
    return f'{bus:02x}/{dev:02x}/{func},0x{offs:x}'

def format_data(data):
    if len(data) <= 8:
        val = f'0x{data_to_value(data):0{len(data)*2}x}'
    else:
        displayed_data = [str(x) for x in data[:7]] + ['..']
        val = '(%s)' % (','.join(displayed_data),)
    return val


def top_obj(obj):
    """Returns the top object given 'obj'"""
    assert obj, "No object provided"
    curr = obj
    while 1:
        up = simics.SIM_object_parent(curr)
        if up is None:
            return curr
        curr = up


class TcfPciException(Exception):
    pass


class TargetPciAccess:
    def __init__(self, cpu):
        self.cpu = cpu
        self.debugger = simics.SIM_get_debugger()
        self.read_using_inquiry = True
        # When set to true: If a read generates an unhandled inquiry exception,
        # the data will be re-read as a non-inquiry read. This enables reading
        # some devices that cannot be read otherwise.
        self.retry_unhandled_inquiry = True
        self.allowed_buses = 4096  # Maximum for PCIEXBAR
        # Maximum bytes to access at once through the interface, memory_space
        # interface supports a maximum of 1024 bytes.
        self.max_access_size = 1024
        # The variable below must be overridden by child class.
        self.memory_space_iface = None
        self.is_pcie = True

    def _log(self, message, level=4):
        pci_trace(level, message)

    def _check_bus_dev_func(self, bus, dev, func):
        if bus < 0 or bus > self.allowed_buses:
            raise TcfPciException(f'Bad bus 0x{bus:x}')
        if dev < 0 or dev > 31:
            raise TcfPciException(f'Bad device 0x{dev:x}')
        if func < 0 or func > 7:
            raise TcfPciException(f'Bad function {func}')

    def _memory_space_read(self, mem_space_iface, addr, size):
        done = False
        inquiry = self.read_using_inquiry
        while not done:
            try:
                data = mem_space_iface.read(None, addr, size, inquiry)
            except simics.SimExc_InquiryUnhandled:
                if not inquiry:
                    err_msg = (f'Got unhandled inquiry read at {addr:x},'
                               ' even though read was not inquiry')
                    pci_log_error(err_msg)
                    raise TcfPciException(err_msg)
                if self.retry_unhandled_inquiry:
                    self._log(f'Failed reading 0x{addr:x}-0x{addr+size:x} as'
                              ' inquiry, retrying as normal read')
                    inquiry = False
                    continue
                raise
            # Other exceptions should be caught by callee.
            done = True
        return data

    def _read_pci_config_space(self, bus, dev, func, offs, size):
        assert self.memory_space_iface
        self._check_pci_config_offset(offs, size)
        data = []
        curr_offs = offs
        remaining_size = size
        access_size = self.max_access_size
        while remaining_size > 0:
            if remaining_size > access_size:
                curr_size = access_size
                remaining_size -= access_size
            else:
                curr_size = remaining_size
                remaining_size = 0

            dev_offs = self._pci_config_space_offset(bus, dev, func, curr_offs)
            pci_read_str = ('read '
                            + pci_device_string(bus, dev, func, curr_offs)
                            + f' (at 0x{dev_offs:x})')
            try:
                curr_data = self._memory_space_read(self.memory_space_iface,
                                                    dev_offs, curr_size)
            except simics.SimExc_General as e:
                curr_data = make_invalid_for_size(curr_size)
                self._log(f'{pci_read_str} failed: {e}', 2)
            else:
                self._log(f'{pci_read_str} -> {format_data(curr_data)}')
            data += curr_data
            curr_offs += curr_size
        return tuple(data)

    def _write_pci_config_space(self, bus, dev, func, offs, data):
        assert self.memory_space_iface
        self._check_pci_config_offset(offs, len(data))
        dev_offs = self._pci_config_space_offset(bus, dev, func, offs)
        access_size = self.max_access_size
        for start_index in range(0, len(data), access_size):
            curr_data = data[start_index:start_index + access_size]
            self._log(f'write {format_data(curr_data)} -> '
                      + pci_device_string(bus, dev, func, offs + start_index)
                      + f' (at 0x{dev_offs + start_index:x})')
            try:
                # Don't write using inquiry, that would enable changing more
                # fields than would be possible on hardware.
                self.memory_space_iface.write(
                    self.cpu, dev_offs + start_index, curr_data, 0)
            except simics.SimExc_General as e:
                raise TcfPciException(
                    f'Failed writing {pci_device_string(bus, dev, func, offs)}'
                    f' (0x{dev_offs + start_index:x}-'
                    f'0x{dev_offs + start_index + len(curr_data) - 1:x}): {e}')

    def _pci_config_space_offset(self, bus, dev, func, offs):
        if self.is_pcie:
            return self._pcie_config_space_offset(bus, dev, func, offs)
        return self._legacy_pci_config_space_offset(bus, dev, func, offs)

    def _legacy_pci_config_space_offset(self, bus, dev, func, offs):
        return (bus << 16) | (dev << 11) | (func << 8) | offs

    def _pcie_config_space_offset(self, bus, dev, func, offs):
        return (bus << 20) | (dev << 15) | (func << 12) | offs

    def _check_pci_config_offset(self, offs, size):
        max_offs = 4096 if self.is_pcie else 256
        if offs < 0 or (offs + size) > max_offs:
            raise TcfPciException(
                f'Bad offset 0x{offs:x}-0x{offs + size - 1:x}')

    def read(self, bus, dev, func, offs, size):
        self._check_bus_dev_func(bus, dev, func)
        return self._read_pci_config_space(bus, dev, func, offs, size)

    def write(self, bus, dev, func, offs, data):
        self._check_bus_dev_func(bus, dev, func)
        self._write_pci_config_space(bus, dev, func, offs, data)


class PciAccessPlatformConf(TargetPciAccess):
    name = 'platform conf'
    def __init__(self, cpu):
        super().__init__(cpu)
        top_comp = cpu.component.top_component
        try:
            platform_conf = top_comp.stc_tools.stc_tools_dev.platform_conf
        except AttributeError:
            raise TcfPciException('No platform_conf available')
        pci_decoder_space = self.__find_pci_conf_decoder(platform_conf)
        try:
            self.memory_space_iface = pci_decoder_space.iface.memory_space
        except AttributeError:
            raise TcfPciException(
                f'memory_space interface missing for {pci_decoder_space.name}')
        self._log(f'Using {self.name} with {pci_decoder_space.name} space')
        self.is_pcie = True

    def __is_cpu_in_socket(self, socket_data):
        for core_data in socket_data.get('cores', {}).values():
            for thread_data in core_data.get('threads', {}).values():
                if self.cpu.name == thread_data.get('name'):
                    return True
        return False

    def __is_cpu_in_socket_hierarchy(self, uncore_name):
        try:
            uncore = simics.SIM_get_object(uncore_name)
        except simics.SimExc_General:
            return False

        def is_parent_or_same(parent, obj):
            if obj is None:
                return False

            if parent == obj:
                return True

            return is_parent_or_same(parent, simics.SIM_object_parent(obj))

        return is_parent_or_same(uncore, self.cpu)

    def __find_socket_for_cpu(self, sockets):
        # First attempt to check if cpu is in hierachy of socket
        for socket_data in sockets.values():
            uncore_name = socket_data.get('uncore', {}).get('name')
            if not uncore_name:
                continue
            if self.__is_cpu_in_socket_hierarchy(uncore_name):
                return socket_data

        for socket_data in sockets.values():
            if self.__is_cpu_in_socket(socket_data):
                return socket_data

        return None

    def __find_pci_conf_decoder(self, platform_conf):
        try:
            sockets = platform_conf['domain']['board']['sockets']
        except KeyError as e:
            raise TcfPciException(f'Failed getting sockets: {e}')
        socket = self.__find_socket_for_cpu(sockets)
        if socket is None:
            raise TcfPciException(f'{self.cpu.name} not found in any socket')
        try:
            decoder_name = socket['uncore']['pci_conf_decoder']
        except KeyError as e:
            raise TcfPciException(f'Failed getting uncore PCI decoder: {e}')
        try:
            decoder_obj = simics.SIM_get_object(decoder_name)
        except simics.SimExc_General as e:
            raise TcfPciException(f'Failed getting object {decoder_name}: {e}')
        return decoder_obj


class PciAccessConfSpace(TargetPciAccess):
    name = 'conf space'
    def __init__(self, cpu):
        super().__init__(cpu)
        (conf_space, is_pcie) = self.__find_conf_space()
        if conf_space is None:
            raise TcfPciException('No conf space found')
        self.memory_space_iface = conf_space.iface.memory_space
        self.is_pcie = is_pcie

    def __is_x86_host_bridge(self, vendor_data, class_data):
        assert len(vendor_data) == 2
        assert len(class_data) == 2
        return vendor_data == (0x86, 0x80) and class_data == (0, 6)

    def __can_find_x86_host_bridge(self, mem_space):
        # Host bridge is either on bus 0 (most platforms) or on bus 0xff (for
        # ICH10). Check for host bridge type in device 0, funciton 0 on these
        # buses.
        buses_to_try = (0, 0xff)
        dev = 0
        func = 0
        vendor_offs = 0
        class_offs = 0xa
        for bus in buses_to_try:
            vendor_addr = self._pci_config_space_offset(bus, dev, func,
                                                        vendor_offs)
            class_addr = self._pci_config_space_offset(bus, dev, func,
                                                       class_offs)
            try:
                vendor_data = self._memory_space_read(
                    mem_space.iface.memory_space, vendor_addr, 2)
            except simics.SimExc_General:
                return False
            try:
                class_data = self._memory_space_read(
                    mem_space.iface.memory_space, class_addr, 2)
            except simics.SimExc_General:
                return False
            if self.__is_x86_host_bridge(vendor_data, class_data):
                return True
        return False

    def __find_conf_space(self):
        top_comp = self.cpu.component.top_component
        pcie_interfaces = ('pcie_map', 'pci_express')
        possible_interfaces_in_prio_order = pcie_interfaces + ('pci_bus',)
        candidates = [
            obj for obj in simics.SIM_object_iterator(top_comp)
            if hasattr(obj, 'conf_space')
            and simics.SIM_c_get_interface(obj.conf_space, 'memory_space')
            and any(simics.SIM_c_get_interface(obj, iface)
                    for iface in possible_interfaces_in_prio_order)
            and self.__can_find_x86_host_bridge(obj.conf_space)
        ]

        if not candidates:
            return (None, False)
        if len(candidates) > 1:
            # Select the ones with the most prioritized interface.
            best_candidates = []
            for iface in possible_interfaces_in_prio_order:
                for candidate in candidates:
                    if hasattr(candidate.iface, iface):
                        best_candidates.append(candidate)
                if best_candidates:
                    candidates = best_candidates
                    break
            assert len(candidates) >= 1
            if len(candidates) > 1:
                candidate_names = [x.name for x in candidates]
                self._log('Found multiple configuration space candidates:'
                          f' {candidate_names}, using first', 1)
        best_candidate = candidates[0]
        is_pcie = False
        for iface in pcie_interfaces:
            if hasattr(best_candidate.iface, iface):
                is_pcie = True
                break
        space_type = 'PCIe' if is_pcie else 'PCI'
        self._log(f'Using {best_candidate.conf_space.name} as {space_type}'
                  ' config space')
        return (best_candidate.conf_space, is_pcie)



class PciAccessHierarchies(TargetPciAccess):
    name = 'topology'
    def __init__(self, cpu):
        super().__init__(cpu)
        self._last_update_cycle = None
        self._root_complexes = None

    def _get_root_complexes(self):
        # Which root complexes to use changes when software configures the PCI
        # devices. Re-read if time has passed.
        if self._last_update_cycle is not None:
            assert self._root_complexes is not None
            return self._root_complexes

        hierarchies = pci_bus_parser.Hierarchy(top_obj(self.cpu))
        roots = hierarchies.find_root_ports()
        main_root = self._find_best_root_0(roots)
        if not main_root:
            raise TcfPciException('Could not find suitable root complex')
        self._root_complexes = {0: main_root}
        self._find_other_roots(roots)
        used_root_comples = ", ".join([f"{bus:02x}:{r.obj.name}" for (bus, r)
                                       in self._root_complexes.items()])
        self._log(f"Used root complexes: {used_root_comples}", 3)
        self._last_update_cycle = self.cpu.cycles
        return self._root_complexes

    def _find_best_root_0(self, roots):
        # Select buses with bus number 0
        candidates = []
        for r in roots:
            if not r.bus_num() == 0:
                continue
            candidates.append(r)
        if not candidates:
            return None

        # Try candidates that have most in common in hiearchy with cpu.
        new_candidates = []
        o = self.cpu
        while not new_candidates:
            o = simics.SIM_object_parent(o)
            if not o:
                break
            for c in candidates:
                if c.obj.name.startswith(o.name):
                    new_candidates.append(c)

        if new_candidates:
            candidates = new_candidates
        if len(candidates) == 1:
            return candidates[0]

        # First prioritize soc0 if in the name, then die0 if in the name.
        # Then priorites indexes 0, first ending with [0] then _0.
        # If there still are multiple candidates then priortize root buses under
        # iop/io names in the hierarchy.
        for match_re in (r'.*soc(\d+)', r'.*die(\d+)',
                         r'.*\[(\d+)\]$', r'.*_(\d+)$',
                         '.*iop', '.*io'):
            new_candidates = []
            matcher = re.compile(match_re)
            for r in candidates:
                root_m = matcher.match(r.obj.name)
                if root_m and ((not root_m.lastindex)
                               or int(root_m.group(1)) == 0):
                    new_candidates.append(r)

            if new_candidates:
                candidates = new_candidates
            if len(candidates) == 1:
                return candidates[0]

        assert candidates, "No candidates"

        # Prioritize newer PCIE classes
        new_candidates = [c for c in candidates
                          if not isinstance(c, pci_bus_parser.LegacyPCIEBus)]
        if new_candidates:
            candidates = new_candidates

        picked = candidates[0]
        if len(candidates) > 1:
            cand_names = [x.obj.name for x in candidates]
            self._log(f'Multiple PCI root candidates: {cand_names}, picking:'
                      f' {picked.obj.name}', 2)
        return picked

    def _find_other_roots(self, roots):
        assert self._root_complexes and 0 in self._root_complexes
        main = self._root_complexes[0]
        candidates = [r for r in roots if r.bus_num() != 0]
        candidates.sort(key=lambda x: x.obj.name)
        new_candidates = []
        # Find objects with the same name, but differently indexed
        for index_re in (r'(.*)(\[)\d+\]$', r'(.*)(_)\d+$'):
            index_matcher = re.compile(index_re)
            m = index_matcher.match(main.obj.name)
            if not m:
                continue
            base = m.group(1)
            suffix_type = m.group(2)
            if suffix_type == '_':
                match_re = fr'{base}_(\d+)$'
            else:
                match_re = fr'{base}\[(\d+)\]$'
            matcher = re.compile(match_re)
            cand = {}  # {index: root} to allow sorting
            for r in candidates:
                m = matcher.match(r.obj.name)
                if m:
                    i = int(m.group(1))
                    cand[i] = r
            # To get index order even if index > 9
            for i in sorted(cand):
                new_candidates.append(cand[i])
            break

        if not new_candidates:
            # Select candidates from the same object hierarchy:
            o = main.obj
            while not new_candidates:
                o = simics.SIM_object_parent(o)
                if not o:
                    break
                for r in candidates:
                    if r.obj.name.startswith(o.name):
                        new_candidates.append(r)

        if new_candidates:
            candidates = new_candidates

        for c in candidates:
            if c.bus_num() not in self._root_complexes:
                self._root_complexes[c.bus_num()] = c

    def _find_bus_to_use(self, bus_nr):
        root_complexes = self._get_root_complexes()
        # Find matching bus number or the existing one prior to the wanted bus.
        while bus_nr not in root_complexes:
            bus_nr -= 1
            assert bus_nr >= 0, "Root zero must exist"
        return root_complexes[bus_nr]

    def read(self, bus_nr, dev_nr, func_nr, offs, size):
        bus = self._find_bus_to_use(bus_nr)
        self._log(f'Topology read {bus_nr:02x}:{dev_nr:02x}.{func_nr:02x},'
                  f'0x{offs:x} - {bus.obj.name}')
        virt_bus = bus_nr - bus.bus_num()
        self.memory_space_iface = bus.conf_space().iface.memory_space
        return self._read_pci_config_space(virt_bus, dev_nr, func_nr, offs,
                                           size)

    def write(self, bus_nr, dev_nr, func_nr, offs, data):
        bus = self._find_bus_to_use(bus_nr)
        self._log(f'Topology write {bus_nr:02x}:{dev_nr:02x}.{func_nr:02x},'
                  f'0x{offs:x} - {bus.obj.name}')
        virt_bus = bus_nr - bus.bus_num()
        self.memory_space_iface = bus.conf_space().iface.memory_space
        self._write_pci_config_space(virt_bus, dev_nr, func_nr, offs, data)


class TcfPciAccess:
    def __init__(self, cpu):
        self.access = None
        # Access type classes to try out in priority order.
        for access_class in (PciAccessPlatformConf,
                             PciAccessConfSpace,
                             PciAccessHierarchies):
            if (enforced_access_type
                and access_class.name != enforced_access_type):
                continue
            try:
                self.access = access_class(cpu)
            except TcfPciException as e:
                self._log(f'{access_class.name} access failed: {e}')
                continue
            return

        raise TcfPciException(
            f'Could not find any access method for {cpu.name}')

    def _log(self, message):
        pci_trace(4, message)

    def read_pci_data(self, bus, dev, func, offs, size):
        return self.access.read(bus, dev, func, offs, size)

    def write_pci_data(self, bus, dev, func, offs, data):
        self.access.write(bus, dev, func, offs, data)


def make_invalid_for_size(size):
    return tuple([0xff] * size)

cached_pci_access_object = {} # {cpu: TcfPciAccess}

def get_pci_access_object(cpu):
    access = cached_pci_access_object.get(cpu)
    if access is None:
        access = TcfPciAccess(cpu)
        cached_pci_access_object[cpu] = access
    return access

def pci_read(cpu, bus, dev, func, offs, size):
    try:
        access_obj = get_pci_access_object(cpu)
        data = access_obj.read_pci_data(bus, dev, func, offs, size)
    except TcfPciException as e:
        pci_trace(1, f'read failed for {bus:02x}/{dev:02x}/{func},'
                  f'0x{offs:x}-0x{offs + size - 1:x}: {e}')
        data = make_invalid_for_size(size)
    assert isinstance(data, tuple), f'Bad data type: {type(data)}'
    return data

def pci_write(cpu, bus, dev, func, offs, data):
    try:
        access_obj = get_pci_access_object(cpu)
        access_obj.write_pci_data(bus, dev, func, offs, data)
    except TcfPciException as e:
        pci_trace(1, f'write failed for {bus:02x}/{dev:02x}/{func},'
                  f'0x{offs:x}-0x{offs + len(data) - 1:x}: {e}')
        return str(e)
    return None

def enforce_access_type(access_type):
    """For testing a specific access type, should match the "name" field of the
    access type class"""
    global enforced_access_type
    enforced_access_type = access_type

enforced_access_type = None
