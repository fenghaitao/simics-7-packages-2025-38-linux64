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

  Interface for reporting the properties of an "output image". 
  I.e., an image that also has a certain place on the drawing canvas. 

  The corresponding DML definition can be found in p-image-properties_interface.dml */

#ifndef P_IMAGE_PROPERTIES_INTERFACE_H
#define P_IMAGE_PROPERTIES_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif


/* Getting width and height of an image */
SIM_INTERFACE(p_image_properties) {
        uint64 (*get_x)  (conf_object_t *obj);
        uint64 (*get_y) (conf_object_t *obj);
        uint64 (*get_width)  (conf_object_t *obj);
        uint64 (*get_height) (conf_object_t *obj);
};

/* Use a #define like this whenever you need to use the name of the interface
   type; the C compiler will then catch any typos at compile-time. */
#define P_IMAGE_PROPERTIES_INTERFACE "p_image_properties"

#ifdef __cplusplus
}
#endif

#endif /* ! P_IMAGE_PROPERTIES_INTERFACE_H */
