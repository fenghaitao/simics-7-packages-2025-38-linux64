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
import dev_util
import pyobj
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

## Receiver for notifications
class notify_completion_receiver(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class notifier_seen(pyobj.SimpleAttribute(False, 'b')):
        """Have we seen a notifier? Reset to False after each use!"""

    class completion_sender(pyobj.Attribute):
        "Object notifying m-compute-complete"
        attrtype = "o|n"

        def getter(self):
            return self.val

        def setter(self, obj):
            simics.SIM_log_info(1, self._up.obj, 0, 
              f"Setting up notification from {obj}")
            self.val = obj
            self.handle = simics.SIM_add_notifier(
                    obj, 
                    simics.SIM_notifier_type("m-compute-complete"), 
                    self._up.obj,
                    self._up.notified, None)

    def notified(self, obj, src, data):
        simics.SIM_log_info(2, self.obj, 0, "Notified!" )
        self.notifier_seen.val = True

# Interrupt signal receiver - used to check that outbound
# signals from the device are indeed being sent
class signal_receiver(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class raise_count(pyobj.SimpleAttribute(0, 'i')):
        """Count number of raise calls to the signal"""

    class lower_count(pyobj.SimpleAttribute(0, 'i')):
        """Count number of lower calls to the signal"""

    class raised(pyobj.SimpleAttribute(0, 'b')):
        """Is the signal currently raised?"""

    class signal(pyobj.Interface):
        """Receive signal calls, remember results."""
        def signal_raise(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Signal raised!" )
            self._up.raised.val = True
            self._up.raise_count.val += 1
        def signal_lower(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Signal lowered!" )
            self._up.raised.val = False
            self._up.lower_count.val += 1

# Create a single clock object 
# That will be used by all sets of test objects created in the below function
clock = simics.SIM_create_object('clock', 'clock', freq_mhz=1000)

# Create the device to tested 
# Plus the stub devices surrounding it
# So that unit testing can be done. 
#   Both the name and class are arguments, to allow a single test case
#   in a single simulation instance to create multiple sets of objects
#   under test.  Instead of creating one separate test for each 
#   variant. 
def create_m_compute(name="compute", cls="m_compute"):
    '''Create a new m_compute object'''

    # Test memory 
    mem = simics.pre_conf_object("memory_"+name,
                                 "sparse-memory")
    mem_space=simics.pre_conf_object("mem_space_"+name,
                                     "memory-space",
                                     map = [[0x0, mem, 0, 0, 0x100000000]])
    stub_done = simics.pre_conf_object("stub_done_"+name,
                                       "signal_receiver")
    compute = simics.pre_conf_object(
        name,
        cls, 
        queue=clock, 
        local_memory=mem_space,
        operation_done=stub_done)
    
    stub_notified = simics.pre_conf_object(
        "stub_notified_"+name,
        "notify_completion_receiver",
        completion_sender=compute)         

    ## Create objects from the pre-objects
    preobjs = [compute, stub_notified, stub_done, mem_space, mem]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert pre-object list to object pointers
    objs=[simics.SIM_get_object(p.name) for p in preobjs]
    
    ## Add in the global clock object and return the list to test
    return objs + [clock]
