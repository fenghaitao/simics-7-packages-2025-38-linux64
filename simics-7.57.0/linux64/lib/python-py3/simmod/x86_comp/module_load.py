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


from . import x86_comp
from . import x86_comp_cmos
from . import x86_connector
from . import x86_motherboard
from . import x86_northbridge
from . import x86_processor
from . import x86_southbridge
x86_comp.x86_chassis.register()
x86_motherboard.motherboard_x86_simple.register()
x86_motherboard.motherboard_x86_simple_no_apic.register()
