/*
  sample-device-mixed.c - sample code for a mixed DML/C Simics device

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/simulator/sim-get-class.h>

#include "sample-device-mixed.h"

uint64
calculate_value_in_c(uint64 v)
{
        return v + 4711;
}

void
call_out_to_c(conf_object_t *obj)
{
        const myinterface_interface_t *iface =
                SIM_c_get_interface(obj, "myinterface");
        ASSERT(iface);
        iface->one(obj);
        iface->two(obj, 4711);
}

/*
 * This is an example how you can register events entirely
 * from the C code. Also see how to call this function in init_local
 */

static void
birthday_reminder_event(conf_object_t *obj, void *userdata)
{
        SIM_LOG_INFO(1, obj, 0, "Birthday reminder!");
}

static event_class_t *birthday_event_class;

static void
register_event_classes(conf_class_t *conf_class)
{
        birthday_event_class = SIM_register_event(
                "birthday reminder",
                conf_class,
                Sim_EC_No_Flags, /* flags */
                birthday_reminder_event,
                NULL, /* destroy */
                NULL, /* get_value */
                NULL, /* set_value */
                NULL); /* describe */
}

/*
 * This is the module init function. It is called after DMLC generated classes
 * have been registered.
 */
void
init_local()
{
        conf_class_t *conf_class = SIM_get_class("sample_device_mixed");

        /* Register pure C events */
        register_event_classes(conf_class);
}
