/*
  © 2011 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SERIAL_INTERRUPT_INTERFACE_H
#define SERIAL_INTERRUPT_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/*::add interface to-section add-on-interfaces
short: interfaces for serial interrupt

The interfaces `serial_interrupt_master` and `serial_interrupt_slave` are
used to model serial interrupt communications between a serial interrupt
controller and a serial interrupt device. The controller implements
`serial_interrupt_master` and the device implements `serial_interrupt_slave`.

The device calls `start_request` in the controller to request serial
interrupt transfer cycles start frame.

The controller calls `start` to start the serial interrupt communications,
detects interrupt states one by one by calling `fetch`, and
finishes the serial interrupt sequence by `stop`.

The returned value of `fetch` is the level of the current data frame.
It is either 0 (low) or 1 (high).

The `mode` is used to specifies the SERIRQ transfer cycles mode.
It is 1 for *Quiet* and 0 for *Continuous* mode.

## Execution Context

Cell Context for all methods.
*/
SIM_INTERFACE(serial_interrupt_slave) {
        void (*start)(conf_object_t *obj);
        int (*fetch)(conf_object_t *obj);
        void (*stop)(conf_object_t *obj, int mode);
};

#define SERIAL_INTERRUPT_SLAVE_INTERFACE "serial_interrupt_slave"

// ADD INTERFACE serial_interrupt_slave_interface_t

/*::append interface to-page serial_interrupt_slave_interface_t */
SIM_INTERFACE(serial_interrupt_master) {
        void (*start_request)(conf_object_t *obj);
};

#define SERIAL_INTERRUPT_MASTER_INTERFACE "serial_interrupt_master"

// ADD INTERFACE serial_interrupt_master_interface_t

#ifdef __cplusplus
}
#endif

#endif /* ! SERIAL_INTERRUPT_INTERFACE_H */
