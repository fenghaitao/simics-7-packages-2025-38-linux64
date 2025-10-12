/*
  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

/*
----------------------------------------------------------------------------------

  Interface for a button to interact with the panel controller. 
  - Check if a button is "hit" by a certain coordinate
  - A set of transitions/events:
    
    - When a button is clicked, it gets start_press()
      - Then, other events can show up:
        - If the user pulls the mouse out of the button, it gets leave_button()
        - If the user returns to the button, it then gets return_to_button()
      - If the user releases the button when in the button, it gets end_press()
      - If the user releases the button outside the button, it gets cancel_press()

  The corresponding DML definition can be found in p-control-button_interface.dml 
  
*/

#ifndef P_CONTROL_BUTTON_INTERFACE_H
#define P_CONTROL_BUTTON_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/* This defines a new interface type. Its corresponding C data type will be
   called "p_control_button_interface_t". */
SIM_INTERFACE(p_control_button) {
    // The button should know its own coordinates
    bool (*hit) (conf_object_t *obj, int x, int y);

    // Initialize anything to do with looks
    void (*initial_state)    (conf_object_t *obj);

    // Button press events
    void (*start_press)      (conf_object_t *obj);
    void (*end_press)        (conf_object_t *obj);   
    void (*cancel_press)     (conf_object_t *obj);
    void (*down_in)          (conf_object_t *obj);
    void (*down_outside)     (conf_object_t *obj);
};

/* Use a #define like this whenever you need to use the name of the interface
   type; the C compiler will then catch any typos at compile-time. */
#define P_CONTROL_BUTTON_INTERFACE "p_control_button"

#ifdef __cplusplus
}
#endif

#endif /* ! P_CONTROL_BUTTON_INTERFACE_H */
