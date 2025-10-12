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


import cli
import instrumentation

def get_info(obj):
    return [(None, [("Instrumentation connection", obj.dest.name)])]

cli.new_info_command("instrumentation_filter_aggregator", get_info)

def get_status(obj):
    l = instrumentation.get_filter_disabled_reasons(obj.disabled_sources)
    nl = zip(l, obj.disabled_sources)
    return [("Disabled filter sources", nl)]

cli.new_status_command("instrumentation_filter_aggregator", get_status)
