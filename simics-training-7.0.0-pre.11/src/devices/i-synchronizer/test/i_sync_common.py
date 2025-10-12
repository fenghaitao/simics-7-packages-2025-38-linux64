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


import simics
import pyobj

## Receiver for notifications
class notify_receiver(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  

    class notifier_seen(pyobj.SimpleAttribute(False, 'b')):
        """Have we seen a notifier? Reset to False after each use!"""

    class notification(pyobj.Attribute):
        "Object and notifier to listen to"
        attrtype = "[os]"

        def getter(self):
            return self.val

        def setter(self, val):
            # Test utility, no input value checking done
            simics.SIM_log_info(1, self._up.obj, 0, 
            f"Setting up notification from {val}")
            [obj,notifier] = val
            self.val = [obj,notifier]
            self.handle = simics.SIM_add_notifier(
                    obj, 
                    simics.SIM_notifier_type(notifier), 
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

## Create the test system
## - Set the e2l parameter to True to also get a 
##   signal-bus and connected e2l devices
def create_test_subsystem(name="t",with_e2l=False):
    # Number of subsystem
    num_sub_systems = 4

    n = simics.pre_conf_object(name, 'namespace')
    
    # Clocks
    n.clock = simics.pre_conf_object('clock', freq_mhz = 1000)

    # Device
    n.dev = simics.pre_conf_object('i_synchronizer', queue=n.clock,
                                   num_sub_systems = num_sub_systems,
                                   irq_delay = 100)
    
    # Memory map, put the device in N places to mimic "real" usage
    mmap = [[0x1000 + 0x1000*i, n.dev.bank.regs,  0,    0, 0x10] 
             for i in range(num_sub_systems) ]
    n.memmap = simics.pre_conf_object('memory-space', 
                                        queue=n.clock,
                                        map=mmap)

    # Receiver for the IRQs
    if with_e2l:
        # Full subsystem with N devices connected to the 
        # signal bus, and a signal receiver to each e2l
        l = []
        n.e2l = simics.pre_conf_object('index-map')
        for i in range(num_sub_systems):            
            n.e2l[i] = simics.pre_conf_object("i_synchronizer_e2l",
                                              queue=n.clock)
            n.e2l[i].irq_rec = simics.pre_conf_object("signal_receiver",
                                            queue=n.clock)
            n.e2l[i].attr.level_out = n.e2l[i].irq_rec
            l.append( n.e2l[i].port.edge_in )
            n.memmap.attr.map.append( [0x10000 + 0x1000*i, n.e2l[i].bank.regs, 0, 0, 0x10] )
        n.signal_bus = simics.pre_conf_object("signal-bus",
                                              queue=n.clock,
                                              targets = l)
        n.dev.attr.irq = n.signal_bus        
    else:
        # IRQ receiver - for simple tests        
        n.irq_rec = simics.pre_conf_object("signal_receiver",
                                            queue=n.clock)
        n.dev.attr.irq = n.irq_rec

    # Notifier receiver
    n.notifier_rec = simics.pre_conf_object(
        "notify_receiver",
        queue=n.clock,
        notification=[n.dev,"i-synchronizer-release"])         

    # Create all the objects
    simics.SIM_add_configuration([n],None)
    
    return simics.SIM_get_object(n.name)

