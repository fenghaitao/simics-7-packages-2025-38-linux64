/*
  © 2020 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

/*
--------------------------------------------------------------------------------

  serial-out-mux : Device to explore how Simics interfaces work
                 : using the serial device interface.
                 :
                 : Also, show what the Simics API looks like in C
                 :
                 : Part of Simics training materials
                 : Most definitely not a production-quality implementation

*/


#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <simics/device-api.h>
#include <simics/devs/serial-device.h>
#include <simics/simulator-api.h>    

#define CLASS_NAME "serial-out-mux"

//
// Object structure - one structure like this is allocated for each
//                    object created from this class.
//
typedef struct {
    // Simics configuration object for this object.
    conf_object_t obj;

    // The object to pass on serial transactions to
    conf_object_t * original_target_obj;
    // cache the interface to call into, derived from the target_obj
    const serial_device_interface_t *original_target_siface;

    // The object to copy serial transactions to
    conf_object_t * mux_target_obj;
    const serial_device_interface_t *mux_target_siface;

} serial_mux_device_t;

//
// log groups - this class can have up to 63 unique log groups
// defined in init.c
//
extern const char *const serial_mux_log_groups[];

// Enum, corresponding to one bit per
enum serial_mux_log_groups_values {
    Log_Operation = 1,
    Log_Class_Func = 2,
};


//
// alloc - called to allocate memory for an instance of the class.
//
static conf_object_t *
alloc_smux(conf_class_t *cls)
{
    serial_mux_device_t *dev = MM_ZALLOC(1, serial_mux_device_t);
    return &dev->obj;
}

//
// init - initialize device state (into the device structure)
//        called once all objects in the current batch have been
//        allocated.  But before attributes are set from the outside.
//
//        init can fail, and indicates a failure to init by returning NULL.
//
//        Any memory allocated here for things like internal caches
//        would need to be freed in deinit()
//
static lang_void *
init_smux(conf_object_t *obj)
{
    serial_mux_device_t *mux = (serial_mux_device_t *) obj;

    // Logging is available here, since we have an actual obj
    SIM_LOG_INFO(3, obj, Log_Class_Func, "init() called");

    // Attribute default values -- all NULL
    mux->original_target_obj = NULL;
    mux->original_target_siface = NULL;
    mux->mux_target_obj = NULL;
    mux->mux_target_siface = NULL;

    // Return the same pointer, everything went fine
    return obj;
}

//
// finalize - finalize the state of the object, based on any attributes
//            set after init was called.  Can only do local setup, not
//            call other objects!
//
//            finalize cannot fail.
//
//        Any memory allocated here for things like internal caches
//        would need to be freed in deinit()
//
// Historical note:
//
// Note that DML post_init maps to the older-style finalize() function
// used with SIM_register_class. That variant of finalize() was allowed
// to call other objects, provided they did SIM_require_object on them
// first.
//
static void
finalize_smux(conf_object_t *obj)
{
    SIM_LOG_INFO(3, obj, Log_Class_Func, "finalize() called");

    // Nothing to do, everything has been taken care of in the attributes
}

//
// objects_finalized - all objects have had their finalize() called. At this
//                     point they are in a state that allows them to be
//                     called.  In this function, this object can call
//                     interfaces in other objects that are needed in order
//                     to set up for simulation.
//
//        Any memory allocated here for things like internal caches
//        would need to be freed in deinit()
//
static void
objects_finalized_smux(conf_object_t *obj)
{
    SIM_LOG_INFO(3, obj, Log_Class_Func, "objects_finalized() called");

    // Nothing to do here either.
}

//
// deinit - object is being deleted.  Undo the effects of init(), finalize(),
//          objects_finalized(), and any attributes that allocate memory.
//
static void
deinit_smux(conf_object_t *obj)
{
    SIM_LOG_INFO(3, obj, Log_Class_Func, "deinit() called");

    // Nothing to do here, we just have a passive reference to another object
}

