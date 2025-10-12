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

import dev_util
import conf
import stest
import p_output_image_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create an instance of the device to test
[dev, stub_d] = p_output_image_common.create_p_output_image("output_image")

# Write your tests here

# Check that configuration can be retrieved
ix = dev.x
iy = dev.y
stest.expect_equal(dev.iface.p_image_properties.get_x(), ix,
             "Interface does not return current x")
stest.expect_equal(dev.iface.p_image_properties.get_y(), iy,
             "Interface does not return current y")

# Check that image_count can be read but not changed
stest.expect_equal(dev.image_count, 0, "There should be zero images at start")
with stest.expect_exception_mgr(simics.SimExc_AttrNotWritable):
    dev.image_count = 1

# Send in a few files
#
# To test the p-output-image file name handling, 
# all that is needed is a real file.  It does not
# have to be an image at all, as it is never 
# actually subjected to the PNG loader. 

# These sizes will be returned
stub_d.fake_png_image_width = 90
stub_d.fake_png_image_height = 45

# Drive in a set of images 
i0 = os.path.abspath("fakeimg1.txt")
i1 = os.path.abspath("fakeimg1.txt")
dev.images = [i0, i1]

# Check that the state is updated as expected
stest.expect_equal(len(dev.images), 2, "Missed loading at least one image")
stest.expect_equal(dev.image_count, 2, "Image counter incorrect")
stest.expect_equal(dev.iface.p_image_properties.get_width(), 90,
             "Interface does not return correct image width") 
stest.expect_equal(dev.iface.p_image_properties.get_height(), 45,
             "Interface does not return correct image height")

# Fake a draw operation via setting the state
dev.iface.uint64_state.set(0)
# Check the arguments sent to the stub device
stest.expect_equal(stub_d.last_draw_filename, i0, "Wrong image drawn")
stest.expect_equal(stub_d.last_draw_x, ix, "Not drawing to correct place")
stest.expect_equal(stub_d.last_draw_y, iy, "Not drawing to correct place")

# Fake a draw operation via setting the state
dev.iface.uint64_state.set(1)
# Check the arguments sent to the stub device
stest.expect_equal(stub_d.last_draw_filename, i1, "Wrong image drawn")
stest.expect_equal(stub_d.last_draw_x, ix, "Not drawing to correct place")
stest.expect_equal(stub_d.last_draw_y, iy, "Not drawing to correct place")


# Test drawing a non-existent state num ber
with stest.expect_log_mgr(log_type="error"):
    dev.iface.uint64_state.set(2) 
