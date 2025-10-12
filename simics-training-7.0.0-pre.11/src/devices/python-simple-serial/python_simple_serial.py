# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


##---------------------------------------------------------------------------------- 
##
## Example simple Python device for Model Builder Training
##
## Implements a trivial serial device:
## - One send register, sends character immediately 
## - One receive register holding the last seen character
##

import pyobj
import simics

class python_simple_serial(pyobj.ConfObject):
    """Simple serial device implemented in Python, 
       for use in model builder training.  
    """

    _class_desc = "simple serial device (in Python)"

    def _initialize(self):
        super()._initialize()
        # cache the serial_device interface to call
        self.serial_output_iface_cache = None

    def _status(self):
        return [("Registers", [("Receive", self.receive_register.val),
                               ("Transmit", self.transmit_register.val)])]

    ##
    ## Register values
    ## 
    class receive_register(pyobj.SimpleAttribute(0, 'i')):
        """The <i>receive</i> register, last character received."""

    class transmit_register(pyobj.SimpleAttribute(0, 'i')):
        """The <i>transmit</i> register, last character sent."""

    ## A simple event just to populate the event queues to show what
    ## happens at deletion
    
    class some_event(pyobj.Event):
        """An example event for training."""
        def callback(self, data):
            pass

    ##
    ## Attribute for serial console to connect to
    ## -- Skip supporting old-style ports, expect target
    ##    to be an object or a port object ("o")
    class console(pyobj.Attribute):
        """The console to send output characters to, 
           has to implement the <i>serial_device</i> interface."""
        attrtype = "o|n"
        # Initialize
        def _initialize(self):
            self.val = None
            # Cache the serial_device interface of the object
            self._up.serial_output_iface_cache = None
        # Get - just return the current value
        def getter(self):
            return self.val
        # Set - check that the target does have a serial_device interface
        def setter(self, console):
            if console == None:
                self.val = None
                self._up.serial_output_iface_cache = None
                return simics.Sim_Set_Ok
            # Check that the given object has the required interface
            iface = simics.SIM_get_interface(console, "serial_device")
            if iface == None:
                # Do not change the stored values in the attribute
                # Bad assignments should not have side-effects
                return simics.Sim_Set_Interface_Not_Found
            # Store the values
            self.val = console
            self._up.serial_output_iface_cache = iface
            
    ##
    ## Interface for inbound serial operations 
    ##  
    class serial_device(pyobj.Interface):
        def write(self, value):
            ## Incoming byte - store
            simics.SIM_log_info(2, self._up.obj, 0,
                                "Incoming character: '0x%x'" % (value))
            self._up.receive_register.val = value
            return 1  ## tell the sender the write succeeded
        def receive_ready(self):
            ## Called by the console we are connected to
            ## in case it is once again ready to receive
            ## after a write operation returned 0.
            ##
            ## This simple device just ignores such cases.
            simics.SIM_log_unimpl(1, self._up.obj, 0,
                                  "receive_ready called, ignoring")
            
    ##
    ## Interface for inbound memory operations
    ##
    ##   Offset 0x00 - transmit, single byte
    ##          0x04 - receive, single byte
    class io_memory(pyobj.Interface):
        def operation(self, mop, info):
            # offset within our device
            offset = (simics.SIM_get_mem_op_physical_address(mop)
                      + info.start - info.base)
            # Only accept byte accesses
            if simics.SIM_get_mem_op_size(mop) != 1:
                # make sure a broken read still returns a value
                if simics.SIM_mem_op_is_read(mop):
                    simics.SIM_set_mem_op_value_le(mop, 0)
                # Log error 
                simics.SIM_log_error(self._up.obj, 0, f"Wrong-size access to offset {offset:#04x}")
                # Still return that the call succeeded 
                return simics.Sim_PE_No_Exception
            # Which offset was hit?
            if offset == 0x00:
                # transmit register @0x00 is read-write and sends a character out
                #
                if simics.SIM_mem_op_is_read(mop):
                    ### READ case
                    #  No special handling of inquiry needed
                    val = self._up.transmit_register.val
                    simics.SIM_set_mem_op_value_le(mop, val)
                    simics.SIM_log_info(2, self._up.obj, 0,
                                        f"Reading from transmit register ({val:#04x})")                                        
                else:
                    ### WRITE case
                    val = simics.SIM_get_mem_op_value_le(mop)
                    ## Set the value, for inquiry and non-inquiry
                    self._up.transmit_register.val = val
                    simics.SIM_log_info(2, self._up.obj, 0,
                                        f"Write to transmit register ({val:#04x})")
                    # If inquiry access, leave it here, as it should not do the side-effect
                    if not simics.SIM_get_mem_op_inquiry(mop):  
                        # Send character
                        if self._up.serial_output_iface_cache != None:
                            self._up.some_event.post(self._up.obj.queue, None, cycles = 1000)
                            simics.SIM_log_info(2, self._up.obj, 0,
                                                f"Sending character to console ({val:#04x})")
                            self._up.serial_output_iface_cache.write(val)
            elif offset == 0x04:
                # register @0x04 reads out the last character received
                # writing it changes the stored value, just because
                if simics.SIM_mem_op_is_write(mop):
                    ### WRITE case
                    # this is a little endian device
                    val = simics.SIM_get_mem_op_value_le(mop)
                    # Log the access, and then store the value
                    # This works equally for both regular and inquiry accesses
                    # since this register treats both in the same way
                    simics.SIM_log_info(2, self._up.obj, 0,
                                        f"Writing to receive register ({val:#04x})")
                    self._up.receive_register.val = val
                else:
                    ### READ case
                    #  No special handling of inquiry needed
                    val = self._up.receive_register.val
                    simics.SIM_set_mem_op_value_le(mop, val)
                    simics.SIM_log_info(2, self._up.obj, 0,
                                        f"Reading from receive register ({val:#04x})")                    
            else:
                ### This is not an offset that the device handles
                if simics.SIM_get_mem_op_inquiry(mop):
                    return simics.Sim_PE_Inquiry_Unhandled
                if simics.SIM_mem_op_is_read(mop):
                    # read - just return zero
                    simics.SIM_set_mem_op_value_le(mop, 0)
                # Real read or write, log an error (inquiry should not error)
                simics.SIM_log_error(self._up.obj, 0, 
                                     f"Access to non-existing offset ({offset:#04x}).")
            return simics.Sim_PE_No_Exception
