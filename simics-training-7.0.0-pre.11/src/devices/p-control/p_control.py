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

## 
## Python-language Simics module
##
## The p-control class handles mouse inputs from a graphics console
## and converts it into operations on a set of controls 
##

import pyobj

# Tie code to specific API, simplifying upgrade to new major version
import simics_6_api as simics


class p_control(pyobj.ConfObject):
    """Controller for a custom panel in a graphics console.  
    Implements the functionality of receiving mouse clicks from
    the graphics console and converting it to actions on the buttons
    and toggles shown in the panel."""
    _class_desc = "panel controller"
    _do_not_init = object()
    
    def _initialize(self):
        super()._initialize()
        # Cached information about the display
        self.drawing_intf_cache = None
        self.display_width = 0
        self.display_height = 0
        # Cached information about the controls
        self.control_ifs = []

    def _finalize(self):
        # All attributes in all objects are set, we can now
        # correctly read the display size
        self.display_width  = self.drawing_intf_cache.get_width()
        self.display_height = self.drawing_intf_cache.get_height()    
        simics.SIM_log_info(3, self.obj, 0,
                            f"Read display properties {self.display_width}, {self.display_height}")
        # Button state init
        self.left_button_down = False
        # Tracking active control
        self.active_control = None
        # Draw all buttons - no, cannot do that
        # since this is called in an undefined
        # order with respect to other objects.
        # And thus over-drawing will not work 
        # reliably.  

    def _info(self):
        return [("Associated objects", [
                  ("Display:", self.display.val),
                  ("Controls:", self.controls.val)])]

    def _status(self):
        return []

    #
    # User-interface controls/controls checking
    # - Return None in case nothing was hit
    # - Otherwise, return the button hit
    #   Which is a tuple (control object, interface to it)
    def find_control_hit(self, x, y):
        # iterates over cached interface references
        for (c,i) in self.control_ifs:
            if i.hit(x,y):
                return (c,i)  
        return None
 
    #
    # Button management logic
    #
    def button_down(self,px_x,px_y):
        simics.SIM_log_info(2, self.obj, 0,
                            f"Button press down at ({px_x},{px_y})")
        self.active_control = self.find_control_hit(px_x,px_y)
        if(self.active_control!=None):
            (c,i) = self.active_control
            i.start_press()
        
    def button_still_down(self,px_x,px_y):
        simics.SIM_log_info(3, self.obj, 0,
                            f"Button still down at ({px_x},{px_y})")
        ## Only check where we are in case there is an active control
        if(self.active_control!=None):
            (c,i) = self.active_control
            if(i.hit(px_x,px_y)):
                # Inside the active control 
                # Up to the control optimize redraws if it wants to 
                i.down_in()
            else:
                # Outside
                i.down_outside()

    def button_release(self,px_x,px_y):
        simics.SIM_log_info(2, self.obj, 0,
                            f"Button released at ({px_x},{px_y})")
        ## Only check where we are in case there is an active control
        if(self.active_control!=None):
            (c,i) = self.active_control
            if(i.hit(px_x,px_y)):
                # Inside the active control 
                i.end_press()
            else:
                # Outside
                i.cancel_press()


    #
    # The set of controls that this controller is using. A list of objects. 
    # 
    class controls(pyobj.Attribute):
        """The list of controls this controller uses.  Each button must
        implement the p-control-button interface."""
        attrtype = "[o*]"
        def _initialize(self):
            self.val = []
            # Cache the serial_device interface of the object
            self._up.control_ifs = []
        # Get - just return the current value
        def getter(self):
            return self.val
        # Set - evaluate the list 
        def setter(self,controls):
            # Iterate over the list
            # Cache interfaces
            ifs = []
            for b in controls:
                iface = simics.SIM_get_interface(b,"p_control_button")
                if iface == None:
                    # Error
                    simics.SIM_log_error(self._up.obj, 0,
                                        f"Object: '{b}' does not implement p_control_button")
                    return simics.Sim_Set_Interface_Not_Found
                ## This button was OK. 
                ## Remember both the interface and the button, for debug 
                ifs.append((b,iface))
            # Update attribute value and the cache
            self.val = controls
            self._up.control_ifs = ifs
            return simics.Sim_Set_Ok
    
    #
    # The p-display this controller is working with
    # - Really only used to get a consistent idea for the size of the
    #   display.  Assumes the display size does not change during the 
    #   execution of the system.  Seems like a safe assumption. 
    # 
    class display(pyobj.Attribute):
        """The panel display object used together with this controller."""
        attrtype = "o|n"
        # Initialize
        def _initialize(self):
            self.val = None
            # Cache the serial_device interface of the object
            self._up.drawing_intf_cache = None
            self._up.display_width = 0
            self._up.display_height = 0
        # Get - just return the current value
        def getter(self):
            return self.val
        # Set - check that the target does have drawing interface
        #       so that it is the right kind of object
        def setter(self,display):
            if display == None:
                self.val = None
                self._up.drawing_intf_cache = None
                self._up.display_width = 0
                self._up.display_height = 0
                return simics.Sim_Set_Ok
            # Check that the given object has the required interface
            iface = simics.SIM_get_interface(display,"p_display_draw")
            if iface == None:
                # Do not change the stored value, do not change
                # the cached values. 
                # Bad assignments should not have side-effects
                return simics.Sim_Set_Interface_Not_Found
            # Store the object reference
            self.val = display
            # Cached values
            self._up.drawing_intf_cache = iface
            return simics.Sim_Set_Ok

    # 
    # "pointer" port implements the abs_pointer interface. Called
    # from the graphics console when mouse activity is seen in the 
    # console.  Includes both plain mouse moves, as well as button
    # presses.
    #
    class pointer(pyobj.PortObject):
        class abs_pointer(pyobj.Interface):
            def set_state(self, s):
                ## Get button state from the console
                b = s.buttons
                ## Convert the coordinates to pixels
                px_x = int((s.x / 0xffff) * self._up._up.display_width)
                px_y = int((s.y / 0xffff) * self._up._up.display_height)
                #z = s.z
                # Check mouse controls and determine button transitions
                if(b & simics.Abs_Pointer_Button_Left):
                    # Button is down
                    if( self._up._up.left_button_down == False):
                        ## Transition to button down 
                        self._up._up.button_down(px_x,px_y)
                        self._up._up.left_button_down = True
                    else :
                        ## The button was already down
                        self._up._up.button_still_down(px_x,px_y)
                else:
                    # Button is up
                    if( self._up._up.left_button_down == False):
                        # Button is up, was up before, do nothing
                        pass
                    else :
                        ## Transition to button up from button down
                        self._up._up.button_release(px_x,px_y)
                        self._up._up.left_button_down = False

#                    btn = self._up._up.find_button_hit(px_x,px_y)
#                    print(f"Left button down at {px_x}, {px_y}, hitting {btn}")
                                        



