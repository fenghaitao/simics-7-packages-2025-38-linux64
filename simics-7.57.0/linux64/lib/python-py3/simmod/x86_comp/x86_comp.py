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


from . import x86_motherboard
from . import x86_northbridge
from . import x86_southbridge
from comp import *

class x86_chassis(StandardComponent):
    """Standard x86 chassis."""
    _class_desc = 'standard x86 chassis'
    _do_not_init = object()

    class basename(StandardComponent.basename):
        val = "chassis"

    def get_processors(self):
        ret = []
        sub_cmps = [x for x in self.obj.iface.component.get_slot_objects() if (
                isinstance(x, simics.conf_object_t) and hasattr(x.iface, 'component'))]
        for c in sub_cmps:
            if hasattr(c, 'cpu_list'):
                ret += c.cpu_list
        return list(set(ret))

    def get_clock(self):
        # If there's a sub-component with component_queue, then we try
        # to use that otherwise we pick the first processor as clock.
        sub_cmps = [x for x in self.obj.iface.component.get_slot_objects() if (
                isinstance(x, simics.conf_object_t) and hasattr(x.iface, 'component'))]
        clocks = []
        for c in sub_cmps:
            if hasattr(c, 'component_queue'):
                q = c.component_queue
                if q:
                    clocks.append(q)
        if len(clocks) > 0:
            return clocks[0]

        cpus = self.get_processors()
        return self.get_processors()[0] if cpus else None

    class cpu_list(StandardComponent.cpu_list):
        def getter(self):
            return self._up.get_processors()

    class component_queue(StandardComponent.component_queue):
        def getter(self):
            return self._up.get_clock()

    class system_icon(StandardComponent.system_icon):
        val = "intel-logo.png"

    class top_level(StandardComponent.top_level):
        def _initialize(self):
            self.val = True
