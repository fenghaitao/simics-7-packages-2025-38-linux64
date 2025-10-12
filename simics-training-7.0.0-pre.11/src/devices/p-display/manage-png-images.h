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

   Handling PNG files

   skip-t187-header-check: true
*/

#ifndef MANAGE_PNG_IMAGES_H
#define MANAGE_PNG_IMAGES_H

#include <simics/device-api.h>

typedef struct {
    int    width;
    int    height;
    uint32 *data;   // pointer to array of ARGB uint32s
} loaded_image_t;

// Function called to load an image and get an ID back
uint64 load_png_image_impl (conf_object_t *obj, char * filename);

// Functions called to get the image data for a loaded PNG
int     get_loaded_image_height (conf_object_t *obj, uint64 id);
int     get_loaded_image_width (conf_object_t *obj, uint64 id);
uint32 *get_loaded_image_data (conf_object_t *obj, uint64 id);

#endif
