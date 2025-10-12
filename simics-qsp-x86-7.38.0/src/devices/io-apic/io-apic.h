/*
  io-apic.h

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef __IO_APIC_H__
#define __IO_APIC_H__

#include <simics/device-api.h>
#if defined(__cplusplus)
extern "C" {
#endif

/*
 * IO-APIC interface.
 *
 * eoi() is called by the apic-bus when it receives an end-of-interrupt message
 * for a level-triggered interrupt. eoi() is called for all IO-APICs connected
 * to the apic-bus, regardless of the actual initiator. Vector is the interrupt
 * vector number between 16 and 255.
 *
 * interrupt() / interrupt_clear() are used by devices that want to generate an
 * interrupt towards the IO-APIC. The pin argument is the input pin number, a
 * value between 0 and 23. For edge-triggered interrupts, only interrupt()
 * should be called.
 */

SIM_INTERFACE(ioapic) {
        void (*eoi)(conf_object_t *obj, int vector);
        void (*interrupt)(conf_object_t *obj, int pin);
        void (*interrupt_clear)(conf_object_t *obj, int pin);
};

#define IOAPIC_INTERFACE "ioapic"

#if defined(__cplusplus)
}
#endif
#endif /* __APIC_H__ */
