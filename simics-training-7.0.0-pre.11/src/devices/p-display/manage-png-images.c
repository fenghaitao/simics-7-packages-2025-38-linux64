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

*/

#include "manage-png-images.h"
#include "png.h"
#include <errno.h>
#include <assert.h>

//----------------------------------------------------------------------
//
// Converting image ID to and from pointer
//
//----------------------------------------------------------------------
loaded_image_t *pointer_from_id(conf_object_t *obj, uint64 id) {
    // This is highly simplistic, but this code does not need
    // to be super-robust against malice and mistakes
    return (loaded_image_t*) id;
}

uint64 id_from_pointer(conf_object_t *obj, loaded_image_t *ptr) {
    return (uint64) ptr;
}

//----------------------------------------------------------------------
//
// convert_png_to_loaded_image()
//
//----------------------------------------------------------------------
void convert_png_to_loaded_image(loaded_image_t *ip, 
                                 png_bytepp png_i, 
                                 png_byte color_type) {
    // This is already checked in the calling code
    assert((color_type==PNG_COLOR_TYPE_RGB) || (color_type==PNG_COLOR_TYPE_RGBA));

    // Shorter variable names
    int width  = ip->width;
    int height = ip->height;
    int i,j;
    int bytes_per_pixel = (color_type==PNG_COLOR_TYPE_RGB) ? 3 : 4;

    // Loop over each row, 
    for(i=0;i<height;i++) {
        png_bytep row_pointer = png_i[i];
        for(j=0;j<width;j++) {
            // Build a pixel
            uint32 pixel;
            uint8  r,g,b,a;

            // This code works since bytes_per_pixel is to 3 or 4
            r = row_pointer[(j*bytes_per_pixel) + 0];
            g = row_pointer[(j*bytes_per_pixel) + 1];                
            b = row_pointer[(j*bytes_per_pixel) + 2];                

            if(bytes_per_pixel==3) {
                a = 0xff;  // Fully opaque
            } else {
                a = row_pointer[(j*bytes_per_pixel) + 3];                
            }

            // Build into our ARGB format in 32-bit word
            pixel = (a << 24) + (r << 16) + (g << 8) + (b);

            // Save in the data structure
            ip->data[j+(i*width)] = pixel;
        }
    }
}

//----------------------------------------------------------------------
//
// read_png_file()
// - Actually load an image
// - Allocate a new loaded_image struct 
// - Put pixels into the struct
// - Return pointer to the struct
//
// Gets a Simics object pointer to use logs for errors  
//----------------------------------------------------------------------
#define NOT_SUCCESSFUL NULL

loaded_image_t *read_png_file(conf_object_t *obj, char * filename ) {

    // Open the file for reading
    SIM_LOG_INFO(2, obj, 0, "Loading PNG file: %s", filename);
    FILE *file = fopen(filename, "rb");
    if(file==NULL) {
        SIM_LOG_ERROR(obj, 0, "PNG file '%s' could not be opened (%d)!", filename, errno);
        return NOT_SUCCESSFUL;
    }

    png_structp png  = NULL;
    png_infop   info = NULL;

    png = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    if (!png) {
        SIM_LOG_ERROR(obj, 0, "Out of memory reading: %s", filename);
        fclose(file);
        return NOT_SUCCESSFUL;
    }

    info = png_create_info_struct(png);
    if (!info) {
        SIM_LOG_ERROR(obj, 0, "Out of memory reading: %s", filename);
        png_destroy_read_struct(&png, NULL, NULL);
        fclose(file);
        return NOT_SUCCESSFUL;
    }

    if (setjmp(png_jmpbuf(png))) {
        // Get here in case some other libpng call fails
        SIM_LOG_ERROR(obj, 0, "Failure reading: %s", filename);
        png_destroy_read_struct(&png, &info, NULL);
        fclose(file);
        return NOT_SUCCESSFUL;
    }   

    // Read file metadata
    png_init_io(png, file);

    // Load file contents
    png_bytepp row_pointers;  
    png_read_png(png, info, PNG_TRANSFORM_IDENTITY, NULL);
    row_pointers = png_get_rows(png, info);

    int width, height;
    png_byte color_type;
    png_byte bit_depth;

    width      = png_get_image_width(png, info);
    height     = png_get_image_height(png, info);
    color_type = png_get_color_type(png, info);
    bit_depth  = png_get_bit_depth(png, info);

    SIM_LOG_INFO(3, obj, 0, "PNG image size: %d, %d", width, height);    
    SIM_LOG_INFO(3, obj, 0, "PNG color type: %d. Bit depth: %d", color_type, bit_depth);
    // We only like bit depth 8
    // and color types 2 and 6 (2=RGB, 6=RGBA)
    if (! (color_type==PNG_COLOR_TYPE_RGB || color_type==PNG_COLOR_TYPE_RGBA)) {
        SIM_LOG_ERROR(obj, 0, "Only RGB or RGBA images accepted");
        png_destroy_read_struct(&png, &info, NULL);
        fclose(file);
        return NOT_SUCCESSFUL;
    }
    if (bit_depth!=8) {
        SIM_LOG_ERROR(obj, 0, "Only 8-bit images accepted");
        png_destroy_read_struct(&png, &info, NULL);
        fclose(file);
        return NOT_SUCCESSFUL;
    }

       // Allocate the image structure
    loaded_image_t *ip;
    ip = MM_MALLOC(1,loaded_image_t);
    ip->width=width;
    ip->height=height;
    ip->data = MM_MALLOC(height*width,uint32);

    // Convert data to our format
    convert_png_to_loaded_image(ip,row_pointers,color_type);

    // Clean up, after the data has been used. 
    png_destroy_read_struct(&png, &info, NULL); 
    fclose(file);

    return ip;
}

//----------------------------------------------------------------------
//
// load_png_image_impl()
// - Actually load an image
// - Allocate a new loaded_image struct 
//     (no need to worry about deallocation at this stage...)
// - Return "ID"
//     Where 0 means failure
// 
// Basically relies on the above read_png_file function
//----------------------------------------------------------------------
uint64 load_png_image_impl(conf_object_t *obj, char * filename) {

    loaded_image_t *ip;

    ip = read_png_file(obj,filename);
  
    return id_from_pointer(obj,ip);
}

//----------------------------------------------------------------------
//
// getters for image properties
//
//----------------------------------------------------------------------
int get_loaded_image_width(conf_object_t *obj, uint64 id) {
    return (pointer_from_id(obj,id))->width;
}

int get_loaded_image_height(conf_object_t *obj, uint64 id) {
    return (pointer_from_id(obj,id))->height;
}

uint32 *get_loaded_image_data(conf_object_t *obj, uint64 id) {
    return (pointer_from_id(obj,id))->data;
}


// init_local() is necessary. 
//
// The DML class is automatically handled, this is for any Simics API
// declarations that the C code does on its own (registering new classes, 
// notifiers, etc)
void
init_local(void)
{
}
