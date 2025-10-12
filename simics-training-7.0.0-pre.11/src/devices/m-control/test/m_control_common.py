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

## Test globals
num_compute_units = 6

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
            simics.SIM_log_info(1, self._up.obj, 0, f"Setting up notification from {obj}" )
            self.val = obj
            self.handle = simics.SIM_add_notifier(
                    obj, 
                    simics.SIM_notifier_type("m-compute-complete"), 
                    self._up.obj,
                    self._up.notified, None)

    def notified(self, obj, src, data):
        simics.SIM_log_info(2, self.obj, 0, "Notified!" )
        self.notifier_seen.val = True

# Checking for signal 
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

# Checking for control unit signals
class compute_control_receiver(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class start_count(pyobj.SimpleAttribute(0, 'i')):
        """Count number of start calls to this stub compute unit"""

    class clear_count(pyobj.SimpleAttribute(0, 'i')):
        """Count number of clear calls to this stub compute unit"""

    class m_compute_control(pyobj.Interface):
        def start_operation(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Operation start called!" )
            self._up.start_count.val += 1
        def clear_done(self):
            simics.SIM_log_info(2, self._up.obj, 0, "Clear done called!" )
            self._up.clear_count.val +=1


# Extend this function if your device requires any additional attributes to be
# set. It is often sensible to make additional arguments to this function
# optional, and let the function create mock objects if needed.
#
# Takes the name of the class of the object to create as an argument, 
# to allow it to be used to test both the standard and the stall variants.
#
# It creates the objects in a namespace to make it possible to create
# multiple sets of objects in a single test.  The info/status test 
# takes advantage of this and subjects both classes to the same test 
# in one go. 

def create_m_control(namespace="test", classname="m_control"):
    '''Create a new m_control object with test scaffolding'''

    ## Add pre-conf objects  
    n = simics.pre_conf_object(namespace, 'namespace')

    ## Always good to have a clock so that time can progress
    n.clock = simics.pre_conf_object('clock', freq_mhz=1000)

    n.stub_done = simics.pre_conf_object("signal_receiver")

    ## Memory spaces required by the device object
    n.local_memory = simics.pre_conf_object('memory-space')
    n.register_memory = simics.pre_conf_object('memory-space')

    ## Stubs for the compute units to control
    n.stub_compute = simics.pre_conf_object('index-map')
    stub_compute_units = []
    for i in range (num_compute_units):
        n.stub_compute[i] =  simics.pre_conf_object("compute_control_receiver") 
        stub_compute_units.append(n.stub_compute[i])

    ## Main device object to test
    n.dev = simics.pre_conf_object(classname, 
                                    connected_compute_unit_count=num_compute_units,
                                    local_memory=n.local_memory,
                                    register_memory=n.register_memory,
                                    operation_done=n.stub_done,
                                    compute_unit_control = stub_compute_units,
                                    queue=n.clock)
    
    ## Notifier receiver to test notifications 
    n.stub_notified = simics.pre_conf_object("notify_completion_receiver",
                                             completion_sender=n.dev)

    ## Add the control device to the register memory map to support 
    ## some tests.
    n.register_memory.attr.map=[]
    n.register_memory.attr.map.append([0x1000, n.dev.bank.ctrl, 0, 0, 0x1000])

    ## Create all the objects
    simics.SIM_add_configuration([n], None)

    # Grab the actual objects that the test code needs to operate on 
    cobj = simics.SIM_get_object(n.dev.name)
    sn_obj = simics.SIM_get_object(n.stub_notified.name)
    clockobj = simics.SIM_get_object(n.clock.name)
    sd_obj = simics.SIM_get_object(n.stub_done.name)
    scu_objs = [simics.SIM_get_object(o.name) for o in stub_compute_units]
    lm_obj = simics.SIM_get_object(n.local_memory.name)
    rm_obj = simics.SIM_get_object(n.register_memory.name)    

    return [cobj, clockobj, sd_obj, sn_obj, scu_objs, lm_obj, rm_obj]