//
// dealloc - deallocate the memory allocated in alloc
//
//           Split from deinit(), since it is possible for the objects to be
//           allocated, and then immediately deleted due to failures
//           to initialize or allocate other objects.
//
static void
dealloc_smux(conf_object_t *obj)
{
    serial_mux_device_t *mux = (serial_mux_device_t *)obj;

    SIM_LOG_INFO(3, obj, Log_Class_Func, "dealloc() called");

    // Return the memory allocated in alloc()
    MM_FREE(mux);
}

//------------------------------------------------------------------------------
// Serial interface inbound calls.
//
//   Both write() and receive_ready() are passed on to both the "original
//   target" and "mux target" devices. In each case, the cached interface is
//   used to do the call. This is the standard Simics pattern in C. If caching
//   was not used, these functions would need to do SIM_c_get_interface() each
//   time (including error handling). Which would be more complicated and
//   significantly slower.
//
int serial_in_write(conf_object_t *obj, int value) {
    serial_mux_device_t *mux = (serial_mux_device_t *)obj;
    int chars = 0;
    int chars_m = 0;

    SIM_LOG_INFO(2, &(mux->obj), 0,
                 "serial write(),"
                 " incoming value: 0x%.2x ('%c')",
                 value, value);

    // Send to mux device, if connected
    // - First argument to the function call is the object that is being called
    // - When writing DML or Python this is mostly invisible, but critical in C
    if(mux->mux_target_siface!= NULL) {
      SIM_LOG_INFO(3, &(mux->obj), 0, "Passing on to mux target");
      chars_m = mux->mux_target_siface->write(mux->mux_target_obj, value);
    }
    
    // Send to original device, if connected
    if(mux->original_target_siface!= NULL) {
      SIM_LOG_INFO(3, &(mux->obj), 0, "Passing on to original target");
      chars = mux->original_target_siface->write(
              mux->original_target_obj, value);
    }

    // Sanity check, just because
    if(chars != chars_m) {
      SIM_LOG_INFO(1, &(mux->obj), 0,
		   "Different results from mux and original target"
                   " (m=%d, o=%d)",
                   chars_m, chars);
    }
    
    return chars; //number of characters actually written to original device
}

void serial_in_receive_ready(conf_object_t *obj) {
    serial_mux_device_t *mux = (serial_mux_device_t *)obj;
    SIM_LOG_INFO(2, &(mux->obj), 0, "serial receive_ready() called");

    // Send to mux device, if connected
    if(mux->mux_target_siface!= NULL) {
      SIM_LOG_INFO(3, &(mux->obj), 0, "Passing on to mux target");
      mux->mux_target_siface->receive_ready(mux->mux_target_obj);    
    }
    
    // Send to original device, if connected
    if(mux->original_target_siface!= NULL) {
      SIM_LOG_INFO(3, &(mux->obj), 0, "Passing on to original target");
      mux->original_target_siface->receive_ready(mux->original_target_obj);    
    }
}

//------------------------------------------------------------------------------
// Attribute: original_target
//   Set the reference to the target
//   Does not allow for old-style named port references
//
static set_error_t
set_original_target_attribute(conf_object_t *obj, attr_value_t *val)
{
    serial_mux_device_t              *mux = (serial_mux_device_t *)obj;
    conf_object_t                    *serobj;
    const serial_device_interface_t  *seriface;

    // parse the value using Simics API calls
    serobj = SIM_attr_object_or_nil (*val);
    
    // Log the setting of the attribute, to help in labs looking at
    // object creation and destruction
    SIM_LOG_INFO(3, obj, Log_Class_Func,
                 "set for attribute \"original_target\" called");

    if(serobj != NULL) {
        // Cache the interface to save time in calls
        //   (standard Simics modeling practice)
        seriface = SIM_C_GET_INTERFACE(serobj, serial_device);
        if (seriface == NULL)
            return Sim_Set_Interface_Not_Found;
        mux->original_target_siface = seriface;
    } else {
        // For the case where we get a NULL obj, also nullify the interface
        mux->original_target_siface = NULL;
    }

    mux->original_target_obj = serobj;
    return Sim_Set_Ok;
}

