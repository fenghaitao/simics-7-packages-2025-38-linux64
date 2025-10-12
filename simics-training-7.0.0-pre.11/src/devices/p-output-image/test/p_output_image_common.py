# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Unit test for the p-image-output class
#
# Check that we can create an object, given its required objects
# Check that it 


import stest
import pyobj
import dev_util
import conf
import simics

## Stub the display, required by the output image object
## in order to be created.  The resulting object is a 
## Simics conf_object_t object, can you cannot declare
## Python methods in it and expect them to be directly
## visible.
class stub_display(pyobj.ConfObject):
    def _initialize(self):
        self.img_id = 0x4000   # Make it look pointer-like
        self.img_map = {}
        super()._initialize()  

    # Simics attributes
    class width(pyobj.SimpleAttribute(512,type='i')):
        """Fake width of display."""

    class height(pyobj.SimpleAttribute(384,type='i')):
        """Fake height of display."""

    # For testing output image
    class fake_png_image_width(pyobj.SimpleAttribute(100,type='i')):
        """Set to guide the result from get_png_image_width."""

    class fake_png_image_height(pyobj.SimpleAttribute(50,type='i')):
        """Set to guide the result from get_png_image_height."""

    class last_draw_id(pyobj.SimpleAttribute(0,type='i')):
        """Last received id for draw_png_image"""

    class last_draw_filename(pyobj.SimpleAttribute("none",type='s')):
        """Filename computed from id from last call to draw_png_image"""

    class last_draw_x(pyobj.SimpleAttribute(0,type='i')):
        """Last received x for draw_png_image"""

    class last_draw_y(pyobj.SimpleAttribute(0,type='i')):
        """Last received y for draw_png_image"""

    class p_display_draw(pyobj.Interface):
        """Fake necessary calls in the display unit."""
        def get_width(self):
            return self._up.width.val

        def get_height(self):
            return self._up.height.val

        def color_rect(self,x,y,w,h,argb):
            pass

        def draw_image_alpha(self,x,y,w,h,pxs):
            pass

        # Needed for testing the output image functionality 
        #
        # Accept any filename, and convert it to an ID#
        # 
        def load_png_image(self,filename):
            id = self._up.img_id
            self._up.img_map[id]=filename
            self._up.img_id = self._up.img_id + 0x110
            simics.SIM_log_info(2, self._up.obj, 0, f"Loading image {filename} - {id:#x}" )
            return id

        def draw_png_image(self,x,y,id):
            simics.SIM_log_info(2, self._up.obj, 0, f"Draw image {id:#x} at {x},{y}" )
            self._up.last_draw_id.val = id
            self._up.last_draw_filename.val = self._up.img_map[id]
            self._up.last_draw_x.val = x
            self._up.last_draw_y.val = y

        def get_png_image_width(self,id):
            return self._up.fake_png_image_width.val

        def get_png_image_height(self,id):
            return self._up.fake_png_image_height.val

# Create objects for test 
def create_p_output_image(name="oi"):
    '''Create a new p_output_image object'''

    ## Stub display
    stub_d = simics.pre_conf_object('stub_display', 
                                    'stub_display',
                                    width=768,
                                    height=512)

    ## Device under test
    dev = simics.pre_conf_object(name, 'p_output_image',
                                 draw=stub_d,
                                 x=100, 
                                 y=50)

    ## Objects
    preobjs = [ dev, stub_d ]
    simics.SIM_add_configuration(preobjs, None)

    ## Convert preobjs to objs
    objs=[simics.SIM_get_object(p.name) for p in preobjs]

    return objs
