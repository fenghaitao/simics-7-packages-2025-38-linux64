/* sample-device.c - sample code for a Simics device

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>

#include <simics/model-iface/transaction.h>

#include "sample-interface.h"

typedef struct {
        /* Simics configuration object */
        conf_object_t obj;

        /* device specific data */
        unsigned value;

} sample_device_t;

/* Allocate memory for the object. */
static conf_object_t *
alloc_object(conf_class_t *cls)
{
        sample_device_t *sample = MM_ZALLOC(1, sample_device_t);
        return &sample->obj;
}

/* Dummy function that doesn't really do anything. */
static void
simple_method(conf_object_t *obj, int arg)
{
        sample_device_t *sample = (sample_device_t *)obj;
        SIM_LOG_INFO(1, &sample->obj, 0,
                     "'simple_method' called with arg %d", arg);
}

static exception_type_t
issue(conf_object_t *obj, transaction_t *t, uint64 addr)
{
        sample_device_t *sample = (sample_device_t *)obj;

        if (SIM_transaction_is_read(t)) {
                SIM_set_transaction_value_le(t, sample->value);
                SIM_LOG_INFO(1, &sample->obj, 0, "read from offset %lld: 0x%x",
                             addr, sample->value);
        } else {
                sample->value = SIM_get_transaction_value_le(t);
                SIM_LOG_INFO(1, &sample->obj, 0, "write to offset %lld: 0x%x",
                             addr, sample->value);
        }
        return Sim_PE_No_Exception;
}

static set_error_t
set_value_attribute(conf_object_t *obj, attr_value_t *val)
{
        sample_device_t *sample = (sample_device_t *)obj;
        sample->value = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_value_attribute(conf_object_t *obj)
{
        sample_device_t *sample = (sample_device_t *)obj;
        return SIM_make_attr_uint64(sample->value);
}

/* called once when the device module is loaded into Simics */
void
init_local()
{
        /* Register the class with callbacks used when creating and deleting
           new instances of the class */
        const class_info_t funcs = {
                .alloc = alloc_object,
                .short_desc = "sample C device",
                .description =
                "The sample-device device is a dummy device that compiles and"
                " that can be loaded into Simics. Using it as a starting point"
                " when writing own devices for Simics is encouraged. Several"
                " device specific functions are included. The source is"
                " included in <tt>simics/src/devices/sample-device-c</tt>.",
        };
        conf_class_t *class = SIM_create_class("sample-device-c", &funcs);

        /* Register the 'sample-interface', which is an example of a unique,
           customized interface that we've implemented for this device. */
        static const sample_interface_t sample_iface = {
                .simple_method = simple_method
        };
        SIM_register_interface(class, SAMPLE_INTERFACE, &sample_iface);

        /* Register the 'transaction' interface, which is the
           interface that is implemented by memory mapped devices. */
        static const transaction_interface_t transaction_iface = {
                .issue = issue,
        };
        SIM_REGISTER_INTERFACE(class, transaction, &transaction_iface);

        /* Register attributes (device specific data) together with functions
           for getting and setting these attributes. */
        SIM_register_attribute(
                class, "value",
                get_value_attribute, set_value_attribute,
                Sim_Attr_Optional, "i",
                "The <i>value</i> field.");
}
