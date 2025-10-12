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


# Test that the order of object initialization (as given by the
# object's names) does not matter for the caching of the capacity. This
# was tested due to a bug found that caused capacity to be incorrectly
# reported as 0 if the image was initialized after the cdrom-image.

import stest
from cdrom_common import *

SIM_add_configuration(pre_conf_cd_objs('simple-cd.craff', 'cd1', 'aimage'),
                      None)
SIM_add_configuration(pre_conf_cd_objs('simple-cd.craff', 'cd2', 'zimage'),
                      None)

stest.expect_equal(conf.cd1.capacity, conf.cd2.capacity)