static attr_value_t
get_original_target_attribute(conf_object_t *obj)
{
    serial_mux_device_t *mux = (serial_mux_device_t *)obj;
    return SIM_make_attr_object(mux->original_target_obj);
}

//------------------------------------------------------------------------------
// Attribute: mux_target
//   Set the reference to the target
//   Does not allow for old-style named port references
//
static set_error_t
set_mux_target_attribute(conf_object_t *obj, attr_value_t *val)
{
    serial_mux_device_t              *mux = (serial_mux_device_t *)obj;
    conf_object_t                    *serobj;
    const serial_device_interface_t  *seriface;

    // parse the value using Simics API calls
    serobj = SIM_attr_object_or_nil (*val);

    // Log the setting of the attribute, to help in labs looking at
    // object creation and destruction
    SIM_LOG_INFO(3, obj, Log_Class_Func,
                 "set for attribute \"mux_target\" called");

    if(serobj != NULL) {
        // Cache the interface to save time in calls
        //   (standard Simics modeling practice)
        seriface = SIM_C_GET_INTERFACE(serobj, serial_device);
        if (seriface == NULL)
            return Sim_Set_Interface_Not_Found;
        mux->mux_target_siface = seriface;
    } else {
        // For the case where we get a NULL obj, also nullify the interface
        mux->mux_target_siface = NULL;
    }

    mux->mux_target_obj = serobj;
    return Sim_Set_Ok;
}

static attr_value_t
get_mux_target_attribute(conf_object_t *obj)
{
    serial_mux_device_t *mux = (serial_mux_device_t *)obj;
    return SIM_make_attr_object(mux->mux_target_obj);
}

//------------------------------------------------------------------------------
// Called once when the device module is loaded into Simics
//
// Registers the class with Simics, adds attributes and interfaces to the class
//
void
init_mux(void)
{
    const class_info_t classinfo = {
      .alloc = alloc_smux,
      .init = init_smux,
      .finalize = finalize_smux,
      .objects_finalized = objects_finalized_smux,
      .deinit = deinit_smux,
      .dealloc = dealloc_smux,
      .kind = Sim_Class_Kind_Vanilla,
      .short_desc  = "serial output multiplexer",
      .description = "Device that takes a stream of serial device calls "
                     "and multiplexes them out to multiple devices. "
                     "Used in Simics model builder training."
    };

    // Register the class with Simics, including the name of the class and
    // the functions given above.
    //
    // SIM_create_class() is recommended since Simics Base 6.0.40
    //
    conf_class_t *class = SIM_create_class(CLASS_NAME, &classinfo);

    //
    // Error handling - check exception raised from core
    //
    if (SIM_clear_exception() != SimExc_No_Exception) {
        SIM_printf("Failed to create class %s: %s\n",
		   CLASS_NAME,
		   SIM_last_error());
        return;  // we have lost, get out of here
    }
    
    // Register log groups on the class
    SIM_log_register_groups(class, serial_mux_log_groups);

    // Register the serial_device interface used to receive calls
    static const serial_device_interface_t serial_in_iface = {
      .write         = serial_in_write,
      .receive_ready = serial_in_receive_ready
    };
    SIM_REGISTER_INTERFACE(class, serial_device, &serial_in_iface);
    
    // Register the attributes on the class
    //   Used to point at objects to send interface calls to.
    //
    //   Note that documentation about required interfaces is simply
    //   inserted as more text in the documentation string.
    SIM_register_attribute(
      class,
      "original_target",
      get_original_target_attribute,
      set_original_target_attribute,
      Sim_Attr_Optional,
      "o|n",
      "Original target of the serial interface."
      "\n\nRequired interfaces: <iface>serial_device</iface>.");
    
    SIM_register_attribute(
      class,
      "mux_target",
      get_mux_target_attribute,
      set_mux_target_attribute,
      Sim_Attr_Optional,
      "o|n",
      "Additional (mux) target for serial interface calls."
      "\n\nRequired interfaces: <iface>serial_device</iface>.");
}
