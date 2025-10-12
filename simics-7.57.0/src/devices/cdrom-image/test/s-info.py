# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test that info command works with various values for image attribute
import pyobj, simics, stest
from configuration import OBJECT

class pimage(pyobj.ConfObject):
    class files(pyobj.SimpleAttribute([])):
        pass
    class iport(pyobj.Port):
        class image(pyobj.Interface):
            def size(self):
                return 2048

run_command('new-cdrom-image name=dut')
dut = conf.dut

# No image set
stest.expect_equal(dut.image, None)
run_command('dut.info')

# Simple image
SIM_create_object('image', 'img', size=2048)
dut.image = conf.img
run_command('dut.info')

# Image in a port
simics.SIM_set_configuration([OBJECT('pimg', 'pimage')])
dut.image = [conf.pimg, 'iport']
run_command('dut.info')
