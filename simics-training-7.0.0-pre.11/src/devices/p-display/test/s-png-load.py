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

import stest
import os
import p_display_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create an instance of the device to test
[dev, clock] = p_display_common.create_p_display()

dif = dev.port.draw.iface.p_display_draw

# Test the loading of actual PNG images
#
# In so far that files do get loaded, and that we do get
# the dimensions back from the load 
#
i1 = os.path.abspath("test-image-600x200.png")
id1 = dif.load_png_image(i1)

stest.expect_different(id1, 0, "Image handle should be non-zero")
stest.expect_equal(dif.get_png_image_width(id1), 600, 
                   "Image expected to be 600 wide")
stest.expect_equal(dif.get_png_image_height(id1), 200, 
                   "Image expected to be 200 high")

# Another image, to test handling more > 1
i2 = os.path.abspath("test-image-600x200.png")
id2 = dif.load_png_image(i2)

stest.expect_different(id2, 0, "Image handle should be non-zero")
stest.expect_equal(dif.get_png_image_width(id2), 600, 
                   "Image expected to be 600 wide")
stest.expect_equal(dif.get_png_image_height(id2), 200, 
                   "Image expected to be 200 high")

# And yet another image, of a different size
i3 = os.path.abspath("test-image-3-600x400.png") 
id3 = dif.load_png_image(i3)

stest.expect_equal(dif.get_png_image_width(id3), 600, 
                   "Image expected to be 600 wide")
stest.expect_equal(dif.get_png_image_height(id3), 400, 
                   "Image expected to be 400 high")

# Test with a non-existing file
bad1 = "does-not-exist.png"
with stest.expect_log_mgr(obj=dev,log_type="error"):
    bad_id1 = dif.load_png_image(bad1)
stest.expect_equal(bad_id1, 0, "Bad image should return zero")

