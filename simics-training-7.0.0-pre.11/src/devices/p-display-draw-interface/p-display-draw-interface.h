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

  Interface for drawing in the panel display unit:
  - Set entire display to BG color
  - Retrieve size
  - Set color of a rectangle
  - Insert an RGB image with Alpha channel 

*/
#ifndef P_DISPLAY_DRAW_INTERFACE_H
#define P_DISPLAY_DRAW_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/* This defines a new interface type. Its corresponding C data type will be
   called "p_display_draw_interface_t". */
SIM_INTERFACE(p_display_draw) {
   // Dimensions of the display itself
   int  (*get_width)(conf_object_t *obj);
   int  (*get_height)(conf_object_t *obj);   

   //  Color a rectangle.  The color is given as 0xAARRGGBB 
   //                      With A=0xFF being opaque, A=0x00 being transparent
   void (*color_rect)(conf_object_t *obj, int x, int y, int width, int height, uint32 argb);

   // Draw an image with alpha:
   //   Cover the given rectangle
   //   Each pixel is 0xAARRGGBB - consistent with Simics graphics consoles 
   void (*draw_image_alpha)(conf_object_t *obj, int x, int y, 
                            int width, int height, bytes_t pixels);

   // Draw PNG files loaded from files
   //   First, load an image from a named file. Get the pointer. 
   //   Second, use the returned ID/pointer to order a draw. 
   uint64 (*load_png_image) (conf_object_t *obj, char * filename);   
   void   (*draw_png_image) (conf_object_t *obj, int x, int y, uint64 image);

   // Get the size of the images, to avoid hard-coding image sizes everywhere
   uint64 (*get_png_image_width) (conf_object_t *obj, uint64 image);   
   uint64 (*get_png_image_height) (conf_object_t *obj, uint64 image);      

};

/* Use a #define like this whenever you need to use the name of the interface
   type; the C compiler will then catch any typos at compile-time. */
#define P_DISPLAY_DRAW_INTERFACE "p_display_draw"

#ifdef __cplusplus
}
#endif

#endif /* ! P_DISPLAY_DRAW_INTERFACE_H */
