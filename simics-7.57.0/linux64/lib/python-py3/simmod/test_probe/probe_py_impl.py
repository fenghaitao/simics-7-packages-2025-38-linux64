# © 2023 Intel Corporation
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


# Convert a sequence of list and tuples to only lists.
def listify(seq):
    if not isinstance(seq, list) and not isinstance(seq, tuple):
        return seq
    ret = []
    for s in seq:
        ret.append(listify(s))
    return ret


class py_test_probe:
    cls = confclass("py_test_probe", pseudo=True,
                    short_doc = "probe implemented in Python",
                    doc = "Example of an object written in Python implementing the probe interface.")
    cls.attr.incr("n", default=None, doc="Increment the probe value.")

    @cls.finalize
    def finalize_instance(self):
        self.val = 0

    @cls.attr.incr.setter
    def incr(self, _):
        self.val += 1

    @cls.iface.probe
    def value(self):
        return self.val

    @cls.iface.probe
    def properties(self):
        return listify([(Probe_Key_Kind, "test.py.probe")])


class py_array_test_probe:
    cls = confclass("py_array_test_probe", pseudo=True,
                    short_doc = "probe array implemented in Python",
                    doc = "Example of an object written in Python implementing the probe array interface.")
    cls.attr.incr("n", default=None, doc="Increment the probe array values.")
    cls.attr.size("i", doc="Size of the probe array.")

    @cls.finalize
    def finalize_instance(self):
        self.val = [x for x in range(self.size)]

    @cls.attr.incr.setter
    def incr(self, _):
        self.val = [x + 1 for x in self.val]

    @cls.iface.probe_array
    def num_indices(self):
        return self.size

    @cls.iface.probe_array
    def value(self, idx):
        return self.val[idx]

    @cls.iface.probe_array
    def all_values(self):
        return self.val.copy()

    @cls.iface.probe_array
    def properties(self, idx):
        return listify(
            [(Probe_Key_Kind, f"test.py_array.probe{idx}"),])
