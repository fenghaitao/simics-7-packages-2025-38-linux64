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

from simics import *
from . import probes
from .common import listify
from .probe_cache import cached_probe_read

class CellIoProbes:
    cls = confclass("probe_cell_io_access", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for cell io-probes.")

    cls.attr.cell_owner("o", default = None, doc = "The cell object.")

    @cached_probe_read
    def cached_all_cell_io_accesses(self):
        l = []
        for p in probes.get_cell_probes(self.cell_owner, "dev.io_access_count"):
            v = p.value()
            if v:
                l.append((p.prop.owner_obj, v))
        return l

    class cell_io_probe:
        __slots__ = ('kind', 'display', 'probe_type', 'width', 'fmt', 'desc')

        def __init__(self, kind, display, probe_type, width, desc):
            self.kind = kind
            self.display = display
            self.probe_type = probe_type
            self.width = width
            self.desc = desc

        @staticmethod
        def value(io_access_list):
            assert 0  # Should be overridden

    class cell_io_access_count(cell_io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            return sum([v for _,v in io_access_list])

    class cell_io_access_class_histogram(cell_io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            h = {}
            for (o, v) in io_access_list:
                cls_str = f"<{o.classname}>"
                h.setdefault(cls_str, 0)
                h[cls_str] += v

            return listify(list(h.items()))

    class cell_io_access_object_histogram(cell_io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            return [[o.name, v] for (o, v) in io_access_list]

    idx2probe = {
        0: cell_io_access_count(
            "cell.io_access_count", "IO accesses", "int", 12,
            "Total memory or port accesses towards devices in a cell."),

        1: cell_io_access_class_histogram(
            "cell.io_access_class_histogram", "IO Access Class Histogram",
            "histogram", 50,
            "The classes which have most io-accesses from CPUs in a cell."),

        2: cell_io_access_object_histogram(
            "cell.io_access_object_histogram", "IO Access Object Histogram",
            "histogram", 60,
            "The objects which have most io-accesses from CPUs in a cell."),
    }

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.idx2probe)

    @cls.iface.probe_index
    def value(self, idx):
        io_accesses = self.cached_all_cell_io_accesses()
        p = self.idx2probe[idx]
        return p.value(io_accesses)

    @cls.iface.probe_index
    def properties(self, idx):
        p = self.idx2probe[idx]
        prop = [
            (Probe_Key_Kind, p.kind),
            (Probe_Key_Display_Name, p.display),
            (Probe_Key_Description, p.desc),
            (Probe_Key_Type, p.probe_type),
            (Probe_Key_Categories, ["device", "io"]),
            (Probe_Key_Width, p.width),
            (Probe_Key_Owner_Object, self.cell_owner)]
        return listify(prop)
