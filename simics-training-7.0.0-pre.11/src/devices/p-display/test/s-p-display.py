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
import p_display_common

# Raise the log level to make the test logs more useful for debug
cli.global_cmds.log_level(level=3)

# Create an instance of the device to test
[dev, clock] = p_display_common.create_p_display()

# What would a test of this actually mean
# that is not rather complicated to set up



