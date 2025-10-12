# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# This parses PCIe hierarchies in a similar way as the list-pcie-hierarchies
# command.

import simics

class PCIEBusError(Exception):
    pass


def is_pci_device(obj):
    return hasattr(obj.iface, "pcie_device") or hasattr(obj.iface, "pci_device")


def find_parent_pci_device(obj):
    curr_obj = obj
    while curr_obj:
        if is_pci_device(curr_obj):
            return curr_obj
        curr_obj = simics.SIM_object_parent(curr_obj)
    return None

def attr_object(attr):
    if isinstance(attr, simics.conf_object_t):
        return attr
    elif (isinstance(attr, list) and len(attr) == 2
          and isinstance(attr[0], simics.conf_object_t)
          and isinstance(attr[1], str)):
        if not hasattr(attr[0], "port"):
            return None
        dev = getattr(attr[0].port, attr[1], None)
        if dev:
            return dev
    return None

class Bus:
    def __init__(self, obj):
        self.obj = obj
        self.legacy = False

    def bus_num(self):
        raise NotImplementedError

    def conf_space(self):
        return getattr(self.obj, "conf_space", None)

    def get_upstream_target(self):
        raise NotImplementedError

    def get_downstream_targets(self):
        return []


class DownstreamPort(Bus):
    def __init__(self, obj):
        super().__init__(obj)
        self._parse_upstream_target()  # Must be done before downstream
        self._parse_downstream_targets()

    def bus_num(self):
        return self.obj.sec_bus_num

    def _parse_upstream_target(self):
        self._upstream_target = getattr(self.obj, "upstream_target", None)

    def get_upstream_target(self):
        return self._upstream_target

    def _parse_downstream_targets(self):
        self._downstream_targets = []
        devs = self.obj.devices
        for d in devs:
            if isinstance(d, list):
                if d[-1] == self._upstream_target:
                    continue
                self._downstream_targets.append(d[-1])
            else:
                self._downstream_targets.append(d)

        for (_, obj) in self.obj.functions:
            parent = find_parent_pci_device(obj)
            if (parent and parent not in devs
                and parent != self.obj.upstream_target):
                self._downstream_targets.append(parent)


    def get_downstream_targets(self):
        return self._downstream_targets

    def has_functions(self):
        return len(self.obj.functions) > 0


class DownstreamPortLegacy(DownstreamPort):
    pass


class LegacyPCIEBus(Bus):
    def __init__(self, obj):
        super().__init__(obj)
        self._parse_upstream_target()  # Must be done before downstream
        self._parse_downstream_targets()
        self.legacy = True

    def bus_num(self):
        return self.obj.bus_number

    def has_functions(self):
        return len(self.obj.pci_devices) > 0

    def _parse_upstream_target(self):
        target = attr_object(getattr(self.obj, "upstream_target", None))
        if not target:
            target = getattr(self.obj, "memory_space", None)
        self._upstream_target = target

    def get_upstream_target(self):
        return self._upstream_target

    def _parse_downstream_targets(self):
        self._downstream_targets = []
        for d in self.obj.pci_devices:
            if attr_object(d[2]) == self._upstream_target:
                continue
            self._downstream_targets.append(d[2])

    def get_downstream_targets(self):
        return self._downstream_targets

class Hierarchy:
    def __init__(self, top_obj):
        self.max_depth = 15
        self._top_obj = top_obj
        self._parse_buses()

    def _parse_buses(self):
        self.buses = []
        for obj in simics.SIM_object_iterator(self._top_obj):
            if obj.classname == "pcie-downstream-port":
                self.buses.append(DownstreamPort(obj))
            elif obj.classname == "pcie-downstream-port-legacy":
                self.buses.append(DownstreamPortLegacy(obj))
            elif obj.classname == "pcie-bus":
                self.buses.append(LegacyPCIEBus(obj))

    def find_root_ports(self):
        downstream_targets = set([])
        upstream_targets = set([])
        for bus in self.buses:
            downstream_targets |= set(bus.get_downstream_targets())
            up_target = bus.get_upstream_target()
            if up_target:
                upstream_targets.add(bus)
            if bus.legacy and bus.has_functions():
                upstream_targets.add(bus)
        roots = []
        for bus in upstream_targets:
            if (bus.get_upstream_target() not in downstream_targets
                and bus.has_functions()):
                roots.append(bus)

        # Store in self for debugging purpose:
        self.upstream_targets = upstream_targets
        self.downstream_targets = downstream_targets
        self.roots = roots

        return roots
