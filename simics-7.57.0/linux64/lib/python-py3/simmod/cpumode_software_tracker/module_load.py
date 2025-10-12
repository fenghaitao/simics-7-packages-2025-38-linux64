# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from . import cpumode_software_tracker
cpumode_software_tracker.cpumode_software_tracker.register()
cpumode_software_tracker.cpumode_software_mapper.register()

from . import cpumode_composition
cpumode_composition.cpumode_software_tracker_comp.register()
